from types import SimpleNamespace
import yaml

import sys
sys.path.append('lib')

from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
)


def on_start(event,
             app_name,
             config,
             image_resource,
             spec_is_set):
    """Generates the k8s spec needed to deploy Prometheus on k8s

    :param: :class:`ops.framework.EventBase` event: The event that triggered
        the calling handler.

    :param str app_name: The name of the application.

    :param dict config: Key-value pairs derived from config options declared
        in config.yaml

    :param OCIImageResource image_resource: Image resource object containing
        the registry path, username, and password.

    :param bool spec_is_set: Indicates whether the spec has been previously
        set by Juju or not.

    :returns: An object containing the spec dict and other attributes.

    :rtype: :class:`handlers.OnStartHandlerOutput`

    """
    if spec_is_set:
        output = dict(
            unit_status=ActiveStatus(),
            spec=None
        )
    else:
        prometheus_yaml = yaml.dump({
            'global': {
                'scrape_interval': '15s',
                'external_labels': external_labels
            },
            'scrape_configs': [
                {
                    'job_name': 'prometheus',
                    'scrape_interval': '5s',
                    'static_configs': [
                        {
                            'targets': [
                                f'localhost:{advertised_port}'
                            ]
                        }
                    ]
                }
            ]
        })

        output = dict(
            unit_status=MaintenanceStatus("Configuring pod"),
            spec={
                'containers': [
                    {
                        'name': app_name,
                        'imageDetails': {
                            'imagePath': image_resource.image_path,
                            'username': image_resource.username,
                            'password': image_resource.password
                        },
                        'ports': [
                            {
                                'containerPort': advertised_port,
                                'protocol': 'TCP'
                            }
                        ],
                        'files': [
                            {
                                'name': 'config',
                                'mountPath': '/etc/prometheus',
                                'files': {
                                    'prometheus.yml': prometheus_yaml
                                }
                            }
                        ]
                    }
                ]
            }
        )
    return SimpleNamespace(**output)
