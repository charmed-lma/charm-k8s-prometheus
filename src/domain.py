import copy
import json
import logging
import yaml
import http.client
import sys
import time
import random

sys.path.append('lib')

logger = logging.getLogger()
from jinja2 import Environment, FileSystemLoader
from exceptions import (
    CharmError, ExternalLabelParseError,
    TimeStringParseError, PrometheusAPIError
)


# There is never ever a need to customize the advertised port of a
# containerized Prometheus instance so we are removing that config
# option and making it statically default to its typical 9090
PROMETHEUS_ADVERTISED_PORT = 9090


# DOMAIN MODELS
class PrometheusJujuPodSpec:

    def __init__(self,
                 app_name,
                 prom_image_path,
                 prom_repo_username,
                 prom_repo_password,
                 nginx_image_path,
                 nginx_repo_username,
                 nginx_repo_password,
                 prometheus_cli_args,
                 prometheus_config,
                 nginx_config,
                 enforce_pod_restart_workaround,
                 ssl_cert,
                 ssl_key):

        self._enforce_pod_restart = enforce_pod_restart_workaround
        self._ssl_cert = ssl_cert
        self._ssl_key = ssl_key
        self._prometheus_config = prometheus_config
        self._nginx_config = nginx_config
        self._spec = {
            'containers': [{
                'name': app_name,
                'imageDetails': {
                    'imagePath': prom_image_path,
                    'username': prom_repo_username,
                    'password': prom_repo_password
                },
                'args': prometheus_cli_args,
                'readinessProbe': {
                    'httpGet': {
                        'path': '/-/ready',
                        'port': PROMETHEUS_ADVERTISED_PORT
                    },
                    'initialDelaySeconds': 10,
                    'timeoutSeconds': 30
                },
                'livenessProbe': {
                    'httpGet': {
                        'path': '/-/healthy',
                        'port': PROMETHEUS_ADVERTISED_PORT
                    },
                    'initialDelaySeconds': 30,
                    'timeoutSeconds': 30
                },
                'files': [{
                    'name': 'prom-config',
                    'mountPath': '/etc/prometheus',
                    'files': {
                        'prometheus.yml': ''
                    }
                }]
            }, {
                'name': '{0}-nginx'.format(app_name),
                'imageDetails': {
                    'imagePath': nginx_image_path,
                    'username': nginx_repo_username,
                    'password': nginx_repo_password
                },
                'ports': [{
                    'containerPort': 80,
                    'name': 'nginx-http',
                    'protocol': 'TCP'
                }, {
                    'containerPort': 443,
                    'name': 'nginx-https',
                    'protocol': 'TCP'
                }],
                'files': [{
                    'name': 'nginx-config',
                    'mountPath': '/etc/nginx/conf.d',
                    'files': {
                        'default.conf': ''
                    }
                }]
            }
            ]
        }

    def to_dict(self):
        final_dict = copy.deepcopy(self._spec)
        final_dict['containers'][0]['files'][0]['files']['prometheus.yml'] = \
            self._prometheus_config.yaml_dump()
        final_dict['containers'][1]['files'][0]['files']['default.conf'] = \
            self._nginx_config.render_config()

        if (self._ssl_cert and not self._ssl_key) or \
                (not self._ssl_cert and self._ssl_key):
            raise CharmError(
                'In order to use TLS endpoint, '
                'both ssl_cert and ssl_key have to be configured'
            )

        if self._ssl_cert and self._ssl_key:
            final_dict['containers'][1]['files'].append({
                'name': 'prom-ssl',
                'mountPath': '/etc/nginx/ssl',
                'files': {
                    'prom-tls.pem': self._ssl_cert,
                    'prom-tls.key': self._ssl_key,
                }
            })

        # (vgrevtsev) As for Jul 2020, there is no clear way to tell
        # the NGINX to reload and/or restart itself. This is a workaround,
        # which actually enforces the k8s to rebuild the pod, leading
        # to the service restart.

        if self._enforce_pod_restart:
            def randomizer():
                return str(hash(random.random()))[:4]
            final_dict['containers'][1]['files'].append({
                'name': 'rand-{0}'.format(randomizer()),
                'mountPath': '/tmp',
                'files': {
                    randomizer(): randomizer()
                }
            })

        return final_dict


