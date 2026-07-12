# Publishing to PyPI

PyPI releases are immutable. If a published artifact is wrong, fix the source and publish a new patch version; never move or recreate an existing release tag.

The checks below are release evidence, not proof of a live backend deployment. They apply when preparing a release and do not block research branches or ordinary commits.

## Release checklist

### Before creating `vX.Y.Z`

- [ ] `pyproject.toml` contains `version = "X.Y.Z"`.
- [ ] `src/spooled/_version.py` uses installed package metadata and its source-checkout fallback is exactly `X.Y.Z`.
- [ ] `uv.lock` records the local `spooled` package as `X.Y.Z`; regenerate it after any package metadata or dependency-floor change.
- [ ] The default REST user-agent is `spooled-python/X.Y.Z` and derives from the canonical package version rather than an independent literal.
- [ ] Sync worker, async worker, direct `SpooledWorkerOptions`, and gRPC worker registration all default to the canonical package version.
- [ ] `CHANGELOG.md` contains `## [X.Y.Z] - YYYY-MM-DD`.
- [ ] Release-specific version references in `README.md`, `docs/`, and release-contract tests are synchronized or intentionally version-neutral.
- [ ] `uv lock --check`, lint, type checks, unit tests, build, and `twine check dist/*` succeed.
- [ ] Checked-in protobuf/gRPC stubs are regenerated from `proto/spooled.proto` with the locked tools and produce no unexpected diff.
- [ ] Declared `grpcio` and `protobuf` floors satisfy the runtime versions embedded in the generated stubs.
- [ ] A clean install of the built wheel reports `spooled.__version__ == "X.Y.Z"`, sends `spooled-python/X.Y.Z`, and imports the generated gRPC modules.

The release-contract tests derive their expected release from `pyproject.toml`; do not add a second hardcoded expected version to those assertions.

### Tag and publication

- [ ] The release commit is final; create `vX.Y.Z` once and do not move it.
- [ ] The GitHub Release targets the same commit as `vX.Y.Z`.
- [ ] PyPI lists both wheel and sdist for `X.Y.Z`.
- [ ] PyPI Trusted Publisher provenance names this repository, `publish.yml`, `refs/tags/vX.Y.Z`, and the expected commit.
- [ ] Artifact SHA-256 values and upload time are recorded in the release evidence.
- [ ] A clean environment installs `spooled[all]==X.Y.Z` from PyPI and repeats the version, user-agent, worker-registration, and gRPC import smoke checks.

## Workflow boundary

`.github/workflows/publish.yml` is triggered only by a published GitHub Release. Its strict tag and release-metadata checks therefore do not run for normal pushes or pull requests. Normal development remains governed by `.github/workflows/ci.yml`.
