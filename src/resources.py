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
            raise MissingResourceError(self.resource_name)

        resource_yaml = path.read_text()

        if not resource_yaml:
            raise MissingResourceError(self.resource_name)

        try:
            resource_dict = yaml.safe_load(resource_yaml)
        except yaml.YAMLError as e:
            raise InvalidResourceError(self.resource_name) from e
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
    status_type = BlockedStatus
    status_message = 'Resource error'

    def __init__(self, resource_name):
        super().__init__(resource_name)
        self.status = \
            self.status_type(f'{self.status_message}: {resource_name}')


class MissingResourceError(ModelError):
    status_message = 'Missing resource'


class InvalidResourceError(ModelError):
    status_message = 'Invalid resource'