class PrometheusConfigFile:
    '''
    https://prometheus.io/docs/prometheus/latest/configuration/configuration
    '''

    def __init__(self, global_opts, alerting=None):
        # Mutable defaults bug as described in https://bit.ly/3cF0k0w
        if not alerting:
            alerting = dict()

        self._config_dict = {
            'global': global_opts,
            'scrape_configs': [],
            'alerting': alerting
        }

    def add_scrape_config(self, scrape_config):
        '''
        https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config
        '''
        self._config_dict['scrape_configs'].append(scrape_config)

    def yaml_dump(self):
        return yaml.dump(self._config_dict)

    def to_dict(self):
        return self._config_dict

    def __repr__(self):
        return str(self._config_dict)


class NginxConfigFile:
    def __init__(self, charm_config):
        ctxt = {
            'advertised_port': PROMETHEUS_ADVERTISED_PORT,
            'ssl_cert': charm_config.get('ssl_cert', False),
            'ssl_key': charm_config.get('ssl_key', False),
        }
        tenv = Environment(loader=FileSystemLoader('templates'))
        template = tenv.get_template('prometheus-nginx.conf.j2')
        self.rendered_config = template.render(ctxt)

    def render_config(self):
        return self.rendered_config


# DOMAIN SERVICES

# More stateless functions. This group is purely business logic that take
# simple values or data structures and produce new values from them.

def build_prometheus_cli_args(charm_config):
    """
    This function is taking the default Prometheus CLI args
    (https://github.com/prometheus/prometheus/blob/master/Dockerfile#L26)
    which we can consider as immutable, and adding some more tunables
    from the charm config options.

    Additionally, a "--web.enable-lifecycle" flag (which is disabled
    by default) has been added in order to enable live config reload option
    using HTTP call.

    :param charm_config: A fw_adapter.get_config() dict instance.
    """

    prometheus_cli_args = [
        "--config.file=/etc/prometheus/prometheus.yml",
        "--storage.tsdb.path=/prometheus",
        "--web.enable-lifecycle",
        "--web.console.templates=/usr/share/prometheus/consoles",
        "--web.console.libraries=/usr/share/prometheus/console_libraries"
    ]

    if charm_config.get('log-level'):
        log_level = charm_config['log-level'].lower()
        allowed_log_levels = ['debug', 'info', 'warn', 'error', 'fatal']
        if log_level not in allowed_log_levels:
            logging.error(
                "Invalid loglevel: {0} given, {1} allowed. Falling "
                "back to DEBUG loglevel.".format(
                    log_level, "/".join(allowed_log_levels)
                )
            )
            log_level = "debug"
    else:
        # fallback to the default option
        log_level = 'info'

    prometheus_cli_args.append(
        "--log.level={0}".format(log_level)
    )

    if charm_config['web-enable-admin-api']:
        prometheus_cli_args.append("--web.enable-admin-api")

    if charm_config['web-page-title']:
        # TODO: Some validation/sanitization?
        prometheus_cli_args.append(
            "--web.page-title=\"{0}\"".format(
                charm_config['web-page-title']
            )
        )

    if charm_config['tsdb-wal-compression']:
        prometheus_cli_args.append(
            "--storage.tsdb.wal-compression"
        )

    kv_config = {
        'web-max-connections': 'web.max-connections',
        'tsdb-retention-time': 'storage.tsdb.retention.time',
        'alertmanager-notification-queue-capacity':
            'alertmanager.notification-queue-capacity',
        'alertmanager-timeout': 'alertmanager.timeout'
    }

    for key, value in kv_config.items():
        if charm_config.get(key):
            prometheus_cli_args.append(
                "--{0}={1}".format(
                    value, charm_config[key]
                )
            )

    logger.debug("Rendered CLI args: {0}".format(
        ' '.join(prometheus_cli_args))
    )
    return prometheus_cli_args


