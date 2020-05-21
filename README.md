Juju Charm/Operator for Prometheus on Kubernetes
================================================

CI Badges
---------

Click on each badge for more details.

| Branch | Build Status | Coverage |
|--------|--------------|----------|
| master | [![Build Status (master)](https://travis-ci.org/relaxdiego/charm-k8s-prometheus.svg?branch=master)](https://travis-ci.org/relaxdiego/charm-k8s-prometheus) | [![Coverage Status](https://coveralls.io/repos/github/relaxdiego/charm-k8s-prometheus/badge.svg?branch=master)](https://coveralls.io/github/relaxdiego/charm-k8s-prometheus?branch=master) |


Quick Start
-----------


```
git submodule update --init --recursive
sudo snap install juju --classic
sudo snap install microk8s --classic
sudo microk8s.enable dns dashboard registry storage metrics-server ingress
sudo usermod -a -G microk8s $(whoami)
```

Log out then log back in so that the new group membership is applied to
your shell session.

```
juju bootstrap microk8s mk8s
```

Optional: Grab coffee/beer/tea or do a 5k run. Once the above is done, do:

```
juju create-storage-pool operator-storage kubernetes storage-class=microk8s-hostpath
juju add-model lma
juju deploy . --resource prometheus-image=prom/prometheus:v2.18.1
```

Wait until `juju status` shows that the prometheus app has a status of active.


Preview the Prometheus GUI
--------------------------

Add the following entry to your machine's `/etc/hosts` file:

    <microk8s-host-ip>	prometheus.local

Run:

    juju config prometheus juju-external-hostname=prometheus.local
    juju expose prometheus

Now browse to http://prometheus.local.

> A NOTE ABOUT THE EXTERNAL HOSTNAME: If you are using a k8s distribution
> other than microk8s, you need to ensure that there is an LB sitting in
> front of the k8s nodes and that you use that LB's IP address in place of
> `<microk8s-host-ip>`. Alternatively, instead of adding a static entry in
> `/etc/hosts` such as above, you may use an FQDN as the value to
> `juju-external-hostname`.

The default prometheus.yml includes a configuration that scrapes metrics
from Prometheus itself. Execute the following query to show TSDB stats:

    rate(prometheus_tsdb_head_chunks_created_total[1m])

For more info on getting started with Prometheus see [its official getting
started guide](https://prometheus.io/docs/prometheus/latest/getting_started/).


Monitoring Kubernetes
---------------------

To monitor the kubernetes cluster, deploy it with the following config option:

    juju deploy . --resource prometheus-image=prom/prometheus:v2.18.1 \
        --config monitor-k8s=true

If the charm has already been deployed, you may also configure it at runtime:

    juju config prometheus monitor-k8s=true

WARNING: This second method is experimental and not yet fully supported and will
require some manual intervention by sending a `SIGHUP` to the Prometheus process
in the k8s pod. Do this by running the following after executing the `juju config`
command:

    kubectl -n lma exec <k8s-pod-name> -- kill -1 <prometheus-pid>

Prometheus' PID in the pod is usually 1 but if you're not sure, run:

    kubectl -n lma exec <k8s-pod-name> -- ps | grep /bin/prometheus | awk '{print $1}'


Use Prometheus as a Grafana Datasource
--------------------------------------

Refer to the [Grafana Operator](https://github.com/relaxdiego/charm-k8s-grafana)
Quick Start guide to learn how to use Prometheus with Grafana.


Running the Unit Tests on Your Workstation
------------------------------------------

To run the test using the default interpreter as configured in `tox.ini`, run:

    tox

If you want to specify an interpreter that's present in your workstation, you
may run it with:

    tox -e py37

To view the coverage report that gets generated after running the tests above,
run:

    make coverage-server

The above command should output the port on your workstation where the server is
listening on. If you are running the above command on [Multipass](https://multipass.io),
first get the Ubuntu VM's IP via `multipass list` and then browse to that IP and
the abovementioned port.

NOTE: You can leave that static server running in one session while you continue
to execute `tox` on another session. That server will pick up any new changes to
the report automatically so you don't have to restart it each time.


Relying on More Comprehensive Unit Tests
----------------------------------------

To ensure that this charm is tested on the widest number of platforms possible,
we make use of Travis CI which also automatically reports the coverage report
to a publicly available Coveralls.io page. To get a view of what the state of
each relevant branch is, click on the appropriate badges found at the top of
this README.


References
----------

Much of how this charm is architected is guided by the following classic
references. It will do well for future contributors to read and take them to heart:

1. [Hexagonal Architecture](https://en.wikipedia.org/wiki/Hexagonal_architecture_(software)) by Alistair Cockburn
1. [Boundaries (Video)](https://pyvideo.org/pycon-us-2013/boundaries.html) by Gary Bernhardt
1. [Domain Driven Design (Book)](https://dddcommunity.org/book/evans_2003/) by Eric Evans
