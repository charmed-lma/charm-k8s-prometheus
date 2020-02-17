import json
import http.client
import os
import ssl
from types import SimpleNamespace
import yaml

import sys
sys.path.append('lib')

from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
)
from resources import (
    ResourceError,
)


def _create_output_obj(dict_obj):
    return SimpleNamespace(**dict_obj)


def on_config_changed(event, app_name):
    with open("/var/run/secrets/kubernetes.io/serviceaccount/token") \
            as token_file:
        kube_token = token_file.read()

    ssl_context = ssl.SSLContext()
    ssl_context.load_verify_locations(
        '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')

    headers = {
        'Authorization': f'Bearer {kube_token}'
    }

    namespace = os.environ["JUJU_MODEL_NAME"]

    path = f'/api/v1/namespaces/{namespace}/pods?' \
           f'labelSelector=juju-app={app_name}'

    conn = http.client.HTTPSConnection('kubernetes.default.svc',
                                       context=ssl_context)
    conn.request(method='GET', url=path, headers=headers)

    try:
        response = json.loads(conn.getresponse().read())
    except Exception:
        response = {}

    if response.get('kind', '') == 'PodList' and response['items']:
        unit = os.environ['JUJU_UNIT_NAME']
        unit_pod = next(
            (item for item in response['items']
             if item['metadata']['annotations'].get('juju.io/unit') == unit),
            None
        )

        if unit_pod:
            is_ready = next(
                (
                    condition['status'] == "True" for condition
                    in unit_pod['status']['conditions']
                    if condition['type'] == 'ContainersReady'
                ),
                False
            )
            is_running = unit_pod['status']['phase'] == 'Running'
            if is_running and is_ready:
                unit_status = ActiveStatus()
            elif is_running and not is_ready:
                unit_status = MaintenanceStatus("Pod is getting ready")
            else:
                unit_status = MaintenanceStatus("Pod is starting")
        else:
            unit_status = MaintenanceStatus("Waiting to get pod status")
    else:
        unit_status = MaintenanceStatus("Waiting to get list of pods")

    return SimpleNamespace(**dict(
        unit_status=unit_status
    ))


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
        return _create_output_obj(output)
    else:
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
