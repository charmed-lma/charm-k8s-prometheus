import json
import sys
from unittest.mock import (
    call,
    MagicMock,
    patch,
)
import unittest
from uuid import uuid4

sys.path.append('lib')
sys.path.append('src')
from interface_alertmanager import (
    AlertManagerInterface,
    NewAlertManagerRelationEvent,
)


class NewAlertManagerRelationEventTest(unittest.TestCase):

    @patch('interface_alertmanager.EventBase', spec_set=True)
    def test__it_snapshots_the_remote_data(self, mock_event_base_cls):
        # Setup
        mock_handle = MagicMock()
        mock_data = {
            str(uuid4()): str(uuid4()),
            str(uuid4()): str(uuid4()),
            str(uuid4()): str(uuid4()),
        }

        # Exercise
        new_relation_event = NewAlertManagerRelationEvent(mock_handle,
                                                          mock_data)
        snapshot = new_relation_event.snapshot()

        # Assert
        assert snapshot == json.dumps(mock_data)

    @patch('interface_alertmanager.EventBase', spec_set=True)
    def test__it_restores_the_data(self, mock_event_base_cls):
        # Setup
        mock_handle = MagicMock()
        mock_data = {
            str(uuid4()): str(uuid4()),
            str(uuid4()): str(uuid4()),
            str(uuid4()): str(uuid4()),
        }

        # Exercise
        snapshot = json.dumps(mock_data)
        new_relation_event = NewAlertManagerRelationEvent(mock_handle, {})
        new_relation_event.restore(snapshot)

        # Assert
        assert new_relation_event.data == mock_data


class AlertManagerInterfaceTest(unittest.TestCase):

    @patch('interface_alertmanager.FrameworkAdapter', spec_set=True)
    def test__it_observes_the_relation_changed_event(
            self,
            mock_fw_adapter_cls):
        # Setup
        mock_fw_adapter = mock_fw_adapter_cls.return_value
        mock_charm = MagicMock()

        mock_relation_name = str(uuid4())

        # Exercise
        alertmanager_interface = \
            AlertManagerInterface(mock_charm, mock_relation_name)

        # Assert
        assert mock_fw_adapter.observe.call_count == 1
        assert mock_fw_adapter.observe.call_args == \
            call(mock_charm.on[mock_relation_name].relation_changed,
                 alertmanager_interface.on_relation_changed)
