@stealthg0dd Verified the published [0.1.4 release](https://pypi.org/project/arisole-eval/0.1.4/) on macOS arm64 with Python 3.12.13. The unmodified extracted source distribution passes all **32 tests, with no skips**. The same tests also pass against the installed wheel in a fresh environment with the dependency versions held at those used for 0.1.3.

Both YAML configurations are now included in `tests/fixtures/configs`, and the affected tests resolve them within the archive. All **12 retained CLI controls** and their matched/comparable/incomparable counts also pass against the wheel. The original sparse-label case still returns `INSUFFICIENT_DATA`, exit 2.

This resolves the three packaging-related test failures I reported for 0.1.3. Thank you for following through on the release reproducibility as well as the gate correction.

Source archive SHA-256: `c68c7e855366b8d9cdc44b2f334092850de294fb7fe38a358eced3f6ae5bf28c`.

AI assistance was used for verification and drafting.
