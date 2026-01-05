# Incant

[![PyPI version](https://img.shields.io/pypi/v/incus-incant.svg)](https://pypi.org/project/incus-incant/)

Incant is a frontend for [Incus](https://linuxcontainers.org/incus/) that provides a declarative way to define and manage development environments. It simplifies the creation, configuration, and provisioning of Incus instances using YAML-based configuration files.

## Features

- **Declarative Configuration**: Define your development environments using simple YAML files.
- **Shared Folder Support**: Mount the current working directory into the instance.
- **Provisioning Support**: Declare and run provisioning scripts automatically, copy files to the instance, set up an SSH server automatically, and configure an LLMNR daemon.

## Installation

Ensure you have Python installed and `incus` available on your system.

You can install Incant from PyPI:

```sh
pipx install incus-incant
```

Or install directly from Git:

```sh
pipx install git+https://github.com/lnussbaum/incant.git
```

## Usage

### Install and configure Incus

[Incus](https://linuxcontainers.org/incus/) is required by Incant. [Incus' documentation](https://linuxcontainers.org/incus/docs/main/) describes how to install it, but in short, you can do:
```sh
# install Incus from your distribution's packages
apt-get -y install incus

# Configure Incus with default settings
incus admin init --auto

# Add yourself to the incus-admin group
usermod -a -G incus-admin <your_login>

# Gain the new group in the current shell (alternatively, you can log out and log in again)
newgrp incus-admin
```
### Configure Incant

Incant looks for a configuration file named `incant.yaml`, `incant.yaml.j2`, or `incant.yaml.mako` in the current directory.

You can ask Incant to create an example configuration file with:
```sh
$ incant init
```

A very basic example:
```yaml
instances:
  debian-sid:
    image: images:debian/14
```

Another example, that starts a KVM virtual machine:
```yaml
instances:
  debian-sid:
    image: images:debian/14
    vm: true
```

A more complex example that demonstrates most of Incant's features:
```yaml
instances:
  basic-container:
    image: images:ubuntu/24.04
    devices:
      root:
        size: 1GiB
    wait: true # wait for instance to be ready (incus agent running)
    shared_folder: false # disable shared folder (/incant) setup (default: enabled)
    config: # any incus config options
      limits.processes: 100
  basic-vm:
    image: images:ubuntu/24.04
    vm: true
    type: c1-m1 # 1 CPU, 1GB RAM
  provisioned:
    image: images:debian/13
    provision: # a list of provisioning steps
      - | # first, an inlined script
        #!/bin/bash
        set -xe
        apt-get update
        apt-get -y install curl ruby
      # then, a script. the path can be relative to the current dir,
      # as incant will 'cd' to /incant, so the script will be available inside the instance
      - examples/provision/web_server.rb
      - ssh: true # configure an ssh server and provide access
      # - ssh: # same with more configuration
      #    clean_known_hosts: true (that's the default)
      #    # authorized_keys: path to file (default: concatenate id_*.pub)
      - llmnr: true # configure and start an LLMNR daemon
      - copy: # copy a file using 'incus file push'
          source: ./README.md
          target: /tmp/README.md
          mode: "0644"
          uid: 0
          gid: 0
```

### Initialize and Start an Instance

```sh
$ incant up
```

or for a specific instance, if you have several instances described in your configuration file:

```sh
$ incant up my-instance
```

### Provision again an Instance that was already started previously

```sh
$ incant provision
```

or for a specific instance:

```sh
$ incant provision my-instance
```

### Use your Instances

Use [Incus commands](https://linuxcontainers.org/incus/docs/main/instances/) to interact with your instances:

```sh
$ incus exec ubuntu-container -- apt-get update
$ incus shell my-instance # or `incant shell` if you have a single instance
$ incus console my-instance
$ incus file edit my-container/etc/hosts
$ incus file delete <instance_name>/<path_to_file>
```

Your instance's services are directly reachable on the network. They should be discoverable in DNS if the instance supports [LLMNR](https://en.wikipedia.org/wiki/Link-Local_Multicast_Name_Resolution) or [mDNS](https://en.wikipedia.org/wiki/Multicast_DNS).

### Destroy an Instance

```sh
$ incant destroy
```

or for a specific instance:

```sh
$ incant destroy my-instance
```

### View Configuration (especially useful if you use Mako or Jinja2 templates)

```sh
$ incant dump
```

## Caveats

### Shared folders don't work on ARM64

This is known as [Incus issue #91](https://github.com/zabbly/incus/issues/91) and [virtiofsd issue #212](https://gitlab.com/virtio-fs/virtiofsd/-/issues/212).

The default shared folder (/incant) can be disabled using:
```yaml
instances:
  my-instance:
    shared_folder: false
```

### Virtual machines (not containers) for RHEL-based distributions need an explicit agent:config device

This can be added using a pre-launch command, with:
```yaml
instances:
  alma9vm:
    image: images:almalinux/9
    vm: true
    pre-launch:
      - config device add alma9vm agent disk source=agent:config
```

See [Incus documentation](https://linuxcontainers.org/incus/docs/main/reference/devices_disk/)

### Name resolution (DNS) does not work for some images

Some images enable [LLMNR](https://en.wikipedia.org/wiki/Link-Local_Multicast_Name_Resolution) or [mDNS](https://en.wikipedia.org/wiki/Multicast_DNS), so that their names are automatically resolvable from the host. For others, a custom provisioning step (`- llmnr: true`) can be added to enable LLMNR in `systemd-resolved` at instance startup.
* Images that are known to work out of the box: debian/{11,12,13,14}, archlinux/current
* Images that are known to work with `llmnr: true`: ubuntu/{22.04,24.04}, almalinux/{8,9,10}

### No network connectivity when Docker is installed

If Docker is installed on the same machine as Incus is running on, started instances may not have
network connectivity. See the Incus documentation for how to mitigate that:
[Prevent connectivity issues with Incus and Docker](https://linuxcontainers.org/incus/docs/main/howto/network_bridge_firewalld/#prevent-connectivity-issues-with-incus-and-docker)

## Incant compared to Vagrant

Incant is inspired by Vagrant, and intended as an Incus-based replacement for Vagrant.

The main differences between Incant and Vagrant are:

* Incant is Free Software (licensed under the Apache 2.0 license). Vagrant is licensed under the non-Open-Source Business Source License.
* Incant is only a frontend for [Incus](https://linuxcontainers.org/incus/), which supports containers (LXC-based) and virtual machines (KVM-based) on Linux. It will not attempt to be a more generic frontend for other virtualization providers. Thus, Incant only works on Linux.

Some technical differences are useful to keep in mind when migrating from Vagrant to Incant.

* Incant is intended as a thin layer on top of Incus, and focuses on provisioning. Once the provisioning has been performed by Incant, you need to use Incus commands such as `incus shell` to work with your instances.
* Incant shares the current directory as `/incant` inside the instance (compared to Vagrant's sharing of `/vagrant`). Incant tries to share the current directory read-write (using Incus' `shift=true`) but this fails in some cases, such as restricted containers. So there are chances that the directory will only be shared read-only.
* Incant does not create a user account inside the instance -- you need to use the root account, or create a user account during provisioning (for example, with `adduser --disabled-password --gecos "" incant`)
* Incant uses a YAML-based description format for instances. [Mako](https://www.makotemplates.org/) or [Jinja2](https://jinja.palletsprojects.com/) templates can be used to those YAML configuration files if you need more complex processing, similar to what is available in *Vagrantfiles* (see the examples/ directory).

## Incant compared to other projects

There are several other projects addressing similar problem spaces. They are shortly described here so that you can determine if Incant is the right tool for you.

* [lxops](https://github.com/melato/lxops) and [blincus](https://blincus.dev/) manage the provisioning of Incus instances using a declarative configuration format, but the provisioning actions are described using  [cloud-init](https://cloud-init.io/) configuration files. [lxops](https://github.com/melato/lxops) uses [cloudconfig](https://github.com/melato/cloudconfig) to apply them, while [blincus](https://blincus.dev/) requires *cloud* instances that include cloud-init. In contrast, using Incant does not require knowing about cloud-init or fitting into cloud-init's formalism.
* [terraform-provider-incus](https://github.com/lxc/terraform-provider-incus) is a [Terraform](https://www.terraform.io/) or [OpenTofu](https://opentofu.org/) provider for Incus. Incant uses a more basic scheme for provisioning, and does not require knowing about Terraform or fitting into Terraform's formalism.
* [cluster-api-provider-lxc (CAPL)](https://github.com/neoaggelos/cluster-api-provider-lxc) is an infrastructure provider for Kubernetes' Cluster API, which enables deploying Kubernetes clusters on Incus. Incant focuses on the more general use case of provisioning system containers or virtual machines outside of the Kubernetes world.
* [devenv](https://devenv.sh/) is a [Nix](https://nixos.org/)-based development environment manager. It also uses a declarative file format. It goes further than Incant by including the definition of development tasks. It also covers defining services that run inside the environment, and generating OCI containers to deploy the environment to production. Incant focuses on providing the environment based on classical Linux distributions and tools.

## Copyright and License

Copyright 2025 Lucas Nussbaum

Licensed under the Apache License, Version 2.0 (the "License"); you may not use
this software except in compliance with the License.  You may obtain a copy of
the License at <http://www.apache.org/licenses/LICENSE-2.0>, or in the
[LICENSE](LICENSE) file.

Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied.  See the License for the
specific language governing permissions and limitations under the License.
