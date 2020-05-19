import copy
import json
import yaml

import sys
sys.path.append('lib')

from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
)


# DOMAIN MODELS

class PrometheusJujuPodSpec:

    def __init__(self,
                 app_name,
                 image_path,
                 repo_username,
                 repo_password,
                 advertised_port,
                 prometheus_config):

        self._prometheus_config = prometheus_config
        self._spec = {
            'containers': [{
                'name': app_name,
                'imageDetails': {
                    'imagePath': image_path,
                    'username': repo_username,
                    'password': repo_password
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
                        'prometheus.yml': ''
                    }
                }]
            }]
        }

    def to_dict(self):
        final_dict = copy.deepcopy(self._spec)
        final_dict['containers'][0]['files'][0]['files']['prometheus.yml'] = \
            self._prometheus_config.yaml_dump()
        return final_dict


class PrometheusConfigFile:
    '''
    https://prometheus.io/docs/prometheus/latest/configuration/configuration
    '''

    def __init__(self, global_opts):
        self._config_dict = {
            'global': global_opts,
            'scrape_configs': [],
        }

    def add_scrape_config(self, scrape_config):
        '''
        https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config
        '''
        self._config_dict['scrape_configs'].append(scrape_config)

    def yaml_dump(self):
        return yaml.dump(self._config_dict)


# DOMAIN SERVICES

# More stateless functions. This group is purely business logic that take
# simple values or data structures and produce new values from them.

def build_juju_pod_spec(app_name,
                        charm_config,
                        image_meta,
                        prometheus_server_details=None):

    external_labels = json.loads(charm_config['external-labels'])
    advertised_port = charm_config['advertised-port']

    # This is the first pass at enabling the addition of more metrics to
    # prometheus. For now these other metrics are hard coded but future
    # commits will allow for operations teams to add arbitrary metrics.

    prometheus_config = PrometheusConfigFile(
        global_opts={
            'scrape_interval': '15s',
            'external_labels': external_labels
        }
    )
    prometheus_config.add_scrape_config({
        'job_name': 'prometheus',
        'scrape_interval': '5s',
        'static_configs': [{
            'targets': [
                f'localhost:{advertised_port}'
            ]
        }]
    })
    prometheus_config.add_scrape_config({
        'job_name': 'kube-metrics-server',
        'scrape_interval': '5s',
        'metrics_path': '/metrics',
        'tls_config': {
            'insecure_skip_verify': True
        },
        'scheme': 'https',
        'static_configs': [{
            'targets': [
                'metrics-server.kube-system.svc:443'
            ]
        }]
    })

    spec = PrometheusJujuPodSpec(
        app_name=app_name,
        image_path=image_meta.image_path,
        repo_username=image_meta.repo_username,
        repo_password=image_meta.repo_password,
        advertised_port=advertised_port,
        prometheus_config=prometheus_config)

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
