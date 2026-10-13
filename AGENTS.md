# AGENTS.md — Incant

Incant is a frontend for [Incus](https://linuxcontainers.org/incus/) that provides declarative development environments via YAML config. Vagrant-like, but Incus-only (Linux containers + KVM VMs).

## Commands

```bash
poetry install                          # Install deps
poetry run pytest                       # Run all tests (fails if coverage < 15%)
poetry run pytest tests/test_incant.py -v   # Run one test file
poetry run pytest -k "test_name" -v     # Run one test by name

# Lint/typecheck — all must pass in CI
poetry run ruff check incant/
poetry run isort --check --diff incant/
poetry run flake8 .
poetry run pylint incant/               # fail-under=8, tests/ excluded
poetry run mypy incant
poetry run bandit -r incant/
poetry run radon cc incant/
poetry run typos incant/
```

Line length: **110** (black, ruff, flake8, pylint all agree).

## Architecture

```
incant/cli.py              → Click commands: up, provision, shell, destroy, dump, list, init
incant/incant.py           → Incant class: orchestrates create → wait → share → provision
incant/config_manager.py   → Loads incant.yaml (.yaml/.yaml.j2/.yaml.mako), validates, builds InstanceConfig
incant/incus_cli.py        → Subprocess wrapper for all `incus` CLI calls
incant/provisioning_manager.py → Dispatches provision steps to registered provisioners
incant/provisioners/       → Pluggable provisioners (auto-register via __init_subclass__)
incant/types.py            → InstanceConfig, FilePushConfig dataclasses
incant/exceptions.py       → IncantError, ConfigurationError, InstanceError, IncusCommandError, ProjectError
```

**Config flow:** `incant.yaml` → Jinja2/Mako render (if templated) → YAML parse → validate → `InstanceConfig` dataclasses.

**Provisioners** (in `incant/provisioners/`): `script`, `ssh`, `llmnr`, `copy`. Each sets `config_key` and auto-registers. Add new ones by subclassing `Provisioner` in `base.py`.

**YAML keys are kebab-case** (`pre-launch`, `shared-folder`) → mapped to snake_case in `InstanceConfig` via `config_manager.py`.

## Conventions

- Python >= 3.11. Type hints everywhere (mypy enforced).
- All `incus` subprocess calls go through `IncusCLI._run_command()`. Use `# nosec B404` / `# nosec B603` for bandit.
- Raise custom exceptions from `incant/exceptions.py` — never bare `Exception`.
- Tests use `unittest.mock`. `MockReporter` helper in `tests/test_incant.py`. Coverage floor: **15%**.

## Gotchas

- **Always run from project root** — Incant shares `Path.cwd()` as `/incant` inside instances.
- **`debian/` contains build artifacts** after local builds (`.debhelper.log`, `files`, `substvars`) — don't commit them.
- **AI-assisted commits**: include `AI-assisted: yes, <agent> + <model>` pseudo-header.

## Release

See `RELEASE_CHECKLIST.md`. Version in `pyproject.toml` + `debian/changelog` must match. Tag as `vX.Y`.
