import sys
import unittest
from unittest.mock import (
    create_autospec,
)

sys.path.append('lib')
from ops.model import (
    Resources
)

sys.path.append('src')
from resources import (
    PrometheusImageResource,
)


class PrometheusImageResourceTest(unittest.TestCase):

    def test__init(self):
        # Setup
        mock_resources_repo = create_autospec(Resources, set_spec=True)

        # Exercise
        PrometheusImageResource(resources_repo=mock_resources_repo)
