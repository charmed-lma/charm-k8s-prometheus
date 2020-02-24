import sys
sys.path.append('lib')

from ops.framework import (
    EventBase,
    EventSource,
    EventsBase,
    Object,
)


#
# Server
#

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

#
# Client
#

class ServerAvailableEvent(EventBase):
    pass


class ClientEvents(EventsBase):
    server_available = EventSource(ServerAvailableEvent)


class Client(Object):
    on = ClientEvents()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)

        self._relation_name = relation_name

        self.framework.observe(charm.on[relation_name].relation_changed,
                               self.on_relation_changed)

    @property
    def relation_name(self):
        return self._relation_name

    def on_relation_changed(self, event):
        pass
