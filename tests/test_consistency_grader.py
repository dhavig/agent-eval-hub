"""Cross-surface consistency — does the phone give the same answer as the PC?"""
from __future__ import annotations

from agent_eval_hub.graders.consistency import cross_surface_consistency, jaccard


def test_jaccard_identical_strings_is_one():
    assert jaccard("hello world", "hello world") == 1.0


def test_jaccard_disjoint_strings_is_zero():
    assert jaccard("apples oranges", "xylophone") == 0.0


def test_jaccard_is_case_insensitive():
    assert jaccard("Hello World", "hello world") == 1.0


def test_jaccard_partial_overlap_between_zero_and_one():
    sim = jaccard("the weather in paris is 15c", "weather paris 15c clear")
    assert 0 < sim < 1


def test_jaccard_handles_both_empty_as_identical():
    assert jaccard("", "") == 1.0


def test_jaccard_empty_vs_nonempty_is_zero():
    assert jaccard("", "anything") == 0.0


def test_cross_surface_passes_above_threshold():
    r = cross_surface_consistency("weather 15c paris", "paris 15c weather", threshold=0.5)
    assert r.passed
    assert r.similarity > 0.5


def test_cross_surface_fails_below_threshold():
    r = cross_surface_consistency(
        "the weather is fifteen degrees",
        "i don't know the weather",
        threshold=0.8,
    )
    assert not r.passed
    assert "jaccard" in r.detail


def test_cross_surface_labels_in_detail():
    r = cross_surface_consistency("x", "x", threshold=0.5, label_a="cloud", label_b="device")
    assert "cloud" in r.detail and "device" in r.detail
