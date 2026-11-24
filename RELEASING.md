# Releasing vol-surf

The candidate introduces the supported `vol_surf` API for Black-76 European
pricing, implied volatility, and normalized call surfaces. Review changes to
function signatures, input conventions, domain handling, and numerical behavior
as part of approving the v1 API.

## Stable 1.0.0 gates

- [ ] The maintainer approves the v1 API scope and selects a distribution license.
  Add the license file and matching package metadata before publishing.
- [ ] Run all CI jobs on the release commit on `main`. The matrix covers Python
  3.11–3.14 on Linux and Python 3.14 on macOS and Windows. The distribution job
  checks both the wheel and source archive, compares a second build byte for
  byte, and tests the installed wheel.
- [ ] Confirm the README examples, numerical references, boundary behavior, and
  surface shape checks all pass. Record known limitations in the release notes.
- [ ] Set `pyproject.toml` to version `1.0.0` and update the development-status
  classifier and README. Build and verify these exact sources before tagging.

## Build and check

Run from a clean checkout of the release commit in a fresh virtual environment.

```sh
python -m pip install build twine
export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"
rebuild="$(mktemp -d)"
python -m build
python -m build --outdir "$rebuild"
for artifact in dist/*.whl dist/*.tar.gz; do
  cmp "$artifact" "$rebuild/${artifact##*/}" || exit 1
done
python -m twine check --strict dist/*.whl dist/*.tar.gz
python -m pip install dist/vol_surf-1.0.0-py3-none-any.whl
python -m pip check
python -m unittest discover -s tests -v
```

Once the gates are met, create the `v1.0.0` tag on the verified `main` commit and
attach the tested wheel and source archive to its GitHub release. Include the
supported Python versions, public API, and interpolation limits in the notes.
For a PyPI release, confirm control of the project name and configure
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) before upload.
