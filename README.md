Juju Charm for Prometheus on Kubernetes
=======================================

| Branch | Build Status | Coverage |
|--------|--------------|----------|
| master | [![Build Status (master)](https://travis-ci.org/relaxdiego/charm-k8s-prometheus.svg?branch=master)](https://travis-ci.org/relaxdiego/charm-k8s-prometheus) | [![Coverage Status](https://coveralls.io/repos/github/relaxdiego/charm-k8s-prometheus/badge.svg?branch=master)](https://coveralls.io/github/relaxdiego/charm-k8s-prometheus?branch=master) |


Quick-ish Start
---------------


```
git submodule update --init --recursive
sudo snap install juju --classic
sudo snap install microk8s --classic
sudo microk8s.enable dns dashboard registry storage
sudo usermod -a -G microk8s ubuntu
```

Log out then log back in to apply the group membership

```
juju bootstrap microk8s mk8s
```

Optional: Grab coffee/beer/tea or do a 5k run

```
juju create-storage-pool operator-storage kubernetes storage-class=microk8s-hostpath
juju add-model prometheus
juju deploy .
```


Running the Tests on Your Workstation
-------------------------------------

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
to execute `tox` on another session. That server will pick up any new changes to the report
automatically so you don't have to restart it each time.


Relying on More Comprehensive Tests
-----------------------------------

This project makes use of Travis CI and Coveralls.io to generate the build
report and the coverage report automatically. To get a view of what the state
of each relevant branch is, click on the badges found at the top of this README.


References
----------

Much of how this charm is architected is guided by the following classic
references. It will do well for future contributors to read and take them to heart:

1. [Hexagonal Architecture](https://en.wikipedia.org/wiki/Hexagonal_architecture_(software)) by Alistair Cockburn
1. [Boundaries (Video)](https://pyvideo.org/pycon-us-2013/boundaries.html) by Gary Bernhardt
1. [Domain Driven Design (Book)](https://dddcommunity.org/book/evans_2003/) by Eric Evans
