# Adapted from: https://github.com/johnsca/resource-oci-image/tree/e58342913
import yaml
from ops.framework import Object
from ops.model import BlockedStatus, ModelError


class OCIImageResource(Object):
    def __init__(self, resource_name):
        self.resource_name = resource_name

    def fetch(self, resources_adapter):
        path = resources_adapter.fetch(self.resource_name)
        if not path.exists():
            raise ResourceError(
                self.resource_name,
                f'Resource not found at {str(path)})')

        resource_yaml = path.read_text()

        if not resource_yaml:
            raise ResourceError(
                self.resource_name,
                f'Resource unreadable at {str(path)})')

        try:
            resource_dict = yaml.safe_load(resource_yaml)
        except yaml.error.YAMLError:
            raise ResourceError(
                self.resource_name,
                f'Invalid YAML at {str(path)})')
        else:
            self.resource_dict = resource_dict
            return True

    @property
    def image_path(self):
        return self.resource_dict['registrypath']

    @property
    def username(self):
        return self.resource_dict['username']

    @property
    def password(self):
        return self.resource_dict['password']


class ResourceError(ModelError):

    def __init__(self, resource_name, message):
        super().__init__(resource_name)
        self.status = BlockedStatus(f'{resource_name}: {message}')
