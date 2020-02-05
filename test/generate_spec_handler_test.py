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

sys.path.append('src')
from resources import OCIImageResource
import handlers


class GenerateSpecHandlerTest(unittest.TestCase):

    def test_spec_generated_succesfully(self):
        # Set up
        image_metadata = MagicMock(OCIImageResource)
        image_metadata.registry_path = f'{uuid4()}/{uuid4()}'
        image_metadata.username = f'{uuid4()}'
        image_metadata.password = f'{uuid4()}'

        app_name = f'{uuid4()}'
        http_port = random.randint(1, 65535)

        # Exercise the code
        output = handlers.generate_spec(app_name=app_name,
                                        http_port=http_port,
                                        image_metadata_fetched=True,
                                        image_metadata=image_metadata,
                                        spec_is_set=False)

        # Assertions
        assert type(output.unit_status) == MaintenanceStatus
        assert output.unit_status.message == "Configuring pod"

        assert output.spec == {
            'containers': [
                {
                    'name': app_name,
                    'imageDetails': {
                        'imagePath': image_metadata.registry_path,
                        'username': image_metadata.username,
                        'password': image_metadata.password
                    },
                    'ports': [
                        {
                            'containerPort': http_port,
                            'protocol': 'TCP'
                        }
                    ]
                }
            ]
        }
