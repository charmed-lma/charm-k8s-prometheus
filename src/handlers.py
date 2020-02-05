from types import SimpleNamespace

import sys
sys.path.append('lib')

from ops.model import (
    MaintenanceStatus,
)


def generate_spec(app_name,
                  http_port,
                  image_metadata_fetched,
                  image_metadata,
                  spec_is_set):
    """Generates the k8s spec needed to deploy Prometheus on k8s

    :param str app_name: The name of the application.

    :param int http_port: The port number inside the container that prometheus
        should bind to.

    :param bool image_metadata_fetched: Indicates whether the image metadata
        been fetched or not.

    :param OCIImageResource image_metadata: Image metadata object containing
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
                        'imagePath': image_metadata.registry_path,
                        'username': image_metadata.username,
                        'password': image_metadata.password
                    },
                    'ports': [
                        {
                            'containerPort': http_port,
                            'protocol': 'TCP'
                        }
                    ]
                }
            ]
        }
    )
    return SimpleNamespace(**output)
