import pytest

from ComfyUI_H3_Continuum_Join.constants import (
    PROMPT_MODE_FIXED,
    PROMPT_MODE_LIST,
    PROMPT_MODE_TIMELINE,
)
from ComfyUI_H3_Continuum_Join.v2.prompts import (
    PromptPlanError,
    make_prompt_plan,
    validate_prompt_plan,
)


def test_fixed_prompt_repeats_without_mutation():
    plan = make_prompt_plan(mode=PROMPT_MODE_FIXED, script="hello", chunks=3, chunk_seconds=5)
    assert plan["prompts"] == ["hello", "hello", "hello"]
    assert len(set(plan["hashes"])) == 1
    assert validate_prompt_plan(plan) is plan


def test_list_prompt_uses_separator_and_repeats_last():
    plan = make_prompt_plan(
        mode=PROMPT_MODE_LIST,
        script="first\n---\nsecond",
        chunks=3,
        chunk_seconds=5,
    )
    assert plan["prompts"] == ["first", "second", "second"]
    assert "repeated" in plan["notes"][0]


def test_timeline_prompt_maps_ranges_and_chunk_headers():
    plan = make_prompt_plan(
        mode=PROMPT_MODE_TIMELINE,
        script="[0-5s]\none\n[5-10s]\ntwo\n[Chunk 3]\nthree",
        chunks=3,
        chunk_seconds=5,
    )
    assert plan["prompts"] == ["one", "two", "three"]


def test_timeline_requires_coverage():
    with pytest.raises(PromptPlanError):
        make_prompt_plan(
            mode=PROMPT_MODE_TIMELINE,
            script="[0-5s]\none",
            chunks=2,
            chunk_seconds=5,
        )


def test_native_h3_chunk_duration_rejects_sub_four_seconds():
    with pytest.raises(PromptPlanError):
        make_prompt_plan(mode=PROMPT_MODE_FIXED, script="x", chunks=1, chunk_seconds=3.9)
