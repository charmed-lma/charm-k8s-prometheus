from pathlib import Path
import sys
import unittest
from unittest.mock import (
    call,
    MagicMock
)
from uuid import uuid4

sys.path.append('lib')
from ops.model import (
    Resources
)

sys.path.append('src')
from resources import (
    OCIImageResource
)


class OCIImageResourceTest(unittest.TestCase):

    def test_fetch_image_info_succesfully(self):
        # Setup
        mock_resource_name = f"{uuid4()}"

        mock_image_path = f"{uuid4()}/{uuid4()}"
        mock_image_username = f"{uuid4()}"
        mock_image_password = f"{uuid4()}"

        mock_path_obj = MagicMock(Path)
        mock_path_obj.exists.return_value = True
        mock_path_obj.read_text.return_value = f"""
        registrypath: {mock_image_path}
        username: {mock_image_username}
        password: {mock_image_password}
        """

        mock_resources_adapter = MagicMock(Resources)
        mock_resources_adapter.fetch.return_value = mock_path_obj

        # Exercise
        image_resource = OCIImageResource(resource_name=mock_resource_name)
        result = image_resource.fetch(mock_resources_adapter)

        # Assert
        assert mock_resources_adapter.fetch.call_count == 1
        assert mock_resources_adapter.fetch.call_args == \
            call(mock_resource_name)
        assert result
        assert image_resource.image_path == mock_image_path
        assert image_resource.username == mock_image_username
        assert image_resource.password == mock_image_password
