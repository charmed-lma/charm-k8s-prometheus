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
    MaintenanceStatus,
)

sys.path.append('src')
from charm import (
    Charm
)


class CharmTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        # Ensure that we clean up the tmp directory even when the test
        # fails or errors out for whatever reason.
        self.addCleanup(shutil.rmtree, self.tmpdir)

    def create_framework(self):
        framework = Framework(self.tmpdir / "framework.data",
                              self.tmpdir, CharmMeta(), None)
        # Ensure that the Framework object is closed and cleaned up even
        # when the test fails or errors out.
        self.addCleanup(framework.close)

        return framework

    # spec_set=True ensures we don't define an attribute that is not in the
    # real object, autospec=True automatically copies the signature of the
    # mocked object to the mock.
    @patch('charm.handlers.generate_spec', spec_set=True, autospec=True)
    @patch('charm.OCIImageResource', spec_set=True, autospec=True)
    @patch('charm.FrameworkAdapter', spec_set=True, autospec=True)
    def test__set_spec__spec_should_be_set(self,
                                           mock_framework_adapter_cls,
                                           mock_image_resource_cls,
                                           mock_generate_spec):
        # Setup
        image_resource_fetched = True
        mock_image_resource_obj = mock_image_resource_cls.return_value
        mock_image_resource_obj.fetch.return_value = image_resource_fetched
        mock_image_resource_obj.image_path = f'{uuid4()}/{uuid4()}'
        mock_image_resource_obj.username = f'{uuid4()}'
        mock_image_resource_obj.password = f'{uuid4()}'

        mock_advertised_port = random.randint(1, 64535)
        mock_adapter = mock_framework_adapter_cls.return_value
        mock_adapter.get_app_name.return_value = f'{uuid4()}'
        mock_adapter.get_config.side_effect = [
            mock_advertised_port
        ]

        mock_event = create_autospec(EventBase)

        mock_output = SimpleNamespace(**dict(
            unit_status=MaintenanceStatus("Configuring pod"),
            spec={
                'containers': [
                    {
                        'name': mock_adapter.get_app_name.return_value,
                        'imageDetails': {
                            'imagePath':
                                mock_image_resource_obj.image_path,
                            'username':
                                mock_image_resource_obj.username,
                            'password':
                                mock_image_resource_obj.password
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
        mock_generate_spec.return_value = mock_output

        # Exercise code
        charm_obj = Charm(self.create_framework(), None)
        charm_obj.set_spec(mock_event)

        # Assertions
        assert mock_generate_spec.call_count == 1
        assert mock_generate_spec.call_args == call(
            event=mock_event,
            app_name=mock_adapter.get_app_name.return_value,
            advertised_port=mock_advertised_port,
            image_resource=mock_image_resource_obj,
            spec_is_set=False)

        assert mock_adapter.set_unit_status.call_count == 1
        assert type(mock_adapter.set_unit_status.call_args[0][0]) == \
            MaintenanceStatus
        assert mock_adapter.set_unit_status.call_args[0][0].message == \
            mock_output.unit_status.message

        assert mock_adapter.set_pod_spec.call_count == 1
        assert mock_adapter.set_pod_spec.call_args == \
            call(mock_output.spec)

        assert charm_obj.state.spec_is_set

    @patch('charm.handlers.generate_spec', spec_set=True, autospec=True)
    @patch('charm.OCIImageResource', spec_set=True, autospec=True)
    @patch('charm.FrameworkAdapter', spec_set=True, autospec=True)
    def test__set_spec__spec_should_not_be_set(
            self,
            mock_framework_adapter_cls,
            mock_image_resource_cls,
            mock_generate_spec):
        # Setup
        image_resource_fetched = True
        mock_image_resource_obj = mock_image_resource_cls.return_value
        mock_image_resource_obj.fetch.return_value = image_resource_fetched
        mock_image_resource_obj.image_path = f'{uuid4()}/{uuid4()}'
        mock_image_resource_obj.username = f'{uuid4()}'
        mock_image_resource_obj.password = f'{uuid4()}'

        mock_advertised_port = random.randint(1, 64535)
        mock_adapter = mock_framework_adapter_cls.return_value
        mock_adapter.get_app_name.return_value = f'{uuid4()}'
        mock_adapter.get_config.side_effect = [
            mock_advertised_port
        ]

        mock_event = create_autospec(EventBase)

        mock_output = SimpleNamespace(**dict(
            unit_status=ActiveStatus(),
            spec=None
        ))

        mock_generate_spec.return_value = mock_output

        # Exercise code
        charm_obj = Charm(self.create_framework(), None)
        charm_obj.state.spec_is_set = True
        charm_obj.set_spec(mock_event)

        # Assertions
        assert mock_generate_spec.call_count == 1
        assert mock_generate_spec.call_args == call(
            event=mock_event,
            app_name=mock_adapter.get_app_name.return_value,
            advertised_port=mock_advertised_port,
            image_resource=mock_image_resource_obj,
            spec_is_set=True)

        assert mock_adapter.set_unit_status.call_count == 1
        assert type(mock_adapter.set_unit_status.call_args[0][0]) == \
            ActiveStatus

        assert mock_adapter.set_pod_spec.call_count == 0

        assert charm_obj.state.spec_is_set
