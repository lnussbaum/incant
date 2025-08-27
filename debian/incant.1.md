% incant(1) | User Commands
% August 2025

# NAME

incant - an Incus frontend for declarative development environments

# SYNOPSIS

**incant** [*OPTIONS*] [*COMMAND*]

# DESCRIPTION

**incant** is a command-line tool that provides a declarative way to manage Incus development environments. It uses a YAML configuration file to define instances, their properties, and provisioning steps.

# OPTIONS

**-v**, **--verbose**
: Enable verbose mode.

**-f**, **--config** *PATH*
: Path to the configuration file.

# COMMANDS

**init**
: Create an example configuration file in the current directory.

**up** [*NAME*]
: Start and provision an instance or all instances if no name is provided.

**provision** [*NAME*]
: Provision an instance or all instances if no name is provided.

**shell** [*NAME*]
: Open a shell into an instance. If no name is given and there is only one instance, use it.

**destroy** [*NAME*]
: Destroy an instance or all instances if no name is provided.

**dump**
: Show the generated configuration file.

**list**
: List all instances defined in the configuration.

# FILES

*incant.yaml*
: Default configuration file.

# SEE ALSO

**incus**(1)
