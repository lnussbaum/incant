# Incant

Incant is a frontend for [Incus](https://linuxcontainers.org/incus/) that provides a descriptive way to define and manage development environments. It simplifies the creation, configuration, and provisioning of Incus instances using YAML-based configuration files.

Incant is inspired by Vagrant, and intended as an Incus-based replacement for Vagrant.

## Features

- **Declarative Configuration**: Define your development environments using simple YAML files.
- **Instance Management**: Easily create, start, stop, and destroy instances.
- **Provisioning Support**: Run provisioning scripts automatically.
- **Shared Folder Support**: Mount the current working directory into the instance.

## Installation

FIXME

Ensure you have Python installed and `incus` available on your system.

```sh
# Clone the repository
$ git clone https://github.com/your-repo/incant.git
$ cd incant

# Install dependencies
$ pip install .
```

## Usage

## Configure Incant

Incant looks for a configuration file named `incant.yaml`, `incant.yaml.j2`, or `incant.yaml.mako` in the current directory. Here is an example:

```yaml
instances:
  my-instance:
    image: ubuntu:22.04
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

Incant is inspired by Vagrant and shares some of its features.

FIXME

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

