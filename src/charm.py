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
    BlockedStatus,
)
from ops.framework import StoredState
from adapters.framework import FrameworkAdapter
from domain import (
    build_juju_pod_spec,
    reload_configuration,
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
                self.on_new_alertmanager_relation,
        }
        for event, handler in event_handler_bindings.items():
            self.fw_adapter.observe(event, handler)

        self._stored.set_default(
            recently_started=True,
            config_propagated=True
        )

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
        on_start_handler(event, self.fw_adapter, self._stored)

    def on_upgrade(self, event):
        on_upgrade_handler(event, self.fw_adapter, self._stored)

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

    wait_for_pod_readiness(fw_adapter)
    ensure_config_is_reloaded(event, fw_adapter, state)


def on_new_alertmanager_relation_handler(event, fw_adapter):
    alerting_config = json.loads(event.data.get('alerting_config', '{}'))
    set_juju_pod_spec(fw_adapter, alerting_config)


def on_start_handler(event, fw_adapter, state):
    set_juju_pod_spec(fw_adapter)
    state.recently_started = True
    state.config_propagated = True


def on_upgrade_handler(event, fw_adapter, state):
    on_start_handler(event, fw_adapter, state)


def on_stop_handler(event, fw_adapter):
    fw_adapter.set_unit_status(MaintenanceStatus("Pod is terminating"))


# OTHER FRAMEWORK-SPECIFIC LOGIC

def build_juju_unit_status(pod_status):
    if pod_status.is_unknown:
        unit_status = MaintenanceStatus("Waiting for pod to appear")
    elif not pod_status.is_running:
        unit_status = MaintenanceStatus("Pod is starting")
    elif pod_status.is_running and not pod_status.is_ready:
        unit_status = MaintenanceStatus("Pod is getting ready")
    elif pod_status.is_running and pod_status.is_ready:
        unit_status = ActiveStatus()
    else:
        # Covering a "variable referenced before assignment" linter error
        unit_status = BlockedStatus(
            "Error: Unexpected pod_status received: {0}".format(
                pod_status.raw_status
            )
        )

    return unit_status


def ensure_config_is_reloaded(event, fw_adapter, state):
    juju_model = fw_adapter.get_model_name()
    juju_app = fw_adapter.get_app_name()

    # Prometheus has recently started so its config file and the underlying
    # CofigMap are synchronized so there's no need to reload.
    if state.recently_started:
        state.recently_started = False
        return

    config_was_changed_post_startup = \
        not state.recently_started and state.config_propagated
    config_needs_reloading = \
        not state.recently_started and not state.config_propagated

    if config_was_changed_post_startup:
        # We assume that the new config hasn't propagated all the way up
        # to the Prometheus container.
        state.config_propagated = False

        fw_adapter.set_unit_status(MaintenanceStatus(
            "Waiting for new config to propagate to unit"
        ))
        logger.debug("Config not yet propagated. Deferring.")
        # The rest of this event handler is deferred so that Juju can continue
        # with the config-change cycle, apply the new config to the ConfigMap
        # and allow kubernetes to propogate that the the mounted volume in
        # the Prometheus pod.
        event.defer()
        return

    if config_needs_reloading:
        state.config_propagated = reload_configuration(
            juju_model, juju_app, fw_adapter.get_config()
        )
        if state.config_propagated:
            fw_adapter.set_unit_status(ActiveStatus())
        return


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

    pod_spec = juju_pod_spec.to_dict()
    logging.debug("Configuring pod: set PodSpec to: {0}".format(pod_spec))
    fw_adapter.set_pod_spec(pod_spec)
    fw_adapter.set_unit_status(MaintenanceStatus("Configuring pod"))


def wait_for_pod_readiness(fw_adapter):
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


if __name__ == "__main__":
    main(Charm)
