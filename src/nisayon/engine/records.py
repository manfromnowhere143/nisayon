"""First-case JSON interface. These types describe evidence, not its acceptance.

All times below are seconds. Simulator and host-monotonic clocks are distinct.
Artifact references resolve against the bundle's explicit artifact_root.
"""

from typing import Literal, NotRequired, TypedDict

SCHEMA = "nisayon.first_case.v1"


class Cost(TypedDict):
    category: str
    value: float | None
    unit: str
    missing_reason: str | None


class Artifact(TypedDict):
    path: str
    sha256: str


class TraceStep(TypedDict):
    step: int
    observation_step: int
    observation_sim_time_s: float
    observation_capture: NotRequired[dict]
    captured_observation_step: NotRequired[int]
    captured_observation_sha256: NotRequired[str]
    captured_observation_capture: NotRequired[dict]
    next_observation_capture: NotRequired[dict]
    inference_started_host_s: NotRequired[float]
    inference_finished_host_s: NotRequired[float]
    action_host_s: NotRequired[float]
    action_sim_time_s: float
    next_sim_time_s: float
    intended_action: list[float]
    executed_action: list[float]
    observation_sha256: str
    next_observation_sha256: str
    state_before_sha256: str
    state_after_sha256: str
    observation_source_run_id: str
    next_observation_source_run_id: str
    policy_state_sha256: str | None
    policy_state_after_sha256: NotRequired[str | None]
    policy_reset_before_inference: NotRequired[bool]
    policy_reset_wall_s: NotRequired[float]
    inference_wall_s: float
    cube_height_m: float
    task_success: bool


class Run(TypedDict):
    id: str
    case_id: str
    plan_id: str
    condition_id: str
    seed: int
    evidence_origin: Literal["simulator", "synthetic_development", "invalid_replay_control"]
    candidate_sha256: str
    invocation_id: NotRequired[str]
    execution_identity_sha256: NotRequired[str]
    code_sha256: NotRequired[str]
    code: NotRequired[dict]
    dependencies_sha256: NotRequired[str]
    policy_sha256: NotRequired[str]
    configuration: NotRequired[dict]
    configuration_sha256: NotRequired[str]
    source_identity_unchanged: NotRequired[bool]
    started_at: str
    ended_at: NotRequired[str]
    started_host_s: NotRequired[float]
    ended_host_s: NotRequired[float]
    process_status: Literal["completed", "failed", "interrupted"]
    execution_mode: Literal["full_closed_loop", "recorded_observation_replay"]
    reset_id: str
    initial_state_sha256: str
    trace: list[TraceStep]
    artifacts: list[Artifact]
    measurement_status: Literal["observed", "missing", "invalid"]
    task_outcome: Literal["completed", "failed", "unknown"]
    constraint_violations: list[str]
    costs: list[Cost]
    assignment_role: NotRequired[str]
    prefix_run: NotRequired[dict]
    policy_reset: NotRequired[dict]
    policy_state_reset: NotRequired[dict]
    cost_parent_run_id: NotRequired[str]
    error: NotRequired[str]


class Plan(TypedDict):
    id: str
    case_id: str
    intervention: str
    candidate_sha256: str
    execution_mode: str
    recompute: list[str]
    retain: list[str]
    reset: str


class Case(TypedDict):
    id: str
    task: str
    policy: dict
    backend: dict
    working_revision: str
    changed_revision: str
    predicates: dict
    allowed_repair_scope: list[str]


class Confirmation(TypedDict):
    candidate_sha256: str
    frozen_at: str
    protocol_sha256: str
    condition_ids: list[str]
    reference_run_ids: list[str]
    candidate_run_ids: list[str]
    contamination: list[str]


class Bundle(TypedDict):
    schema: str
    artifact_root: str
    case: Case
    qualification: dict
    plans: list[Plan]
    runs: list[Run]
    confirmation: Confirmation | None
    costs: list[Cost]
