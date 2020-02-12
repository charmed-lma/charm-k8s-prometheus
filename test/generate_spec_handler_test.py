import random
import sys
import unittest
from unittest.mock import (
    create_autospec,
)
from uuid import uuid4
import yaml

sys.path.append('lib')
from ops.framework import (
    EventBase,
)
from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
)

sys.path.append('src')
import handlers
from resources import OCIImageResource


class GenerateSpecHandlerTest(unittest.TestCase):

    def test_pod_spec_should_be_generated(self):
        # Set up
        image_resource = create_autospec(OCIImageResource, spec_set=True)
        image_resource.image_path = f'{uuid4()}/{uuid4()}'
        image_resource.username = f'{uuid4()}'
        image_resource.password = f'{uuid4()}'

        app_name = f'{uuid4()}'
        advertised_port = random.randint(1, 65535)

        mock_event = create_autospec(EventBase)

        expected_external_labels = {
            f'{uuid4()}': f'{uuid4()}',
            f'{uuid4()}': f'{uuid4()}',
            f'{uuid4()}': f'{uuid4()}'
        }

        expected_prometheus_yaml = yaml.dump({
            'global': {
                'scrape_interval': '15s',
                'external_labels': expected_external_labels
            },
            'scrape_configs': [
                {
                    'job_name': 'prometheus',
                    'scrape_interval': '5s',
                    'static_configs': [
                        {
                            'targets': [
                                f'localhost:{advertised_port}'
                            ]
                        }
                    ]
                }
            ]
        })

        expected_spec = {
            'containers': [
                {
                    'name': app_name,
                    'imageDetails': {
                        'imagePath': image_resource.image_path,
                        'username': image_resource.username,
                        'password': image_resource.password
                    },
                    'ports': [
                        {
                            'containerPort': advertised_port,
                            'protocol': 'TCP'
                        }
                    ],
                    'files': [
                        {
                            'name': 'config',
                            'mountPath': '/etc/prometheus',
                            'files': {
                                'prometheus.yml': expected_prometheus_yaml
                            }
                        }
                    ]
                }
            ]
        }

        # Exercise the code
        output = handlers.generate_spec(
            event=mock_event,
            app_name=app_name,
            advertised_port=advertised_port,
            external_labels=expected_external_labels,
            image_resource=image_resource,
            spec_is_set=False)

        # Assertions
        assert type(output.unit_status) == MaintenanceStatus
        assert output.unit_status.message == "Configuring pod"

        assert output.spec == expected_spec

    def test_spec_should_not_be_generated(self):
        # Set up
        image_resource = create_autospec(OCIImageResource, spec_set=True)
        image_resource.image_path = f'{uuid4()}/{uuid4()}'
        image_resource.username = f'{uuid4()}'
        image_resource.password = f'{uuid4()}'

        app_name = f'{uuid4()}'

        advertised_port = random.randint(1, 65535)

        mock_event = create_autospec(EventBase)

        # Exercise the code
        output = handlers.generate_spec(event=mock_event,
                                        app_name=app_name,
                                        advertised_port=advertised_port,
                                        image_resource=image_resource,
                                        spec_is_set=True)

        # Assertions
        assert type(output.unit_status) == ActiveStatus
        assert output.spec is None
