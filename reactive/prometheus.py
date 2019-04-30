from charms.layer.caas_base import pod_spec_set
from charms.reactive import endpoint_from_flag
from charms.reactive import when, when_not
from charms.reactive.flags import set_flag
from charmhelpers.core.hookenv import (
    log,
    metadata,
    config,
)
from charms import layer
from charms.osm.k8s import get_service_ip


@when_not('layer.docker-resource.prometheus-image.fetched')
def fetch_image():
    """Fetch the prometheus-image

    Conditions:
        - Not prometheus-image.fetched
    """
    layer.docker_resource.fetch('prometheus-image')


@when('layer.docker-resource.prometheus-image.failed')
def waiting_for_prometheus_image():
    """Set status blocked

    Conditions:
        - prometheus-image.failed
    """
    layer.status.waiting('Unable to fetch prometheus-image')


@when('layer.docker-resource.prometheus-image.available')
@when_not('mon.ready')
def waiting_for_mon_interface():
    """Set status blocked

    Conditions:
        - prometheus-image.available
        - mon.ready
    """
    layer.status.waiting('Waiting for mon interface')


@when('layer.docker-resource.prometheus-image.available')
@when('mon.ready')
@when_not('prometheus-k8s.configured')
def configure():
    """Configure prometheus-k8s pod

    Conditions:
        - prometheus-image.available
        - prometheus.available
        - Not prometheus-k8s.config-received
        - Not prometheus-k8s.configured
    """
    layer.status.maintenance('Configuring prometheus container')
    try:
        mon = endpoint_from_flag('mon.ready')
        mons = mon.mons()
        mon_unit = mons[0]
        if mon_unit['host'] and mon_unit['port']:
            spec = make_pod_spec(mon_unit['host'], mon_unit['port'])
            log('set pod spec:\n{}'.format(spec))
            success = pod_spec_set(spec)
            if success:
                set_flag('prometheus-k8s.configured')
                layer.status.active('configured')
            else:
                layer.status.blocked('k8s spec failed to deploy')

    except Exception as e:
        layer.status.blocked('k8s spec failed to deploy: {}'.format(e))


@when('prometheus-k8s.configured')
def set_prometheus_active():
    """Set prometheus status active

    Conditions:
        - prometheus-k8s.configured
    """
    layer.status.active('configured')


@when('prometheus-k8s.configured', 'prometheus.joined')
def send_config():
    """Send prometheus configuration to prometheus
    Sent information:
        - Prometheus Host (ip)
        - Prometheus Port

    Conditions:
        - prometheus-k8s.configured
        - prometheus joined
    """
    layer.status.maintenance('Sending prometheus configuration')
    cfg = config()
    try:
        prometheus = endpoint_from_flag('prometheus.joined')
        if prometheus:
            prometheus.send_connection(get_service_ip('prometheus'),
                                       cfg.get('advertised-port'))
    except Exception as e:
        log("Exception sending config: {}".format(e))


def make_pod_spec(mon_host, mon_port):
    """Make pod specification for Kubernetes

    Returns:
        pod_spec: Pod specification for Kubernetes
    """
    image_info = layer.docker_resource.get_info('prometheus-image')

    with open('reactive/spec_template.yaml') as spec_file:
        pod_spec_template = spec_file.read()

    md = metadata()
    cfg = config()

    data = {
        'name': md.get('name'),
        'docker_image_path': image_info.registry_path,
        'docker_image_username': image_info.username,
        'docker_image_password': image_info.password,
        'mon_uri': "{}:{}".format(mon_host, mon_port)
    }
    data.update(cfg)
    return pod_spec_template % data
