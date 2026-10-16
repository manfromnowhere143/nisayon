# N044 bounded routing qualification

Frozen before compiling or executing the routing controls, 16 October 2026.
Source inspection suggests a collision in vla.cpp PR #34 at
42b7ed874567cb753df19de3d726d51b5d99ae63. The server joins each routing frame with
a NUL separator. A DEALER identity containing a trailing NUL and a REQ identity
without it can therefore produce equal keys although ZeroMQ routes them to
different clients. This is a hypothesis about native software, not an observed
robot failure or the cause of either recruited owner's incident.

## Scope and allocation

One bounded local CPU source qualification. Use existing Apple clang 15 and
libzmq 4.3.5. Retrieve a pinned cppzmq header and its MIT license into an isolated
artifact directory, without installing or synchronizing an environment. Extract
the exact envelope_key, send_multipart and recv_multipart functions from the
pinned server, and use its unchanged RequestQueue header. Compile the unchanged
six-function native queue suite. No policy, weights, protobuf validation,
simulator, GPU, robot, cloud allocation or owner task execution.

## Cases and criterion

Drive real in-process ZeroMQ ROUTER/DEALER/REQ sockets, with opaque small payloads
standing in for already validated jobs. Receive both jobs before any worker pop,
representing pending work while inference is occupied. Never launch the full
server or claim its inference/validation path was qualified.

Five transport cases are fixed before outcomes:

1. LATEST: DEALER identity `robot\0` followed by REQ identity `robot`.
2. LATEST: the same distinct peers in reverse request order.
3. LATEST: two ordinary distinct ASCII peers, one DEALER and one REQ.
4. LATEST: two requests from one DEALER with a binary identity.
5. FIFO: the colliding mixed-protocol peer pair.

Distinct-peer cases must retain and serve both requests without a superseded
response. Same-client LATEST must retain only the newest pending request and
return exactly one superseded response to its original peer. Every request must
receive one response via its original unmodified envelope. Bind request identity,
queue result, displaced identity, queue size, pop order and actual client receipts.

Separately enumerate 1,464 distinct frame sequences: first frame is a nonempty
length-1-or-2 string over {NUL, ':', 'a'}, excluding leading NUL, followed by zero,
one or two arbitrary length-0-to-2 frames over that alphabet. Check key
injectivity against exact frame-vector equality. This is a finite algebra
control, not 1,464 robot or network trials, nor a proof of real-world coverage.

## Candidate and comparison

A minimal candidate prefixes each frame with its decimal byte count and ':',
then appends its unchanged bytes. Preserve the full envelope and existing
queue semantics. This is standard unambiguous framing, not a new algorithm.
Run the same controls on original and corrected extraction. Reject a correction
that loses same-client coalescing, changes routing, fails native controls or
collides in the finite pool. Keep the competent native repair as the comparator;
no Nisayon efficiency advantage follows from this correction.

Retain source hashes, exact extraction, compiler/library identity, commands,
process outcomes, failures and known wall time. Unknown model/human/owner costs
remain unknown. On a confirmed native defect, prepare a concise upstream review
with the exact witness and minimal patch under standing targeted correspondence
authority. Do not duplicate recruitment asks. Owner enrollment, fresh task value,
complete comparative effort and separate reuse remain pending.
