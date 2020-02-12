#!/usr/bin/env python3

import sys
sys.path.append('lib')

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main

from adapters import FrameworkAdapter
from resources import PrometheusImageResource
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
            self.on.start: self.set_spec,
            self.on.upgrade_charm: self.set_spec,
            self.on.config_changed: self.set_spec
        }
        for event, handler in event_handler_bindings.items():
            self.adapter.observe(event, handler)

        self.prometheus_image = PrometheusImageResource()

        self.state.set_default(spec_is_set=False)

    def set_spec(self, event):

        resources = self.adapter.get_resources_repo()
        self.prometheus_image.fetch(resources)

        output = handlers.generate_spec(
            event=event,
            app_name=self.adapter.get_app_name(),
            advertised_port=self.adapter.get_config('advertised_port'),
            image_resource=self.prometheus_image,
            spec_is_set=self.state.spec_is_set
        )
        self.adapter.set_unit_status(output.unit_status)

        if output.spec:
            self.adapter.set_pod_spec(output.spec)
            self.state.spec_is_set = True


if __name__ == "__main__":
    main(Charm)
