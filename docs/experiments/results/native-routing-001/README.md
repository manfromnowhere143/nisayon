# Preserve distinct clients in the async queue

**16 October 2026 · N044 · native transport correction; upstream adoption pending.**

In vla.cpp's proposed async server, two distinct clients can receive the same
internal queue key. If both have pending work, the newer request replaces the
other client's request and that client receives `superseded`. The failure
requires colliding binary envelopes; ordinary distinct ASCII clients passed.
This is a reproduced software defect at PR #34 revision
`42b7ed874567cb753df19de3d726d51b5d99ae63`, not a diagnosed owner deployment failure.

A DEALER with identity bytes `robot\0` supplies one routing frame. A REQ with
identity `robot` supplies its identity and an empty delimiter frame. Appending
a zero byte after each frame makes both keys `72 6f 62 6f 74 00 00`. These are
valid distinct identities under ZeroMQ's [binary routing ID contract](https://libzmq.readthedocs.io/en/latest/zmq_setsockopt.html#zmq-routing-id-set-socket-routing-id).
The [REQ envelope contract](https://libzmq.readthedocs.io/en/latest/zmq_socket.html#zmq-router)
accounts for the empty frame. Both pages were read on 16 October 2026; the
executed library was libzmq 4.3.5.

The [minimal patch](envelope-key.patch) prefixes each frame with its decimal byte
length and a colon, then appends the unchanged frame bytes. This preserves frame
boundaries, including embedded zeros, empty frames and colons. The full response
envelope and queue implementation remain unchanged. Length framing is a standard
native correction, with no algorithmic novelty or Nisayon efficiency claim.

## Executed evidence

The [protocol](PROTOCOL.md) was frozen before compilation or execution. Real
inproc ROUTER, DEALER and REQ sockets drove byte-for-byte extractions of the
upstream receive, key and send functions with its unchanged `RequestQueue`.
Both jobs arrived before a pop, representing pending work while inference is
occupied. Small opaque payloads stand in for already validated jobs.

| Fixed control | Original | Length framing |
|---|---|---|
| LATEST, binary DEALER then REQ | First client incorrectly superseded | Both served |
| LATEST, same peers in reverse order | First client incorrectly superseded | Both served |
| LATEST, ordinary distinct ASCII peers | Both served | Both served |
| LATEST, two requests from the same binary client | Older request superseded | Older request superseded |
| FIFO, the colliding mixed-protocol pair | Both served | Both served |
| Finite pool of 1,464 distinct frame vectors | 1,160 unique keys | 1,464 unique keys |

Transport results improve from 3/5 to 5/5. Actual client receipts bind each
response to its request, status and original envelope. The six unchanged native
queue tests pass. The finite pool is a separate algebra control: its 304 excess
inputs sharing prior keys are not 304 robot failures, and the 1,464 inputs are
not independent deployment trials. Two binary-collision transport cases fail
in the original executable, which deliberately exits 1; the correction exits 0.

The first execution and the final execution after Python formatting have exactly
the same variant results. Both are retained. The native C++ harness and patch
did not change between them. Initial Python style checks required import/UTC
cleanup and formatting; the final driver passes the repository's Ruff checks.

## Reproduction and retained record

[result.json](result.json) contains commands, exit codes, source hashes, extracted
function hashes, per-request queue traces, actual receipts and all final controls.
[raw.tar.gz](raw.tar.gz) retains 58 members: both runs, exact executed drivers,
harness, upstream sources and licenses, function extractions, runtime identity,
logs and protocol. [raw-manifest.json](raw-manifest.json) binds every member.
Five source/header/license blobs were also matched to GitHub Git blob identities;
all six required source/license files have fixed SHA-256 checks in the driver.
[sources.json](sources.json) records revisions and retrieval URLs.

Verify retained bytes without executing another experiment:

```sh
python3 docs/experiments/results/native-routing-001/verify.py
```

For an intentional reproduction, extract the archive to a new directory and
use the existing C++17 compiler, pkg-config and libzmq. No Python dependencies
are needed. The pinned cppzmq 4.10.0 header is in the archive. From the repo root:

```sh
mkdir -p artifacts/native-routing-reproduction
tar -xzf docs/experiments/results/native-routing-001/raw.tar.gz \
  -C artifacts/native-routing-reproduction
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  scripts/experiments/qualify_vla_routing.py \
  --source-dir artifacts/native-routing-reproduction/source \
  --output artifacts/native-routing-reproduction/new-run
```

The driver rejects changed source hashes and an existing output directory.
The qualified local stack was Apple clang 15, libzmq 4.3.5, cppzmq 4.10.0 and
macOS arm64. Other platforms are unqualified. The source retains VinRobotics'
[Apache 2.0 license](VLA_LICENSE.md) and cppzmq's [MIT license](CPPZMQ_LICENSE.txt).

## Cost, delivery and limits

The two complete driver executions took 3.151 and 2.630 seconds, including
compilation and native tests. Nested command times are part of those totals.
These single diagnostic timings establish no performance comparison. Source
research, preparation, correspondence, review, provider charges and prospective
owner integration are outside those clocks; complete effort remains unknown.
Acquisition also encountered a missing `LICENSE` path; the root listing resolved
`LICENSE.md`. No existing environment was installed into or synchronized.

The [upstream report](https://github.com/VinRobotics/vla.cpp/pull/34#issuecomment-6210116834)
contains the exact witness, minimal change, checks and scope. Its published body,
author and destination were read back exactly. No maintainer acceptance or
release is established. This adds a technical engagement; it does not enroll
the PR author or either previously invited prospect.

The harness does not execute protobuf validation, the inference worker, the full
server, a policy or robot task. It does not prove this mechanism explains the
Dragonwing, Orin or G1 reports. Owner participation, fresh task confirmation,
complete comparative effort and separate untouched reuse remain missing. The
next decisive step remains qualification of an interested owner's actual choice
and permitted existing records, within the standing one-incident/four-hour intake.
