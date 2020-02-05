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
        framework.model.unit = Mock()
        framework.meta = Mock()
        framework.meta.relations = []
        framework.meta.storages = []
        framework.meta.functions = []
        return framework

    @patch('charm.handlers.generate_spec')
    def test__on_spec_changed__spec_generated(self, mock_generate_spec):
        # Setup
        app_name = f'{uuid4()}'
        http_port = random.randint(1, 65535)
        image_metadata_fetched = True
        image_metadata = SimpleNamespace(**dict(
            registry_path=f'{uuid4()}/{uuid4()}',
            username=f'{uuid4()}',
            password=f'{uuid4()}'
        ))
        spec_is_set = False
        mock_framework = self.create_framework()
        mock_event = MagicMock(EventBase)
        mock_generate_spec.return_value = SimpleNamespace(**dict(
            unit_status=MaintenanceStatus("Configuring pod"),
            spec={
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
        ))

        # Exercise code
        charm_obj = Charm(mock_framework, None)
        charm_obj.on_spec_changed(mock_event)

        # Assertions
        assert mock_generate_spec.call_count == 1
        assert mock_generate_spec.call_args == \
            call(app_name=app_name,
                 http_port=http_port,
                 image_metadata_fetched=image_metadata_fetched,
                 image_metadata=image_metadata,
                 spec_is_set=spec_is_set)

        assert mock_framework.model.unit.status == \
            mock_generate_spec.return_value.unit_status

        assert mock_framework.model.set_spec.call_count == 1
        assert mock_framework.model.set_spec.call_args == \
            call(mock_generate_spec.return_value.spec)
