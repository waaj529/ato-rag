"""Frozen Phase 3 baseline contract."""

from scripts.verify_phase3_exit import verify_phase3_exit


def test_frozen_phase3_baseline_passes_the_revised_exit_gate():
    report = verify_phase3_exit()
    assert report["passed"] is True
    assert report["status"] == "complete_frozen"
    assert report["settings_version"] == "phase3-rrf-v4"
    assert report["failures"] == []
