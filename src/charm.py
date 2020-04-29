#!/usr/bin/env python3
import sys
sys.path.append('lib')

from ops.charm import (
    CharmBase,
)
from ops.main import main

from adapters import FrameworkAdapter
import handlers
import image_registry
from image_registry import (
    ResourceError
)
import k8s


class Charm(CharmBase):

    def __init__(self, *args):
        super().__init__(*args)

        # Abstract out framework and friends so that this object is not
        # too tightly coupled with the underlying framework's implementation.
        # From this point forward, our Charm object will only interact with the
        # adapter and not directly with the framework.
        self.adapter = FrameworkAdapter(self.framework)

        # Bind event handlers to events
        event_handler_bindings = {
            self.on.start: self.on_start_delegator,
            self.on.config_changed: self.on_config_changed_delegator,
            self.on.upgrade_charm: self.on_upgrade_delegator,
        }
        for event, handler in event_handler_bindings.items():
            self.adapter.observe(event, handler)

    def on_start_delegator(self, event):
        try:
            image_meta = image_registry.fetch_meta(
                image_name='prometheus-image',
                resources_repo=self.adapter.get_resources_repo()
            )
        except ResourceError as err:
            self.adapter.set_unit_status(err.status)
            return

        output = handlers.on_start(
            app_name=self.adapter.get_app_name(),
            config=self.adapter.get_config(),
            image_meta=image_meta
        )

        self.adapter.set_pod_spec(output.spec)
        self.adapter.set_unit_status(output.unit_status)

    def on_config_changed_delegator(self, event):
        juju_model = self.adapter.get_model_name()
        juju_app = self.adapter.get_app_name()
        juju_unit = self.adapter.get_unit_name()

        output = None

        while not (output and output.pod_is_ready):
            pod_status = k8s.get_pod_status(juju_model=juju_model,
                                            juju_app=juju_app,
                                            juju_unit=juju_unit)
            output = handlers.on_config_changed(pod_status=pod_status)
            self.adapter.set_unit_status(output.unit_status)

    def on_upgrade_delegator(self, event):
        self.on_start_delegator(event)


if __name__ == "__main__":
    main(Charm)
