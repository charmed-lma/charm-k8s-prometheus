import json
import yaml

import sys
sys.path.append('lib')

from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
)


# DOMAIN SERVICES

# More stateless functions. This group is purely business logic that take
# simple values or data structures and produce new values from them.

def build_juju_pod_spec(app_name,
                        charm_config,
                        image_meta,
                        prometheus_server_details=None):
    external_labels = json.loads(charm_config['external-labels'])
    advertised_port = charm_config['advertised-port']

    spec = {
        'containers': [{
            'name': app_name,
            'imageDetails': {
                'imagePath': image_meta.image_path,
                'username': image_meta.username,
                'password': image_meta.password
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

    return spec


def build_juju_unit_status(pod_status):
    if pod_status.is_unknown:
        unit_status = MaintenanceStatus("Waiting for pod to appear")
    elif not pod_status.is_running:
        unit_status = MaintenanceStatus("Pod is starting")
    elif pod_status.is_running and not pod_status.is_ready:
        unit_status = MaintenanceStatus("Pod is getting ready")
    elif pod_status.is_running and pod_status.is_ready:
        unit_status = ActiveStatus()

    return unit_status
