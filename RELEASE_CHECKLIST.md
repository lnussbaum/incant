# Release Checklist

## 1. Pre-Release Checks

- [ ] **Update dependencies:**
  ```bash
  poetry update
  ```

- [ ] **Run Code Quality Checks:**
  Ensure all linting and tests pass.
  ```bash
  # Run all tests and linters
  poetry run pytest
  poetry run ruff check incant
  poetry run mypy .
  poetry run bandit -r incant/
  poetry run typos
  ```

## 2. Version Bump

- [ ] **Update `pyproject.toml`:**
  Update the `version` field in `pyproject.toml`.
  ```bash
  # Example for 0.5
  poetry version 0.5
  ```

- [ ] **Update `debian/changelog`:**
  Add a new entry for the release.
  ```bash
  # Use dch (devscripts)
  dch -v 0.5 -D unstable "New upstream release."
  ```
  *Note: Ensure the version matches `pyproject.toml`.*

## 3. Commit and Tag

- [ ] **Commit changes:**
  ```bash
  git add pyproject.toml debian/changelog poetry.lock
  git commit -m "Release 0.5"
  ```

- [ ] **Tag the release:**
  ```bash
  git tag -a v0.5 -m "Release 0.5"
  ```

## 4. Build and Verify

- [ ] **Build Python Package:**
  ```bash
  poetry build
  ```

- [ ] **Build Debian Package:**
  ```bash
  dpkg-buildpackage -us -uc
  ```
  *Verify the built packages in the parent directory.*

## 5. Publish

- [ ] **Push to Git:**
  ```bash
  git push origin master --tags
  ```

- [ ] **Publish to PyPI:**
  ```bash
  poetry publish
  ```

- [ ] **Publish to Debian:**
   * Push to Salsa: `git push salsa master --tags`
   * Upload package
