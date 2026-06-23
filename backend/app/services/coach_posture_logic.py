from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DynamicPhase = Literal["phase_initiale", "phase_contractee"]
PostureStatus = Literal["incorrect", "almost", "correct"]


@dataclass(frozen=True)
class DynamicCounterState:
    phase: DynamicPhase = "phase_initiale"
    reps: int = 0
    sets: int = 0
    reps_in_current_set: int = 0


@dataclass(frozen=True)
class StaticHoldState:
    hold_seconds: float = 0.0


def advance_dynamic_counter(
    state: DynamicCounterState,
    observed_phase: DynamicPhase,
    *,
    target_reps_per_set: int = 10,
) -> DynamicCounterState:
    if state.phase == "phase_initiale" and observed_phase == "phase_contractee":
        return DynamicCounterState(
            phase="phase_contractee",
            reps=state.reps,
            sets=state.sets,
            reps_in_current_set=state.reps_in_current_set,
        )

    if state.phase == "phase_contractee" and observed_phase == "phase_initiale":
        reps = state.reps + 1
        reps_in_set = state.reps_in_current_set + 1
        sets = state.sets
        if reps_in_set >= target_reps_per_set:
            sets += 1
            reps_in_set = 0
        return DynamicCounterState(
            phase="phase_initiale",
            reps=reps,
            sets=sets,
            reps_in_current_set=reps_in_set,
        )

    return state


def advance_static_hold(state: StaticHoldState, status: PostureStatus, delta_seconds: float) -> StaticHoldState:
    if status == "correct":
        return StaticHoldState(hold_seconds=max(0.0, state.hold_seconds + delta_seconds))
    return state
