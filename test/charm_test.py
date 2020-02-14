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
    @patch('charm.handlers.on_start', spec_set=True, autospec=True)
    @patch('charm.PrometheusImageResource', spec_set=True, autospec=True)
    @patch('charm.FrameworkAdapter', spec_set=True, autospec=True)
    def test__on_start_delegator__spec_is_set(
            self,
            mock_framework_adapter_cls,
            mock_prometheus_image_resource_cls,
            mock_on_start_handler):

        # Setup
        mock_event = create_autospec(EventBase, spec_set=True)
        mock_adapter = mock_framework_adapter_cls.return_value
        mock_image_resource = mock_prometheus_image_resource_cls.return_value
        mock_output = create_autospec(object)
        mock_output.spec = create_autospec(object)
        mock_output.unit_status = create_autospec(object)
        mock_on_start_handler.return_value = mock_output

        # Exercise
        charm_obj = Charm(self.create_framework(), None)
        charm_obj.on_start_delegator(mock_event)

        # Assertions
        assert mock_adapter.get_config.call_count == 1
        assert mock_adapter.get_config.call_args == call()

        assert mock_on_start_handler.call_count == 1
        assert mock_on_start_handler.call_args == call(
            event=mock_event,
            app_name=mock_adapter.get_app_name.return_value,
            config=mock_adapter.get_config.return_value,
            image_resource=mock_image_resource,
            spec_is_set=False)

        assert mock_adapter.set_pod_spec.call_count == 1
        assert mock_adapter.set_pod_spec.call_args == \
            call(mock_output.spec)

        assert charm_obj.state.spec_is_set

        assert mock_adapter.set_unit_status.call_count == 1
        assert mock_adapter.set_unit_status.call_args == \
            call(mock_output.unit_status)

    # spec_set=True ensures we don't define an attribute that is not in the
    # real object, autospec=True automatically copies the signature of the
    # mocked object to the mock.
    @patch('charm.handlers.on_start', spec_set=True, autospec=True)
    @patch('charm.PrometheusImageResource', spec_set=True, autospec=True)
    @patch('charm.FrameworkAdapter', spec_set=True, autospec=True)
    def test__on_start_delegator__spec_is_not_set_more_than_once(
            self,
            mock_framework_adapter_cls,
            mock_prometheus_image_resource_cls,
            mock_on_start_handler):

        # Setup
        mock_event = create_autospec(EventBase, spec_set=True)
        mock_adapter = mock_framework_adapter_cls.return_value
        mock_image_resource = mock_prometheus_image_resource_cls.return_value
        mock_output = create_autospec(object)
        mock_output.spec = None
        mock_output.unit_status = create_autospec(object)
        mock_on_start_handler.return_value = mock_output

        # Exercise
        charm_obj = Charm(self.create_framework(), None)
        charm_obj.state.spec_is_set = True
        charm_obj.on_start_delegator(mock_event)

        # Assertions
        assert mock_on_start_handler.call_count == 1
        assert mock_on_start_handler.call_args == call(
            event=mock_event,
            app_name=mock_adapter.get_app_name.return_value,
            config=mock_adapter.get_config.return_value,
            image_resource=mock_image_resource,
            spec_is_set=True)

        assert mock_adapter.set_pod_spec.call_count == 0

        assert charm_obj.state.spec_is_set

        assert mock_adapter.set_unit_status.call_count == 1
        assert mock_adapter.set_unit_status.call_args == \
            call(mock_output.unit_status)

    @patch('charm.handlers.on_start', spec_set=True, autospec=True)
    @patch('charm.PrometheusImageResource', spec_set=True, autospec=True)
    @patch('charm.FrameworkAdapter', spec_set=True, autospec=True)
    def test__on_upgrade_delegator__it_updates_the_spec(
            self,
            mock_framework_adapter_cls,
            mock_prometheus_image_resource_cls,
            mock_on_start_handler):

        # Setup
        mock_event = create_autospec(EventBase, spec_set=True)
        mock_adapter = mock_framework_adapter_cls.return_value
        mock_image_resource = mock_prometheus_image_resource_cls.return_value
        mock_output = create_autospec(object)
        mock_output.spec = create_autospec(object)
        mock_output.unit_status = create_autospec(object)
        mock_on_start_handler.return_value = mock_output

        # Exercise
        charm_obj = Charm(self.create_framework(), None)
        charm_obj.state.spec_is_set = True
        charm_obj.on_upgrade_delegator(mock_event)

        # Assertions
        assert mock_adapter.get_config.call_count == 1
        assert mock_adapter.get_config.call_args == call()

        assert mock_on_start_handler.call_count == 1
        assert mock_on_start_handler.call_args == call(
            event=mock_event,
            app_name=mock_adapter.get_app_name.return_value,
            config=mock_adapter.get_config.return_value,
            image_resource=mock_image_resource,
            spec_is_set=False)

        assert mock_adapter.set_pod_spec.call_count == 1
        assert mock_adapter.set_pod_spec.call_args == \
            call(mock_output.spec)

        assert charm_obj.state.spec_is_set

        assert mock_adapter.set_unit_status.call_count == 1
        assert mock_adapter.set_unit_status.call_args == \
            call(mock_output.unit_status)
