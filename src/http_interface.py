import sys
sys.path.append('lib')

from ops.framework import (
    EventBase,
    EventSource,
    EventsBase,
    Object,
)


class NewClientEvent(EventBase):

    def __init__(self, handle, client):
        super().__init__(handle)
        self._client = client

    def client(self):
        return self._client


class ServerAvailableEvent(EventBase):
    pass


class ServerEvents(EventsBase):
    new_client = EventSource(NewClientEvent)
    server_available = EventSource(ServerAvailableEvent)


class Server(Object):
    on = ServerEvents()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)

        self.framework.observe(charm.on[relation_name].relation_joined,
                               self.on_joined)

    def on_joined(self, event):
        self.on.new_client.emit(Client())


class Client:

    def set_server_address(self, host, port):
        self._server_host = host
        self._server_port = port

    @property
    def server_host(self):
        return self._server_host

    @property
    def server_port(self):
        return self._server_port
