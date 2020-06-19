import json
import sys
import unittest
from unittest.mock import (
    call,
    create_autospec,
    patch
)
from uuid import uuid4

sys.path.append('lib')
from ops.framework import (
    EventBase,
)
from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
)
sys.path.append('src')
from adapters import (
    framework,
    k8s,
)
import charm
import domain


# This test is disabled due to the:
# https://github.com/canonical/operator/issues/307
# https://github.com/canonical/operator/issues/309

# class OnConfigChangedHandlerTest(unittest.TestCase):
#     # We are mocking the time module here so that we don't actually wait
#     # 1 second per loop during test exectution.
#     @patch('charm.build_juju_unit_status', spec_set=True, autospec=True)
#     @patch('charm.k8s', spec_set=True, autospec=True)
#     @patch('charm.time', spec_set=True, autospec=True)
#     @patch('charm.build_juju_pod_spec', spec_set=True, autospec=True)
#     @patch('charm.set_juju_pod_spec', spec_set=True, autospec=True)
#     def test__it_blocks_until_pod_is_ready(
#             self,
#             mock_pod_spec,
#             mock_juju_pod_spec,
#             mock_time,
#             mock_k8s_mod,
#             mock_build_juju_unit_status_func):
#         # Setup
#         mock_fw_adapter_cls = \
#             create_autospec(framework.FrameworkAdapter, spec_set=True)
#         mock_fw_adapter = mock_fw_adapter_cls.return_value
#
#         mock_juju_unit_states = [
#             MaintenanceStatus(str(uuid4())),
#             MaintenanceStatus(str(uuid4())),
#             ActiveStatus(str(uuid4())),
#         ]
#         mock_build_juju_unit_status_func.side_effect = mock_juju_unit_states
#
#         mock_event_cls = create_autospec(EventBase, spec_set=True)
#         mock_event = mock_event_cls.return_value
#
#         harness = Harness(charm.Charm)
#         harness.begin()
#         harness.charm._stored.set_default(is_started=False)
#         harness.charm.on.config_changed.emit()
#
#         # # Exercise
#         # charm.on_config_changed_handler(
#         #     mock_event, mock_fw_adapter, harness.charm._stored
#         # )
#         #
#         # # Assert
#         # assert mock_fw_adapter.set_unit_status.call_count == \
#         #     len(mock_juju_unit_states)
#         # assert mock_fw_adapter.set_unit_status.call_args_list == [
#         #     call(status) for status in mock_juju_unit_states
#         # ]


class BuildJujuUnitStatusTest(unittest.TestCase):

    def test_returns_maintenance_status_if_pod_status_cannot_be_fetched(self):
        # Setup
        pod_status = k8s.PodStatus(status_dict=None)

        # Exercise
        juju_unit_status = charm.build_juju_unit_status(pod_status)

        # Assertions
        assert type(juju_unit_status) == MaintenanceStatus
        assert juju_unit_status.message == "Waiting for pod to appear"

    def test_returns_maintenance_status_if_pod_is_not_running(self):
        # Setup
        status_dict = {
            'metadata': {
                'annotations': {
                    'juju.io/unit': uuid4()
                }
            },
            'status': {
                'phase': 'Pending',
                'conditions': [{
                    'type': 'ContainersReady',
                    'status': 'False'
                }]
            }
        }
        pod_status = k8s.PodStatus(status_dict=status_dict)

        # Exercise
        juju_unit_status = charm.build_juju_unit_status(pod_status)

        # Assertions
        assert type(juju_unit_status) == MaintenanceStatus
        assert juju_unit_status.message == "Pod is starting"

    def test_returns_maintenance_status_if_pod_is_not_ready(self):
        # Setup
        status_dict = {
            'metadata': {
                'annotations': {
                    'juju.io/unit': uuid4()
                }
            },
            'status': {
                'phase': 'Running',
                'conditions': [{
                    'type': 'ContainersReady',
                    'status': 'False'
                }]
            }
        }
        pod_status = k8s.PodStatus(status_dict=status_dict)

        # Exercise
        juju_unit_status = charm.build_juju_unit_status(pod_status)

        # Assertions
        assert type(juju_unit_status) == MaintenanceStatus
        assert juju_unit_status.message == "Pod is getting ready"

    def test_returns_active_status_if_pod_is_ready(self):
        # Setup
        status_dict = {
            'metadata': {
                'annotations': {
                    'juju.io/unit': uuid4()
                }
            },
            'status': {
                'phase': 'Running',
                'conditions': [{
                    'type': 'ContainersReady',
                    'status': 'True'
                }]
            }
        }
        pod_status = k8s.PodStatus(status_dict=status_dict)

        # Exercise
        juju_unit_status = charm.build_juju_unit_status(pod_status)

        # Assertions
        assert type(juju_unit_status) == ActiveStatus


