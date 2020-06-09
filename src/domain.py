import copy
import json
import logging
import yaml

logger = logging.getLogger()

import sys
sys.path.append('lib')

logger = logging.getLogger()

from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
    BlockedStatus
)

from exceptions import ExternalLabelParseError, TimeStringParseError


# There is never ever a need to customize the advertised port of a
# containerized Prometheus instance so we are removing that config
# option and making it statically default to its typical 9090
PROMETHEUS_ADVERTISED_PORT = 9090


# DOMAIN MODELS
class PrometheusJujuPodSpec:

    def __init__(self,
                 app_name,
                 image_path,
                 repo_username,
                 repo_password,
                 advertised_port,
                 prometheus_cli_args,
                 prometheus_config):

        self._prometheus_config = prometheus_config
        self._spec = {
            'containers': [{
                'name': app_name,
                'imageDetails': {
                    'imagePath': image_path,
                    'username': repo_username,
                    'password': repo_password
                },
                'args': prometheus_cli_args,
                'ports': [{
                    'containerPort': advertised_port,
                    'protocol': 'TCP'
                }],
                'readinessProbe': {
                    'httpGet': {
                        'path': '/-/ready',
                        'port': advertised_port
                    },
                    'initialDelaySeconds': 10,
                    'timeoutSeconds': 30
                },
                'livenessProbe': {
                    'httpGet': {
                        'path': '/-/healthy',
                        'port': advertised_port
                    },
                    'initialDelaySeconds': 30,
                    'timeoutSeconds': 30
                },
                'files': [{
                    'name': 'config',
                    'mountPath': '/etc/prometheus',
                    'files': {
                        'prometheus.yml': ''
                    }
                }]
            }]
        }

    def to_dict(self):
        final_dict = copy.deepcopy(self._spec)
        final_dict['containers'][0]['files'][0]['files']['prometheus.yml'] = \
            self._prometheus_config.yaml_dump()
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

    def __repr__(self):
        return str(self._config_dict)


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


def build_juju_pod_spec(app_name,
                        charm_config,
                        image_meta,
                        alerting_config=None):

    # Mutable defaults bug as described in https://bit.ly/3cF0k0w
    if not alerting_config:
        alerting_config = dict()

    # There is never ever a need to customize the advertised port of a
    # containerized Prometheus instance so we are removing that config
    # option and making it statically default to its typical 9090

    prom_config = build_prometheus_config(charm_config)

    spec = PrometheusJujuPodSpec(
        app_name=app_name,
        image_path=image_meta.image_path,
        repo_username=image_meta.repo_username,
        repo_password=image_meta.repo_password,
        advertised_port=PROMETHEUS_ADVERTISED_PORT,
        prometheus_cli_args=build_prometheus_cli_args(charm_config),
        prometheus_config=prom_config)

    return spec


def build_juju_unit_status(pod_status):
    if pod_status.is_unknown:
        unit_status = MaintenanceStatus("Waiting for pod to appear")
    elif not pod_status.is_running:
        unit_status = MaintenanceStatus("Pod is starting")
    elif pod_status.is_running and not pod_status.is_ready:
        unit_status = MaintenanceStatus("Pod is getting ready")
    elif pod_status.is_running and pod_status.is_ready:
        unit_status = ActiveStatus()
    else:
        # Covering a "variable referenced before assignment" linter error
        unit_status = BlockedStatus(
            "Error: Unexpected pod_status received: {0}".format(
                pod_status.raw_status
            )
        )

    return unit_status


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
