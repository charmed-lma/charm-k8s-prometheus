from pathlib import Path
import random
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import (
    call,
    create_autospec,
    patch
)
from uuid import uuid4

sys.path.append('src')
sys.path.append('lib')

from ops.charm import (
    CharmMeta,
)
from ops.framework import (
    EventBase,
    Framework
)
from ops.model import (
    ActiveStatus,
    Application,
    MaintenanceStatus,
    Model,
    Pod,
    Resources,
    Unit,
)
from charm import Charm


class CharmTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        # Ensure that we clean up the tmp directory even when the test
        # fails or errors out for whatever reason.
        self.addCleanup(shutil.rmtree, self.tmpdir)

    def create_framework(self):
        framework = Framework(self.tmpdir / "framework.data",
                              self.tmpdir, None, None)
        # Ensure that the Framework object is closed and cleaned up even
        # when the test fails or errors out.
        self.addCleanup(framework.close)

        framework.model = create_autospec(Model,
                                          spec_set=True,
                                          instance=True)
        framework.model.app = create_autospec(Application,
                                              spec_set=True,
                                              instance=True)
        framework.model.app.name = f'{uuid4()}'
        framework.model.pod = create_autospec(Pod,
                                              spec_set=True,
                                              instance=True)
        framework.model.resources = create_autospec(Resources,
                                                    spec_set=True,
                                                    instance=True)
        framework.model.unit = create_autospec(Unit,
                                               spec_set=True,
                                               instance=True)
        framework.model.config = {
            'advertised_port': random.randint(1, 65535)
        }

        framework.meta = create_autospec(CharmMeta,
                                         spec_set=True,
                                         instance=True)
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
        mock_event = create_autospec(EventBase)
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

        # Exercise code
        charm_obj.on_spec_changed(mock_event)

        # Assertions
        assert mock_generate_spec.call_count == 1
        assert mock_generate_spec.call_args == call(
            app_name=mock_framework.model.app.name,
            advertised_port=mock_advertised_port,
            image_resource_fetched=image_resource_fetched,
            image_resource=mock_oci_image_resource_obj,
            spec_is_set=False)

        assert mock_framework.model.unit.status == \
            mock_generate_spec.return_value.unit_status

        assert mock_framework.model.pod.set_spec.call_count == 1
        assert mock_framework.model.pod.set_spec.call_args == \
            call(mock_generate_spec.return_value.spec)

        assert charm_obj.state.spec_is_set

    @patch('charm.handlers.generate_spec', autospec=True)
    @patch('charm.OCIImageResource', autospec=True)
    def test__on_spec_changed__spec_was_previously_set(
            self,
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
        mock_event = create_autospec(EventBase)
        mock_generate_spec.return_value = SimpleNamespace(**dict(
            unit_status=ActiveStatus(),
            spec=None
        ))

        charm_obj = Charm(mock_framework, None)
        charm_obj.state.spec_is_set = True

        # Exercise code
        charm_obj.on_spec_changed(mock_event)

        # Assertions
        assert mock_generate_spec.call_count == 1
        assert mock_generate_spec.call_args == call(
            app_name=mock_framework.model.app.name,
            advertised_port=mock_advertised_port,
            image_resource_fetched=image_resource_fetched,
            image_resource=mock_oci_image_resource_obj,
            spec_is_set=True)

        assert mock_framework.model.unit.status == \
            mock_generate_spec.return_value.unit_status

        assert mock_framework.model.pod.set_spec.call_count == 0

        assert charm_obj.state.spec_is_set
