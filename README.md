Juju Charm for Prometheus on Kubernetes
=======================================

| Branch | Build Status | Coverage |
|--------|--------------|----------|
| master | [![Build Status (master)](https://travis-ci.org/relaxdiego/charm-k8s-prometheus.svg?branch=master)](https://travis-ci.org/relaxdiego/charm-k8s-prometheus) | [![Coverage Status](https://coveralls.io/repos/github/relaxdiego/charm-k8s-prometheus/badge.svg?branch=master)](https://coveralls.io/github/relaxdiego/charm-k8s-prometheus?branch=master) |


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

The aboe command should output the port on your workstation where server is
serving the HTML coverage reports. If you are running this on [Multipass](https://multipass.io)
then first get the Ubuntu VMs IP via `multipass list` and then browse to that
IP and port.


Relying on More Comprehensive Tests
-----------------------------------

This project makes use of Travis CI and Coveralls.io to generate the build
report and the coverage report automatically. To get a view of what the state
of each relevant branch is, click on the badges found at the top of this README.
