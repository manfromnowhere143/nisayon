# Interrupted retained-data workflow

At clean implementation `d14c84d0edfdd2e0939002d3e29f311a8ebeafec`, the
[labelled control](interrupt_before_terminal.py) exited with code 73 immediately
before consuming its first terminal decision. The native source suite remained
read only. All twenty arm declarations had already been synced, and the first
terminal-start receipt survived the exit. No simulator or model was called.

The [interrupted recovery](interrupted-recovery.json) preserves all twenty
assignments: one `terminal_started_outcome_unknown` and nineteen
`declared_awaiting_terminal`. The separate [complete recovery](complete-recovery.json)
finds twenty retained terminal records in `retained-declarations-002`. Both have
zero binding findings. These are exposed historical records and development
statements, not an estimate of repair correctness or a fresh experiment.

| Command | Record | Wall seconds |
|---|---|---:|
| Deliberate process interruption | `f319543e8dd1472cb223cffc0108fdf0` | 0.182126 |
| Read interrupted state | `c2472a4e6d2a4636b4fc5cada670b7ca` | 0.129589 |
| Read complete state | `cf4585efea1c4a799a3bd6e8a698deba` | 0.238692 |

Exact commands and logs are retained under `../engine-continuation-checks-001/`
by those IDs. The first command is intentionally nonzero and remains charged.
Writer walls in the recovery documents are nested components, not extra costs.
The inspection never resumes a trajectory, retries terminal work or supplies
missing timing. The original command record provides its outer wall.
