#!/usr/bin/env python3
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
)

from adapters.framework import FrameworkAdapter
from domain import (
    build_juju_pod_spec,
    build_juju_unit_status,
)
from adapters import k8s
from interface_http import PrometheusInterface


# CHARM

# This charm class mainly does self-configuration via its initializer and
# contains not much logic. It also just has one-liner delegators the design
# of which is further discussed below (just before the delegator definitions)


class Charm(CharmBase):

    def __init__(self, *args):
        super().__init__(*args)

        # Abstract out framework and friends so that this object is not
        # too tightly coupled with the underlying framework's implementation.
        # From this point forward, our Charm object will only interact with the
        # adapter and not directly with the framework.
        self.fw_adapter = FrameworkAdapter(self.framework)
        self.prometheus = PrometheusInterface(self, 'http-api')
        # Bind event handlers to events
        event_handler_bindings = {
            self.on.start: self.on_start,
            self.on.config_changed: self.on_config_changed,
            self.on.upgrade_charm: self.on_upgrade,
            self.on.stop: self.on_stop,
        }
        for event, handler in event_handler_bindings.items():
            self.fw_adapter.observe(event, handler)

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
        on_config_changed_handler(event, self.fw_adapter)

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

def on_config_changed_handler(event, fw_adapter):
    set_juju_pod_spec(fw_adapter)
    juju_model = fw_adapter.get_model_name()
    juju_app = fw_adapter.get_app_name()
    juju_unit = fw_adapter.get_unit_name()

    pod_is_ready = False

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


def on_start_handler(event, fw_adapter):
    set_juju_pod_spec(fw_adapter)


def on_upgrade_handler(event, fw_adapter):
    on_start_handler(event, fw_adapter)


def on_stop_handler(event, fw_adapter):
    fw_adapter.set_unit_status(MaintenanceStatus("Pod is terminating"))


def set_juju_pod_spec(fw_adapter):
    if not fw_adapter.am_i_leader():
        logging.debug("Unit is not a leader, skip pod spec configuration")
        return

    logging.debug("Building Juju pod spec")
    juju_pod_spec = build_juju_pod_spec(
        app_name=fw_adapter.get_app_name(),
        charm_config=fw_adapter.get_config(),
        image_meta=fw_adapter.get_image_meta('prometheus-image')
    )

    logging.debug("Configuring pod")
    fw_adapter.set_pod_spec(juju_pod_spec.to_dict())
    fw_adapter.set_unit_status(MaintenanceStatus("Configuring pod"))


if __name__ == "__main__":
    main(Charm)
