# Read-only GitHub monitoring

`nisayon engagements` collects changes to a bounded list of GitHub discussions.
It retains versioned snapshots and local review receipts. It cannot send a
message, approve a change, merge code or start an agent. Detection does not
establish that an engineering obligation has been resolved.

The public source omits the research workspace's account, discussion registry,
correspondence and review records. To configure your own checkout, create a
local `work/engagements.json` with the following shape, replacing the example
account and thread with identities you intend to monitor:

```json
{
  "schema": "nisayon.engagements.v1",
  "account": "your-account",
  "interval_seconds": 900,
  "searches": [],
  "threads": [{"key": "owner/repository#1", "purpose": "The decision to follow"}]
}
```

The registry accepts one to 80 distinct threads, at most four searches, and an
interval between 300 and 86,400 seconds. Scanning requires authenticated `gh`.
No schedule is installed by importing the package or installing its wheel.

```sh
nisayon engagements status
nisayon engagements scan
```

Same-repository worktrees share `.nisayon/engagements/` beside the common Git
directory. Reads are serialized, follow pagination and retain changed identities
or incomplete reads as review obligations. A scan is not a simultaneous snapshot
of GitHub. Re-read the live thread before making a separate authorized response.

A review receipt binds to the observed fingerprint. Its dispositions are
`awaiting_owner`, `awaiting_maintainer`, `author_action`, `watch` and `closed`.
Changes to discussion or source identity reopen the local review requirement.
No receipt grants scientific acceptance or transfers an earlier result to new
code automatically. On macOS, `scripts/install_engagement_monitor.py` can install
or remove a local LaunchAgent from its canonical checkout after explicit local
configuration; retained snapshots survive removal.
