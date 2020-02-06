import random
import sys
import unittest
from unittest.mock import (
    MagicMock
)
from uuid import uuid4

sys.path.append('lib')
from ops.model import (
    MaintenanceStatus,
)
from oci_image import OCIImageResource

sys.path.append('src')
import handlers


class GenerateSpecHandlerTest(unittest.TestCase):

    def test_spec_generated_succesfully(self):
        # Set up
        image_resource = MagicMock(OCIImageResource)
        image_resource.registry_path = f'{uuid4()}/{uuid4()}'
        image_resource.username = f'{uuid4()}'
        image_resource.password = f'{uuid4()}'

        app_name = f'{uuid4()}'
        advertised_port = random.randint(1, 65535)

        # Exercise the code
        output = handlers.generate_spec(app_name=app_name,
                                        advertised_port=advertised_port,
                                        image_resource_fetched=True,
                                        image_resource=image_resource,
                                        spec_is_set=False)

        # Assertions
        assert type(output.unit_status) == MaintenanceStatus
        assert output.unit_status.message == "Configuring pod"

        assert output.spec == {
            'containers': [
                {
                    'name': app_name,
                    'imageDetails': {
                        'imagePath': image_resource.registry_path,
                        'username': image_resource.username,
                        'password': image_resource.password
                    },
                    'ports': [
                        {
                            'containerPort': advertised_port,
                            'protocol': 'TCP'
                        }
                    ]
                }
            ]
        }
