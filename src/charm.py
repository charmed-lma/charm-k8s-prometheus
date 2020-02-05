#!/usr/bin/env python3.6

import sys
sys.path.append('lib')

from ops.charm import CharmBase
from ops.main import main

import handlers


class DemoCharm(CharmBase):

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.start, self)

    def on_start(self, event):
        output = handlers.start(event)
        self.framework.model.unit.status = output.unit_status


if __name__ == "__main__":
    main(DemoCharm)
