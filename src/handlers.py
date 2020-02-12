from types import SimpleNamespace
import yaml

import sys
sys.path.append('lib')

from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
)


def generate_spec(event,
                  app_name,
                  advertised_port,
                  image_resource,
                  spec_is_set,
                  external_labels={}):
    """Generates the k8s spec needed to deploy Prometheus on k8s

    :param: :class:`ops.framework.EventBase` event: The event that triggered
        the calling handler.

    :param str app_name: The name of the application.

    :param int advertised_port: The port inside the container that prometheus
        should bind to.

    :param OCIImageResource image_resource: Image metadata object containing
        the registry path, username, and password. May be set to None if no
        image metadata is available.

    :param bool spec_is_set: Indicates whether the spec has been previously
        set by Juju or not.

    :param dict external_labels: The labels to attach to metrics in this
        Prometheus instance before they get pulled by an aggregating parent.
        This is useful in the case of federation where you want each datacenter
        to have its own Prometheus instance and then have a global instance
        that pull from each of these "children" instances. By specifying a
        unique set of external_labels for each child instance, you can easily
        determine in the aggregating Prometheus instance which datacenter a
        metric is coming from.


    :returns: An object containing the spec dict and other attributes.

    :rtype: :class:`handlers.SpecGenerationOutput`

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
