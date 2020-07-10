import json
import sys
import unittest
from uuid import uuid4
import yaml
import textwrap
sys.path.append('src')
import domain
from exceptions import (
    TimeStringParseError, ExternalLabelParseError,
    PrometheusAPIError, CharmError
)
from adapters.framework import (
    ImageMeta,
)
from unittest.mock import patch


def get_default_charm_config():
    return {
        'external-labels': '{"foo": "bar"}',
        'monitor-k8s': False,
        'log-level': '',
        'additional-cli-args': None,
        'web-enable-admin-api': True,
        'web-page-title': 'PrometheusTest',
        'web-max-connections': 512,
        'web-read-timeout': '5m',
        'tsdb-retention-time': '18d',
        'tsdb-wal-compression': True,
        'alertmanager-notification-queue-capacity': 10000,
        'alertmanager-timeout': '10s',
        'scrape-interval': '15s',
        'scrape-timeout': '10s',
        'evaluation-interval': '1m'
    }


class PromMockConfig(object):
    def __init__(self):
        self.config = {
            'global': {
                'scrape_interval': '10s',
                'external_labels': {"foo": "bar"},
                'scrape_timeout': '10s',
                'evaluation_interval': '1m'
            },
            'scrape_configs': [
                {
                    'job_name': 'prometheus',
                    'honor_timestamps': True,
                    'scrape_interval': '5s',
                    'scrape_timeout': '5s',
                    'metrics_path': '/metrics',
                    'scheme': 'http',
                    'static_configs': [
                        {'targets': ['localhost:9090']}
                    ]
                }
            ]
        }

    def render(self):
        return {
            "status": "success",
            "data": {
                "yaml": yaml.safe_dump(self.config)
            }
        }


class PrometheusCLIArgumentsTest(unittest.TestCase):
    @staticmethod
    def test__cli_args_are_rendered_correctly():
        config = get_default_charm_config()
        mock_args_config = domain.build_prometheus_cli_args(config)
        expected_cli_args = [
            '--config.file=/etc/prometheus/prometheus.yml',
            '--storage.tsdb.path=/prometheus',
            '--web.enable-lifecycle',
            '--web.console.templates=/usr/share/prometheus/consoles',
            '--web.console.libraries=/usr/share/prometheus/console_libraries',
            '--log.level=info',
            '--web.enable-admin-api',
            '--web.page-title="PrometheusTest"',
            '--storage.tsdb.wal-compression',
            '--web.max-connections=512',
            '--storage.tsdb.retention.time=18d',
            '--alertmanager.notification-queue-capacity=10000',
            '--alertmanager.timeout=10s'
        ]

        assert mock_args_config == expected_cli_args

        # Test unexpected log-level config option
        config['log-level'] = 'SomeUnexpectedValue'
        expected_cli_args[5] = '--log.level=debug'
        mock_args_config = domain.build_prometheus_cli_args(config)
        assert mock_args_config == expected_cli_args

        # Test non-empty valid log-level config option
        config['log-level'] = 'debug'
        mock_args_config = domain.build_prometheus_cli_args(config)
        assert mock_args_config == expected_cli_args


