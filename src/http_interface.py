import sys
sys.path.append('lib')

from ops.framework import (
    EventBase,
    EventSource,
    EventsBase,
    Object,
)


#
# EVENTS
#

class NewHTTPClientEvent(EventBase):

    def __init__(self, handle, client):
        super().__init__(handle)
        self._client = client

    def client(self):
        return self._client


class HTTPServerAvailableEvent(EventBase):
    pass


class HTTPServerEvents(EventsBase):
    new_client = EventSource(NewHTTPClientEvent)
    server_available = EventSource(HTTPServerAvailableEvent)


#
# INTERFACES
#

class HTTPClientInterface:

    def set_http_server(self, host, port):
        self._server_host = host
        self._server_port = port

    @property
    def server_host(self):
        return self._server_host

    @property
    def server_port(self):
        return self._server_port


class HTTPServerInterface(Object):
    on = HTTPServerEvents()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)

    def on_joined(self, event):
        self.on.new_client.emit(HTTPClientInterface())
