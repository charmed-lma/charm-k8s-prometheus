import json
import random
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
from adapters.k8s import (
    PodStatus
)
from adapters.framework import (
    ImageMeta,
)


class BuildJujuPodSpecTest(unittest.TestCase):

    def test__pod_spec_is_generated(self):
        # Set up
        mock_app_name = f'{uuid4()}'

        mock_external_labels = {
            f"{uuid4()}": f"{uuid4()}",
            f"{uuid4()}": f"{uuid4()}",
            f"{uuid4()}": f"{uuid4()}",
        }

        mock_config = {
            'external-labels': json.dumps(mock_external_labels),
            'monitor-k8s': False
        }

        mock_image_meta = ImageMeta({
            'registrypath': str(uuid4()),
            'username': str(uuid4()),
            'password': str(uuid4()),
        })

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
                        ]
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


class BuildPrometheusConfig(unittest.TestCase):

    def test__it_does_not_add_the_kube_metrics_scrape_config(self):
        mock_external_labels = str(uuid4())
        mock_advertised_port = random.randint(1, 65535)
        mock_prometheus_address = 'localhost:{}'.format(mock_advertised_port)

        prometheus_config = domain.build_prometheus_config(
            external_labels=mock_external_labels,
            advertised_port=mock_advertised_port,
            monitor_k8s=False
        )

        expected_config = {
            'global': {
                'scrape_interval': '15s',
                'external_labels': mock_external_labels
            },
            'scrape_configs': [
                {
                    'job_name': 'prometheus',
                    'scrape_interval': '5s',
                    'static_configs': [
                        {'targets': [mock_prometheus_address]}
                    ]
                }
            ]
        }

        assert yaml.safe_load(prometheus_config.yaml_dump()) == expected_config

    def test__it_adds_the_kube_metrics_scrape_config(self):
        mock_external_labels = str(uuid4())
        mock_advertised_port = random.randint(1, 65535)
        mock_prometheus_address = 'localhost:{}'.format(mock_advertised_port)

        prometheus_config = domain.build_prometheus_config(
            external_labels=mock_external_labels,
            advertised_port=mock_advertised_port,
            monitor_k8s=True
        )

        expected_config = {
            'global': {
                'scrape_interval': '15s',
                'external_labels': mock_external_labels
            },
            'scrape_configs': [
                {
                    'job_name': 'prometheus',
                    'scrape_interval': '5s',
                    'static_configs': [
                        {'targets': [mock_prometheus_address]}
                    ]
                }
            ]
        }

        with open('templates/prometheus-k8s.yml') as prom_yaml:
            k8s_scrape_configs = yaml.safe_load(prom_yaml)['scrape_configs']

        for scrape_config in k8s_scrape_configs:
            expected_config['scrape_configs'].append(scrape_config)

        assert yaml.safe_load(prometheus_config.yaml_dump()) == expected_config
