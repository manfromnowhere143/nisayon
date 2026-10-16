# Third-party notices — `arisole-eval`

Runtime dependencies of the default install:

| Package | License | Use |
|---|---|---|
| jsonschema | MIT | Schema validation of comparison / import documents |
| numpy | BSD-3-Clause | Telemetry array helpers |

Optional extras:

| Extra | Packages | License |
|---|---|---|
| `ci` / `dev` | PyYAML, pytest | MIT |
| `pypi` | build, twine | MIT / Apache-2.0 family |

Sample datasets and environment code referenced in provenance (RoboCasa, LeRobot, Hugging Face datasets) remain under their upstream licenses; this package only ships derived evaluation metadata and small synthetic/open-loop telemetry excerpts labeled in `samples/*/PROVENANCE.md`.
