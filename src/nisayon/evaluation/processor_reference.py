"""Reference semantics for a LeRobot-style normalization processor step.

The question this module answers is narrow: given a processor configuration (features,
modes, epsilon), a flat statistics store and a candidate key-resolution rule, what must
the pinned processor do to one feature in one direction, and does an observed float32
output agree with that? It is written from the processor contract in
``normalize_processor.py`` at LeRobot ``5aa74557`` (sha256 ``f0cd88be…``) and from the
saved-artifact layout, not from any Nisayon executor. It never reads a producer's own
verdict or bound key to decide an expectation.

Expected values are computed in exact rational arithmetic from the float32 statistics
and the float32 input, forward ``(x − mean) / (std + eps)`` and inverse
``x · std + mean``; a bit-level float32 emulation (one rounding per elementwise
operation) is reported beside them. Acceptance uses four times the sum of the float32
units in the last place of every rounded intermediate and of the result, plus an absolute
floor of ``1e-6``; near a fixed point the rounded product dominates that sum. A witness
whose expected output equals its input within that tolerance is vacuous: it cannot tell a
working transform from a skipped one.

Nothing here measures a robot task. A supported software correction of the processor is
not a recovered deployment.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from . import codes
from .schema import Malformed, load_json

SOURCE_COMMIT = "5aa74557f84c54d4b458f8b9643c5aa2982acfed"
SOURCE_SHA256 = "f0cd88bec4c954a93ba1cc90300473b96eb177762789c1780cf07801fc1af9d6"
OBSERVATION_SCHEMA = "nisayon.processor-observation.v1"
ASSESSMENT_SCHEMA = "nisayon.processor-reference.assessment.v2"
DECISION_RULE = "external-decision-001/v2"
RULE_CHANGES = (
    "v2 (20 September 2026, after the label-only promotion was reproduced): a "
    "stats_provenance label is a declaration that is retained, reported and compared with "
    "what the evaluator established; it is never a premise of the deployment binding",
    "v2: four facts are reported separately per candidate and feature: numeric agreement, "
    "byte provenance, interpretation and selection; byte provenance is established only from "
    "statistics the evaluator read from, or matched element for element against, the "
    "digest-verified artifact; interpretation and selection are not carried by the input "
    "contract, so a supported deployment binding is unreachable from it and the assessment "
    "says so with the missing inputs named",
    "v2: the supported_software_correction outcome and the unresolved deployment conclusion "
    "are unchanged; a declared label the evaluator cannot establish is a named finding, not a "
    "process failure",
)

IDENTITY = "IDENTITY"
MEAN_STD = "MEAN_STD"
SUPPORTED_MODES = {IDENTITY, MEAN_STD, "MIN_MAX", "QUANTILES", "QUANTILE10"}
REQUIRED_STATS = {
    MEAN_STD: ("mean", "std"),
    "MIN_MAX": ("min", "max"),
    "QUANTILES": ("q01", "q99"),
    "QUANTILE10": ("q10", "q90"),
}
ACTION_TYPE = "ACTION"
ACTION_KEY = "action"
CANDIDATES = ("as_is", "suffix_match", "explicit_override")
DIRECTIONS = ("forward", "inverse")
PROCESSORS = ("preprocessor", "postprocessor")
CLASSES = (
    "identity_mode",
    "skipped_no_stats",
    "transformed",
    "ambiguous",
    "error",
    "unsupported_mode",
    "not_applicable",
)
OUTCOMES = (
    "supported_software_correction",
    "rejected_candidate",
    "invalid_input",
    "unresolved",
)
ULP_TOLERANCE = 4
ABSOLUTE_FLOOR = Fraction(1, 10**6)
DEFAULT_EPS = 1e-8
# Declaration vocabulary for stats_provenance. A label says what the record's author claims
# about the statistics; the evaluator records it and checks what it can, and no label
# decides the deployment binding.
STATS_PROVENANCE = {
    "artifact": "claimed: statistics read from the retained processor state file",
    "reporter_transcription": "claimed: numbers transcribed in the public issue",
    "dataset_metadata": "claimed: statistics from a named dataset's metadata",
    "synthetic_control": "claimed: constructed for a control; no deployment meaning",
    "verified_training_statistics": "claimed: read from the training artifact under custody",
}
# Labels that assert more than an origin the evaluator could establish from its inputs.
CLAIMING_LABELS = {"artifact", "dataset_metadata", "verified_training_statistics"}
BYTE_PROVENANCE = (
    "established_from_artifact",
    "matches_artifact_set",
    "not_established",
    "not_applicable",
)
NOT_CARRIED = "not_carried_by_contract"


# --- float32 helpers -------------------------------------------------------------------


def f32(value: float) -> float:
    """Round a Python float to the nearest float32 (raises on overflow)."""
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def ulp32(value: float) -> Fraction:
    """The float32 unit in the last place at ``value``."""
    if value == 0.0 or not math.isfinite(value):
        return Fraction(2) ** -149
    exponent = math.frexp(abs(value))[1]
    return Fraction(2) ** max(exponent - 24, -149)


def tolerance(
    direction: str, x: Fraction, mean: Fraction, std: Fraction, eps: Fraction
) -> Fraction:
    """Acceptance tolerance for one element: every rounding on the float32 path, propagated.

    Inverse ``x·std + mean`` rounds the product and the sum; forward ``(x − mean)/(std + eps)``
    rounds the difference, the denominator and the quotient. Each rounding is at most half
    a unit in the last place of its own magnitude, so a product far larger than the final
    output (cancellation near a fixed point) contributes far more than the output's ulp.
    The bound is ``ULP_TOLERANCE`` times the sum of those units plus an absolute floor.
    """
    if direction == "inverse":
        product = x * std
        result = product + mean
        units = ulp32(float(product)) + ulp32(float(result))
    else:
        denominator = std + eps
        difference = x - mean
        result = difference / denominator
        units = ulp32(float(difference)) / abs(denominator) + ulp32(float(result))
        if std != 0:
            units += abs(result) * ulp32(float(std)) / abs(std)
    return ULP_TOLERANCE * units + ABSOLUTE_FLOOR


def _fraction(value: object, path: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise Malformed(path, f"expected a number, found {type(value).__name__}")
    if not math.isfinite(value):
        raise Malformed(path, "expected a finite number")
    return Fraction(f32(value))


def _numbers(value: object, path: str) -> list[Fraction]:
    if not isinstance(value, list) or not value:
        raise Malformed(path, "expected a nonempty list of numbers")
    return [_fraction(item, f"{path}[{index}]") for index, item in enumerate(value)]


def _render(value: Fraction) -> float:
    return float(value)


# --- safetensors container --------------------------------------------------------------

_DTYPES = {"F32": ("f", 4), "F64": ("d", 8)}


def read_safetensors(data: bytes) -> dict[str, dict]:
    """Parse a safetensors container: ``{name: {dtype, shape, values}}`` for F32/F64.

    Only the container format is interpreted (8-byte little-endian header length, a JSON
    header, raw little-endian data). Other dtypes are kept with ``values: None`` and their
    dtype so a reader can report them rather than guess.
    """
    if len(data) < 8:
        raise Malformed("safetensors", f"container shorter than a header length ({len(data)} B)")
    (length,) = struct.unpack("<Q", data[:8])
    if 8 + length > len(data):
        raise Malformed("safetensors", f"header length {length} exceeds {len(data) - 8} B")
    try:
        header = json.loads(data[8 : 8 + length].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Malformed("safetensors.header", f"invalid JSON header: {error}") from error
    if not isinstance(header, dict):
        raise Malformed("safetensors.header", "header is not an object")
    body = data[8 + length :]
    tensors: dict[str, dict] = {}
    for name, entry in header.items():
        if name == "__metadata__":
            continue
        path = f"safetensors.header.{name}"
        if not isinstance(entry, dict):
            raise Malformed(path, "tensor entry is not an object")
        dtype = entry.get("dtype")
        shape = entry.get("shape")
        offsets = entry.get("data_offsets")
        if not isinstance(dtype, str) or not isinstance(shape, list):
            raise Malformed(path, "missing dtype or shape")
        if (
            not isinstance(offsets, list)
            or len(offsets) != 2
            or not all(isinstance(o, int) and o >= 0 for o in offsets)
            or offsets[1] < offsets[0]
            or offsets[1] > len(body)
        ):
            raise Malformed(path, f"invalid data_offsets {offsets!r} for {len(body)} data bytes")
        count = 1
        for dim in shape:
            if not isinstance(dim, int) or dim < 0:
                raise Malformed(path, f"invalid shape {shape!r}")
            count *= dim
        values = None
        if dtype in _DTYPES:
            code, width = _DTYPES[dtype]
            if offsets[1] - offsets[0] != count * width:
                raise Malformed(
                    path, f"{count} × {width} B does not match {offsets[1] - offsets[0]} data bytes"
                )
            raw = body[offsets[0] : offsets[1]]
            values = [
                f32(v) if dtype == "F32" else v for v in struct.unpack(f"<{count}{code}", raw)
            ]
        tensors[name] = {"dtype": dtype, "shape": list(shape), "values": values}
    return tensors


def write_safetensors(tensors: dict[str, list[float]], *, dtype: str = "F32") -> bytes:
    """Serialize flat float vectors as a safetensors container (for controls)."""
    code, width = _DTYPES[dtype]
    header: dict[str, dict] = {}
    body = bytearray()
    for name, values in tensors.items():
        start = len(body)
        body += struct.pack(f"<{len(values)}{code}", *values)
        header[name] = {"dtype": dtype, "shape": [len(values)], "data_offsets": [start, len(body)]}
    text = json.dumps(header, separators=(",", ":")).encode("utf-8")
    text += b" " * (-(8 + len(text)) % 8)
    return struct.pack("<Q", len(text)) + text + bytes(body)


def flat_statistics(tensors: dict[str, dict]) -> dict[str, dict[str, list[Fraction] | None]]:
    """Group flat ``feature.stat`` names the way the pinned ``load_state_dict`` does.

    The contract splits each flat key on its last dot (``normalize_processor.py`` lines
    226–234): ``so100.buffer.action.mean`` becomes feature key ``so100.buffer.action`` and
    statistic ``mean``. Insertion order is preserved because the reporter's candidate
    resolves ambiguity by iteration order.
    """
    grouped: dict[str, dict[str, list[Fraction] | None]] = {}
    for flat_key, entry in tensors.items():
        if "." not in flat_key:
            raise Malformed(f"statistics.{flat_key}", "flat key has no '.stat' suffix")
        key, stat = flat_key.rsplit(".", 1)
        values = entry.get("values")
        grouped.setdefault(key, {})[stat] = (
            None if values is None else [Fraction(f32(v)) for v in values]
        )
    return grouped


# --- processor configuration ------------------------------------------------------------


@dataclass(frozen=True)
class Feature:
    name: str
    type: str
    shape: tuple[int, ...]


@dataclass(frozen=True)
class ProcessorSpec:
    role: str
    step_index: int
    registry_name: str
    features: dict[str, Feature]
    norm_map: dict[str, str]
    eps: Fraction
    normalize_observation_keys: frozenset[str] | None
    state_file: str | None

    def mode(self, feature: Feature) -> str:
        return self.norm_map.get(feature.type, IDENTITY)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "step_index": self.step_index,
            "registry_name": self.registry_name,
            "features": {
                name: {"type": f.type, "shape": list(f.shape)} for name, f in self.features.items()
            },
            "norm_map": dict(self.norm_map),
            "eps": float(self.eps),
            "normalize_observation_keys": (
                None
                if self.normalize_observation_keys is None
                else sorted(self.normalize_observation_keys)
            ),
            "state_file": self.state_file,
        }


NORMALIZER_STEPS = {
    "preprocessor": "normalizer_processor",
    "postprocessor": "unnormalizer_processor",
}


def parse_processor_config(document: object, role: str, *, path: str = "$") -> ProcessorSpec:
    """Locate the (un)normalizer step of a saved ``PolicyProcessorPipeline`` config.

    The saved layout is ``{"name", "steps": [{"registry_name", "config", "state_file"}]}``
    with ``config = {"eps", "features": {name: {"type", "shape"}}, "norm_map": {type: mode},
    "normalize_observation_keys"?}``. Anything else is ``Malformed`` with the path.
    """
    if role not in PROCESSORS:
        raise Malformed(path, f"role must be one of {PROCESSORS}")
    if not isinstance(document, dict):
        raise Malformed(path, "expected an object")
    steps = document.get("steps")
    if not isinstance(steps, list):
        raise Malformed(f"{path}.steps", "expected a list of steps")
    wanted = NORMALIZER_STEPS[role]
    found = [
        (index, step)
        for index, step in enumerate(steps)
        if isinstance(step, dict) and step.get("registry_name") == wanted
    ]
    if len(found) != 1:
        raise Malformed(f"{path}.steps", f"expected exactly one {wanted} step, found {len(found)}")
    index, step = found[0]
    config = step.get("config")
    step_path = f"{path}.steps[{index}].config"
    if not isinstance(config, dict):
        raise Malformed(step_path, "expected a config object")
    raw_features = config.get("features")
    if not isinstance(raw_features, dict) or not raw_features:
        raise Malformed(f"{step_path}.features", "expected a nonempty object")
    features: dict[str, Feature] = {}
    for name, entry in raw_features.items():
        fpath = f"{step_path}.features.{name}"
        if not isinstance(entry, dict) or not isinstance(entry.get("type"), str):
            raise Malformed(fpath, "expected {type, shape}")
        shape = entry.get("shape")
        if not isinstance(shape, list) or not all(isinstance(d, int) and d >= 0 for d in shape):
            raise Malformed(f"{fpath}.shape", f"invalid shape {shape!r}")
        features[name] = Feature(name, entry["type"], tuple(shape))
    raw_map = config.get("norm_map")
    if not isinstance(raw_map, dict):
        raise Malformed(f"{step_path}.norm_map", "expected an object")
    norm_map: dict[str, str] = {}
    for ftype, mode in raw_map.items():
        if not isinstance(mode, str):
            raise Malformed(f"{step_path}.norm_map.{ftype}", "expected a mode string")
        norm_map[ftype] = mode
    eps_raw = config.get("eps", DEFAULT_EPS)
    if (
        isinstance(eps_raw, bool)
        or not isinstance(eps_raw, int | float)
        or not math.isfinite(eps_raw)
    ):
        raise Malformed(f"{step_path}.eps", "expected a finite number")
    keys_raw = config.get("normalize_observation_keys")
    keys = None
    if keys_raw is not None:
        if not isinstance(keys_raw, list) or not all(isinstance(k, str) for k in keys_raw):
            raise Malformed(f"{step_path}.normalize_observation_keys", "expected a list of names")
        keys = frozenset(keys_raw)
    state_file = step.get("state_file")
    if state_file is not None and not isinstance(state_file, str):
        raise Malformed(f"{path}.steps[{index}].state_file", "expected a string")
    return ProcessorSpec(
        role, index, wanted, features, norm_map, Fraction(eps_raw), keys, state_file
    )


# --- key resolution per candidate -------------------------------------------------------


def resolve_key(key: str, stats_keys: list[str], candidate: str) -> tuple[str | None, list[str]]:
    """Which statistics key a candidate binds to a feature key, and every match.

    ``as_is`` and ``explicit_override`` use the pinned exact lookup (line 330). The
    reporter's ``suffix_match`` returns the exact key, else the keys ending in ``"." + key``
    or ``"_" + key`` in store order, taking the first when several match. The second
    element lists every match so ambiguity is visible.
    """
    if candidate not in CANDIDATES:
        raise Malformed("candidate", f"expected one of {CANDIDATES}, found {candidate!r}")
    if key in stats_keys:
        return key, [key]
    if candidate != "suffix_match":
        return None, []
    matches = [k for k in stats_keys if k.endswith(f".{key}") or k.endswith(f"_{key}")]
    return (matches[0] if matches else None), matches


# --- expectations ------------------------------------------------------------------------


@dataclass(frozen=True)
class Expectation:
    feature: str
    feature_type: str
    processor: str
    direction: str
    candidate: str
    mode: str
    klass: str
    bound_key: str | None
    matches: tuple[str, ...]
    detail: str
    stats: dict[str, list[Fraction]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "feature": self.feature,
            "feature_type": self.feature_type,
            "processor": self.processor,
            "direction": self.direction,
            "candidate": self.candidate,
            "mode": self.mode,
            "class": self.klass,
            "bound_key": self.bound_key,
            "matches": list(self.matches),
            "detail": self.detail,
        }


def applicable(spec: ProcessorSpec, feature: Feature, direction: str) -> tuple[bool, str]:
    """Whether the pinned step touches this feature in this direction at inference.

    A normalizer (preprocessor) transforms observation features forward and, only when a
    transition carries an action, the action forward; an unnormalizer (postprocessor)
    transforms the action inversely and observation features inversely only when present.
    At inference the preprocessor receives observations and the postprocessor an action.
    """
    is_action = feature.type == ACTION_TYPE
    if spec.role == "preprocessor":
        if direction != "forward":
            return False, "a normalizer step only applies the forward transform"
        if is_action:
            if feature.name != ACTION_KEY:
                return False, "the action lookup uses the constant key 'action' (line 299)"
            return (
                True,
                "action forward: only when the transition carries an action (training or a "
                "diagnostic round trip); not an inference obligation",
            )
        if (
            spec.normalize_observation_keys is not None
            and feature.name not in spec.normalize_observation_keys
        ):
            return False, "feature excluded by normalize_observation_keys"
        return True, "observation feature, forward"
    if direction != "inverse":
        return False, "an unnormalizer step only applies the inverse transform"
    if is_action:
        if feature.name != ACTION_KEY:
            return False, "the action lookup uses the constant key 'action' (line 299)"
        return True, "policy action, inverse"
    return False, "the postprocessor unnormalizes observations only when a transition carries them"


def expectation(
    spec: ProcessorSpec,
    statistics: dict[str, dict[str, list[Fraction] | None]],
    feature_name: str,
    direction: str,
    candidate: str,
) -> Expectation:
    """The class of behaviour the pinned code must show, from contract and bytes alone."""
    if direction not in DIRECTIONS:
        raise Malformed("direction", f"expected one of {DIRECTIONS}, found {direction!r}")
    feature = spec.features.get(feature_name)
    if feature is None:
        return Expectation(
            feature_name,
            "?",
            spec.role,
            direction,
            candidate,
            "?",
            "not_applicable",
            None,
            (),
            "feature is not declared in the processor configuration",
        )
    ok, why = applicable(spec, feature, direction)
    mode = spec.mode(feature)
    base = (feature.name, feature.type, spec.role, direction, candidate, mode)
    if not ok:
        return Expectation(*base, "not_applicable", None, (), why)
    if mode == IDENTITY:
        return Expectation(
            *base, "identity_mode", None, (), "mode IDENTITY: unchanged output is correct"
        )
    lookup_key = ACTION_KEY if feature.type == ACTION_TYPE else feature.name
    bound, matches = resolve_key(lookup_key, list(statistics), candidate)
    if bound is None:
        return Expectation(
            *base,
            "skipped_no_stats",
            None,
            tuple(matches),
            f"no statistics key resolves {lookup_key!r}: the pinned step returns the input",
        )
    if mode not in SUPPORTED_MODES:
        return Expectation(
            *base,
            "unsupported_mode",
            bound,
            tuple(matches),
            f"mode {mode!r} raises ValueError in the pinned step (line 339)",
        )
    entry = statistics[bound]
    required = REQUIRED_STATS[mode]
    missing = [name for name in required if entry.get(name) is None]
    if missing:
        return Expectation(
            *base,
            "error",
            bound,
            tuple(matches),
            f"{mode} needs {required}; {missing} missing or unreadable: the pinned step raises",
        )
    stats = {name: list(entry[name] or []) for name in required}
    lengths = {len(v) for v in stats.values()}
    if len(lengths) != 1:
        return Expectation(
            *base, "error", bound, tuple(matches), f"statistic lengths differ {lengths}"
        )
    if len(matches) > 1:
        return Expectation(
            *base,
            "ambiguous",
            bound,
            tuple(matches),
            f"{len(matches)} keys match {lookup_key!r}; the candidate binds the first in store order",
            stats,
        )
    if mode != MEAN_STD:
        return Expectation(
            *base,
            "transformed",
            bound,
            tuple(matches),
            f"{mode} transform with {bound!r} (value expectation not implemented for this mode)",
            stats,
        )
    return Expectation(
        *base, "transformed", bound, tuple(matches), f"MEAN_STD with {bound!r}", stats
    )


# --- expected values ---------------------------------------------------------------------


@dataclass(frozen=True)
class ExpectedOutput:
    exact: list[Fraction]
    float32: list[float]
    tolerances: list[Fraction]
    vacuous_elements: list[bool]

    @property
    def vacuous(self) -> bool:
        return all(self.vacuous_elements)

    def to_dict(self) -> dict:
        return {
            "exact": [_render(v) for v in self.exact],
            "float32_emulation": list(self.float32),
            "tolerance": [_render(v) for v in self.tolerances],
            "vacuous_elements": list(self.vacuous_elements),
            "vacuous": self.vacuous,
        }


def mean_std_values(
    values: list[Fraction], mean: list[Fraction], std: list[Fraction], eps: Fraction, direction: str
) -> ExpectedOutput:
    """Exact and float32-emulated MEAN_STD outputs, with tolerance and vacuity per element.

    Forward divides by ``std + eps`` and inverse multiplies by ``std`` alone, exactly as the
    pinned step does (lines 357–362); the two are therefore not exact inverses.
    """
    if len(values) != len(mean) or len(mean) != len(std):
        raise Malformed("input", f"{len(values)} values against {len(mean)} statistics")
    exact: list[Fraction] = []
    emulated: list[float] = []
    tolerances: list[Fraction] = []
    vacuous: list[bool] = []
    eps32 = f32(float(eps))
    for x, m, s in zip(values, mean, std, strict=True):
        if direction == "forward":
            if s + eps == 0:
                raise Malformed("statistics", "std + eps is zero: the pinned path divides by zero")
            value = (x - m) / (s + eps)
            denominator = f32(float(s) + eps32)
            emulate = f32(f32(float(x) - float(m)) / denominator) if denominator else math.inf
        else:
            value = x * s + m
            emulate = f32(f32(float(x) * float(s)) + float(m))
        tol = tolerance(direction, x, m, s, eps)
        exact.append(value)
        emulated.append(emulate)
        tolerances.append(tol)
        vacuous.append(abs(value - x) <= tol)
    return ExpectedOutput(exact, emulated, tolerances, vacuous)


def fixed_point(
    mean: list[Fraction], std: list[Fraction], eps: Fraction, direction: str
) -> list[Fraction | None]:
    """Inputs the transform maps to themselves, elementwise (None where none exists)."""
    points: list[Fraction | None] = []
    for m, s in zip(mean, std, strict=True):
        denominator = (1 - s - eps) if direction == "forward" else (1 - s)
        points.append(None if denominator == 0 else m / denominator)
    return points


def compare(expected: ExpectedOutput, observed: list[Fraction]) -> dict:
    """Observed float32 output against the expectation: tolerance, ulps and bit equality."""
    if len(observed) != len(expected.exact):
        return {
            "within_tolerance": False,
            "bit_exact_float32": False,
            "detail": f"{len(observed)} observed values against {len(expected.exact)} expected",
        }
    errors = [abs(o - e) for o, e in zip(observed, expected.exact, strict=True)]
    within = all(err <= tol for err, tol in zip(errors, expected.tolerances, strict=True))
    ulps = [
        float(err / ulp32(float(e))) if math.isfinite(float(e)) else math.inf
        for err, e in zip(errors, expected.exact, strict=True)
    ]
    exact32 = all(float(o) == e for o, e in zip(observed, expected.float32, strict=True))
    return {
        "within_tolerance": within,
        "max_ulp_error": max(ulps) if ulps else 0.0,
        "bit_exact_float32": exact32,
        "detail": "observed against exact rational expectation with the frozen tolerance",
    }


# --- observation records -----------------------------------------------------------------


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _input_bytes(entry: object, path: str, root: Path | None) -> tuple[bytes, dict]:
    data = entry if isinstance(entry, dict) else None
    if data is None:
        raise Malformed(path, "expected {path, sha256, bytes}")
    rel = data.get("path")
    digest = data.get("sha256")
    if not isinstance(rel, str) or not isinstance(digest, str):
        raise Malformed(path, "expected string path and sha256")
    location = Path(rel)
    if not location.is_absolute() and root is not None:
        location = root / location
    if not location.exists():
        raise Malformed(f"{path}.path", f"missing file {location}")
    raw = location.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    identity = {
        "path": str(location),
        "bytes": len(raw),
        "sha256": actual,
        "declared_sha256": digest,
        "digest_matches": actual == digest,
    }
    if "bytes" in data:
        identity["declared_bytes"] = data["bytes"]
        identity["bytes_match"] = data["bytes"] == len(raw)
    return raw, identity


def _statistics_from_values(
    document: object, path: str
) -> dict[str, dict[str, list[Fraction] | None]]:
    if not isinstance(document, dict) or not document:
        raise Malformed(path, "expected {feature: {stat: [numbers]}}")
    result: dict[str, dict[str, list[Fraction] | None]] = {}
    for key, entry in document.items():
        if not isinstance(entry, dict) or not entry:
            raise Malformed(f"{path}.{key}", "expected {stat: [numbers]}")
        result[key] = {
            stat: _numbers(values, f"{path}.{key}.{stat}") for stat, values in entry.items()
        }
    return result


def load_observation(document: object, root: Path | None = None) -> dict:
    """Parse a ``nisayon.processor-observation.v1`` record and its input bytes.

    Returns the parsed specs, the statistics per processor (from the retained state files
    or, for ``explicit_override`` executions, from the record's override values), the
    executions and the producer's decision. Byte identities are verified against the
    declared digests; a mismatch is a finding, not an exception.
    """
    if not isinstance(document, dict):
        raise Malformed("$", "expected an object")
    if document.get("schema") != OBSERVATION_SCHEMA:
        raise Malformed(
            "$.schema", f"expected {OBSERVATION_SCHEMA}, found {document.get('schema')!r}"
        )
    arm = document.get("arm")
    if arm not in ("A", "B"):
        raise Malformed("$.arm", "expected 'A' or 'B'")
    inputs = document.get("inputs")
    if not isinstance(inputs, dict):
        raise Malformed("$.inputs", "expected an object")
    identities: dict[str, dict] = {}
    specs: dict[str, ProcessorSpec] = {}
    statistics: dict[str, dict[str, dict[str, list[Fraction] | None]]] = {}
    tensors_by_role: dict[str, dict[str, dict]] = {}
    for role in PROCESSORS:
        raw, identity = _input_bytes(inputs.get(f"{role}_config"), f"$.inputs.{role}_config", root)
        identities[f"{role}_config"] = identity
        try:
            config = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise Malformed(f"$.inputs.{role}_config", f"invalid JSON: {error}") from error
        specs[role] = parse_processor_config(config, role, path=f"$.inputs.{role}_config")
        raw, identity = _input_bytes(inputs.get(f"{role}_stats"), f"$.inputs.{role}_stats", root)
        identities[f"{role}_stats"] = identity
        tensors = read_safetensors(raw)
        tensors_by_role[role] = tensors
        statistics[role] = flat_statistics(tensors)
    source = inputs.get("processor_source")
    if source is not None:
        raw, identity = _input_bytes(source, "$.inputs.processor_source", root)
        identity["pinned_sha256_matches"] = identity["sha256"] == SOURCE_SHA256
        identities["processor_source"] = identity
    executions = document.get("executions")
    if not isinstance(executions, list):
        raise Malformed("$.executions", "expected a list")
    parsed: list[dict] = []
    for index, item in enumerate(executions):
        path = f"$.executions[{index}]"
        if not isinstance(item, dict):
            raise Malformed(path, "expected an object")
        candidate = item.get("candidate")
        if candidate not in CANDIDATES:
            raise Malformed(f"{path}.candidate", f"expected one of {CANDIDATES}")
        processor = item.get("processor")
        if processor not in PROCESSORS:
            raise Malformed(f"{path}.processor", f"expected one of {PROCESSORS}")
        direction = item.get("direction")
        if direction not in DIRECTIONS:
            raise Malformed(f"{path}.direction", f"expected one of {DIRECTIONS}")
        feature = item.get("feature")
        if not isinstance(feature, str) or not feature:
            raise Malformed(f"{path}.feature", "expected a feature name")
        status = item.get("status")
        if status not in ("completed", "error", "interrupted"):
            raise Malformed(f"{path}.status", "expected completed, error or interrupted")
        values = _numbers(item.get("input"), f"{path}.input")
        output = None
        if status == "completed":
            output = _numbers(item.get("output"), f"{path}.output")
        override = None
        if candidate == "explicit_override":
            override = _statistics_from_values(item.get("override_stats"), f"{path}.override_stats")
        provenance = item.get("stats_provenance", "artifact")
        if provenance not in STATS_PROVENANCE:
            raise Malformed(
                f"{path}.stats_provenance", f"expected one of {sorted(STATS_PROVENANCE)}"
            )
        order = item.get("stats_order")
        if order is not None and (
            not isinstance(order, list) or not all(isinstance(k, str) for k in order)
        ):
            raise Malformed(f"{path}.stats_order", "expected a list of statistics keys")
        parsed.append(
            {
                "id": str(item.get("id", f"execution-{index}")),
                "candidate": candidate,
                "processor": processor,
                "feature": feature,
                "direction": direction,
                "status": status,
                "error": item.get("error"),
                "input": values,
                "output": output,
                "override_stats": override,
                "stats_provenance": provenance,
                "stats_order": order,
            }
        )
    decision = document.get("decision")
    if decision is not None and not isinstance(decision, dict):
        raise Malformed("$.decision", "expected an object")
    reference = document.get("reference_statistics")
    if reference is not None:
        if not isinstance(reference, dict):
            raise Malformed("$.reference_statistics", "expected {provenance, values}")
        provenance = reference.get("provenance")
        if provenance not in STATS_PROVENANCE:
            raise Malformed(
                "$.reference_statistics.provenance", f"expected one of {sorted(STATS_PROVENANCE)}"
            )
        reference = {
            "provenance": provenance,
            "values": _statistics_from_values(
                reference.get("values"), "$.reference_statistics.values"
            ),
        }
    return {
        "arm": arm,
        "incident": document.get("incident"),
        "identities": identities,
        "specs": specs,
        "statistics": statistics,
        "tensors": tensors_by_role,
        "executions": parsed,
        "decision": decision,
        "reference_statistics": reference,
    }


# --- assessment --------------------------------------------------------------------------


def _ordered(stats: dict, order: list[str] | None) -> dict:
    if not order:
        return stats
    unknown = [k for k in order if k not in stats]
    if unknown:
        raise Malformed("stats_order", f"keys not in the retained store: {unknown}")
    return {k: stats[k] for k in order} | {k: v for k, v in stats.items() if k not in order}


def byte_provenance(expected: Expectation, artifact: dict, candidate: str) -> dict:
    """What the evaluator itself establishes about where the bound statistics came from.

    For ``as_is`` and ``suffix_match`` the bound statistics were read by this module from
    the digest-verified state file. For an explicit override they were supplied by the
    record; they count as artifact bytes only when every required statistic equals,
    element for element, one statistics set this module read from the verified artifact.
    Anything else is not established. Nothing here says which model, dataset or feature
    the statistics belong to, or that a deployment selected them.
    """
    if expected.klass not in ("transformed", "ambiguous") or not expected.stats:
        return {"status": "not_applicable", "artifact_key": None}
    if candidate != "explicit_override":
        return {"status": "established_from_artifact", "artifact_key": expected.bound_key}
    for key, entry in artifact.items():
        if all(
            entry.get(name) is not None and list(entry[name]) == list(values)
            for name, values in expected.stats.items()
        ):
            return {"status": "matches_artifact_set", "artifact_key": key}
    return {"status": "not_established", "artifact_key": None}


def _assess_execution(execution: dict, spec: ProcessorSpec, stats: dict) -> dict:
    if execution["candidate"] == "explicit_override":
        store = execution["override_stats"]
    else:
        store = _ordered(stats, execution["stats_order"])
    expected = expectation(
        spec, store, execution["feature"], execution["direction"], execution["candidate"]
    )
    row = {
        "id": execution["id"],
        "candidate": execution["candidate"],
        "processor": execution["processor"],
        "feature": execution["feature"],
        "direction": execution["direction"],
        "status": execution["status"],
        "expected": expected.to_dict(),
        "bound_stats": {
            name: [float(v) for v in values] for name, values in expected.stats.items()
        },
        "byte_provenance": byte_provenance(expected, stats, execution["candidate"])
        | {"declared": execution["stats_provenance"]},
        "agreement": None,
        "vacuous": None,
        "findings": [],
    }
    findings = row["findings"]
    if expected.klass == "not_applicable":
        findings.append(
            {
                "code": codes.PREDICATE_UNMEASURABLE,
                "severity": codes.INFO,
                "detail": expected.detail,
            }
        )
        row["agreement"] = "not_applicable"
        return row
    if expected.klass in ("error", "unsupported_mode"):
        if execution["status"] == "error":
            row["agreement"] = "agrees"
        elif execution["status"] == "completed":
            row["agreement"] = "disagrees"
            findings.append(
                {
                    "code": codes.REPRODUCTION_NOT_FIXED,
                    "severity": codes.INVALID,
                    "detail": "the pinned step raises here; a completed output is not its behaviour",
                }
            )
        else:
            row["agreement"] = "unresolved"
        return row
    if execution["status"] != "completed":
        row["agreement"] = "unresolved"
        findings.append(
            {
                "code": codes.PROCESS_INCOMPLETE,
                "severity": codes.UNRESOLVED,
                "detail": f"execution {execution['status']}: {execution.get('error') or 'no output'}",
            }
        )
        return row
    observed = execution["output"]
    if expected.klass in ("identity_mode", "skipped_no_stats"):
        same = observed == execution["input"]
        row["agreement"] = "agrees" if same else "disagrees"
        row["vacuous"] = False
        if not same:
            findings.append(
                {
                    "code": codes.REPRODUCTION_NOT_FIXED,
                    "severity": codes.INVALID,
                    "detail": f"expected the input unchanged ({expected.klass}); output differs",
                }
            )
        return row
    # transformed or ambiguous under MEAN_STD
    if expected.mode != MEAN_STD:
        row["agreement"] = "unresolved"
        findings.append(
            {
                "code": codes.PREDICATE_UNMEASURABLE,
                "severity": codes.UNRESOLVED,
                "detail": f"value expectation for {expected.mode} is not implemented",
            }
        )
        return row
    try:
        values = mean_std_values(
            execution["input"],
            expected.stats["mean"],
            expected.stats["std"],
            spec.eps,
            execution["direction"],
        )
    except Malformed as error:
        row["agreement"] = "unresolved"
        findings.append(
            {"code": codes.MALFORMED_RECORD, "severity": codes.INVALID, "detail": str(error)}
        )
        return row
    result = compare(values, observed)
    row["expected_output"] = values.to_dict()
    row["comparison"] = result
    row["vacuous"] = values.vacuous
    row["agreement"] = "agrees" if result["within_tolerance"] else "disagrees"
    if values.vacuous:
        findings.append(
            {
                "code": codes.CONFIRMATION_UNINFORMATIVE,
                "severity": codes.UNRESOLVED,
                "detail": "witness at the transform's fixed point: unchanged output is expected "
                "either way, so this execution cannot show a transform ran",
            }
        )
    if not result["within_tolerance"]:
        findings.append(
            {
                "code": codes.REPRODUCTION_NOT_FIXED,
                "severity": codes.INVALID,
                "detail": f"observed output outside tolerance (max {result['max_ulp_error']:.1f} ulp)",
            }
        )
    if expected.klass == "ambiguous":
        alternatives = []
        for key in expected.matches:
            alt = store[key]
            if alt.get("mean") is None or alt.get("std") is None:
                continue
            other = mean_std_values(
                execution["input"], alt["mean"], alt["std"], spec.eps, execution["direction"]
            )
            alternatives.append({"key": key, "float32_emulation": other.float32})
        distinct = len({tuple(a["float32_emulation"]) for a in alternatives})
        row["order_dependent"] = distinct > 1
        row["alternatives"] = alternatives
        findings.append(
            {
                "code": codes.IDENTITY_UNBOUND,
                "severity": codes.REJECTED,
                "detail": f"{len(expected.matches)} statistics keys match; "
                + (
                    "different keys give different outputs"
                    if distinct > 1
                    else "outputs coincide here"
                )
                + "; binding by store order is not a selection",
            }
        )
    return row


def obligations(spec: ProcessorSpec) -> list[dict]:
    """The frozen obligation table for one processor: repair and legitimacy rows."""
    rows = []
    for feature in spec.features.values():
        direction = "inverse" if spec.role == "postprocessor" else "forward"
        ok, why = applicable(spec, feature, direction)
        if not ok or (spec.role == "preprocessor" and feature.type == ACTION_TYPE):
            continue
        mode = spec.mode(feature)
        rows.append(
            {
                "processor": spec.role,
                "feature": feature.name,
                "direction": direction,
                "mode": mode,
                "kind": "identity_legitimacy" if mode == IDENTITY else "repair",
                "why": why,
            }
        )
    return rows


def _reference_mismatch(row: dict, reference: dict | None) -> str | None:
    """Whether the statistics a row bound differ from the declared reference for its feature."""
    if reference is None or row["expected"]["class"] not in ("transformed", "ambiguous"):
        return None
    lookup = ACTION_KEY if row["expected"]["feature_type"] == ACTION_TYPE else row["feature"]
    expected_values = reference["values"].get(lookup)
    if expected_values is None:
        return None
    for name, values in row["bound_stats"].items():
        wanted = expected_values.get(name)
        if wanted is None:
            continue
        if [float(v) for v in wanted] != values:
            return (
                f"{lookup}.{name} bound {row['expected']['bound_key']!r} differs from the reference"
            )
    return None


def _candidate_outcome(
    candidate: str,
    table: list[dict],
    rows: list[dict],
    specs: dict[str, ProcessorSpec],
    statistics: dict,
    reference: dict | None = None,
) -> dict:
    """Apply the frozen rule to one candidate from expectations and exercised executions."""
    unmet: list[str] = []
    reference_mismatches: list[str] = []
    unexercised: list[str] = []
    legitimacy_violations: list[str] = []
    disagreements: list[str] = []
    vacuous_only: list[str] = []
    provenances: set[str] = set()
    evidence: dict[str, dict] = {}
    for obligation in table:
        key = (obligation["processor"], obligation["feature"], obligation["direction"])
        matching = [
            r
            for r in rows
            if r["candidate"] == candidate and (r["processor"], r["feature"], r["direction"]) == key
        ]
        label = f"{key[0]}:{key[1]}:{key[2]}"
        if obligation["kind"] == "identity_legitimacy":
            for r in matching:
                if r["agreement"] == "disagrees":
                    legitimacy_violations.append(label)
            continue
        if not matching:
            # No execution: decide from the expectation alone when it is static.
            spec = specs[key[0]]
            store = statistics[key[0]]
            if candidate == "explicit_override":
                unexercised.append(label)
                continue
            static = expectation(spec, store, key[1], key[2], candidate)
            if static.klass in ("skipped_no_stats", "error", "unsupported_mode"):
                unmet.append(f"{label}: {static.klass} ({static.detail})")
            elif static.klass == "ambiguous":
                unmet.append(f"{label}: ambiguous ({static.detail})")
            else:
                unexercised.append(label)
            continue
        for r in matching:
            klass = r["expected"]["class"]
            provenances.add(r.get("stats_provenance", "artifact"))
            if klass in ("transformed", "ambiguous"):
                evidence[key[1]] = {
                    "feature": key[1],
                    "declared": r.get("stats_provenance", "artifact"),
                    "byte_provenance": r["byte_provenance"]["status"],
                    "artifact_key": r["byte_provenance"]["artifact_key"],
                    "numeric_agreement": r["agreement"] == "agrees" and not r.get("vacuous"),
                }
            mismatch = _reference_mismatch(r, reference)
            if mismatch:
                reference_mismatches.append(f"{r['id']}: {mismatch}")
            if r["agreement"] == "disagrees":
                disagreements.append(f"{r['id']}: {label}")
            if klass in ("skipped_no_stats", "error", "unsupported_mode"):
                unmet.append(f"{label}: {klass}")
            elif klass == "ambiguous":
                unmet.append(f"{label}: ambiguous among {r['expected']['matches']}")
            elif klass == "transformed" and r.get("vacuous"):
                vacuous_only.append(f"{r['id']}: {label}")
            elif r["agreement"] == "unresolved":
                unexercised.append(f"{label} ({r['status']})")
    informative = [
        r
        for r in rows
        if r["candidate"] == candidate
        and r["expected"]["class"] == "transformed"
        and r["agreement"] == "agrees"
        and not r.get("vacuous")
    ]
    covered = {(r["processor"], r["feature"], r["direction"]) for r in informative}
    repair = [
        (o["processor"], o["feature"], o["direction"]) for o in table if o["kind"] == "repair"
    ]
    uncovered = [f"{p}:{f}:{d}" for p, f, d in repair if (p, f, d) not in covered]
    if disagreements:
        outcome = "invalid_input"
        reason = "producer output disagrees with the reference: " + "; ".join(disagreements)
    elif unmet:
        outcome = "rejected_candidate"
        reason = "unmet obligation: " + "; ".join(sorted(set(unmet)))
    elif reference_mismatches:
        outcome = "rejected_candidate"
        reason = (
            "the transform runs, but with statistics that differ from the declared reference: "
            + "; ".join(reference_mismatches)
        )
    elif legitimacy_violations:
        outcome = "rejected_candidate"
        reason = "identity feature changed: " + "; ".join(legitimacy_violations)
    elif uncovered:
        outcome = "unresolved"
        reason = "no informative execution covers: " + "; ".join(uncovered)
        if vacuous_only:
            reason += " (vacuous witnesses: " + "; ".join(vacuous_only) + ")"
    else:
        outcome = "supported_software_correction"
        reason = "every repair obligation transformed with one bound key and a non-vacuous witness"
    binding = "not_applicable"
    missing: list[str] = []
    declared_not_established: list[str] = []
    byte_established = False
    if outcome == "supported_software_correction":
        binding = "unresolved"
        repair_features = [f for _, f, _ in repair]
        byte_established = bool(repair_features) and all(
            evidence.get(f, {}).get("byte_provenance")
            in ("established_from_artifact", "matches_artifact_set")
            for f in repair_features
        )
        for f in repair_features:
            fact = evidence.get(f)
            if fact is None:
                missing.append(f"byte_provenance: {f} (no informative execution)")
            elif fact["byte_provenance"] == "not_established":
                missing.append(
                    f"byte_provenance: {f} (override values match no statistics set in the "
                    "verified artifact)"
                )
        missing.append("interpretation: " + NOT_CARRIED)
        missing.append("selection: " + NOT_CARRIED)
    for fact in evidence.values():
        declared = fact["declared"]
        if declared in CLAIMING_LABELS and (
            fact["byte_provenance"] == "not_established"
            or declared in ("verified_training_statistics", "dataset_metadata")
        ):
            declared_not_established.append(
                f"{fact['feature']}: declared {declared!r}, established "
                f"{fact['byte_provenance']} only"
            )
    return {
        "candidate": candidate,
        "outcome": outcome,
        "reason": reason,
        "unmet": sorted(set(unmet)),
        "unexercised": sorted(set(unexercised)),
        "legitimacy_violations": legitimacy_violations,
        "disagreements": disagreements,
        "reference_mismatches": reference_mismatches,
        "vacuous_only": vacuous_only,
        "statistics_provenance": sorted(provenances),
        "binding_evidence": {
            "numeric_agreement": (
                "established" if outcome == "supported_software_correction" else "not_established"
            ),
            "byte_provenance": (
                ("established" if byte_established else "not_established")
                if outcome == "supported_software_correction"
                else "not_applicable"
            ),
            "per_feature": sorted(evidence.values(), key=lambda e: e["feature"]),
            "interpretation": NOT_CARRIED,
            "selection": NOT_CARRIED,
            "declared_not_established": declared_not_established,
        },
        "deployment_binding": binding,
        "binding_missing": missing,
        "binding_note": (
            "a supported binding needs numeric agreement, byte provenance, interpretation "
            "and selection all established; the input contract carries no field that "
            "establishes interpretation or selection, so the binding stays unresolved "
            "whatever the record declares"
            if binding == "unresolved"
            else None
        ),
    }


def _decision_agreement(producer: dict | None, reference: dict[str, dict]) -> dict:
    if not isinstance(producer, dict):
        return {"status": "no_producer_decision", "per_candidate": {}}
    candidates = producer.get("candidates")
    per: dict[str, dict] = {}
    false_acceptance: list[str] = []
    false_refusal: list[str] = []
    if isinstance(candidates, dict):
        for name, verdict in reference.items():
            declared = candidates.get(name)
            outcome = declared.get("outcome") if isinstance(declared, dict) else None
            same = outcome == verdict["outcome"]
            per[name] = {"producer": outcome, "reference": verdict["outcome"], "agrees": same}
            if outcome == "supported_software_correction" and verdict["outcome"] != outcome:
                false_acceptance.append(name)
            if verdict["outcome"] == "supported_software_correction" and outcome in (
                "rejected_candidate",
                "invalid_input",
            ):
                false_refusal.append(name)
    # A producer may also declare a deployment binding. The reference never derives one
    # from declarations, so a declared supported binding is compared, not adopted.
    declared_binding = producer.get("deployment_applicability") or producer.get(
        "deployment_binding"
    )
    supported_by_reference = [
        name
        for name, verdict in reference.items()
        if verdict.get("deployment_binding") == "supported"
    ]
    false_binding = declared_binding == "supported" and not supported_by_reference
    return {
        "status": "compared",
        "per_candidate": per,
        "false_acceptance": false_acceptance,
        "false_refusal": false_refusal,
        "all_agree": bool(per) and all(v["agrees"] for v in per.values()),
        "declared_deployment_binding": declared_binding,
        "false_binding_acceptance": false_binding,
    }


def assess(document: object, root: Path | None = None) -> dict:
    """Assess a processor observation record against the independent reference."""
    loaded = load_observation(document, root)
    specs = loaded["specs"]
    statistics = loaded["statistics"]
    table = obligations(specs["preprocessor"]) + obligations(specs["postprocessor"])
    rows = [
        _assess_execution(e, specs[e["processor"]], statistics[e["processor"]])
        | {"stats_provenance": e["stats_provenance"]}
        for e in loaded["executions"]
    ]
    exercised = sorted({r["candidate"] for r in rows})
    declared = loaded["reference_statistics"]
    reference = {
        c: _candidate_outcome(c, table, rows, specs, statistics, declared)
        for c in CANDIDATES
        if c in exercised or c != "explicit_override"
    }
    identity_problems = [
        name for name, identity in loaded["identities"].items() if not identity["digest_matches"]
    ]
    findings = [f for r in rows for f in r["findings"]]
    for verdict in reference.values():
        for note in verdict["binding_evidence"]["declared_not_established"]:
            findings.append(
                {
                    "code": codes.PROVENANCE_NOT_ESTABLISHED,
                    "severity": codes.UNRESOLVED,
                    "detail": f"{verdict['candidate']}: {note}",
                }
            )
    agreement = _decision_agreement(loaded["decision"], reference)
    if agreement.get("false_binding_acceptance"):
        findings.append(
            {
                "code": codes.PROVENANCE_NOT_ESTABLISHED,
                "severity": codes.UNRESOLVED,
                "detail": "producer declares deployment binding supported; no candidate's "
                "binding evidence establishes interpretation or selection",
            }
        )
    if identity_problems:
        findings.append(
            {
                "code": codes.ARTIFACT_DIGEST_MISMATCH,
                "severity": codes.INVALID,
                "detail": "declared digest differs from the bytes: " + ", ".join(identity_problems),
            }
        )
    supported = [c for c, v in reference.items() if v["outcome"] == "supported_software_correction"]
    if identity_problems or any(v["outcome"] == "invalid_input" for v in reference.values()):
        overall = "invalid_input"
    elif supported:
        overall = "supported_software_correction"
    elif any(v["outcome"] == "unresolved" for v in reference.values()):
        overall = "unresolved"
    else:
        overall = "rejected_candidate"
    return {
        "schema": ASSESSMENT_SCHEMA,
        "decision_rule": DECISION_RULE,
        "rule_changes": list(RULE_CHANGES),
        "reference_source": {"commit": SOURCE_COMMIT, "normalize_processor_sha256": SOURCE_SHA256},
        "arm": loaded["arm"],
        "incident": loaded["incident"],
        "inputs": loaded["identities"],
        "resolved": {role: spec.to_dict() for role, spec in specs.items()},
        "statistics_keys": {
            role: {key: sorted(stat for stat in entry) for key, entry in statistics[role].items()}
            for role in PROCESSORS
        },
        "tensor_dtypes": {
            role: {name: t["dtype"] for name, t in loaded["tensors"][role].items()}
            for role in PROCESSORS
        },
        "obligations": table,
        "executions": rows,
        "reference_decision": {
            "overall": overall,
            "supported_candidates": supported,
            "per_candidate": reference,
        },
        "reference_statistics": (
            None
            if declared is None
            else {
                "provenance": declared["provenance"],
                "features": sorted(declared["values"]),
            }
        ),
        "producer_decision": loaded["decision"],
        "decision_agreement": agreement,
        "findings": findings,
        "binding_contract_limit": (
            f"{OBSERVATION_SCHEMA} carries no field that establishes which model, dataset and "
            "feature semantics a statistics set belongs to, or which statistics the target "
            "deployment selected; a supported deployment binding is unreachable from it"
        ),
        "boundary": (
            "software mechanism only: a supported correction of the processor step is not a "
            "recovered robot task; declared provenance is reported, never assumed, and the "
            "deployment binding stays unresolved until interpretation and selection evidence "
            "exist outside this contract"
        ),
    }


# --- execution-lane record adapter ---------------------------------------------------------

EXECUTION_SCHEMA = "nisayon.external-processor-observation.v1"
CAPTURE_SCHEMA = "nisayon.external-source-capture.v1"
_STATE_FILES = {
    "preprocessor": "policy_preprocessor_step_5_normalizer_processor.safetensors",
    "postprocessor": "policy_postprocessor_step_0_unnormalizer_processor.safetensors",
}


def _manifest_inputs(manifest: object) -> dict[str, dict]:
    """The four processor inputs named in an execution-lane source-capture manifest."""
    if not isinstance(manifest, dict) or manifest.get("schema") != CAPTURE_SCHEMA:
        raise Malformed("manifest.schema", f"expected {CAPTURE_SCHEMA}")
    found: dict[str, dict] = {}
    for entry in manifest.get("retrieved", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        name = Path(entry["path"]).name
        for role in PROCESSORS:
            if name == f"policy_{role}.json":
                found[f"{role}_config"] = entry
            elif name == _STATE_FILES[role]:
                found[f"{role}_stats"] = entry
    return {
        key: {"path": entry["path"], "sha256": entry.get("sha256"), "bytes": entry.get("bytes")}
        for key, entry in found.items()
    }


def observation_from_execution_record(
    document: object, manifest: object = None, *, arm: str = "B"
) -> dict:
    """Map an execution-lane observation record onto ``nisayon.processor-observation.v1``.

    The execution record carries one operation on one pipeline. Its inputs by role supply
    that pipeline's configuration and state; the counterpart pipeline's files come from
    the source-capture manifest when given, so both obligation tables can be read from
    bytes. The producer's ``resolved`` block (its own key resolution) is deliberately not
    copied: the reference resolves keys itself.
    """
    if not isinstance(document, dict) or document.get("schema") != EXECUTION_SCHEMA:
        raise Malformed("$.schema", f"expected {EXECUTION_SCHEMA}")
    operation = mapping_or_malformed(document.get("operation"), "$.operation")
    observation = mapping_or_malformed(document.get("observation"), "$.observation")
    execution = mapping_or_malformed(document.get("execution"), "$.execution")
    pipeline = operation.get("pipeline")
    role = {"policy_preprocessor": "preprocessor", "policy_postprocessor": "postprocessor"}.get(
        pipeline
    )
    if role is None:
        raise Malformed("$.operation.pipeline", f"unknown pipeline {pipeline!r}")
    inputs: dict[str, dict] = dict(_manifest_inputs(manifest)) if manifest is not None else {}
    source = None
    for index, item in enumerate(document.get("inputs") or []):
        if not isinstance(item, dict):
            raise Malformed(f"$.inputs[{index}]", "expected an object")
        entry = {"path": item.get("path"), "sha256": item.get("sha256"), "bytes": item.get("bytes")}
        if item.get("role") == "pipeline_config":
            inputs[f"{role}_config"] = entry
        elif item.get("role") == "processor_state":
            inputs[f"{role}_stats"] = entry
        elif item.get("role") == "normalizer_implementation":
            source = entry
    if source is not None:
        inputs["processor_source"] = source
    status = observation.get("status")
    process = execution.get("process_status")
    if status == "observed" and process == "completed":
        mapped_status = "completed"
    elif process in ("interrupted", "timeout"):
        mapped_status = "interrupted"
    elif status in ("invalid_input", "unsupported", "unresolved") or process != "completed":
        mapped_status = "error"
    else:
        raise Malformed("$.observation.status", f"unmapped status {status!r}/{process!r}")
    candidate = document.get("candidate") or operation.get("candidate") or "as_is"
    row: dict = {
        "id": str(document.get("id") or document.get("recorded_at") or "execution"),
        "candidate": candidate,
        "processor": role,
        "feature": operation.get("requested_feature_key"),
        "direction": "inverse" if operation.get("inverse") else "forward",
        "input": operation.get("witness"),
        "status": mapped_status,
        "stats_provenance": operation.get("stats_provenance", "artifact"),
    }
    if mapped_status == "completed":
        row["output"] = observation.get("output")
    else:
        row["error"] = observation.get("reason") or str(process)
    if candidate == "explicit_override":
        row["override_stats"] = operation.get("override_stats")
    return {
        "schema": OBSERVATION_SCHEMA,
        "arm": arm,
        "incident": document.get("incident"),
        "inputs": inputs,
        "executions": [row],
        "decision": document.get("decision"),
        "reference_statistics": document.get("reference_statistics"),
        "adapted_from": {
            "schema": EXECUTION_SCHEMA,
            "raw_record": document.get("raw_record"),
            "request": document.get("request"),
            "cost": document.get("cost"),
            "limits": document.get("limits"),
        },
    }


CASE_SCHEMA = "nisayon.external-processor-case.v1"
STORE_EXECUTION_SCHEMA = "nisayon.external-processor-execution.v1"
STORE_SUMMARY_SCHEMA = "nisayon.external-processor-result.v1"
_CANDIDATE_NAMES = {
    "C0_as_is": "as_is",
    "C1_suffix_match": "suffix_match",
    "C2_explicit_override": "explicit_override",
}
_CASE_ROLES = {
    "preprocessor_config": "preprocessor_config",
    "postprocessor_config": "postprocessor_config",
    "preprocessor_state": "preprocessor_stats",
    "postprocessor_state": "postprocessor_stats",
    "normalizer_implementation": "processor_source",
}


def observation_from_case_store(
    store: Path, case: object, sources: Path, *, arm: str = "B"
) -> dict:
    """Map a frozen case and its execution store onto ``nisayon.processor-observation.v1``.

    Inputs come from the case's source list (paths under ``sources``). Each incident
    execution record becomes one execution; the suffix order and the explicit-override
    statistics are taken from the frozen case, never from the producer's record, and the
    producer's own key resolution is not copied. Control assignments and the C3
    availability check are not executions of the processor and are left out. The
    producer's per-candidate outcomes come from ``summary.json`` when it exists.
    """
    if not isinstance(case, dict) or case.get("schema") != CASE_SCHEMA:
        raise Malformed("case.schema", f"expected {CASE_SCHEMA}")
    inputs: dict[str, dict] = {}
    for index, source in enumerate(case.get("sources") or []):
        if not isinstance(source, dict):
            raise Malformed(f"case.sources[{index}]", "expected an object")
        key = _CASE_ROLES.get(source.get("role"))
        if key is not None:
            inputs[key] = {
                "path": str(sources / source["path"]),
                "sha256": source.get("sha256"),
                "bytes": source.get("bytes"),
            }
    candidates = case.get("candidates") or []
    explicit = next(
        (c for c in candidates if isinstance(c, dict) and c.get("id") == "C2_explicit_override"),
        None,
    )
    orders = case.get("suffix_orders") or []
    executions: list[dict] = []
    folder = store / "executions"
    for assignment in case.get("assignments") or []:
        if not str(assignment).startswith("incident-"):
            continue
        path = folder / f"{assignment}.json"
        if not path.exists():
            continue
        record = load_json(path)
        if not isinstance(record, dict) or record.get("schema") != STORE_EXECUTION_SCHEMA:
            raise Malformed(str(path), f"expected {STORE_EXECUTION_SCHEMA}")
        candidate = _CANDIDATE_NAMES.get(record.get("candidate"))
        if candidate is None:
            continue
        observation = mapping_or_malformed(record.get("observation"), f"{path}:observation")
        process = record.get("process_status")
        if process == "completed" and observation.get("status") == "completed":
            status = "completed"
        elif process == "error" or observation.get("status") == "error":
            status = "error"
        else:
            status = "interrupted"
        row: dict = {
            "id": str(assignment),
            "candidate": candidate,
            "processor": record.get("processor"),
            "feature": record.get("feature"),
            "direction": record.get("direction"),
            "input": observation.get("input"),
            "status": status,
            "stats_provenance": "artifact",
            "producer_declared": {
                "statistics_key": record.get("statistics_key"),
                "statistics_matches": record.get("statistics_matches"),
                "changed": observation.get("changed"),
            },
        }
        if status == "completed":
            row["output"] = observation.get("output")
        else:
            error = observation.get("error")
            row["error"] = json.dumps(error) if isinstance(error, dict) else str(error or process)
        if candidate == "suffix_match" and orders:
            index = 1 if str(assignment).endswith("-reordered") and len(orders) > 1 else 0
            row["stats_order"] = list(orders[index])
        if candidate == "explicit_override":
            if explicit is None or not isinstance(explicit.get("stats"), dict):
                raise Malformed("case.candidates", "C2_explicit_override needs frozen stats")
            row["override_stats"] = explicit["stats"]
            row["stats_provenance"] = (
                "reporter_transcription"
                if record.get("feature") == "observation.state"
                else "artifact"
            )
        executions.append(row)
    decision = None
    summary_path = store / "summary.json"
    if summary_path.exists():
        summary = load_json(summary_path)
        if isinstance(summary, dict) and summary.get("schema") == STORE_SUMMARY_SCHEMA:
            produced = (summary.get("decisions") or {}).get("candidates") or []
            decision = {
                "candidates": {
                    _CANDIDATE_NAMES[item["candidate"]]: {
                        "outcome": item.get("outcome"),
                        "reasons": item.get("reasons"),
                    }
                    for item in produced
                    if isinstance(item, dict) and item.get("candidate") in _CANDIDATE_NAMES
                },
                "software_decision": (summary.get("decisions") or {}).get("software_decision"),
                "deployment_decision": (summary.get("decisions") or {}).get("deployment_decision"),
            }
    return {
        "schema": OBSERVATION_SCHEMA,
        "arm": arm,
        "incident": case.get("incident"),
        "inputs": inputs,
        "executions": executions,
        "decision": decision,
        "adapted_from": {
            "case_id": case.get("id"),
            "case_frozen_at": case.get("frozen_at"),
            "store": str(store),
            "summary_present": summary_path.exists(),
            "witnesses": case.get("witnesses"),
        },
    }


def assess_case_store(store: Path, case_path: Path, sources: Path, *, arm: str = "B") -> dict:
    document = observation_from_case_store(store, load_json(case_path), sources, arm=arm)
    assessment = assess(document, None)
    assessment["adapted_from"] = document["adapted_from"]
    assessment["records"] = [str(store / "executions"), str(case_path)]
    return assessment


def mapping_or_malformed(value: object, path: str) -> dict:
    if not isinstance(value, dict):
        raise Malformed(path, "expected an object")
    return value


def merge_observations(documents: list[dict]) -> dict:
    """Combine single-operation observations of one incident into one record.

    Inputs must agree byte for byte (same path and digest per role) or the merge is
    malformed; executions are concatenated in the given order with unique ids; a
    producer decision is taken from the last record that carries one.
    """
    if not documents:
        raise Malformed("$", "no records to merge")
    merged = json.loads(json.dumps(documents[0]))
    merged["executions"] = []
    seen: set[str] = set()
    for index, document in enumerate(documents):
        path = f"$[{index}]"
        if document.get("schema") != OBSERVATION_SCHEMA:
            raise Malformed(f"{path}.schema", f"expected {OBSERVATION_SCHEMA}")
        if document.get("arm") != merged.get("arm"):
            raise Malformed(f"{path}.arm", "records of different arms cannot be merged")
        for role, entry in (document.get("inputs") or {}).items():
            known = merged["inputs"].get(role)
            if known is None:
                merged["inputs"][role] = entry
            elif known.get("sha256") != entry.get("sha256"):
                raise Malformed(f"{path}.inputs.{role}", "digest differs between records")
        for execution in document.get("executions") or []:
            identifier = str(execution.get("id"))
            if identifier in seen:
                identifier = f"{identifier}#{index}"
            seen.add(identifier)
            merged["executions"].append({**execution, "id": identifier})
        if document.get("decision") is not None:
            merged["decision"] = document["decision"]
        if document.get("reference_statistics") is not None:
            merged["reference_statistics"] = document["reference_statistics"]
    if len(documents) > 1:
        merged["adapted_from"] = [d.get("adapted_from") for d in documents]
    return merged


def assess_files(paths: list[Path], root: Path | None = None, manifest: Path | None = None) -> dict:
    """Assess one record, or several single-operation execution records merged."""
    if not paths:
        raise Malformed("$", "no record given")
    base = root if root is not None else paths[0].parent
    capture = load_json(manifest) if manifest is not None else None
    documents = []
    for path in paths:
        document = load_json(path)
        if isinstance(document, dict) and document.get("schema") == EXECUTION_SCHEMA:
            document = observation_from_execution_record(document, capture)
        documents.append(document)
    document = documents[0] if len(documents) == 1 else merge_observations(documents)
    assessment = assess(document, base)
    if isinstance(document, dict) and "adapted_from" in document:
        assessment["adapted_from"] = document["adapted_from"]
    assessment["records"] = [str(path) for path in paths]
    return assessment


def assess_file(path: Path, root: Path | None = None, manifest: Path | None = None) -> dict:
    return assess_files([path], root, manifest)


def render(assessment: dict) -> str:
    lines = [
        f"processor reference · rule {assessment['decision_rule']} · arm {assessment['arm']}",
        f"reference decision: {assessment['reference_decision']['overall']}",
    ]
    for name, verdict in assessment["reference_decision"]["per_candidate"].items():
        lines.append(f"  {name:<18}{verdict['outcome']:<32}{verdict['reason']}")
        if verdict["deployment_binding"] != "not_applicable":
            evidence = verdict["binding_evidence"]
            lines.append(
                f"  {'':<18}deployment binding: {verdict['deployment_binding']} "
                f"(numeric {evidence['numeric_agreement']}, bytes {evidence['byte_provenance']}, "
                f"interpretation {evidence['interpretation']}, selection {evidence['selection']})"
            )
            for fact in evidence["per_feature"]:
                lines.append(
                    f"  {'':<18}  {fact['feature']}: declared {fact['declared']}, "
                    f"established {fact['byte_provenance']}"
                    + (f" [{fact['artifact_key']}]" if fact["artifact_key"] else "")
                )
    lines.append("executions:")
    for row in assessment["executions"]:
        expected = row["expected"]
        extra = ""
        if row.get("comparison"):
            extra = f" max {row['comparison']['max_ulp_error']:.2f} ulp"
        if row.get("vacuous"):
            extra += " VACUOUS"
        if row.get("order_dependent"):
            extra += " ORDER-DEPENDENT"
        lines.append(
            f"  {row['id']:<34}{row['candidate']:<18}{row['processor']:<14}"
            f"{row['feature']:<20}{row['direction']:<9}{expected['class']:<18}"
            f"{row['agreement']}{extra}"
        )
    agreement = assessment["decision_agreement"]
    if agreement["status"] == "compared":
        lines.append(
            "producer decision: "
            + ("agrees on every candidate" if agreement["all_agree"] else "differs")
            + (
                "; declares a supported deployment binding the evidence does not establish"
                if agreement.get("false_binding_acceptance")
                else ""
            )
            + (
                f"; false acceptance {agreement['false_acceptance']}"
                if agreement["false_acceptance"]
                else ""
            )
            + (
                f"; false refusal {agreement['false_refusal']}"
                if agreement["false_refusal"]
                else ""
            )
        )
    else:
        lines.append("producer decision: none recorded")
    for finding in assessment["findings"]:
        lines.append(f"  [{finding['severity']}] {finding['code']}: {finding['detail']}")
    lines.append(assessment["boundary"])
    return "\n".join(lines)
