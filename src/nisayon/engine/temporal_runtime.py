"""Execute bounded scripted transport events through an ordinary action queue.

The schedule supplies messages and a virtual clock, not future observations of
a robot. Every remedy executes a fresh queue. This module records software
facts and local admission choices; the separate evaluator owns conclusions.
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from .io import digest
from .temporal_clocks import age_at


def stamp(value: int) -> dict:
    return {"value": value, "clock": "controller", "unit": "ns"}


@dataclass(frozen=True)
class Action:
    action_id: str
    chunk_id: str
    ordinal: int
    target_step: int
    value: object
    req_id: str | None
    request_order: int
    generation: int | None
    config_sha256: str | None
    activation: int | None
    acquired: dict | None


class ScriptedSendFailure(Exception):
    """The scripted send failed; distinct from a journal or filesystem failure."""


class ScriptedSink:
    """An actual local call with scripted return/failure, without robot effects."""

    def send(self, action: Action, outcome: str, entered: Callable[[], None]) -> bool:
        entered()  # An action_dispatched event means this software call was entered.
        if outcome == "raise":
            raise ScriptedSendFailure("scripted software send failure")
        if outcome == "ack_missing":
            return False
        if outcome != "ack":
            raise ValueError(f"Unsupported scripted sink outcome: {outcome}")
        return True


class TemporalRuntime:
    def __init__(self, case: dict, remedy: dict, emit: Callable[[dict], None]):
        self.case = copy.deepcopy(case)
        self.remedy = copy.deepcopy(remedy)
        self.emit_to_store = emit
        self.generation = case["initial_generation"]
        self.config = case["initial_configuration"]
        self.activation = 0
        self.step = 0
        self.now = 0
        self.input_id: str | None = None
        self.observations: dict[str, dict] = {}
        self.requests: dict[str, dict] = {}
        self.request_observations: dict[str, dict | None] = {}
        self.seen_chunks: dict[str, str] = {}
        self.queue: dict[int, Action] = {}
        self.attempted: set[str] = set()
        self.counts: Counter = Counter()
        self.sink = ScriptedSink()

    def emit(self, kind: str, **fields) -> None:
        self.emit_to_store(
            {"kind": kind, "at": stamp(self.now), "input_id": self.input_id, **fields}
        )
        self.counts[kind] += 1

    def start(self) -> None:
        self.emit("episode_start", generation=self.generation, activation=self.activation)

    def execute(self, operation: dict) -> None:
        self.now = operation["at_ns"]
        self.input_id = operation["id"]
        name = operation["operation"]
        handler = getattr(self, "_" + name, None)
        if handler is None or name not in {
            "observe",
            "request",
            "response",
            "dispatch",
            "reset",
            "configure",
            "gap",
            "cancel_request",
        }:
            raise ValueError(f"Unsupported temporal operation: {name}")
        handler(operation)

    def _observe(self, operation: dict) -> None:
        identifier = operation["obs_id"]
        if identifier in self.observations:
            raise ValueError(f"Observation identity reused: {identifier}")
        observation = {
            "obs_id": identifier,
            "generation": self.generation,
            "step": operation["step"],
            "at": copy.deepcopy(operation.get("stamp", stamp(self.now))),
            "activation": self.activation,
        }
        self.observations[identifier] = observation
        # acquired at stays null if unavailable. The input event's virtual time
        # is separately retained, never promoted to acquisition evidence.
        self.emit("observation_acquired", **observation, observed_by_driver_at=stamp(self.now))

    def _request(self, operation: dict) -> None:
        identifier = operation["req_id"]
        if identifier in self.requests:
            raise ValueError(f"Request identity reused: {identifier}")
        observation = copy.deepcopy(self.observations.get(operation["obs_id"]))
        request = {
            "req_id": identifier,
            "obs_id": operation["obs_id"],
            "generation": self.generation,
            "config_sha256": self.config,
            "activation": self.activation,
            "order": len(self.requests),
            "observation_available_at_send": observation is not None,
        }
        self.requests[identifier] = request
        # A later acquisition cannot become the input of an earlier request.
        # An acquired observation with a missing timestamp is still an observed
        # input; its age stays unresolved in the separate deadline guard.
        self.request_observations[identifier] = observation
        self.emit("request_sent", **request)

    def _response(self, operation: dict) -> None:
        response = {
            key: copy.deepcopy(operation[key])
            for key in (
                "resp_id",
                "req_id",
                "chunk_id",
                "generation",
                "config_sha256",
                "first_step",
                "delivery_id",
            )
        }
        values = operation["values"]
        response["ordinals"] = len(values)
        response["values_sha256"] = digest(values)
        self.emit("response_arrived", **response)
        request = self.requests.get(response["req_id"])
        observation = self.request_observations.get(response["req_id"])
        signature = digest({k: v for k, v in response.items() if k != "delivery_id"})
        prior = self.seen_chunks.get(response["chunk_id"])
        self.seen_chunks.setdefault(response["chunk_id"], signature)
        reason = None
        if self.remedy["drop_all"]:
            reason = "drop_all_control"
        elif self.remedy["deduplicate"] and prior is not None:
            reason = "duplicate_chunk" if prior == signature else "chunk_identity_collision"
        elif self.remedy["bind_request"] and (request is None or observation is None):
            reason = "unbound_request_or_observation"
        elif self.remedy["bind_request"] and observation["step"] != response["first_step"]:
            reason = "response_observation_step_mismatch"
        elif self.remedy["fence_generation"] and (
            request is None
            or observation is None
            or request["generation"] != self.generation
            or observation["generation"] != self.generation
            or response["generation"] != self.generation
        ):
            reason = "generation_fence"
        elif self.remedy["bind_configuration"] and (
            request is None
            or response["config_sha256"] != request["config_sha256"]
            or request["config_sha256"] != self.config
            or request["activation"] != self.activation
            or observation is None
            or observation["activation"] != self.activation
        ):
            reason = "configuration_fence"
        elif self.remedy["deadline_check"] in {"arrival", "arrival_and_dispatch"}:
            age = age_at(
                observation["at"] if observation else None,
                stamp(self.now),
                self.case["clocks"],
                self.case["configuration"]["max_age"],
            )
            if age.status != "within":
                reason = "arrival_age_" + age.status
        admitted, skipped, replaced, decisions = [], [], [], []
        for ordinal, value in enumerate(values):
            target = response["first_step"] + ordinal
            action_id = f"{response['chunk_id']}:{ordinal}"
            refusal = reason
            existing = self.queue.get(target)
            order = request["order"] if request else -1
            if refusal is None and self.remedy["deduplicate"] and action_id in self.attempted:
                refusal = "action_already_attempted"
            if refusal is None and self.remedy["ordered_overlap"]:
                if target < self.step:
                    refusal = "step_already_consumed"
                elif existing is not None and order < existing.request_order:
                    refusal = "older_request_overlap"
            if refusal is not None:
                skipped.append(ordinal)
                decisions.append({"ordinal": ordinal, "disposition": "skipped", "reason": refusal})
                continue
            if existing is not None:
                replaced.append(existing.action_id)
            self.queue[target] = Action(
                action_id,
                response["chunk_id"],
                ordinal,
                target,
                copy.deepcopy(value),
                response["req_id"],
                order,
                response["generation"],
                response["config_sha256"],
                request["activation"] if request else None,
                copy.deepcopy(observation["at"]) if observation else None,
            )
            admitted.append(ordinal)
            decisions.append({"ordinal": ordinal, "disposition": "admitted", "reason": "admitted"})
        self.emit(
            "queue_admitted",
            chunk_id=response["chunk_id"],
            delivery_id=response["delivery_id"],
            admitted=admitted,
            skipped=skipped,
            replaced=replaced,
            reason=reason or ("admitted" if admitted else "all_ordinals_skipped"),
            decisions=decisions,
        )

    def _dispatch(self, operation: dict) -> None:
        self.counts["control_opportunities"] += 1
        target = self.step if self.remedy["ordered_overlap"] else min(self.queue, default=self.step)
        action = self.queue.pop(target, None)
        refusal, age = None, None
        if action is None:
            refusal = "empty_queue"
        elif self.remedy["fence_generation"] and action.generation != self.generation:
            refusal = "generation_fence"
        elif self.remedy["bind_configuration"] and (
            action.config_sha256 != self.config or action.activation != self.activation
        ):
            refusal = "configuration_fence"
        elif self.remedy["deadline_check"] in {"dispatch", "arrival_and_dispatch"}:
            age = age_at(
                action.acquired,
                stamp(self.now),
                self.case["clocks"],
                self.case["configuration"]["max_age"],
            )
            if age.status != "within":
                refusal = "dispatch_age_" + age.status
        if refusal is not None:
            self.emit(
                "dispatch_refused",
                action_id=action.action_id if action else None,
                chunk_id=action.chunk_id if action else None,
                ordinal=action.ordinal if action else None,
                step=self.step,
                generation=self.generation,
                reason=refusal,
                age_guard=age.record() if age else None,
            )
            return
        assert action is not None
        self.attempted.add(action.action_id)
        dispatched_step = self.step
        self.step += 1
        dispatch_id = f"{self.input_id}:send"

        def entered():
            self.emit(
                "action_dispatched",
                action_id=action.action_id,
                chunk_id=action.chunk_id,
                ordinal=action.ordinal,
                step=dispatched_step,
                target_step=action.target_step,
                generation=self.generation,
                config_sha256=self.config,
                activation=self.activation,
                value=action.value,
                sink="scripted_software_call",
                dispatch_id=dispatch_id,
                age_guard=age.record() if age else None,
            )

        try:
            acknowledged = self.sink.send(action, operation.get("sink_outcome", "ack"), entered)
        except ScriptedSendFailure as error:
            self.emit(
                "dispatch_failed",
                action_id=action.action_id,
                dispatch_id=dispatch_id,
                reason=str(error),
            )
        else:
            if acknowledged:
                self.emit(
                    "dispatch_acknowledged", action_id=action.action_id, dispatch_id=dispatch_id
                )
            else:
                self.emit(
                    "evidence_gap",
                    what="dispatch_acknowledgement",
                    action_id=action.action_id,
                    dispatch_id=dispatch_id,
                    reason="scripted_sink_returned_without_acknowledgement",
                )

    def _reset(self, operation: dict) -> None:
        incoming = [self.queue[key].action_id for key in sorted(self.queue)]
        generation = operation["generation"]
        if generation <= self.generation:
            raise ValueError("Reset generation must advance")
        self.emit("reset_requested", generation_from=self.generation, generation_to=generation)
        self.generation, self.step = generation, 0
        if self.remedy["reset_queue"]:
            self.queue.clear()
        self.emit(
            "reset_completed",
            generation=generation,
            queued_before_reset=incoming,
            queued_at_reset=[self.queue[key].action_id for key in sorted(self.queue)],
        )

    def _configure(self, operation: dict) -> None:
        new = operation["config_sha256"]
        if new not in self.case["configuration_catalog"]:
            raise ValueError("Configuration not in frozen catalog")
        old = self.config
        self.config, self.activation = new, self.activation + 1
        incoming = [self.queue[key].action_id for key in sorted(self.queue)]
        if self.remedy["bind_configuration"]:
            self.queue.clear()
        self.emit(
            "configuration_changed",
            from_sha256=old,
            to_sha256=new,
            activation=self.activation,
            queued_before=incoming,
            queued_after=[self.queue[key].action_id for key in sorted(self.queue)],
            local_queue_revocation=self.remedy["bind_configuration"],
        )

    def _gap(self, operation: dict) -> None:
        self.emit(
            "evidence_gap",
            **{
                k: copy.deepcopy(v)
                for k, v in operation.items()
                if k not in {"id", "at_ns", "operation"}
            },
        )

    def _cancel_request(self, operation: dict) -> None:
        self.emit(
            "cancellation_requested",
            target=operation["target"],
            scope="remote_computation_request_only",
            completion_observed=False,
        )