def build_juju_pod_spec(app_name, charm_config, prom_image_meta,
                        nginx_image_meta, alerting_config=None):

    # Mutable defaults bug as described in https://bit.ly/3cF0k0w
    if not alerting_config:
        alerting_config = dict()

    prom_config = build_prometheus_config(charm_config)
    nginx_config = NginxConfigFile(charm_config)

    spec = PrometheusJujuPodSpec(
        app_name=app_name,
        prom_image_path=prom_image_meta.image_path,
        prom_repo_username=prom_image_meta.repo_username,
        prom_repo_password=prom_image_meta.repo_password,
        nginx_image_path=nginx_image_meta.image_path,
        nginx_repo_username=nginx_image_meta.repo_username,
        nginx_repo_password=nginx_image_meta.repo_password,
        prometheus_cli_args=build_prometheus_cli_args(charm_config),
        prometheus_config=prom_config,
        nginx_config=nginx_config,
        enforce_pod_restart_workaround=charm_config.get(
            'enforce-pod-restart', False
        ),
        ssl_cert=charm_config.get('ssl_cert'),
        ssl_key=charm_config.get('ssl_key'),
    )

    return spec


def validate_and_parse_external_labels(raw_labels):
    """
    Determines, if the input variable can be safely injected into the
    Prometheus config (input variable should be a dict, containing ONLY the
    strings as its values).

    :param raw_labels: Charm 'external-labels' config option.
    """
    ERROR_MESSAGE = "external-labels malformed JSON"

    if not raw_labels:  # empty string
        return {}

    try:
        parsed_labels = json.loads(raw_labels)
    except (ValueError, TypeError):
        raise ExternalLabelParseError(
            "{0}: {1}".format(ERROR_MESSAGE, raw_labels)
        )

    if not isinstance(parsed_labels, dict):
        raise ExternalLabelParseError(
            "{0}: expected dict, got {1}".format(
                ERROR_MESSAGE, type(parsed_labels)
            )
        )

    for key, value in parsed_labels.items():
        if not isinstance(key, str):
            raise ExternalLabelParseError(
                "{0}: external-labels.{1} key has to be str, {2} got".format(
                    ERROR_MESSAGE, key, type(key)
                )
            )
        if not isinstance(value, str):
            raise ExternalLabelParseError(
                "{0}: external-labels.{1} value has to be str, {2} got".format(
                    ERROR_MESSAGE, key, type(value)
                )
            )

    return parsed_labels


def validate_and_parse_time_values(key, value):
    def abort():
        msg = "Invalid time definition for key {0} - got: {1}".format(
            key, value
        )
        logger.error(msg)
        raise TimeStringParseError(msg)

    if not value:
        abort()

    time, unit = value[:-1], value[-1]

    if unit not in ['y', 'w', 'd', 'h', 'm', 's', 'ms']:
        logger.error("wrong unit")
        abort()

    try:
        int(time)
    except ValueError:
        logger.error("cannot convert time to int")
        abort()

    return value