class BuildJujuPodSpecTest(unittest.TestCase):
    def test__pod_spec_is_generated(self):
        # Set up
        mock_app_name = str(uuid4())

        mock_external_labels = {
            str(uuid4()): str(uuid4()),
            str(uuid4()): str(uuid4()),
            str(uuid4()): str(uuid4()),
        }

        mock_config = get_default_charm_config()
        mock_config['external-labels'] = json.dumps(mock_external_labels)

        mock_image_meta = ImageMeta({
            'registrypath': str(uuid4()),
            'username': str(uuid4()),
            'password': str(uuid4()),
        })

        mock_args_config = domain.build_prometheus_cli_args(mock_config)

        # Exercise
        juju_pod_spec = domain.build_juju_pod_spec(
            app_name=mock_app_name, charm_config=mock_config,
            prom_image_meta=mock_image_meta, nginx_image_meta=mock_image_meta
        )

        expected_nginx_config = textwrap.dedent("""\
        server {
            listen 80;
            server_name _;
            access_log /var/log/nginx/prometheus-http.access.log main;
            error_log /var/log/nginx/prometheus-http.error.log;
            location / {
                proxy_pass http://localhost:9090;
            }
        }""")

        # Assertions
        assert isinstance(juju_pod_spec, domain.PrometheusJujuPodSpec)
        self.assertEqual(juju_pod_spec.to_dict(), {'containers': [{
            'name': mock_app_name,
            'imageDetails': {
                'imagePath': mock_image_meta.image_path,
                'username': mock_image_meta.repo_username,
                'password': mock_image_meta.repo_password
            },
            'args': mock_args_config,
            'readinessProbe': {
                'httpGet': {
                    'path': '/-/ready',
                    'port': 9090
                },
                'initialDelaySeconds': 10,
                'timeoutSeconds': 30
            },
            'livenessProbe': {
                'httpGet': {
                    'path': '/-/healthy',
                    'port': 9090
                },
                'initialDelaySeconds': 30,
                'timeoutSeconds': 30
            },
            'files': [{
                'name': 'prom-config',
                'mountPath': '/etc/prometheus',
                'files': {
                    'prometheus.yml': yaml.dump({
                        'global': {
                            'scrape_interval': '15s',
                            'scrape_timeout': '10s',
                            'evaluation_interval': '1m',
                            'external_labels': mock_external_labels
                        },
                        'scrape_configs': [
                            {
                                'metrics_path': '/metrics',
                                'honor_timestamps': True,
                                'scheme': 'http',
                                'job_name': 'prometheus',
                                'scrape_interval': '5s',
                                'scrape_timeout': '5s',
                                'static_configs': [
                                    {
                                        'targets': [
                                            'localhost:9090'
                                        ]
                                    }
                                ]
                            }
                        ],
                        'alerting': {}
                    })
                }
            }]
        }, {
            'name': '{0}-nginx'.format(mock_app_name),
            'imageDetails': {
                'imagePath': mock_image_meta.image_path,
                'username': mock_image_meta.repo_username,
                'password': mock_image_meta.repo_password
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
                    'default.conf': expected_nginx_config
                }
            }]
        }
        ]})


class ExternalMetricsParserTest(unittest.TestCase):
    def test__external_metrics_parser(self):
        with self.assertRaises(ExternalLabelParseError):    # malformed json
            domain.validate_and_parse_external_labels("{abc")
            domain.validate_and_parse_external_labels("somerandomstring")
            domain.validate_and_parse_external_labels(json.dumps({
                True: ["val1", "val2"]
            }))
            domain.validate_and_parse_external_labels(json.dumps({
                "key": ["val1", "val2"]
            }))
            domain.validate_and_parse_external_labels(json.dumps([]))

        self.assertEqual(domain.validate_and_parse_external_labels(""), {})
        self.assertEqual(domain.validate_and_parse_external_labels("{}"), {})

        labels = {"foo": "bar", "baz": "qux"}
        self.assertEqual(
            domain.validate_and_parse_external_labels(json.dumps(labels)),
            labels
        )


class TimeValuesParserTest(unittest.TestCase):
    def test__time_parser(self):
        with self.assertRaises(TimeStringParseError):    # malformed values
            for value in [None, False, '', 'foo', 'bam', '55z', '999']:
                domain.validate_and_parse_time_values('test', value)

        for value in ["15m", "1d", "30d", "1m", "1y"]:
            self.assertEqual(
                domain.validate_and_parse_time_values('test', value), value
            )


class ConfigReloadTest(unittest.TestCase):

    @patch('domain.time', spec_set=True, autospec=True)
    @patch('domain._prometheus_http_api_call', spec_set=True, autospec=True)
    def test__reload_configuration(
            self, prometheus_http_api_call_mock, time_mock):
        prom_api_response = PromMockConfig()

        # These two are not returned by Prom API in reality (if empty),
        # but they have to be present - otherwise charm will not be able
        # to compare expected and given configs.

        charm_config = get_default_charm_config()
        charm_config['external-labels'] = {}
        del prom_api_response.config['global']['external_labels']

        # Wrong config comes from Prometheus
        prometheus_http_api_call_mock.return_value = prom_api_response.render()
        self.assertFalse(domain.reload_configuration(
            'juju-app', 'juju-model', charm_config
        ))

        # After some times it becomes valid
        prom_api_response.config['global']['scrape_interval'] = '15s'
        prometheus_http_api_call_mock.return_value = prom_api_response.render()
        self.assertTrue(domain.reload_configuration(
            'juju-app', 'juju-model', charm_config
        ))

        # Prom API returned some error
        prometheus_http_api_call_mock.side_effect = PrometheusAPIError('test')
        self.assertFalse(domain.reload_configuration(
            'juju-app', 'juju-model', charm_config
        ))

    def test_config_propagation_raises_on_wrong_arg(self):
        with self.assertRaises(CharmError):
            for opt in [{}, get_default_charm_config()]:
                domain.check_config_propagation('juju-app', 'juju-model', opt)


