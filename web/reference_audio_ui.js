const NORMALIZED_INPUT_LABELS = {
    reference_video_1: "Video Guide Frames",
    driving_audio: "Driving Audio",
    audio_vae: "Driving Audio VAE",
    reference_audio_1: "Reference Audio (Optional)",
    reference_audio_vae: "Reference Audio VAE (Optional)",
};

export function normalizeReferenceAudioLabels(node) {
    if (!node) {
        return false;
    }
    for (const input of node.inputs || []) {
        const label = NORMALIZED_INPUT_LABELS[input.name];
        if (label) {
            input.label = label;
        }
    }
    return true;
}
