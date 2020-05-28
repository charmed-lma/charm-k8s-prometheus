import json
import logging

logger = logging.getLogger()

from ops.framework import (
    EventSource,
    Object,
    ObjectEvents,
)
from ops.framework import EventBase
from adapters.framework import FrameworkAdapter


class NewAlertManagerRelationEvent(EventBase):

    def __init__(self, handle, remote_data):
        super().__init__(handle)
        self.data = dict(remote_data)

    # The Operator Framework will serialize and deserialize this event object
    # as it passes it to the charm. The following snapshot and restore methos
    # ensure that our underlying data don't get lost along the way.

    def snapshot(self):
        return json.dumps(self.data)

    def restore(self, snapshot):
        self.data = json.loads(snapshot)


class AlertManagerEvents(ObjectEvents):
    new_relation = EventSource(NewAlertManagerRelationEvent)


class AlertManagerInterface(Object):
    on = AlertManagerEvents()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)

        self.fw_adapter = FrameworkAdapter(self.framework)
        self.relation_name = relation_name

        self.fw_adapter.observe(charm.on[relation_name].relation_changed,
                                self.on_relation_changed)

    def on_relation_changed(self, event):
        remote_data = event.relation.data[event.unit]
        logging.debug(
            "Received remote_data: {}".format(dict(remote_data))
        )

        logger.debug("Emitting new_relation event")
        self.on.new_relation.emit(remote_data)
