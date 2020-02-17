#!/usr/bin/env python3

import sys
sys.path.append('lib')

from ops.charm import (
    CharmBase,
)
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
)

from adapters import FrameworkAdapter
from resources import (
    PrometheusImageResource,
)
import handlers


class Charm(CharmBase):

    # Initialize the object's stored state
    state = StoredState()

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

        self.prometheus_image = PrometheusImageResource(
            resources_repo=self.adapter.get_resources_repo()
        )

        self.state.set_default(spec_is_set=False)

    def on_config_changed_delegator(self, event):
        unit_status = None

        while not isinstance(unit_status, ActiveStatus):
            output = handlers.on_config_changed(
                event=event,
                app_name=self.adapter.get_app_name()
            )

            unit_status = output.unit_status
            self.adapter.set_unit_status(unit_status)

    def on_start_delegator(self, event):
        output = handlers.on_start(
            event=event,
            app_name=self.adapter.get_app_name(),
            config=self.adapter.get_config(),
            image_resource=self.prometheus_image,
            spec_is_set=self.state.spec_is_set
        )

        if output.spec:
            self.adapter.set_pod_spec(output.spec)
            self.state.spec_is_set = True

        self.adapter.set_unit_status(output.unit_status)

    def on_upgrade_delegator(self, event):
        self.state.spec_is_set = False
        self.on_start_delegator(event)


if __name__ == "__main__":
    main(Charm)
