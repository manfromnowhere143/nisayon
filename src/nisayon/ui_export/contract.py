"""Version-one wire objects. Numerical readings retain their source precision."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Index = Annotated[int, Field(ge=0, le=1_000_000)]
Number = Annotated[float, Field(allow_inf_nan=False)]
Vector3 = Annotated[list[Number], Field(min_length=3, max_length=3)]
Pose = Annotated[list[Number], Field(min_length=7, max_length=7)]


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class FileRef(Wire):
    path: Annotated[str, Field(pattern=r"^(objects|generations)/[0-9a-f]{64}\.json$")]
    sha256: Sha256
    byte_length: Annotated[int, Field(gt=0, le=16_777_216)]
    media_type: Literal["application/json"] = "application/json"
    kind: Literal["manifest", "case", "samples", "reconstruction", "model", "decision"]
    required: bool = True


class Source(Wire):
    id: str
    label: str
    sha256: Sha256
    byte_length: Annotated[int, Field(gt=0, le=1_073_741_824)]
    encoding: Literal["json", "gzip-json", "gzip-jsonl", "mjcf", "asset", "python"]
    canonical_json_sha256: Sha256 | None = None


class Locator(Wire):
    source_id: str
    pointer: str | None = None
    line: Annotated[int, Field(ge=1)] | None = None


class RunKey(Wire):
    bundle_sha256: Sha256
    run_id: str


class Memory(Wire):
    before: Literal["initialized_none", "present", "unavailable"]
    after: Literal["initialized_none", "present", "unavailable"]
    before_sha256: Sha256 | None
    after_sha256: Sha256 | None
    episode_reset: bool | None
    reset_before_inference: bool | None


class Sample(Wire):
    row_index: Index
    step: Index
    action_sim_time_s: Number
    next_sim_time_s: Number
    observation_sim_time_s: Number
    observation_age_s: Number
    original: dict[str, JsonValue]
    observations: dict[str, JsonValue] | None
    memory: Memory
    source: Locator
    raw_source: Locator | None


class Samples(Wire):
    schema_version: Literal["nisayon.ui-samples.v1"] = Field(alias="schema")
    run: RunKey
    rows: Annotated[list[Sample], Field(max_length=100_000)]


class Node(Wire):
    id: Index
    name: str
    parent_id: Index


class Site(Wire):
    id: Index
    name: str
    body_id: Index


class Geom(Wire):
    id: Index
    name: str
    body_id: Index
    type: str
    size: Vector3


class Model(Wire):
    schema_version: Literal["nisayon.ui-model.v1"] = Field(alias="schema")
    source_id: str
    nq: Index
    nmocap: Index
    nv: Index | None = None
    nu: Index | None = None
    joints: list[dict[str, JsonValue]] = Field(default_factory=list)
    actuators: list[dict[str, JsonValue]] = Field(default_factory=list)
    bodies: list[Node]
    sites: list[Site]
    geoms: list[Geom]
    omitted_mesh_count: Index
    representation: Literal["articulated_schematic"]
    limitations: list[str]


class Convention(Wire):
    handedness: Literal["right"] = "right"
    up: Literal["Z"] = "Z"
    length_unit: Literal["m"] = "m"
    quaternion_order: Literal["wxyz"] = "wxyz"
    pose_layout: Literal["x,y,z,qw,qx,qy,qz"] = "x,y,z,qw,qx,qy,qz"
    clock: Literal["simulation"] = "simulation"


class Frame(Wire):
    row_index: Index
    phase: Literal["before", "after"]
    stored_time_s: Number
    state_sha256: Sha256
    bodies: list[Pose]
    sites: list[Pose]
    geoms: list[Pose]
    residuals: dict[str, Number | None]
    physical: dict[str, JsonValue] | None = None


class Reconstruction(Wire):
    schema_version: Literal["nisayon.ui-reconstruction.v1"] = Field(alias="schema")
    run: RunKey
    model: FileRef
    raw_source_id: str
    method: Literal["mj_kinematics"]
    mujoco_version: Literal["3.2.7"]
    numpy_version: str
    convention: Convention
    frames: Annotated[list[Frame], Field(max_length=200_000)]
    maximum_residuals: dict[str, Number]


class Finding(Wire):
    id: str
    kind: Literal["descriptive"] = "descriptive"
    code: str
    detail: str
    run: RunKey
    row_index: Index
    phase: Literal["before", "after"]
    step: Index
    definition: str
    threshold: Number
    source: Locator


class Run(Wire):
    key: RunKey
    role: str
    plan_id: str | None = None
    plan: dict[str, JsonValue] | None = None
    execution: dict[str, JsonValue] | None = None
    stage: str
    condition_id: str
    process_status: str
    measurement_status: str
    task_outcome: str
    samples: FileRef
    reconstruction: FileRef | None
    model: FileRef | None
    source: Locator
    raw_source_id: str | None
    sample_count: Index
    last_next_sim_time_s: Number | None = None
    reset: dict[str, JsonValue]
    costs: list[dict[str, JsonValue]]
    cost_parent_run_id: str | None
    evaluator: dict[str, JsonValue] | None
    indexes: dict[str, list[Index]] = Field(default_factory=dict)


class Decision(Wire):
    schema_version: Literal["nisayon.ui-decision.v1"] = Field(alias="schema")
    source: Locator
    bundle_sha256: Sha256
    execution_bundle_sha256: Sha256 | None = None
    source_canonical_bundle_sha256: Sha256
    stage: str
    decision: str
    scope: str
    reasons: list[dict[str, JsonValue]]
    premises: dict[str, JsonValue]
    evaluator: dict[str, JsonValue]
    runs: dict[str, JsonValue]
    projection_redactions: list[str]


class Case(Wire):
    schema_version: Literal["nisayon.ui-case.v1"] = Field(alias="schema")
    case_key: str
    case_id: str
    experiment_id: str
    arm: str
    task: str
    predicates: dict[str, JsonValue]
    runs: list[Run]
    decisions: list[FileRef]
    findings: list[Finding]
    trial: dict[str, JsonValue] | None
    confirmation: dict[str, JsonValue]
    comparison_alignment: str
    limitations: list[str]


class CaseRef(Wire):
    case_key: str
    case_id: str
    object: FileRef


class Manifest(Wire):
    schema_version: Literal["nisayon.ui-generation.v1"] = Field(alias="schema")
    adapter: str
    experiment_id: str
    capabilities: list[str]
    sources: list[Source]
    cases: list[CaseRef]
    files: list[FileRef]
    limitations: list[str]


class Discovery(Wire):
    schema_version: Literal["nisayon.ui-discovery.v1"] = Field(alias="schema")
    manifest: FileRef


class Integrity(Wire):
    schema_version: Literal["nisayon.ui-integrity.v1"] = Field(alias="schema")
    manifest: FileRef


class LibraryEntry(Wire):
    case_key: str
    case_id: str
    directory: Annotated[str, Field(pattern=r"^D(01|03|05|06|08|10)-[a-z-]+$")]
    manifest: FileRef


class Library(Wire):
    schema_version: Literal["nisayon.ui-library.v1"] = Field(alias="schema")
    default_case_key: str
    cases: Annotated[list[LibraryEntry], Field(min_length=1, max_length=6)]


Document = Annotated[
    Manifest | Case | Samples | Model | Reconstruction | Decision | Discovery | Integrity | Library,
    Field(discriminator="schema_version"),
]
DOCUMENT = TypeAdapter(Document)


def json_schema() -> dict:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **DOCUMENT.json_schema()}
