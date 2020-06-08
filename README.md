Juju Charm/Operator for Prometheus on Kubernetes
================================================

CI Badges
---------

Click on each badge for more details.

| Branch | Build Status | Coverage |
|--------|--------------|----------|
| master | [![Build Status (master)](https://travis-ci.org/charmed-lma/charm-k8s-prometheus.svg?branch=master)](https://travis-ci.org/charmed-lma/charm-k8s-prometheus) | [![Coverage Status](https://coveralls.io/repos/github/charmed-lma/charm-k8s-prometheus/badge.svg?branch=master)](https://coveralls.io/github/charmed-lma/charm-k8s-prometheus?branch=master) |


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

Refer to the [Grafana Operator](https://github.com/charmed-lma/charm-k8s-grafana)
Quick Start guide to learn how to use Prometheus with Grafana.


Use Prometheus with AlertManager
--------------------------------

Refer to the [AlertManager Operator](https://github.com/charmed-lma/charm-k8s-alertmanager)
Quick Start guide to learn how to use Prometheus with AlertManager.


This Charm's Architecture
-------------------------

To learn how to navigate this charm's code and become an effective contributor,
please read the [Charmed LMA Operators Architecture](https://docs.google.com/document/d/1V5cA9D1YN8WGEClpLhUwQt2dYrg5VZEY99LZiE6Mx_A/edit?usp=sharing)
reference doc.


Preparing Your Workstation for Local Development
------------------------------------------------

1. Install pyenv so that you can test with different versions of Python

    curl -L https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash

2. Append the following to your ~/.bashrc then log out and log back in

    export PATH="/home/mark/.pyenv/bin:$PATH"
    eval "$(pyenv init -)"
    eval "$(pyenv virtualenv-init -)"

3. Install development packages. These are needed by pyenv to compile Python

    sudo apt install build-essential libssl-dev zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev \
    xz-utils tk-dev libffi-dev liblzma-dev python3-openssl git

4. Install Python 3.6.x and 3.7.x

    NOTE: Replace X with the correct minor version as shown in `pyenv install --list`

    pyenv install 3.6.X
    pyenv install 3.7.X

5. Test by cd-ing in and out of your working directory

    ~/charm-k8s-prometheus $ python --version
    Python 3.7.7
    ~ $ cd ..
    ~ $ python --version
    Python 3.6.9
    ~ $ cd -
    ~/charm-k8s-prometheus $ python --version
    Python 3.7.7

6. Test if tox is able to run tests against all declared environments

    tox


If You Want More Control Over Your Python Environments
------------------------------------------------------

1. Install venv and virtualenvwrapper

    sudo apt install python3-venv
    pip3 install virtualenvwrapper

2. Append the following to your ~/.bashrc, then log out and log back in

    export WORKON_HOME=$HOME/.virtualenvs
    source $(which virtualenvwrapper.sh)

3. Make two virtualenvs that you can quickly switch between for testing

   pyenv virtualenv --python $(pyenv which python3.6) charm-k8s-prometheus-py36
   pyenv virtualenv --python $(pyenv which python3.7) charm-k8s-prometheus-py37

4. Activate any one of them

   pyenv activate charm-k8s-prometheus-py36

5. Install the dependencies in the virtualenv

   pip3 install -r test-requirements.txt

6. Deactivate to leave the virtual environment

    pyenv deactivate


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


Troubleshooting
---------------

Since Kubernetes charms are not supported by `juju debug-hooks`, the only
way to intercept code execution is to initialize the non-tty-bound
debugger session and connect to the session externally.

For this purpose, we chose the [rpdb](https://pypi.org/project/rpdb/), the
remote Python debugger based on pdb.

For example, given that you have already deployed an application named
`prometheus` in a Juju model named `lma` and you would like to debug your
`config-changed` handler, execute the following:


    kubectl exec -it pod/prometheus-operator-0 -n lma -- /bin/sh


This will open an interactive shell within the operator pod. Then, install
the editor and the RPDB:


    apt update
    apt install telnet vim -y
    pip3 install rpdb


Open the charm entry point in the editor:


    vim /var/lib/juju/agents/unit-prometheus-0/charm/src/charm.py


Find a `on_config_changed_handler` function definition in the `charm.py` file.
Modify it as follows:


    def on_config_changed_handler(event, fw_adapter):
        import rpdb
        rpdb.set_trace()
        # < ... rest of the code ... >


Save the file (`:wq`). Do not close the current shell session!

Open another terminal session and trigger the `config-changed` hook as follows:


    juju config prometheus external-labels='{"foo": "bar"}'


Do a `juju status`, until you will see the following:


    Unit           Workload  Agent      Address    Ports     Message
    prometheus/0*  active    executing  10.1.28.2  9090/TCP  (config-changed)

This message means, that unit has started the `config-changed` hook routine and
it was already intercepted by the rpdb.

Now, return back to the operator pod session.

Enter the interactive debugger:


    telnet localhost 4444


You should see the debugger interactive console.


    # telnet localhost 4444
    Trying ::1...
    Trying 127.0.0.1...
    Connected to localhost.
    Escape character is '^]'.
    > /var/lib/juju/agents/unit-prometheus-0/charm/hooks/config-changed(91)on_config_changed_handler()
    -> set_juju_pod_spec(fw_adapter)
    (Pdb) where
      /var/lib/juju/agents/unit-prometheus-0/charm/hooks/config-changed(141)<module>()
    -> main(Charm)
      /var/lib/juju/agents/application-prometheus/charm/lib/ops/main.py(212)main()
    -> _emit_charm_event(charm, juju_event_name)
      /var/lib/juju/agents/application-prometheus/charm/lib/ops/main.py(128)_emit_charm_event()
    -> event_to_emit.emit(*args, **kwargs)
      /var/lib/juju/agents/application-prometheus/charm/lib/ops/framework.py(205)emit()
    -> framework._emit(event)
      /var/lib/juju/agents/application-prometheus/charm/lib/ops/framework.py(710)_emit()
    -> self._reemit(event_path)
      /var/lib/juju/agents/application-prometheus/charm/lib/ops/framework.py(745)_reemit()
    -> custom_handler(event)
      /var/lib/juju/agents/unit-prometheus-0/charm/hooks/config-changed(68)on_config_changed()
    -> on_config_changed_handler(event, self.fw_adapter)
    > /var/lib/juju/agents/unit-prometheus-0/charm/hooks/config-changed(91)on_config_changed_handler()
    -> set_juju_pod_spec(fw_adapter)
    (Pdb)

From this point forward, the usual pdb commands apply. For more information on 
how to use pdb, see the [official pdb documentation](https://docs.python.org/3/library/pdb.html)


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
