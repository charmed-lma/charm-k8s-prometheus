import json
from types import SimpleNamespace
import yaml

import sys
sys.path.append('lib')

from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
)
from k8s import (
    ServiceSpec,
    PodStatus,
)
from resources import (
    ResourceError,
)


def _create_output_obj(dict_obj):
    return SimpleNamespace(**dict_obj)


def on_new_http_client(event, app_name):
    """Configures an `http_interface.ServerDetails` object designated by
    `server_details` with the hostname and port of the HTTP server's k8s
    Service object.

    :param: :class:`http_interface.ServerDetails` server_details: the object
        that will be configured by this handler with details about the server.
        It will eventually make its way to the actual client which will use the
        information to configure itself.

    :param str app_name: The name of the server application. This will be used
        by this handler to obtain the Service specs of the server.

    """
    # Fetch the k8s Service resource fronting the server pods
    service_spec = ServiceSpec(app_name)
    service_spec.fetch()

    # Use the information from the k8s Service resource to configure the
    # server_details
    # server_details.set_address(host=service_spec.host, port=service_spec.port)

    return SimpleNamespace(**dict(
        this="works",
        # server_details=server_details
    ))


def on_start(event,
             app_name,
             config,
             image_resource):
    """Generates the k8s spec needed to deploy Prometheus on k8s

    :param: :class:`ops.framework.EventBase` event: The event that triggered
        the calling handler.

    :param str app_name: The name of the application.

    :param dict config: Key-value pairs derived from config options declared
        in config.yaml

    :param OCIImageResource image_resource: Image resource object containing
        the registry path, username, and password.

    :returns: An object containing the spec dict and other attributes.

    :rtype: :class:`handlers.OnStartHandlerOutput`

    """
    try:
        image_resource.fetch()
    except ResourceError as err:
        output = dict(
            unit_status=err.status,
            spec=None
        )
        return _create_output_obj(output)

    external_labels = json.loads(config['external-labels'])
    advertised_port = config['advertised-port']

    output = dict(
        unit_status=MaintenanceStatus("Configuring pod"),
        spec={
            'containers': [{
                'name': app_name,
                'imageDetails': {
                    'imagePath': image_resource.image_path,
                    'username': image_resource.username,
                    'password': image_resource.password
                },
                'ports': [{
                    'containerPort': advertised_port,
                    'protocol': 'TCP'
                }],
                'readinessProbe': {
                    'httpGet': {
                        'path': '/-/ready',
                        'port': advertised_port
                    },
                    'initialDelaySeconds': 10,
                    'timeoutSeconds': 30
                },
                'livenessProbe': {
                    'httpGet': {
                        'path': '/-/healthy',
                        'port': advertised_port
                    },
                    'initialDelaySeconds': 30,
                    'timeoutSeconds': 30
                },
                'files': [{
                    'name': 'config',
                    'mountPath': '/etc/prometheus',
                    'files': {
                        'prometheus.yml': yaml.dump({
                            'global': {
                                'scrape_interval': '15s',
                                'external_labels': external_labels
                            },
                            'scrape_configs': [{
                                'job_name': 'prometheus',
                                'scrape_interval': '5s',
                                'static_configs': [{
                                    'targets': [
                                        f'localhost:{advertised_port}'
                                    ]
                                }]
                            }]
                        })
                    }
                }]
            }]
        }
    )

    return _create_output_obj(output)


def on_config_changed(event, app_name):

    pod_status = PodStatus(app_name=app_name)
    pod_status.fetch()

    pod_is_ready = False

    if pod_status.is_unknown:
        unit_status = MaintenanceStatus("Waiting for pod to appear")
    elif not pod_status.is_running:
        unit_status = MaintenanceStatus("Pod is starting")
    elif pod_status.is_running and not pod_status.is_ready:
        unit_status = MaintenanceStatus("Pod is getting ready")
    elif pod_status.is_running and pod_status.is_ready:
        unit_status = ActiveStatus()
        pod_is_ready = True

    return SimpleNamespace(**dict(
        unit_status=unit_status,
        pod_is_ready=pod_is_ready
    ))
