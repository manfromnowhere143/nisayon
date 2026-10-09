# Clock declarations: closing the reference's clock-evidence boundary

**Retrospective study record, 20 September 2026, resumed 11:19:22 UTC.** The execution
lane froze four clock-declaration controls before running eight software assignments on
`7022cca` and committed them at `852b1eb` (`../../../../../experiments/results/temporal-integration-001/CLOCK_CONFORMANCE.md`).
With the same events and the same two declarations for the `sensor`/`controller` pair,
the version-2 reference read C02 (fresh relation listed first) as age 20 ms and assigned
contract satisfied, and C03 (stale relation first) as 120 ms and violated. The record
declares no priority. The coordinator's bounded API diagnostic on eleven labelled copies
of the healthy T01 trace added a `TypeError` when `declared_mappings` is the integer 1,
silent acceptance of a non-object list member, of a stamp on an undeclared clock and of a
missing `names` list. This record states the rule that settles the boundary, retains the
before-state on the public path, and reassesses every retained population under the
corrected reference. Nothing here executes the producer, retries a send or measures a
robot; the conventional/selected tie and the historical robot findings are untouched.

Consumed execution delivery: `87ddd5b` by fast-forward (it contains `852b1eb` and the
lane's later admission-conformance and combined-deadline controls). Version-2 module at
consumption: `83b7618a…` (unchanged since `8e54650`).

## The rule

The full statement lives in the evaluation contract
([`docs/evaluation/README.md`](../../../../README.md#clock-declarations-the-rule-and-its-supported-domain)).
In short: a declaration asserts one unit-rate constant-offset relation between two
declared clocks, `t_to ∈ [t_from + offset ± uncertainty]`; the reverse direction is the
same relation; the supported domain holds at most one relation per unordered pair, an
exact repeat counts once, and any other second declaration makes the pair conflicting in
every list order. Conflicting declarations establish no calibration: read jointly, two
different exact offsets are inconsistent; read as alternatives, both 20 ms and 120 ms
would have to lie within 50 ms. Freshness through such a pair is unresolved, unless
same-clock chain evidence alone proves expiry. The admissible-age set must be nonempty
and inside `[0, max_age]` for a fresh verdict; empty is inconsistent, unknown is not
zero. Malformed containers and members are named problems (the trace reads `invalid`),
never exceptions; unsupported fields, unit mismatches and undeclared clocks leave the pair
unmapped and freshness unresolved; `clocks` or `names` absent is a named legacy rule
under which only the clock literally named `controller` is declared.

## Before-state at the consumed source

- `before/assessments.json` (`reassess.py`, recorder `d12a679c`, module `83b7618a…` at
  `87ddd5b`): all populations, now including the six request-binding records, the six
  demonstration records (read by reference from the execution lane's artifact store and
  bound by the canonical digest the committed record carries), the eight clock controls
  and the lane's later eight admission and 24 combined-deadline controls, each separate.
- `before/cli/` with `manifest.json` (`record_cli.py`, one recorder run per input): the
  public command on the eight C-case traces and on seventeen labelled diagnostic copies of
  T01 (`inputs/`, written by `make_inputs.py` from the committed trace, digests in
  `inputs/manifest.json`). Reproduced before any change: C02 unfenced within 20 ms and
  C03 unfenced beyond 120 ms with identical declarations; `mapping_container_scalar`
  exits 1 with `TypeError: 'int' object is not iterable` on the public path;
  `non_object_member`, `undeclared_acquisition_clock`, `missing_clock_names`,
  `unsupported_field`, `duplicate_declaration` and `reverse_direction_equivalent` all read
  freshness satisfied; `negative_uncertainty` reads unresolved through the chain
  contradiction, not through a named defect.

## The correction (version 3, tested source `976c2f7`, module `77e92594…`)

`nisayon.evaluation.temporal` writes `nisayon.temporal-assessment.v3`. The shape of
`temporal_contract` and `predicates` is unchanged; `evidence` gains `clocks` (the parsed
model: controller, names, relations, conflicting and unsupported pairs, undeclared clocks,
diagnostics, problems, legacy rule, supported domain), `clock_diagnostics` and
`identity_conflicts`; `retrospective` gains `chunk_identity`; every `age_readings` row
names its chronology category. Seventeen discriminating tests
(`tests/evaluation/test_evaluation_temporal_clocks.py`) fix each reading, with the
premises stated per block: the conflicting orders and their single-relation controls on
constructed and on the committed C traces; chain evidence proving expiry under a
conflict; nonempty versus empty admissible-age sets and uncertainty widening; exact
equality and one-unit expiry through a mapping at the 2^60 epoch; declaration
permutation on five declaration sets; reverse-direction equivalence; consistent
clock-origin translation with a controller shift of 2^54 and a sensor shift of 2^53+11;
a bijective rename that keeps the controller role; every malformed and unsupported form;
the public command on the scalar container; and the admitted-identity cases.

## Eight clock-case outcomes, before and after

| Assignment | Producer operation | v2 freshness / assigned | v3 freshness / assigned | v3 clock evidence |
|---|---|---|---|---|
| C01 unfenced | dispatch, acknowledged | satisfied / satisfied (20 ms) | satisfied / satisfied (20 ms) | supported |
| C01 conventional | dispatch, acknowledged | satisfied / satisfied | satisfied / satisfied | supported |
| C02 unfenced | dispatch | satisfied / satisfied (20 ms, first match) | **unresolved / unresolved** (`conflicting_declarations`, no age) | conflicting |
| C02 conventional | refuse, age unresolved | satisfied (vacuous) / violated | satisfied (vacuous) / violated | conflicting |
| C03 unfenced | dispatch | violated / violated (120 ms, first match) | **unresolved / unresolved** (`conflicting_declarations`, no age) | conflicting |
| C03 conventional | refuse, age unresolved | satisfied (vacuous) / violated | satisfied (vacuous) / violated | conflicting |
| C04 unfenced | dispatch | violated / violated (120 ms) | violated / violated (120 ms) | supported |
| C04 conventional | refuse, overdue | satisfied (vacuous) / violated | satisfied (vacuous) / violated | supported |

C02 and C03 now read identically in every field the rule governs; the legacy
`temporal_contract` stays violated for all eight through the separate grid criterion, as
before. The conventional refusals of C02/C03 are the producer's frozen policy (refuse an
unsupported relation) and now coincide with the reference's evidence status; C04's
refusal is a correct expiry refusal. The conventional records' `evidence.completeness`
moves from complete to incomplete because the declarations are conflicting evidence
whether or not a dispatch consumed them; no predicate of theirs changes.

## Malformed and unsupported input dispositions (public command, `after/cli/`)

| Input (labelled copy of T01) | Before (`83b7618a…`) | After (`77e92594…`) |
|---|---|---|
| `mapping_container_scalar` (integer 1) | exit 1, `TypeError: 'int' object is not iterable` | exit 0; `temporal_contract` invalid, problem "clocks.declared_mappings is int, not a list; no relation is used"; predicates visible; freshness unresolved |
| `mapping_container_object` | unresolved (accidental) | invalid, named container problem |
| `non_object_member` `[null, fresh]` | satisfied (member silently dropped) | invalid, problem "[0] is not an object"; no relation used (`malformed_declarations`) |
| `negative_uncertainty` | unresolved through a chain contradiction | invalid, problem "uncertainty -1 is negative" |
| `boolean_offset` | unresolved (accidental) | invalid, named numeric problem |
| `unsupported_field` (`rate`) | satisfied (field ignored) | unresolved, `unsupported_declaration`, clock evidence unsupported |
| `unit_mismatch` (declaration in ms) | unresolved (silent) | unresolved, `unit_mismatch` named |
| `undeclared_acquisition_clock` | satisfied | unresolved, `undeclared_clock`; `undeclared_clocks: ["sensor"]` |
| `missing_clock_names` | satisfied (fell back to controller) | unresolved, legacy rule `names_absent` named; the sensor clock is undeclared |
| `no_clocks_object` | unresolved (silent) | unresolved, legacy rule `clocks_absent` named |
| `duplicate_declaration`, `reverse_direction_equivalent` | satisfied (first match) | satisfied; counted once with a `duplicate_declaration` diagnostic |
| `unchanged_healthy`, `single_fresh`, `single_stale`, `conflict_*` | as the C cases | as the C cases |

The coordinator's eleven diagnostic outcomes are reproduced in `before/cli/` and are not
counted as producer evidence.

## Reassessment of every retained population (230 role assignments and 3 prefixes)

`manifest.json` lists each population with every assignment identity and trace digest,
before (`d12a679c`, module `83b7618a…` at `87ddd5b`) and after (`04de904d`, module
`77e92594…` at `976c2f7`), and `comparison.json` names the reason for every changed
predicate; it names all of them.

| Population | n | Predicates changed | Reason |
|---|---|---|---|
| original | 120 | none | |
| exploratory boundaries | 30 | none | |
| precision | 6 | none | |
| ABA reduction | 22 | none | |
| request binding | 6 | none | |
| demonstration (T03 × 6, by reference) | 6 | none | |
| clock conformance | 8 | 2: C02 and C03 unfenced `freshness` → unresolved | conflicting declarations |
| admission conformance | 8 | 1: Y02 conventional `freshness` violated → satisfied (20 ms) | admitted identity |
| combined deadline | 24 | 4: Y02 under all four remedies, `freshness` violated → satisfied (20 ms) | admitted identity |
| interrupted prefixes | 3 | none | |

The 190 records of the execution lane's earlier reconciliation are unchanged in every
predicate, aggregate, assigned reading, alignment and observation-context field; only
the four C02 rows of the combined-deadline population and the two conventional C rows
change `evidence.completeness` to incomplete for the conflicting declarations they carry.
The assignment-8 dispositions, the 59 explained usefulness disagreements, the grid and
assigned criteria, the stricter observation fence, the unattainable T18 target, the null
ABA reduction at its witness definition and the separate A→A property are untouched.
The 13 frozen cases (`cases-v3/`, recorder `0e381520`, 12 of 13 with the retained
disagreement) and the 216-schedule enumeration (`enumeration-v3/`, `44bef52d`, 864 rows
identical) are unchanged; their traces are byte-identical to the originals and are not
copied again. The execution lane's saved version-2 assessment of `clock-conformance-001`
(8 assignments, bound to module `83b7618a…`) is refused by its own reader under version
3 ("Assessment reader, reference or interpreter changed"; `reuse-invalidation.json`,
recorder `43b76ed3`, 285 store files unchanged).

## Delivery provenance (Y02)

The Y02 records deliver a second response under chunk id `c0` bound to a different
request (`q1`, observation acquired at −100 ms); the ordinary producer refuses it
(`chunk_identity_collision`) and sends the original action, value 1, from the observation
acquired at 0 ms. Version 2 rebound `c0` to the refused delivery at arrival and read the
original action's age as 120 ms. Version 3 keeps the identity a chunk was first bound to,
records the second delivery as a pending conflict, and lets the producer's admission
decision resolve it: rejected keeps the queued action's binding (Y02 conventional and the
four combined-deadline Y02 rows read 20 ms, satisfied, with `identity_conflicts` showing
the rejected delivery); admitted rebinds the chunk (Y02 unfenced reads 120 ms, violated,
`chunk_identity` violated); a conflict with no admission decision stays pending,
`chunk_identity` unresolved and completeness incomplete (tested). Y01 and Y04 are
unchanged; Y03's replacement uses a distinct chunk id and is not a conflict. The
premise is stated in the reading: a chunk id names one response, and a queued action
keeps the identity it was admitted with. The producer's `age_guard` is not read.

## Limitations

- The supported clock domain is deliberately narrow: one direct relation per pair, no
  composition, rate, drift, validity interval or selection. A record that needs richer
  calibration semantics reads unresolved, with the category named, until the interface
  declares them; the rule text says what a future field would have to record.
- A conflicting pair is refused even when the two declarations' intervals overlap
  (for example equal offsets with different uncertainties); the bounded rule does not
  intersect or unite them, because the record does not say which reading it means.
- Malformed declarations make the whole trace invalid while every predicate stays
  visible; a producer that wants a partial reading must emit a well-formed list.
- The legacy rules (`clocks` or `names` absent) declare only the controller clock; older
  records that used other clock names without declaring them now read unresolved
  instead of satisfied, which is the intended loss of an unearned verdict.
- Chain lower bounds still depend on the recorded arrival or controller-stamped request
  of the bound observation and the premise that acquisition precedes possession.

## Costs, resources and time

Recorded commands of this assignment: before-reassessment `d12a679c` (0.195 s), 25
before-CLI runs (0.08–0.14 s each; `before/cli/manifest.json`), after-reassessment
`04de904d` (0.240 s), 25 after-CLI runs (`after/cli/manifest.json`), cases `0e381520`
(0.122 s, exit 1 by design), enumeration `44bef52d` (0.267 s), reuse check `43b76ed3`
(0.218 s). Process CPU of the two reassessments: 0.126 s and 0.135 s, far inside the 30
CPU-second suballocation; retained records under this directory about 5.7 MiB, inside
the 16 MiB ceiling. The coordinator's packet (181,108 output bytes, zero source
downloads) is read, not copied. No producer execution, retry, simulator, learned
inference, weights, paid compute, hardware, reserved access, outreach or publication;
DC01 stays six used, two retry slots unused, sixteen unallocated. Full application check
on clean `46a3386` (application source identical to `976c2f7`): recorder `aecbce48`,
245.609 s wall (11:37:16Z to 11:41:22Z), 833 tests passed, 1 skipped, lint, formatting
(339 files) and 107 document checks; free disk 23.8 GB after the run; the temporary
storage peak of this check was not sampled, and the unmeasured peak of the assignment-8
check is not inferred from anything later.

Time: resumed 11:19:22Z. Earlier windows: 03:55:58Z–04:54:35Z and 08:50:32Z–09:36Z;
the pauses between windows (3 h 56 min, then 1 h 43 min) were not work. The five-hour
useful-work request remains unfulfilled by the clock; nothing was padded. Active effort
outside recorded commands is unmeasured.
