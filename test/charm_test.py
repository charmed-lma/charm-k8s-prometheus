from pathlib import Path
import random
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import (
    call,
    MagicMock,
    Mock,
    patch
)
from uuid import uuid4

sys.path.append('src')
sys.path.append('lib')

from ops.framework import (
    EventBase,
    Framework
)
from ops.model import (
    MaintenanceStatus,
)
from charm import Charm


class CharmTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmpdir)

    def create_framework(self):
        framework = Framework(self.tmpdir / "framework.data",
                              self.tmpdir, None, None)
        self.addCleanup(framework.close)

        framework.model = Mock()
        framework.model.app = Mock()
        framework.model.app.name = f'{uuid4()}'
        framework.model.unit = Mock()
        framework.model.config = {
            'advertised_port': random.randint(1, 65535)
        }
        framework.state = Mock()

        framework.meta = Mock()
        framework.meta.relations = []
        framework.meta.storages = []
        framework.meta.functions = []

        return framework

    @patch('charm.handlers.generate_spec', autospec=True)
    @patch('charm.OCIImageResource', autospec=True)
    def test__on_spec_changed__spec_generated(self,
                                              mock_oci_image_resource_cls,
                                              mock_generate_spec):
        # Setup
        mock_oci_image_resource_obj = mock_oci_image_resource_cls.return_value
        mock_oci_image_resource_obj.registry_path = f'{uuid4()}/{uuid4()}'
        mock_oci_image_resource_obj.username = f'{uuid4()}'
        mock_oci_image_resource_obj.password = f'{uuid4()}'
        image_resource_fetched = True
        mock_oci_image_resource_obj.fetch.return_value = image_resource_fetched

        mock_framework = self.create_framework()
        mock_advertised_port = mock_framework.model.config['advertised_port']
        mock_event = MagicMock(EventBase)
        mock_generate_spec.return_value = SimpleNamespace(**dict(
            unit_status=MaintenanceStatus("Configuring pod"),
            spec={
                'containers': [
                    {
                        'name': mock_framework.model.app.name,
                        'imageDetails': {
                            'imagePath':
                                mock_oci_image_resource_obj.registry_path,
                            'username':
                                mock_oci_image_resource_obj.username,
                            'password':
                                mock_oci_image_resource_obj.password
                        },
                        'ports': [
                            {
                                'containerPort': mock_advertised_port,
                                'protocol': 'TCP'
                            }
                        ]
                    }
                ]
            }
        ))

        charm_obj = Charm(mock_framework, None)
        spec_is_set = charm_obj.state.spec_is_set

        # Exercise code
        charm_obj.on_spec_changed(mock_event)

        # Assertions
        assert mock_generate_spec.call_count == 1
        assert mock_generate_spec.call_args == call(
            app_name=mock_framework.model.app.name,
            advertised_port=mock_advertised_port,
            image_resource_fetched=image_resource_fetched,
            image_resource=mock_oci_image_resource_obj,
            spec_is_set=spec_is_set)

        assert mock_framework.model.unit.status == \
            mock_generate_spec.return_value.unit_status

        assert mock_framework.model.set_spec.call_count == 1
        assert mock_framework.model.set_spec.call_args == \
            call(mock_generate_spec.return_value.spec)

        assert charm_obj.state.spec_is_set
