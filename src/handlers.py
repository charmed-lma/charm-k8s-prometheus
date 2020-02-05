from types import SimpleNamespace

import sys
sys.path.append('lib')

from ops.model import (
    MaintenanceStatus,
)


def generate_spec(app_name,
                  advertised_port,
                  image_resource_fetched,
                  image_resource,
                  spec_is_set):
    """Generates the k8s spec needed to deploy Prometheus on k8s

    :param str app_name: The name of the application.

    :param int advertised_port: The port inside the container that prometheus
        should bind to.

    :param bool image_resource_fetched: Indicates whether the image metadata
        been fetched or not.

    :param OCIImageResource image_resource: Image metadata object containing
        the registry path, username, and password.

    :param bool spec_is_set: Indicates whether the spec has been previously
        set by Juju or not.


    :returns: An object containing the spec dict and other attributes.

    :rtype: :class:`handlers.SpecGenerationOutput`

    """
    output = dict(
        unit_status=MaintenanceStatus("Configuring pod"),
        spec={
            'containers': [
                {
                    'name': app_name,
                    'imageDetails': {
                        'imagePath': image_resource.registry_path,
                        'username': image_resource.username,
                        'password': image_resource.password
                    },
                    'ports': [
                        {
                            'containerPort': advertised_port,
                            'protocol': 'TCP'
                        }
                    ]
                }
            ]
        }
    )
    return SimpleNamespace(**output)
