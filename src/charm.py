#!/usr/bin/env python3

import sys
sys.path.append('lib')

from ops.charm import CharmBase
from ops.main import main

import handlers


class Charm(CharmBase):

    def __init__(self, *args):
        super().__init__(*args)

        for event in (self.on.start,
                      self.on.upgrade_charm,
                      self.on.config_changed):
            self.framework.observe(event, self.on_spec_changed)

    def on_spec_changed(self, event):
        output = handlers.generate_spec(event)
        self.framework.model.unit.status = output.unit_status
        if output.spec:
            self.framework.model.set_spec(output.spec)


if __name__ == "__main__":
    main(Charm)
