from pathlib import Path
import shutil
import sys
import tempfile
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

sys.path.append('src')
from charm import (
    Charm
)
from handlers import (
    ConfigChangeOutput,
    StartOutput
)
from image_registry import (
    ResourceError
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

    @patch('charm.handlers.on_config_changed', spec_set=True, autospec=True)
    @patch('charm.FrameworkAdapter', spec_set=True, autospec=True)
    @patch('charm.k8s', spec_set=True, autospec=True)
    def test__on_config_changed_delegator__it_blocks_until_pod_is_ready(
            self,
            mock_k8s_mod,
            mock_framework_adapter_cls,
            mock_on_config_changed_handler):
        # Setup
        mock_outputs = [
            ConfigChangeOutput(unit_status=object(), pod_is_ready=False),
            ConfigChangeOutput(unit_status=object(), pod_is_ready=False),
            ConfigChangeOutput(unit_status=object(), pod_is_ready=True)
        ]
        mock_on_config_changed_handler.side_effect = mock_outputs
        mock_pod_status = mock_k8s_mod.get_pod_status.return_value
        mock_adapter = mock_framework_adapter_cls.return_value
        mock_event = create_autospec(EventBase, spec_set=True)

        # Exercise
        charm_obj = Charm(self.create_framework(), None)
        charm_obj.on_config_changed_delegator(mock_event)

        # Assert
        assert mock_on_config_changed_handler.call_count == len(mock_outputs)
        assert mock_on_config_changed_handler.call_args_list == [
            call(pod_status=mock_pod_status) for i in range(len(mock_outputs))
        ]

        assert mock_adapter.set_unit_status.call_count == len(mock_outputs)
        assert mock_adapter.set_unit_status.call_args_list == [
            call(mock_output.unit_status) for mock_output in mock_outputs
        ]

    # spec_set=True ensures we don't define an attribute that is not in the
    # real object, autospec=True automatically copies the signature of the
    # mocked object to the mock.
    @patch('charm.handlers.on_start', spec_set=True, autospec=True)
    @patch('charm.image_registry', spec_set=True, autospec=True)
    @patch('charm.FrameworkAdapter', spec_set=True, autospec=True)
    def test__on_start_delegator__spec_is_set(
            self,
            mock_framework_adapter_cls,
            mock_image_registry_mod,
            mock_on_start_handler):

        # Setup
        mock_adapter = mock_framework_adapter_cls.return_value
        mock_image_meta = mock_image_registry_mod.fetch_meta.return_value
        mock_output = StartOutput(spec=object(), unit_status=object())
        mock_on_start_handler.return_value = mock_output

        # Exercise
        charm_obj = Charm(self.create_framework(), None)
        charm_obj.on_start_delegator(create_autospec(EventBase, spec_set=True))

        # Assertions
        assert mock_on_start_handler.call_count == 1
        assert mock_on_start_handler.call_args == call(
            app_name=mock_adapter.get_app_name.return_value,
            config=mock_adapter.get_config.return_value,
            image_meta=mock_image_meta)

        assert mock_adapter.set_pod_spec.call_count == 1
        assert mock_adapter.set_pod_spec.call_args == \
            call(mock_output.spec)

        assert mock_adapter.set_unit_status.call_count == 1
        assert mock_adapter.set_unit_status.call_args == \
            call(mock_output.unit_status)

    @patch('charm.image_registry', spec_set=True, autospec=True)
    @patch('charm.FrameworkAdapter', spec_set=True, autospec=True)
    def test__on_start_delegator__image_meta_fetch_failed(
            self,
            mock_framework_adapter_cls,
            mock_image_registry_mod):
        # Setup
        mock_error = ResourceError(resource_name=str(uuid4()),
                                   message=str(uuid4()))
        mock_image_registry_mod.fetch_meta.side_effect = mock_error
        mock_adapter = mock_framework_adapter_cls.return_value

        # Exercise
        charm_obj = Charm(self.create_framework(), None)
        charm_obj.on_start_delegator(create_autospec(EventBase, spec_set=True))

        # Assertions
        assert mock_adapter.set_pod_spec.call_count == 0
        assert mock_adapter.set_unit_status.call_count == 1
