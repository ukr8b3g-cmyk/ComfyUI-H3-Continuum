import pytest

from ComfyUI_H3_Continuum_Join.constants import (
    PROMPT_FORMAT_AUTO,
    PROMPT_FORMAT_FIXED,
    PROMPT_MODE_FIXED,
    PROMPT_MODE_LIST,
    PROMPT_MODE_TIMELINE,
)
from ComfyUI_H3_Continuum_Join.v2.prompts import (
    PromptPlanError,
    apply_prompt_overrides,
    build_sampler_prompt_plan,
    detect_prompt_mode,
    make_prompt_plan,
    parse_sparse_prompt_overrides,
    validate_sparse_prompt_overrides,
    validate_prompt_plan,
)


def test_fixed_prompt_repeats_without_mutation():
    plan = make_prompt_plan(mode=PROMPT_MODE_FIXED, script="hello", chunks=3, chunk_seconds=5)
    assert plan["prompts"] == ["hello", "hello", "hello"]
    assert len(set(plan["hashes"])) == 1
    assert validate_prompt_plan(plan) is plan


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ("one continuous prompt", PROMPT_MODE_FIXED),
        ("first\n---\nsecond", PROMPT_MODE_LIST),
        ("[0-5s]\nfirst", PROMPT_MODE_TIMELINE),
        ("[Chunk 1]\nfirst", PROMPT_MODE_TIMELINE),
    ],
)
def test_auto_detects_prompt_format(script, expected):
    assert detect_prompt_mode(script) == expected


def test_auto_plan_records_detected_format_without_changing_schema_mode():
    plan = make_prompt_plan(mode=PROMPT_FORMAT_AUTO, script="first\n---\nsecond", chunks=2, chunk_seconds=5)
    assert plan["mode"] == PROMPT_MODE_LIST
    assert plan["prompts"] == ["first", "second"]
    assert plan["notes"][0] == "Auto detected List"


def test_simple_fixed_format_maps_to_stable_fixed_plan_mode():
    plan = make_prompt_plan(mode=PROMPT_FORMAT_FIXED, script="same", chunks=2, chunk_seconds=5)
    assert plan["mode"] == PROMPT_MODE_FIXED


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


def test_timeline_preamble_is_applied_to_every_chunk():
    plan = make_prompt_plan(
        mode=PROMPT_FORMAT_AUTO,
        script="Refer to <Picture 1>.\n[0-5s]\none\n[5-10s]\ntwo",
        chunks=2,
        chunk_seconds=5,
    )
    assert plan["prompts"] == ["Refer to <Picture 1>.\n\none", "Refer to <Picture 1>.\n\ntwo"]
    assert plan["notes"] == ["Auto detected Timeline", "applied timeline preamble to all chunks"]


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


def test_external_prompt_overrides_only_the_connected_clip_and_rehashes_it():
    plan = make_prompt_plan(mode=PROMPT_MODE_LIST, script="first\n---\nsecond\n---\nthird", chunks=3, chunk_seconds=5)
    updated = apply_prompt_overrides(plan, [None, "external second", None])
    assert updated["prompts"] == ["first", "external second", "third"]
    assert updated["hashes"][0] == plan["hashes"][0]
    assert updated["hashes"][1] != plan["hashes"][1]
    assert updated["hashes"][2] == plan["hashes"][2]
    assert updated["notes"][-1] == "external Clip Prompt input(s): 2"


def test_external_prompt_with_same_text_keeps_the_same_hash():
    plan = make_prompt_plan(mode=PROMPT_MODE_FIXED, script="same", chunks=2, chunk_seconds=5)
    assert apply_prompt_overrides(plan, [None, "same"])["hashes"] == plan["hashes"]


def test_external_prompt_rejects_empty_connected_text():
    plan = make_prompt_plan(mode=PROMPT_MODE_FIXED, script="fallback", chunks=1, chunk_seconds=5)
    with pytest.raises(PromptPlanError):
        apply_prompt_overrides(plan, ["   "])


def test_sequence_prompt_precedes_connected_plan_and_legacy_script():
    connected = make_prompt_plan(mode=PROMPT_FORMAT_FIXED, script="connected plan", chunks=2, chunk_seconds=5)
    resolved = build_sampler_prompt_plan(prompt_mode=PROMPT_FORMAT_AUTO, prompt_script="legacy", sequence_prompt="first\n---\nsecond", prompt_plan=connected, chunks=2, chunk_seconds=5)
    assert resolved["prompts"] == ["first", "second"]


def test_connected_plan_precedes_legacy_script_without_sequence_input():
    connected = make_prompt_plan(mode=PROMPT_FORMAT_FIXED, script="connected plan", chunks=2, chunk_seconds=5)
    resolved = build_sampler_prompt_plan(prompt_mode=PROMPT_FORMAT_AUTO, prompt_script="legacy", sequence_prompt=None, prompt_plan=connected, chunks=2, chunk_seconds=5)
    assert resolved is connected


def test_sparse_overrides_replace_only_explicit_clips_and_rehash():
    plan = make_prompt_plan(mode=PROMPT_FORMAT_FIXED, script="Sequence Prompt", chunks=5, chunk_seconds=5)
    sparse = validate_sparse_prompt_overrides(parse_sparse_prompt_overrides("[Clip 2]\nclose-up\n\n[Clip 5]\nfinish naturally"), chunks=5)
    updated = apply_prompt_overrides(plan, [sparse.get(index) for index in range(1, 6)])
    assert updated["prompts"] == ["Sequence Prompt", "close-up", "Sequence Prompt", "Sequence Prompt", "finish naturally"]
    assert updated["hashes"][0] == plan["hashes"][0]
    assert updated["hashes"][1] != plan["hashes"][1]
    assert updated["hashes"][2] == plan["hashes"][2]
    assert updated["hashes"][3] == plan["hashes"][3]
    assert updated["hashes"][4] != plan["hashes"][4]


def test_sparse_override_clip_one_leaves_remaining_clips_unchanged():
    plan = make_prompt_plan(mode=PROMPT_FORMAT_FIXED, script="base", chunks=5, chunk_seconds=5)
    sparse = validate_sparse_prompt_overrides(parse_sparse_prompt_overrides("[Clip 1]\nopening override"), chunks=5)
    updated = apply_prompt_overrides(plan, [sparse.get(index) for index in range(1, 6)])
    assert updated["prompts"] == ["opening override", "base", "base", "base", "base"]


def test_sparse_override_rejects_out_of_range_clip():
    sparse = parse_sparse_prompt_overrides("[Clip 6]\noutside")
    with pytest.raises(PromptPlanError, match="outside"):
        validate_sparse_prompt_overrides(sparse, chunks=5)


def test_sparse_override_rejects_duplicate_clip():
    with pytest.raises(PromptPlanError, match="more than once"):
        parse_sparse_prompt_overrides("[Clip 2]\nfirst\n\n[Chunk 2]\nsecond")


def test_sparse_override_rejects_timeline_preamble():
    with pytest.raises(PromptPlanError, match="before the first"):
        parse_sparse_prompt_overrides("global text\n[Clip 1]\nopening override")
