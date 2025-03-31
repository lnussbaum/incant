# Incant

[![PyPI version](https://img.shields.io/pypi/v/incus-incant.svg)](https://pypi.org/project/incus-incant/)

Incant is a frontend for [Incus](https://linuxcontainers.org/incus/) that provides a declarative way to define and manage development environments. It simplifies the creation, configuration, and provisioning of Incus instances using YAML-based configuration files.


## Features

- **Declarative Configuration**: Define your development environments using simple YAML files.
- **Provisioning Support**: Declare and run provisioning scripts automatically.
- **Shared Folder Support**: Mount the current working directory into the instance.

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

## Configure Incant

Incant looks for a configuration file named `incant.yaml`, `incant.yaml.j2`, or `incant.yaml.mako` in the current directory. Here is an example:

```yaml
instances:
  my-instance:
    image: images:debian/12
    vm: false # use a container, not a KVM virtual machine
    provision:
      - echo "Hello, World!"
      - apt-get update && apt-get install -y curl
```


### Initialize and Start an Instance

```sh
$ incant up
```

or for a specific instance:

```sh
$ incant up my-instance
```

### Provision an Instance

```sh
$ incant provision
```

or for a specific instance:

```sh
$ incant provision my-instance
```

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

## Migrating from Vagrant

Incant is inspired by Vagrant, and intended as an Incus-based replacement for Vagrant.

The main differences between Incant and Vagrant are:

* Incant is Free Software (licensed under the MIT license). Vagrant is licensed under the non-Open-Source Business Source License.
* Incant is only a frontend for [Incus](https://linuxcontainers.org/incus/), which supports containers (LXC-based) and virtual machines (KVM-based) on Linux. It will not attempt to be a more generic frontend for other virtualization providers. Thus, Incant only works on Linux.

Some technical differences are useful to keep in mind when migrating from Vagrant to Incant.

* Incant is intended as thin layer on top of Incus, and focuses on provisioning. Once the provisioning has been performed by Incant, you need to use Incus commands such as `incus shell` to work with your instances.
* Incant shares the current directory as `/incant` inside the instance (compared to Vagrant's sharing of `/vagrant`).
* Incant does not create a user account inside the instance -- you need to use the root account, or create a user account during provisioning (for example, with `adduser --disabled-password --gecos "" incant`)
* Incant uses a different, YAML-based, description format for instances. [Mako](https://www.makotemplates.org/) or [Jinja2](https://jinja.palletsprojects.com/) templates can be used to generate parts of those YAML configuration files.

## Incant compared to other projects

There are several other projects addressing similar problem spaces. They are shortly described here so that you can determine if Incant is the right tool for you.

* [lxops](https://github.com/melato/lxops) also manages the provisioning of Incus instances using a declarative configuration format, but provisioning steps are described using [cloud-init](https://cloud-init.io/) configuration files and applied with [cloudconfig](https://github.com/melato/cloudconfig). In contrast, using Incant does not require knowing about cloud-init or fitting into cloud-init's formalism.
* [terraform-provider-incus](https://github.com/lxc/terraform-provider-incus) is a [Terraform](https://www.terraform.io/) or [OpenTofu](https://opentofu.org/) provider for Incus. Incant uses a more basic scheme for provisioning, and does not require knowing about Terraform or fitting into Terraform's formalism.
* [cluster-api-provider-lxc (CAPL)](https://github.com/neoaggelos/cluster-api-provider-lxc) is an infrastructure provider for Kubernetes' Cluster API, which enables deploying Kubernetes clusters on Incus. Incant focuses on the more general use case of provisioning system containers or virtual machines outside of the Kubernetes world.
* [devenv](https://devenv.sh/) is a [Nix](https://nixos.org/)-based development environment manager. It also uses a declarative file format. It goes further than Incant by including the definition of development tasks. It also covers defining services that run inside the environment, and generating OCI containers to deploy the environment to production. Incant focuses on providing the environment based on classical Linux distributions and tools.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

