#!/usr/bin/env python3
import json
import logging

logger = logging.getLogger()
import sys
import time

sys.path.append('lib')

from ops.charm import (
    CharmBase,
)
from ops.main import main
from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
    BlockedStatus
)
from ops.framework import StoredState
from adapters.framework import FrameworkAdapter
from domain import (
    build_juju_pod_spec,
    build_juju_unit_status,
)
from adapters import k8s
from exceptions import CharmError
from interface_alertmanager import AlertManagerInterface
from interface_http import PrometheusInterface


# CHARM

# This charm class mainly does self-configuration via its initializer and
# contains not much logic. It also just has one-liner delegators the design
# of which is further discussed below (just before the delegator definitions)


class Charm(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        # Abstract out framework and friends so that this object is not
        # too tightly coupled with the underlying framework's implementation.
        # From this point forward, our Charm object will only interact with the
        # adapter and not directly with the framework.
        self.fw_adapter = FrameworkAdapter(self.framework)
        self.prometheus = PrometheusInterface(self, 'http-api')
        self.alertmanager = AlertManagerInterface(self, 'alertmanager')
        # Bind event handlers to events
        event_handler_bindings = {
            self.on.start: self.on_start,
            self.on.config_changed: self.on_config_changed,
            self.on.upgrade_charm: self.on_upgrade,
            self.on.stop: self.on_stop,
            self.alertmanager.on.new_relation:
                self.on_new_alertmanager_relation
        }
        for event, handler in event_handler_bindings.items():
            self.fw_adapter.observe(event, handler)

        self._stored.set_default(is_started=False)

    # DELEGATORS

    # These delegators exist to decouple the actual handlers from the
    # underlying framework which has some very specific requirements that
    # do not always apply to every event. For instance if we were to add
    # an interface in our initializer, we would be forced to write unit
    # tests that mock out that object even for handlers that do not need
    # it. This hard coupling results in verbose tests that contain unused
    # mocks. These tests tend to be hard to follow. To counter that, the
    # logic is moved away from this class.

    def on_config_changed(self, event):
        on_config_changed_handler(event, self.fw_adapter, self._stored)

    def on_new_alertmanager_relation(self, event):
        on_new_alertmanager_relation_handler(event, self.fw_adapter)

    def on_start(self, event):
        on_start_handler(event, self.fw_adapter)

    def on_upgrade(self, event):
        on_upgrade_handler(event, self.fw_adapter)

    def on_stop(self, event):
        on_stop_handler(event, self.fw_adapter)


# EVENT HANDLERS
# These event handlers are designed to be stateless and, as much as possible,
# procedural (run from top to bottom). They are stateless since any stored
# states are already handled by the Charm object anyway and also because this
# simplifies testing of said handlers. They are also procedural since they are
# similar to controllers in an MVC app in that they are only concerned with
# coordinating domain models and services.

def on_config_changed_handler(event, fw_adapter, state):
    set_juju_pod_spec(fw_adapter)
    juju_model = fw_adapter.get_model_name()
    juju_app = fw_adapter.get_app_name()
    juju_unit = fw_adapter.get_unit_name()

    pod_is_ready = False

    # TODO: Fail by timeout, if pod will never go to the Ready state?
    while not pod_is_ready:
        logging.debug("Checking k8s pod readiness")
        k8s_pod_status = k8s.get_pod_status(juju_model=juju_model,
                                            juju_app=juju_app,
                                            juju_unit=juju_unit)
        logging.debug("Received k8s pod status: {0}".format(k8s_pod_status))
        juju_unit_status = build_juju_unit_status(k8s_pod_status)
        logging.debug("Built unit status: {0}".format(juju_unit_status))
        fw_adapter.set_unit_status(juju_unit_status)
        pod_is_ready = isinstance(juju_unit_status, ActiveStatus)
        time.sleep(1)


def on_new_alertmanager_relation_handler(event, fw_adapter):
    alerting_config = json.loads(event.data.get('alerting_config', '{}'))
    set_juju_pod_spec(fw_adapter, alerting_config)


def on_start_handler(event, fw_adapter):
    set_juju_pod_spec(fw_adapter)


def on_upgrade_handler(event, fw_adapter):
    on_start_handler(event, fw_adapter)


def on_stop_handler(event, fw_adapter):
    fw_adapter.set_unit_status(MaintenanceStatus("Pod is terminating"))


def set_juju_pod_spec(fw_adapter, alerting_config=None):
    # Mutable defaults bug as described in https://bit.ly/3cF0k0w
    if not alerting_config:
        alerting_config = dict()

    if not fw_adapter.unit_is_leader():
        logging.debug("Unit is not a leader, skip pod spec configuration")
        return

    if alerting_config:
        logger.debug(
            "Got alerting config: {} {}".format(type(alerting_config),
                                                alerting_config)
        )

    logging.debug("Building Juju pod spec")
    try:
        juju_pod_spec = build_juju_pod_spec(
            app_name=fw_adapter.get_app_name(),
            charm_config=fw_adapter.get_config(),
            image_meta=fw_adapter.get_image_meta('prometheus-image'),
            alerting_config=alerting_config
        )
    except CharmError as e:
        fw_adapter.set_unit_status(
            BlockedStatus("Pod spec build failure: {0}".format(e))
        )
        return

    logging.debug("Configuring pod")
    fw_adapter.set_pod_spec(juju_pod_spec.to_dict())
    fw_adapter.set_unit_status(MaintenanceStatus("Configuring pod"))


if __name__ == "__main__":
    main(Charm)
