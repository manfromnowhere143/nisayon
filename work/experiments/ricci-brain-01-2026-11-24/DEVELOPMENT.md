# Development failures and corrections

These runs are development evidence. Their successes are not added to held-out
sample sizes, and their failures remain available under `artifacts/ricci-brain-01/`.
Source identity is retained by each episode. Earlier pilots are indexed in
[development-ledger.json](development-ledger.json) and
[development-source.json](development-source.json).

The first version completed all eight nominal configurations, then ran 139
sealed episodes before a fairness defect was discovered. Host scheduling changed
which nominal commands passed deadline admission. Two trajectories with **no
recovery decision** diverged at 0.04 s and later had different outcomes. Thus the
apparent action-selection advantage was invalid. The campaign was interrupted;
its partial next episode and all sealed records remain. See
[confounded-campaign-01.json](confounded-campaign-01.json). Fresh held-out
configurations replaced those exposed in this campaign.

Version 2 advances physics under the preceding command for a fixed 20 ms
computation/delivery interval. Actual host costs are still measured but cannot
change a treatment. Its first nominal gate completed 5/8. Inspecting landing
showed a scheduled, unloaded foot being admitted as support. Requiring measured
contact and predicting state to command delivery removed that virtual support;
the next gate completed 0/8 and exposed the trajectory's dependence on it.

A contact-confirmed transition then held COM over the stance foot while extending
the landing trajectory. The initial 25 mm extension was insufficient to load the
foot, producing a retained timeout without an observed fall. A 40 mm bounded
extension, measured touchdown anchor, 2 mm compression target and 20 N acquisition /
5 N release hysteresis improved contact transfer. The 13 s episode horizon includes
a development allowance of two seconds for this transition; lift, step, tilt,
penetration, joint-limit and set-down thresholds were unchanged. Gate 04 completed
6/8. The two remaining runs exhausted their bounded continuation after OSQP
reported `solved inaccurate`; this status did not establish physical infeasibility.

[The retained residual audit](qp-residual-audit-01.json) reconstructed those
solutions from the controller-visible packets at source `6847a01f`. Their original
constraint violations were at most 8.24e-6 in their stated units. A new check of
**every** original constraint was added, including for status `solved`. Its first
uniform 1e-4 numerical tolerance caused 0/8 completions in gate 05. This rejected
millinewton-level force-cone residuals that normal relative solver tolerances admit.
An intermediate uniform 1e-3 check also rejected a retained development episode.
The final numerical allowances distinguish force-cone rows (0.01 N) from the
remaining rows (0.001 in their SI units), with separate dynamics and torque checks.
These allowances were set before the new held-out evaluation. They do not change
physical outcome thresholds. Corrupted solutions are rejected even if the solver
status claims success.

The successful single-case repairs do not substitute for the complete nominal
gate. The current gate and experiment verdict are in [RESULTS.md](RESULTS.md).
The source for the current campaign is `6181707e45c44eeb3ab5e6427821ff0d80c04f15`.
A numerical admission failure, true physical infeasibility, an observed fall and a
censored future are different findings; this packet does not collapse them.

The retrospective audit script is retained as `audit_qp_residuals.py`. It used the
then-current trusted source and does not execute archived producer code. Running
it against a later controller is a new diagnostic, not reproduction of the old
policy's internal solves. Episode replay instead reconstructs recorded actions
and measurements and remains valid across controller revisions when the adapter
schema and MuJoCo version match.