class OnConfigChangedHandlerTest(unittest.TestCase):

    @patch('charm.wait_for_pod_readiness', spec_set=True, autospec=True)
    @patch('charm.ensure_config_is_reloaded', spec_set=True, autospec=True)
    def test__it_pod_is_ready_and_config_is_updated(
        self,
        mock_ensure_config_is_reloaded,
        mock_wait_for_pod_readiness_func
    ):
        # Setup
        mock_fw_adapter_cls = \
            create_autospec(framework.FrameworkAdapter, spec_set=True)
        mock_fw = mock_fw_adapter_cls.return_value

        mock_event_cls = create_autospec(EventBase)
        mock_event = mock_event_cls.return_value

        mock_state_cls = \
            create_autospec(charm.StoredState, spec_set=True)
        mock_state = mock_state_cls.return_value

        # Exercise
        charm.on_config_changed_handler(mock_event, mock_fw, mock_state)

        # Assert
        assert mock_wait_for_pod_readiness_func.call_count == 1

        assert mock_ensure_config_is_reloaded.call_count == 1


class WaitForPodReadinessTest(unittest.TestCase):

    # We are mocking the time module here so that we don't actually wait
    # 1 second per loop during test exectution.
    @patch('charm.build_juju_unit_status', spec_set=True, autospec=True)
    @patch('charm.k8s', spec_set=True, autospec=True)
    @patch('charm.time', spec_set=True, autospec=True)
    @patch('charm.set_juju_pod_spec', spec_set=True, autospec=True)
    def test__it_blocks_until_pod_is_ready(
            self,
            mock_pod_spec,
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

        # Exercise
        charm.wait_for_pod_readiness(mock_fw_adapter)

        # Assert
        assert mock_fw_adapter.set_unit_status.call_count == \
            len(mock_juju_unit_states)
        assert mock_fw_adapter.set_unit_status.call_args_list == [
            call(status) for status in mock_juju_unit_states
        ]


class OnNewAlertManagerRelationHandler(unittest.TestCase):

    @patch('charm.build_juju_pod_spec', spec_set=True, autospec=True)
    def test__it_updates_the_juju_pod_spec_with_alerting_config(
            self,
            mock_build_juju_pod_spec_func):
        # Setup
        mock_fw_adapter_cls = \
            create_autospec(framework.FrameworkAdapter,
                            spec_set=True)
        mock_fw = mock_fw_adapter_cls.return_value
        mock_fw.unit_is_leader.return_value = True

        mock_event_cls = create_autospec(EventBase)
        mock_event = mock_event_cls.return_value
        mock_data = {str(uuid4()): str(uuid4())}
        mock_event.data = dict(alerting_config=json.dumps(mock_data))

        mock_prom_juju_pod_spec = create_autospec(domain.PrometheusJujuPodSpec)
        mock_build_juju_pod_spec_func.return_value = mock_prom_juju_pod_spec

        # Exercise
        charm.on_new_alertmanager_relation_handler(mock_event, mock_fw)

        # Assert
        assert mock_build_juju_pod_spec_func.call_count == 1
        assert mock_build_juju_pod_spec_func.call_args == \
            call(app_name=mock_fw.get_app_name.return_value,
                 charm_config=mock_fw.get_config.return_value,
                 image_meta=mock_fw.get_image_meta.return_value,
                 alerting_config=mock_data)

        assert mock_fw.set_pod_spec.call_count == 1
        assert mock_fw.set_pod_spec.call_args == \
            call(mock_prom_juju_pod_spec.to_dict())

        assert mock_fw.set_unit_status.call_count == 1
        args, kwargs = mock_fw.set_unit_status.call_args_list[0]
        assert type(args[0]) == MaintenanceStatus


class OnStartHandlerTest(unittest.TestCase):

    @patch('charm.build_juju_pod_spec', spec_set=True, autospec=True)
    def test__it_updates_the_juju_pod_spec(self,
                                           mock_build_juju_pod_spec_func):
        # Setup
        mock_fw_adapter_cls = \
            create_autospec(framework.FrameworkAdapter,
                            spec_set=True)
        mock_fw = mock_fw_adapter_cls.return_value
        mock_fw.unit_is_leader.return_value = True

        mock_event_cls = create_autospec(EventBase, spec_set=True)
        mock_event = mock_event_cls.return_value

        mock_prom_juju_pod_spec = create_autospec(domain.PrometheusJujuPodSpec)
        mock_build_juju_pod_spec_func.return_value = mock_prom_juju_pod_spec

        mock_state = create_autospec(charm.StoredState).return_value

        # Exercise
        charm.on_start_handler(mock_event, mock_fw, mock_state)

        # Assert
        assert mock_state.recently_started
        assert mock_state.config_propagated

        assert mock_build_juju_pod_spec_func.call_count == 1
        assert mock_build_juju_pod_spec_func.call_args == \
            call(app_name=mock_fw.get_app_name.return_value,
                 charm_config=mock_fw.get_config.return_value,
                 image_meta=mock_fw.get_image_meta.return_value,
                 alerting_config={})

        assert mock_fw.set_pod_spec.call_count == 1
        assert mock_fw.set_pod_spec.call_args == \
            call(mock_prom_juju_pod_spec.to_dict())

        assert mock_fw.set_unit_status.call_count == 1
        args, kwargs = mock_fw.set_unit_status.call_args_list[0]
        assert type(args[0]) == MaintenanceStatus
