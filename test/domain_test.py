import json
import sys
import unittest
from uuid import uuid4
import yaml

sys.path.append('lib')
from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
)

sys.path.append('src')
import domain
from exceptions import TimeStringParseError, ExternalLabelParseError
from adapters.k8s import (
    PodStatus
)
from adapters.framework import (
    ImageMeta,
)


def get_default_charm_config():
    return {
        'external-labels': '{"foo": "bar"}',
        'monitor-k8s': False,
        'log-level': '',
        'additional-cli-args': None,
        'web-enable-admin-api': False,
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


class PrometheusCLIArgumentsTest(unittest.TestCase):
    @staticmethod
    def test__cli_args_are_rendered_correctly():
        # mock_config = self.default_mock_config
        config = get_default_charm_config()
        mock_args_config = domain.build_prometheus_cli_args(config)
        expected_cli_args = [
            '--config.file=/etc/prometheus/prometheus.yml',
            '--storage.tsdb.path=/prometheus',
            '--web.enable-lifecycle',
            '--web.console.templates=/usr/share/prometheus/consoles',
            '--web.console.libraries=/usr/share/prometheus/console_libraries',
            '--log.level=info',
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
    @staticmethod
    def test__pod_spec_is_generated():
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
            app_name=mock_app_name,
            charm_config=mock_config,
            image_meta=mock_image_meta)

        # Assertions
        assert isinstance(juju_pod_spec, domain.PrometheusJujuPodSpec)
        assert juju_pod_spec.to_dict() == {'containers': [{
            'name': mock_app_name,
            'imageDetails': {
                'imagePath': mock_image_meta.image_path,
                'username': mock_image_meta.repo_username,
                'password': mock_image_meta.repo_password
            },
            'args': mock_args_config,
            'ports': [{
                'containerPort': 9090,
                'protocol': 'TCP'
            }],
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
                'name': 'config',
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
                                'job_name': 'prometheus',
                                'scrape_interval': '5s',
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
        }]}


class BuildJujuUnitStatusTest(unittest.TestCase):

    def test_returns_maintenance_status_if_pod_status_cannot_be_fetched(self):
        # Setup
        pod_status = PodStatus(status_dict=None)

        # Exercise
        juju_unit_status = domain.build_juju_unit_status(pod_status)

        # Assertions
        assert type(juju_unit_status) == MaintenanceStatus
        assert juju_unit_status.message == "Waiting for pod to appear"

    def test_returns_maintenance_status_if_pod_is_not_running(self):
        # Setup
        status_dict = {
            'metadata': {
                'annotations': {
                    'juju.io/unit': uuid4()
                }
            },
            'status': {
                'phase': 'Pending',
                'conditions': [{
                    'type': 'ContainersReady',
                    'status': 'False'
                }]
            }
        }
        pod_status = PodStatus(status_dict=status_dict)

        # Exercise
        juju_unit_status = domain.build_juju_unit_status(pod_status)

        # Assertions
        assert type(juju_unit_status) == MaintenanceStatus
        assert juju_unit_status.message == "Pod is starting"

    def test_returns_maintenance_status_if_pod_is_not_ready(self):
        # Setup
        status_dict = {
            'metadata': {
                'annotations': {
                    'juju.io/unit': uuid4()
                }
            },
            'status': {
                'phase': 'Running',
                'conditions': [{
                    'type': 'ContainersReady',
                    'status': 'False'
                }]
            }
        }
        pod_status = PodStatus(status_dict=status_dict)

        # Exercise
        juju_unit_status = domain.build_juju_unit_status(pod_status)

        # Assertions
        assert type(juju_unit_status) == MaintenanceStatus
        assert juju_unit_status.message == "Pod is getting ready"

    def test_returns_active_status_if_pod_is_ready(self):
        # Setup
        status_dict = {
            'metadata': {
                'annotations': {
                    'juju.io/unit': uuid4()
                }
            },
            'status': {
                'phase': 'Running',
                'conditions': [{
                    'type': 'ContainersReady',
                    'status': 'True'
                }]
            }
        }
        pod_status = PodStatus(status_dict=status_dict)

        # Exercise
        juju_unit_status = domain.build_juju_unit_status(pod_status)

        # Assertions
        assert type(juju_unit_status) == ActiveStatus


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
