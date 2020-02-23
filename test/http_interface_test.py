from pathlib import Path
import shutil
import random
import sys
import tempfile
import unittest
from unittest.mock import (
    call,
    create_autospec,
    patch,
)
from uuid import uuid4

sys.path.append('lib')
from ops.charm import (
    CharmBase,
    CharmMeta,
)
from ops.framework import (
    BoundEvent,
    Framework,
)

sys.path.append('src')
from http_interface import (
    Client,
    Server,
    NewClientEvent,
)


class ClientTest(unittest.TestCase):

    def test__set_server_address__saves_the_host_and_port_info(self):
        # Set up
        mock_port = random.randint(1, 65535)
        mock_host = f'{uuid4()}'

        # Exercise
        client = Client()
        client.set_server_address(host=mock_host, port=mock_port)

        # Assertions
        assert client.server_host == mock_host
        assert client.server_port == mock_port


class ServerTest(unittest.TestCase):

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

    @patch('http_interface.ServerEvents', autospec=True, spec_set=True)
    @patch('http_interface.Client', autospec=True, spec_set=True)
    def test__on_joined__emits_the_new_client_event(
            self,
            mock_client_cls,
            mock_server_events_cls):
        # Set up
        mock_charm = CharmBase(self.create_framework(), None)
        mock_name = f'{uuid4()}'
        mock_event = create_autospec(NewClientEvent, spec_set=True)

        # Because of the way `Server.on` is defined (i.e. it's defined when
        # the class is loaded), we cannot use @patch to mock it because it
        # would be too late by then (since we load a class when we import).
        # Thus we mock `Server.on` after the object has been created as
        # a workaround. Note how we still use `create_autospec` and `spec_set`
        # to ensure that our mock stays in-sync with the actual object.
        server = Server(mock_charm, mock_name)
        mock_server_events = create_autospec(server.on, spec_set=True)
        mock_server_events.new_client = \
            create_autospec(BoundEvent, spec_set=True).return_value
        server.on = mock_server_events

        # Exercise
        server.on_joined(mock_event)

        # Assertions
        assert mock_server_events.new_client.emit.call_count == 1
        assert mock_server_events.new_client.emit.call_args == \
            call(mock_client_cls.return_value)

        assert mock_client_cls.call_count == 1
        assert mock_client_cls.call_args == call()
