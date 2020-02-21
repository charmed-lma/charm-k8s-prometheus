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
    HTTPClientInterface,
    HTTPServerInterface,
    NewHTTPClientEvent,
)


class HTTPClientInterfaceTest(unittest.TestCase):

    def test__set_http_server__saves_the_host_and_port_data(self):
        # Set up
        mock_port = random.randint(1, 65535)
        mock_host = f'{uuid4()}'

        # Exercise
        http_client_interface = HTTPClientInterface()
        http_client_interface.set_http_server(host=mock_host, port=mock_port)

        # Assertions
        assert http_client_interface.server_host == mock_host
        assert http_client_interface.server_port == mock_port


class HTTPServerInterfaceTest(unittest.TestCase):

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

    @patch('http_interface.HTTPServerEvents', autospec=True, spec_set=True)
    @patch('http_interface.HTTPClientInterface', autospec=True, spec_set=True)
    def test__on_joined__emits_the_new_client_event(
            self,
            mock_http_client_interface_cls,
            mock_http_server_events_cls):
        # Set up
        mock_charm = CharmBase(self.create_framework(), None)
        mock_name = f'{uuid4()}'
        mock_event = create_autospec(NewHTTPClientEvent, spec_set=True)
        mock_http_server_events = mock_http_server_events_cls.return_value
        mock_http_server_events.new_client = \
            create_autospec(BoundEvent, spec_set=True).return_value

        # Exercise
        http_server_interface = HTTPServerInterface(mock_charm, mock_name)
        http_server_interface.on_joined(mock_event)

        # Assertions
        assert mock_http_server_events.new_client.emit.call_count == 1
        assert mock_http_server_events.new_client.emit.call_args == \
            call(mock_http_client_interface_cls.return_value)

        assert mock_http_client_interface_cls.call_count == 1
        assert mock_http_client_interface_cls.call_args == call()
