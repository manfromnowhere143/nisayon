# Installed reader check

A private local wheel built from clean
`28e29a8c6e9d38a30a21c36893da9382e04b88ee` was installed offline with the
locked `records` dependencies. The [check](check_installed_reader.py) ran Python
in isolated mode from a directory outside the checkout and verified that the
imported module came from that environment's `site-packages`.

The [result](check.json) records the wheel, requirements and module digests,
Python/dependency versions and absence of Torch, robosuite and MuJoCo. Its real
RoboLab import equals the current checkout import byte-for-byte, SHA-256
`089983905a37f02e65c66593106046a7007060749a01fd667917f39dc621a624`.
This is a local macOS ARM64/Python 3.12.13 check, not a new release or a claim
of qualification on other interpreters or platforms. Nothing was published.

The [requirements](requirements.txt) were exported with `uv export --frozen
--extra records --no-dev --no-emit-project` and installed using `uv pip sync
--offline --require-hashes`. Exact build, environment, install and run commands
are retained under `../engine-continuation-checks-001/` with IDs
`7769b54a1b1e4910b405439162cfa24d`, `c2c1c1b793dc4fa28c3f9c16b924c27a`,
`69b30aefc7e34913a1754fddbd4de1e2`, `f2dbbc08a0d14d7e8c129865cf93836c`,
`3eca6ef405b0453ca20e5974750011de` and `27e5972df616468fb58640f877048802`.
No package download, simulator execution or model call was needed.
