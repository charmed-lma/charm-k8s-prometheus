#!/usr/bin/env python3

import sys
sys.path.append('lib')

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main

from oci_image import OCIImageResource
import handlers


class Charm(CharmBase):
    state = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        for event in (self.on.start,
                      self.on.upgrade_charm,
                      self.on.config_changed):
            self.framework.observe(event, self.on_spec_changed)

        self.prometheus_image = OCIImageResource(self, 'prometheus_image')

        try:
            self.state.spec_is_set
        except AttributeError:
            self.state.spec_is_set = False

    def on_spec_changed(self, event):
        fw = self.framework

        output = handlers.generate_spec(
            app_name=fw.model.app.name,
            advertised_port=fw.model.config['advertised_port'],
            image_resource_fetched=self.prometheus_image.fetch(),
            image_resource=self.prometheus_image,
            spec_is_set=self.state.spec_is_set
        )
        fw.model.unit.status = output.unit_status

        if output.spec:
            fw.model.set_spec(output.spec)

        self.state.spec_is_set = (output.spec is not None)


if __name__ == "__main__":
    main(Charm)
