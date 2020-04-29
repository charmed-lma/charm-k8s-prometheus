import json
import random
import sys
import unittest
from unittest.mock import (
    call,
    create_autospec,
)
from uuid import uuid4
import yaml

sys.path.append('lib')
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
)

sys.path.append('src')
import handlers
from k8s import (
    PodStatus
)
from resources import (
    ResourceError,
    OCIImageResource,
)


class OnStartHandlerTest(unittest.TestCase):

    def test_pod_spec_is_generated(self):
        # Set up
        mock_app_name = f'{uuid4()}'

        mock_advertised_port = random.randint(1, 65535)
        mock_external_labels = {
            f"{uuid4()}": f"{uuid4()}",
            f"{uuid4()}": f"{uuid4()}",
            f"{uuid4()}": f"{uuid4()}",
        }

        mock_config = {
            'advertised-port': mock_advertised_port,
            'external-labels': json.dumps(mock_external_labels)
        }

        mock_image_resource = create_autospec(OCIImageResource, spec_set=True)
        mock_image_resource.fetch.return_value = True

        # Exercise
        output = handlers.on_start(
            app_name=mock_app_name,
            config=mock_config,
            image_resource=mock_image_resource)

        # Assertions
        assert mock_image_resource.fetch.call_count == 1
        assert mock_image_resource.fetch.call_args == call()

        assert type(output.unit_status) == MaintenanceStatus
        assert output.unit_status.message == "Configuring pod"

        assert type(output.spec) == dict
        assert output.spec == {'containers': [{
            'name': mock_app_name,
            'imageDetails': {
                'imagePath': mock_image_resource.image_path,
                'username': mock_image_resource.username,
                'password': mock_image_resource.password
            },
            'ports': [{
                'containerPort': mock_config['advertised-port'],
                'protocol': 'TCP'
            }],
            'readinessProbe': {
                'httpGet': {
                    'path': '/-/ready',
                    'port': mock_config['advertised-port']
                },
                'initialDelaySeconds': 10,
                'timeoutSeconds': 30
            },
            'livenessProbe': {
                'httpGet': {
                    'path': '/-/healthy',
                    'port': mock_config['advertised-port']
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
                                            f'localhost:{mock_advertised_port}'
                                        ]
                                    }
                                ]
                            }
                        ]
                    })
                }
            }]
        }]}

    def test_ResourceError_is_caught_and_handled_properly(self):
        # Set up
        mock_app_name = f'{uuid4()}'

        mock_advertised_port = random.randint(1, 65535)
        mock_external_labels = {
            f"{uuid4()}": f"{uuid4()}",
            f"{uuid4()}": f"{uuid4()}",
            f"{uuid4()}": f"{uuid4()}",
        }

        mock_config = {
            'advertised-port': mock_advertised_port,
            'external-labels': json.dumps(mock_external_labels)
        }

        mock_resource_error = ResourceError(f'{uuid4()}', f'{uuid4()}')
        mock_image_resource = create_autospec(OCIImageResource, spec_set=True)
        mock_image_resource.fetch.side_effect = mock_resource_error

        # Exercise
        output = handlers.on_start(
            app_name=mock_app_name,
            config=mock_config,
            image_resource=mock_image_resource)

        # Assertions
        assert mock_image_resource.fetch.call_count == 1

        assert type(output.unit_status) == BlockedStatus
        assert output.unit_status == mock_resource_error.status

        assert output.spec is None


class OnConfigChangedHandler(unittest.TestCase):

    def test_returns_maintenance_status_if_pod_status_cannot_be_fetched(self):
        # Setup
        pod_status = PodStatus(status_dict=None)

        # Exercise
        output = handlers.on_config_changed(pod_status)

        # Assertions
        assert type(output.unit_status) == MaintenanceStatus
        assert output.unit_status.message == "Waiting for pod to appear"
        assert not output.pod_is_ready

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
        output = handlers.on_config_changed(pod_status)

        # Assertions
        assert type(output.unit_status) == MaintenanceStatus
        assert output.unit_status.message == "Pod is starting"
        assert not output.pod_is_ready

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
        output = handlers.on_config_changed(pod_status)

        # Assertions
        assert type(output.unit_status) == MaintenanceStatus
        assert output.unit_status.message == "Pod is getting ready"
        assert not output.pod_is_ready

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
        output = handlers.on_config_changed(pod_status)

        # Assertions
        assert type(output.unit_status) == ActiveStatus
        assert output.pod_is_ready
