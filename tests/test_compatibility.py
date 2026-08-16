from types import SimpleNamespace

from ComfyUI_H3_Continuum_Join.compatibility import (
    _missing_callable_parameters,
    accelerator_summary,
)


def test_signature_contract_accepts_legacy_packed_layout_signature():
    def native(
        self,
        text_len,
        latent_t,
        latent_h,
        latent_w,
        audio_t,
        keyframes=None,
        refs=None,
        frame_count=None,
    ):
        pass

    assert _missing_callable_parameters(
        native,
        positional=("text_len", "latent_t", "latent_h", "latent_w", "audio_t"),
        keywords=("keyframes", "refs"),
    ) == []


def test_signature_contract_accepts_current_packed_layout_without_frame_count():
    def native(
        self,
        text_len,
        latent_t,
        latent_h,
        latent_w,
        audio_t,
        keyframes=None,
        refs=None,
    ):
        pass

    assert _missing_callable_parameters(
        native,
        positional=("text_len", "latent_t", "latent_h", "latent_w", "audio_t"),
        keywords=("keyframes", "refs"),
    ) == []


def test_signature_contract_accepts_sol_attn_style_forwarding_wrapper():
    # Sol-Attn's H3 Morton registration wraps PackedLayout.__init__ with this
    # effective shape: five named base args followed by *args/**kwargs.
    def sol_wrapper(
        self, text_len, latent_t, latent_h, latent_w, audio_t, *args, **kwargs
    ):
        pass

    assert _missing_callable_parameters(
        sol_wrapper,
        positional=("text_len", "latent_t", "latent_h", "latent_w", "audio_t"),
        keywords=("keyframes", "refs"),
    ) == []


def test_signature_contract_still_fails_closed_for_real_keyword_removal():
    def incompatible(self, text_len, latent_t, latent_h, latent_w, audio_t):
        pass

    assert _missing_callable_parameters(
        incompatible,
        positional=("text_len", "latent_t", "latent_h", "latent_w", "audio_t"),
        keywords=("keyframes", "refs"),
    ) == ["keyframes", "refs"]


def test_accelerator_summary_reads_modelpatcher_wrappers_and_transformer_markers():
    model = SimpleNamespace(
        wrappers={
            "diffusion_model": {
                "spectrum_h3.diffusion_model": [object()],
            },
            "apply_model": {
                "h3_continuum_join.apply_model.v1": [object()],
            },
        },
        model_options={
            "transformer_options": {
                "optimized_attention_override": object(),
                "sol_compose": {"min_tokens": 4096},
            },
            "h3_continuum_join": {"api_version": 1},
        },
    )
    summary = accelerator_summary(model)
    assert "Spectrum" in summary
    assert "Sol-Attn" in summary
    assert "attention override" in summary
    assert "Continuum" in summary


def test_accelerator_summary_is_informational_when_no_markers_exist():
    model = SimpleNamespace(wrappers={}, model_options={})
    assert "informational only" in accelerator_summary(model)