class HTTPCallTest(unittest.TestCase):
    @patch('domain.http.client.HTTPConnection', spec_set=True, autospec=True)
    def test__http_handler_raises_on_malformed_response(
            self, mocked_http_client):

        # Invalid method
        with self.assertRaises(CharmError):
            domain._prometheus_http_api_call(
                'juju-model', 'juju-app', 'FOO', '/-/', return_response=False
            )

        # Prom responded with 200 OK
        mocked_http_client.return_value.getresponse.return_value.status = 200
        domain._prometheus_http_api_call(
            'juju-model', 'juju-app', 'GET', '/-/', return_response=False
        )

        # Prom responded with 200 AND valid JSON file
        prom_api_config = json.dumps(PromMockConfig().render())
        mocked_http_client.return_value.getresponse.\
            return_value.read.return_value = prom_api_config
        domain._prometheus_http_api_call(
            'juju-model', 'juju-app', 'GET', '/-/',
        )

        # Prom responded with 200 but malformed json
        # (normally shouldn't happen)
        mocked_http_client.return_value.getresponse.\
            return_value.read.return_value = "[malformed-json-here"
        with self.assertRaises(PrometheusAPIError):
            domain._prometheus_http_api_call(
                'juju-model', 'juju-app', 'GET', '/-/'
            )

        # Prom responded with HTTP 300, smth went wrong
        mocked_http_client.return_value.getresponse.return_value.status = 300
        with self.assertRaises(PrometheusAPIError):
            domain._prometheus_http_api_call(
                'juju-model', 'juju-app', 'GET', '/-/', return_response=False
            )


class BuildPrometheusConfig(unittest.TestCase):

    def test__it_does_not_add_the_kube_metrics_scrape_config(self):
        charm_config = get_default_charm_config()
        prometheus_config = domain.build_prometheus_config(
            get_default_charm_config()
        )

        expected_config = {
            'global': {
                'scrape_interval': '15s',
                'scrape_timeout': '10s',
                'evaluation_interval': '1m',
                'external_labels': json.loads(charm_config['external-labels'])
            },
            'scrape_configs': [
                {
                    'job_name': 'prometheus',
                    'scrape_interval': '5s',
                    'scrape_timeout': '5s',
                    'metrics_path': '/metrics',
                    'honor_timestamps': True,
                    'scheme': 'http',
                    'static_configs': [
                        {
                            'targets': [
                                'localhost:{}'.format(
                                    domain.PROMETHEUS_ADVERTISED_PORT
                                )
                            ]
                        }
                    ]
                }
            ],
            'alerting': {}
        }

        self.assertEqual(
            expected_config, yaml.safe_load(prometheus_config.yaml_dump())
        )

    def test__it_adds_the_kube_metrics_scrape_config(self):
        charm_config = get_default_charm_config()
        charm_config['monitor-k8s'] = True
        prometheus_config = domain.build_prometheus_config(charm_config)

        expected_config = {
            'global': {
                'scrape_interval': '15s',
                'scrape_timeout': '10s',
                'evaluation_interval': '1m',
                'external_labels': json.loads(charm_config['external-labels'])
            },
            'scrape_configs': [
                {
                    'job_name': 'prometheus',
                    'scrape_interval': '5s',
                    'scrape_timeout': '5s',
                    'metrics_path': '/metrics',
                    'honor_timestamps': True,
                    'scheme': 'http',
                    'static_configs': [
                        {
                            'targets': [
                                'localhost:{}'.format(
                                    domain.PROMETHEUS_ADVERTISED_PORT
                                )
                            ]
                        }
                    ]
                }
            ],
            'alerting': {}
        }

        with open('templates/prometheus-k8s.yml') as prom_yaml:
            k8s_scrape_configs = yaml.safe_load(prom_yaml)['scrape_configs']

        for scrape_config in k8s_scrape_configs:
            expected_config['scrape_configs'].append(scrape_config)

        self.assertEqual(
            expected_config, yaml.safe_load(prometheus_config.yaml_dump())
        )
