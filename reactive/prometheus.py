from charms.layer.caas_base import pod_spec_set
from charms.reactive import endpoint_from_flag
from charms.reactive import when, when_not
from charms.reactive.flags import set_flag, register_trigger, clear_flag
from charmhelpers.core.hookenv import (
    log,
    metadata,
    config,
)
from charms import layer
from charmhelpers.core.hookenv import is_leader


register_trigger(when='layer.docker-resource.prometheus-image.changed',
                 clear_flag='prometheus-k8s.configured')


@when('layer.docker-resource.prometheus-image.failed')
def waiting_for_prometheus_image():
    """Set status blocked

    Conditions:
        - prometheus-image.failed
    """
    layer.status.waiting('Unable to fetch prometheus-image')


@when('layer.docker-resource.alpine-image.failed')
def waiting_for_alpine_image():
    """Set status blocked

    Conditions:
        - alpine-image.failed
    """
    layer.status.waiting('Unable to fetch alpine-image')


@when('layer.docker-resource.prometheus-image.available')
@when('layer.docker-resource.alpine-image.available')
@when_not('prometheus-k8s.configured')
def configure():
    """Configure prometheus-k8s pod

    Conditions:
        - prometheus-image.available
        - Not prometheus-k8s.configured
    """
    layer.status.maintenance('Configuring prometheus container')
    try:
        spec = make_pod_spec()
        log('set pod spec:\n{}'.format(spec))
        pod_spec_set(spec)
        set_flag('prometheus-k8s.configured')
        layer.status.active('ready')

    except Exception as e:
        layer.status.blocked('k8s spec failed to deploy: {}'.format(e))


@when('prometheus-k8s.configured')
@when_not('prometheus-k8s.active')
def set_prometheus_active():
    """Set prometheus status active

    Conditions:
        - prometheus-k8s.configured
    """
    layer.status.active('ready')
    set_flag('prometheus-k8s.active')


@when('prometheus-k8s.active', 'prometheus.available')
def send_config():
    """Send prometheus configuration to prometheus
    Sent information:
        - Prometheus Host (ip)
        - Prometheus Port

    Conditions:
        - prometheus-k8s.active
        - prometheus.available
    """
    layer.status.maintenance('Sending prometheus configuration')
    cfg = config()
    try:
        prometheus = endpoint_from_flag('prometheus.available')
        if prometheus:
            prometheus.configure(port=cfg.get('advertised-port'))
            clear_flag('prometheus.available')
            set_prometheus_active()
    except Exception as e:
        log("Exception sending config: {}".format(e))


def make_pod_spec():
    """Make pod specification for Kubernetes

    Returns:
        pod_spec: Pod specification for Kubernetes
    """
    image_info = layer.docker_resource.get_info('prometheus-image')
    a_image_info = layer.docker_resource.get_info('alpine-image')

    with open('reactive/spec_template.yaml') as spec_file:
        pod_spec_template = spec_file.read()

    md = metadata()
    cfg = config()

    data = {
        'name': md.get('name'),
        'docker_image_path': image_info.registry_path,
        'docker_image_username': image_info.username,
        'docker_image_password': image_info.password,
        'a_docker_image_path': a_image_info.registry_path,
        'a_docker_image_username': a_image_info.username,
        'a_docker_image_password': a_image_info.password,
    }
    data.update(cfg)
    return pod_spec_template % data
