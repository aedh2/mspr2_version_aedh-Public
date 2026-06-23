from __future__ import annotations

from app.services.coach_posture_logic import (
    DynamicCounterState,
    StaticHoldState,
    advance_dynamic_counter,
    advance_static_hold,
)


def test_dynamic_counter_counts_only_complete_cycle():
    state = DynamicCounterState()

    state = advance_dynamic_counter(state, "phase_contractee", target_reps_per_set=2)
    assert state.reps == 0
    assert state.phase == "phase_contractee"

    state = advance_dynamic_counter(state, "phase_initiale", target_reps_per_set=2)
    assert state.reps == 1
    assert state.sets == 0
    assert state.phase == "phase_initiale"

    state = advance_dynamic_counter(state, "phase_contractee", target_reps_per_set=2)
    state = advance_dynamic_counter(state, "phase_initiale", target_reps_per_set=2)
    assert state.reps == 2
    assert state.sets == 1
    assert state.reps_in_current_set == 0


def test_static_hold_advances_only_when_posture_is_correct():
    state = StaticHoldState()

    state = advance_static_hold(state, "incorrect", 3.0)
    assert state.hold_seconds == 0

    state = advance_static_hold(state, "correct", 2.5)
    state = advance_static_hold(state, "almost", 4.0)
    assert state.hold_seconds == 2.5
