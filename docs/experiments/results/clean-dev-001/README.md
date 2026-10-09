# Clean development and simulation installations

**9 October 2026 · local software qualification complete.**

A fresh default installation could not collect the tests: the development group
omitted NumPy, h5py and psutil. The original run produced **18 collection errors**;
its [output](before-collection.stdout.log) remains retained. The first candidate
exposed [one further unconditional robomimic import](first-candidate.stdout.log)
in the training-contract test. Both failed attempts remain in the command ledger.

The development group now explicitly includes those three already-locked
packages. Four test modules declare their optional PyTorch/robomimic requirements;
their existing scenarios and assertions are unchanged. Both profiles ran in
separate worktrees and newly created environments from parent `f1c3c43`, with the
exact six-file candidate identities recorded in [validation.json](validation.json).

| Check | Observed outcome |
|---|---|
| Default `uv sync --frozen; make check` | 1,125 passed, 29 reported skips; lint, formatting and docs passed |
| `simulation` extra, then `UV_NO_SYNC=1 make check` | 1,164 passed, one private-raw-store skip; lint, formatting and docs passed |
| That raw-store test, same new full-stack Python with retained data available | One passed, zero skips |

The last two runs cover **1,165 distinct passing tests**. They are separate runs,
not a claim that the empty checkout contained private evidence. Base-profile skip
counts include four modules skipped during collection, so they are not counts of
all underlying test functions. The ledger retains every skip and reconciles the
base passes and the full profile's missing test against the combined coverage.

The new full installation contains PyTorch **2.5.1**, robomimic **0.3.0**,
robosuite **1.4.1**, MuJoCo **3.2.7**, NumPy **1.26.4**, h5py **3.16.0** and
psutil **7.2.2**. Imports and a real CPU tensor operation passed before the test
result was accepted. The 86-package installation used the existing uv cache;
this does not measure cold network installation. The full tests exercise actual
robomimic sequence preprocessing, checkpoint decoding and tensor operations.
No dependency version was upgraded: all **104 external lock records are identical**.

The [preservation readback](preservation.json) matches both retained research
environment trees against B2's frozen identities. The development lockfile itself
has changed because of its added development dependencies. The old lock remains
in Git at the source parent and under `artifacts/clean-dev-001/before/uv.lock`;
historical protocols continue to require their pinned source and environment.

Use the [updated setup recipes](../../../DEVELOPMENT.md#local-setup) in a separate
checkout. `UV_NO_SYNC=1` follows the explicit full-stack sync so the checks run
against the completed installation without resynchronizing it. It must not replace the
initial installation. Base CI remains the documented lightweight profile.

Both full check commands completed on macOS 14.4 ARM64 with Python 3.12.13 and
uv 0.11.28. They took 287.861507 and 316.237688 seconds respectively, with
overlapping execution. The [ledger](validation.json) retains all measured attempts,
log identities and the unmeasured cost boundary. Linux CI was not executed here.
These software tests consume no new A1, B1 or B2 condition and establish no new
robot capability or comparative advantage.

The next research step remains a consequential deployment incident with its
existing trace and matching source/settings, followed by a competent comparison
under equal information and full known costs. Installing libraries does not
supply that incident evidence.
