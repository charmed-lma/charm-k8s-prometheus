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


class PodStatus:

    def __init__(self, app_name):
        self._token_file = \
            "/var/run/secrets/kubernetes.io/serviceaccount/token"
        self._app_name = app_name
        self._status = None

    def fetch(self):
        with open(self._token_file) \
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
               f'labelSelector=juju-app={self._app_name}'

        conn = http.client.HTTPSConnection('kubernetes.default.svc',
                                           context=ssl_context)
        conn.request(method='GET', url=path, headers=headers)

        try:
            response = json.loads(conn.getresponse().read())
        except Exception:
            response = {}

        if response.get('kind', '') == 'PodList' and response['items']:
            unit = os.environ['JUJU_UNIT_NAME']
            status = next(
                (i for i in response['items']
                 if i['metadata']['annotations'].get('juju.io/unit') == unit),
                None
            )

        self._status = status

    @property
    def is_ready(self):
        if not self._status:
            return False

        return next(
            (
                condition['status'] == "True" for condition
                in self._status['status']['conditions']
                if condition['type'] == 'ContainersReady'
            ),
            False
        )

    @property
    def is_running(self):
        if not self._status:
            return False

        return self._status['status']['phase'] == 'Running'

    @property
    def is_unknown(self):
        return not self._status


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
