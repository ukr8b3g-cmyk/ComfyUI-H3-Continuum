from ComfyUI_H3_Continuum_Join import public_api


def test_public_api_is_v2_ready_and_complete():
    assert public_api.PUBLIC_API_VERSION == 2
    for name in (
        "make_extension_shape",
        "prepare_conditioning",
        "new_h3_latent",
        "capture_state",
        "select_context",
        "patch_layout_in_place",
        "trim_audio",
        "assemble_segments",
        "make_prompt_plan",
        "derive_chunk_seed",
        "choose_context_frames",
        "validate_session",
    ):
        assert callable(getattr(public_api, name))
