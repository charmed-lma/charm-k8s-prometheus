# Overview

Prometheus for Juju CAAS

## Testing

The tests of this charm are done using tox and Zaza.



### Prepare environment

The machine in which the tests are run needs access to a juju k8s controller. The easiest way to approach this is by executing the following commands:

```
sudo apt install tox -y
sudo snap install microk8s --classic
sudo snap install juju

microk8s.status --wait-ready
microk8s.enable storage dashboard dns

juju bootstrap microk8s k8s-cloud
```

If /usr/bin/python does not exist, you should probably need to do this:

```
sudo ln -s /usr/bin/python3 /usr/bin/python
```
### Build Charm

**Download dependencies:**

```
mkdir -p ~/charm/layers ~/charm/build ~/charm/interfaces
git clone https://git.launchpad.net/canonical-osm ~/canonical-osm

cd ~/charm/layers
git clone https://git.launchpad.net/charm-k8s-prometheus prometheus-k8s 

cd ~/charm/interfaces
mv ~/canonical-osm/charms/interfaces/* .
```

**Charm structure:**

```
├── config.yaml
├── icon.svg
├── layer.yaml
├── metadata.yaml
├── reactive
│   ├── spec_template.yaml
│   └── prometheus.py
├── README.md
├── test-requirements.txt
├── tests
│   ├── basic_deployment.py
│   ├── bundles
│   │   ├── prometheus-ha.yaml
│   │   └── prometheus.yaml
│   └── tests.yaml
└── tox.ini
```

**Setup environment variables:**

```
export CHARM_LAYERS_DIR=~/charm/layers
export CHARM_BUILD_DIR=~/charm/build
export CHARM_INTERFACES_DIR=~/charm/interfaces
```

**Build:**

```
mkdir ~/charm/layers/prometheus-k8s/tests/build
charm build ~/charm/layers/prometheus-k8s
mv ~/charm/build/* ~/charm/layers/prometheus-k8s/tests/build/
```

### Test charm with Tox

```
cd ~/charm/layers/prometheus-k8s
tox -e func
```
