from types import SimpleNamespace

import sys
sys.path.append('lib')

from ops.model import (
    MaintenanceStatus,
)


def start(event):
    output = {
        'unit_status': MaintenanceStatus("Great Success!")
    }
    return SimpleNamespace(**output)
