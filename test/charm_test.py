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
from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
)

sys.path.append('src')
from adapters import (
    framework,
)
import charm


class CharmTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        # Ensure that we clean up the tmp directory even when the test
        # fails or errors out for whatever reason.
        self.addCleanup(shutil.rmtree, self.tmpdir)

    def create_framework(self):
        raw_meta = {
            'provides': {'http-api': {"interface": "prometheus-http-api"}}
        }
        framework = Framework(self.tmpdir / "framework.data",
                              self.tmpdir, CharmMeta(raw=raw_meta), None)
        # Ensure that the Framework object is closed and cleaned up even
        # when the test fails or errors out.
        self.addCleanup(framework.close)

        return framework

    @patch('charm.FrameworkAdapter', spec_set=True, autospec=True)
    def test__init__works_without_a_hitch(self,
                                          mock_framework_adapter_cls):
        # Exercise
        charm.Charm(self.create_framework(), None)


class OnConfigChangedHandlerTest(unittest.TestCase):

    # We are mocking the time module here so that we don't actually wait
    # 1 second per loop during test exectution.
    @patch('charm.build_juju_unit_status', spec_set=True, autospec=True)
    @patch('charm.k8s', spec_set=True, autospec=True)
    @patch('charm.time', spec_set=True, autospec=True)
    @patch('charm.build_juju_pod_spec', spec_set=True, autospec=True)
    @patch('charm.build_pod_spec', spec_set=True, autospec=True)
    def test__it_blocks_until_pod_is_ready(
            self,
            mock_pod_spec,
            mock_juju_pod_spec,
            mock_time,
            mock_k8s_mod,
            mock_build_juju_unit_status_func):
        # Setup
        mock_fw_adapter_cls = \
            create_autospec(framework.FrameworkAdapter, spec_set=True)
        mock_fw_adapter = mock_fw_adapter_cls.return_value

        mock_juju_unit_states = [
            MaintenanceStatus(str(uuid4())),
            MaintenanceStatus(str(uuid4())),
            ActiveStatus(str(uuid4())),
        ]
        mock_build_juju_unit_status_func.side_effect = mock_juju_unit_states

        mock_event_cls = create_autospec(EventBase, spec_set=True)
        mock_event = mock_event_cls.return_value

        # Exercise
        charm.on_config_changed_handler(mock_event, mock_fw_adapter)

        # Assert
        assert mock_fw_adapter.set_unit_status.call_count == \
            len(mock_juju_unit_states)
        assert mock_fw_adapter.set_unit_status.call_args_list == [
            call(status) for status in mock_juju_unit_states
        ]


class OnStartHandlerTest(unittest.TestCase):

    @patch('charm.build_juju_pod_spec', spec_set=True, autospec=True)
    def test__it_updates_the_juju_pod_spec(self,
                                           mock_build_juju_pod_spec_func):
        # Setup
        mock_fw_adapter_cls = \
            create_autospec(framework.FrameworkAdapter,
                            spec_set=True)
        mock_fw = mock_fw_adapter_cls.return_value
        mock_fw.am_i_leader.return_value = True

        mock_event_cls = create_autospec(EventBase, spec_set=True)
        mock_event = mock_event_cls.return_value

        # Exercise
        charm.on_start_handler(mock_event, mock_fw)

        # Assert
        assert mock_build_juju_pod_spec_func.call_count == 1
        assert mock_build_juju_pod_spec_func.call_args == \
            call(app_name=mock_fw.get_app_name.return_value,
                 charm_config=mock_fw.get_config.return_value,
                 image_meta=mock_fw.get_image_meta.return_value)

        assert mock_fw.set_pod_spec.call_count == 1
        assert mock_fw.set_pod_spec.call_args == \
            call(mock_build_juju_pod_spec_func.return_value)

        assert mock_fw.set_unit_status.call_count == 1
        args, kwargs = mock_fw.set_unit_status.call_args_list[0]
        assert type(args[0]) == MaintenanceStatus