def build_prometheus_config(charm_config):
    prometheus_global_opts = {
        'external_labels': validate_and_parse_external_labels(
            charm_config['external-labels']
        )
    }

    time_config_values = {
        'scrape-interval': 'scrape_interval',
        'scrape-timeout': 'scrape_timeout',
        'evaluation-interval': 'evaluation_interval'
    }

    for key, value in time_config_values.items():
        prometheus_global_opts[value] = validate_and_parse_time_values(
            key, charm_config.get(key)
        )

    prometheus_config = PrometheusConfigFile(
        global_opts=prometheus_global_opts
    )

    # Scrape its own metrics
    prometheus_config.add_scrape_config({
        'job_name': 'prometheus',
        'scrape_interval': '5s',
        'scrape_timeout': '5s',
        'metrics_path': '/metrics',
        'honor_timestamps': True,
        'scheme': 'http',
        'static_configs': [{
            'targets': [
                'localhost:{}'.format(PROMETHEUS_ADVERTISED_PORT)
            ]
        }]
    })

    if charm_config.get('monitor-k8s'):
        with open('templates/prometheus-k8s.yml') as prom_yaml:
            k8s_scrape_configs = \
                yaml.safe_load(prom_yaml).get('scrape_configs', [])

        for scrape_config in k8s_scrape_configs:
            prometheus_config.add_scrape_config(scrape_config)

    logger.debug("Build prom config: {}".format(prometheus_config))
    return prometheus_config


def _prometheus_http_api_call(
        model_name, app_name, method, endpoint, return_response=True):

    if method not in ['GET', 'POST', 'PUT']:
        raise CharmError('Wrong HTTP method')

    host = "{0}.{1}.svc".format(app_name, model_name)
    conn = http.client.HTTPConnection(host)
    conn.request(method=method, url=endpoint)
    logger.debug("Calling Prom API: {0} {1}".format(method, endpoint))

    # TODO: Handle the un-available API endpoint case
    response = conn.getresponse()

    if response.status < 200 or response.status >= 300:
        logger.error("API returned error: {0}".format(
            response.read()
        ))
        raise PrometheusAPIError("Prom API returned error, see unit logs")

    if return_response:
        try:
            return json.loads(response.read())
        except (ValueError, TypeError) as e:
            logger.error("Prom API returned non-JSON: {0}".format(e))
            raise PrometheusAPIError("Non-JSON response returned")


def reload_configuration(juju_model, juju_app, current_charm_config):

    try:
        expected_config = build_prometheus_config(current_charm_config)
        logging.debug(
            "Awaiting Prom config to be: {0}".format(expected_config)
        )

        i = 0
        while True:
            # Wait, until ConfigMap changes will be propagated
            config_reload_api_call(juju_model, juju_app)
            new_config_applied = check_config_propagation(
                juju_model, juju_app, expected_config
            )
            if new_config_applied:
                break
            i += 1
            if i > 5:
                logger.error(
                    "Config has not been propagated after timeout"
                )
                return False
            time.sleep(5)

        logger.debug("Config reloaded")
    except CharmError as e:
        logger.error("Exception raised: {0}".format(e))
        return False

    return new_config_applied


def config_reload_api_call(model_name, app_name):
    return _prometheus_http_api_call(
        model_name, app_name, 'POST', '/-/reload', return_response=False
    )


def check_config_propagation(model_name, app_name, expected_config):
    """
    :param model_name
    :param app_name
    :param expected_config: PrometheusConfigFile instance
    """

    if not isinstance(expected_config, PrometheusConfigFile):
        raise CharmError(
            "Expected PrometheusConfigFile instance, got {0}".format(
                type(expected_config)
            )
        )

    logging.debug("Expected: {0}".format(expected_config))
    response = _prometheus_http_api_call(
        model_name, app_name, 'GET', '/api/v1/status/config'
    )
    current_config = yaml.safe_load(response['data']['yaml'])

    # Some of the config options may be empty, so we have to re-add them
    # back to the received dict; otherwise this comparison will fail.

    if not current_config['global'].get('external_labels'):
        logging.debug("No external_labels received, adding empty key")
        current_config['global']['external_labels'] = {}

    if not current_config.get('alerting'):
        logging.debug("No alerting received, adding empty key")
        current_config['alerting'] = {}

    logging.debug("Received from API: {0}".format(current_config))
    return current_config == expected_config.to_dict()
