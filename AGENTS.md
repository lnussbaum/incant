# AGENTS.md — Incant

Incant is a frontend for [Incus](https://linuxcontainers.org/incus/) that provides a declarative way to define and manage development environments using YAML-based configuration files. It is inspired by Vagrant but focused solely on Incus (Linux containers and KVM VMs).

## Project Structure

```
incant/
├── incant/                 # Main Python package
│   ├── __init__.py         # Package exports (Incant, IncusCLI)
│   ├── __main__.py         # python -m incant entry point
│   ├── cli.py              # Click CLI commands (up, down, provision, shell, destroy, init, dump, list)
│   ├── incant.py           # Core Incant class — orchestrates instance lifecycle
│   ├── config_manager.py   # Config loading (YAML/Jinja2/Mako), validation, instance parsing
│   ├── incus_cli.py        # Python wrapper around the `incus` CLI (subprocess calls)
│   ├── provisioning_manager.py  # Dispatches provisioning steps to provisioners
│   ├── reporter.py         # Styled console output (success/info/warning/error)
│   ├── constants.py        # Click style definitions
│   ├── exceptions.py       # Custom exceptions: IncantError, ConfigurationError, InstanceError, etc.
│   ├── types.py            # Dataclasses: InstanceConfig, FilePushConfig
│   └── provisioners/       # Pluggable provisioners
│       ├── __init__.py     # REGISTERED_PROVISIONERS registry
│       ├── base.py         # Abstract Provisioner class with auto-registration
│       ├── script.py       # Run shell scripts inside instances
│       ├── ssh_server.py   # Configure SSH server + authorized_keys
│       ├── llmnr.py        # Enable LLMNR name resolution
│       └── copy_file.py    # Push files via `incus file push`
├── tests/                  # Pytest test suite
│   ├── test_incant.py
│   ├── test_config_manager.py
│   ├── test_incus_cli.py
│   ├── test_provision_manager.py
│   ├── test_ssh_provisioner.py
│   └── test_invalid_configs.py
├── examples/               # Example incant.yaml configs (advanced, network, provisioning)
├── debian/                 # Debian packaging (control, rules, changelog, man page)
├── bash_completion/        # Shell completion script
├── dist/                   # Built wheels and sdists (gitignored)
├── pyproject.toml          # Poetry-based project config (Python >=3.11)
├── poetry.lock             # Locked dependencies
├── incant.yaml             # Project's own incant config (dogfooding)
└── README.md               # User-facing documentation
```

## Build & Development Commands

This project uses **Poetry** for dependency management and packaging.

```bash
# Install dependencies
poetry install

# Run the CLI in development mode
poetry run incant --help

# Initialize an example config
poetry run incant init

# Run tests (with coverage — fails below 15%)
poetry run pytest

# Run a single test file
poetry run pytest tests/test_incant.py -v

# Run a single test
poetry run pytest tests/test_incant.py::TestClass::test_method -v
```

## Linting & Code Quality

Multiple linters are configured — all must pass in CI:

```bash
# Ruff (primary linter — E, F, W, I, B, PL rules)
poetry run ruff check incant/

# Black-compatible line length: 110
poetry run ruff format --check incant/   # if ruff format is used

# isort (import sorting)
poetry run isort --check-only incant/

# flake8
poetry run flake8 incant/

# pylint (threshold: fail-under=8, tests/ excluded)
poetry run pylint incant/

# mypy (type checking)
poetry run mypy incant

# bandit (security)
poetry run bandit -r incant/

# radon (complexity metrics)
poetry run radon cc incant/ -a

# typos (spell checking)
poetry run typos
```

**Line length: 110** (consistent across black, ruff, flake8, pylint).

## Code Style & Conventions

- **Python >= 3.11** — uses modern typing (`Optional`, `Dict`, `List` from `typing`, not built-in generics in some files; `dict[str, ...]` in newer files like `provisioners/base.py`).
- **Type hints** are used throughout. mypy is enforced in CI.
- **Docstrings**: pylint has `missing-docstring` disabled, but public methods should still have docstrings.
- **Imports**: isort/ruff enforce import ordering — stdlib, third-party, local.
- **Error handling**: Use custom exceptions from `incant/exceptions.py` (`IncantError`, `ConfigurationError`, `InstanceError`, `IncusCommandError`, `ProjectError`). Never raise bare `Exception`.
- **Subprocess calls**: All `incus` CLI invocations go through `IncusCLI._run_command()`. Use `# nosec B404` / `# nosec B603` for bandit where subprocess is intentional.
- **Provisioners**: New provisioners extend `Provisioner` in `incant/provisioners/base.py` and set a `config_key` class variable. They auto-register via `__init_subclass__`.
- **Configuration keys**: YAML config uses kebab-case (e.g., `pre-launch`, `shared-folder`) which is mapped to snake_case in `InstanceConfig` dataclass fields via `config_manager.py`.
- **Testing**: Tests use `unittest.mock` for mocking. `MockReporter` is a common test helper. Coverage must be >= 15%.

## Key Architecture Notes

- **Config flow**: `ConfigManager` finds `incant.yaml` (or `.yaml.j2`/`.yaml.mako`) → renders templates → parses YAML → validates → creates `InstanceConfig` dataclasses.
- **Instance lifecycle**: `Incant.up()` → creates instances in parallel → waits for agent → sets up shared folders → provisions. `Incant.destroy()` → stops and deletes.
- **Shared folders**: The current directory is shared as `/incant` inside instances. Additional `shared_folders` entries use `<source>:<path>` format. Uses Incus `disk` devices with `shift=true` (falls back without shift on failure).
- **Provisioning**: Steps are a list of either inline scripts (strings) or single-key dicts (`ssh:`, `copy:`, `llmnr:`, `script:`). Provisioners are dispatched by `ProvisionManager`.
- **IncusCLI**: Thin wrapper around `incus` subprocess calls. Retries shared folder mounts up to 10 times. Handles VM vs container differences.

## CI/CD

GitHub Actions workflows in `.github/workflows/` run on push/PR:
- `pytest.yml` — Tests with coverage
- `ruff.yml`, `flake8.yml`, `isort.yml`, `black.yml` — Linting
- `mypy.yml`, `pylint.yml` — Type checking & static analysis
- `bandit.yml`, `radon.yml`, `typos.yml` — Security, complexity, spelling
- `deb.yml` — Debian package build

All use Python 3.11 on `ubuntu-latest` with Poetry.

## Packaging & Release

See `RELEASE_CHECKLIST.md` for the full release process. Key points:
- Version is in `pyproject.toml` (currently 0.5)
- Debian packaging in `debian/` (uses `dch` for changelog, `dpkg-buildpackage`)
- Releases are tagged (e.g., `v0.5`) and published to PyPI + Salsa (Debian)
- `poetry build` creates wheel + sdist in `dist/`

## Gotchas & Quirks

- **Shared folders don't work on ARM64** (Incus issue #91 / virtiofsd issue #212).
- **RHEL-based VMs** need an explicit `agent:config` disk device via `pre-launch`.
- **Docker + Incus conflict**: If Docker is installed, instances may lose network connectivity (firewalld/iptables conflict).
- **LLMNR/mDNS**: Not all images support name resolution out of the box; use `- llmnr: true` provisioning step.
- **Coverage threshold**: pytest is configured with `--cov-fail-under=15` — tests will fail if coverage drops below 15%.
- **Debian build artifacts**: The `debian/` directory contains build artifacts (`.debhelper.log`, `files`, `substvars`, etc.) that may appear after local builds.
- **Working directory matters**: Incant shares `Path.cwd()` as `/incant` — always run from the project root.
- **AI-assisted commits**: When committing AI-generated changes, include a pseudo-header: `AI-assisted: yes, <agent> + <model>`.
