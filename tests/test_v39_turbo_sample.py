import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
NAME = "MiniMax_H3_Continuum_V39_Turbo_Sample.json"

def test_turbo_sample_is_installable_and_keeps_prompt_and_explicit_settings():
    path = ROOT / "examples/workflows" / NAME
    payload = path.read_bytes()
    assert (ROOT / "examples" / NAME).read_bytes() == payload
    with ZipFile(path.with_suffix(".zip")) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == [NAME]
        assert archive.read(NAME) == payload
    graph = json.loads(payload)
    nodes = {n["id"]: n for n in graph["nodes"]}
    preview = next(n for n in nodes.values() if n["type"] == "ModelPreviewOverrideKJ")
    ports = {port["name"]: port["link"] for port in preview["inputs"]}
    assert ports["vae"] is None and ports["audio_vae"] is None
    assert any(link[0] == ports["model"] and link[3] == preview["id"] for link in graph["links"])
    assert all(link[4] == 0 for link in graph["links"] if link[3] == preview["id"])
    assert preview["widgets_values"][-2] == "none"
    named = nodes[312]["widgets_values_named"]
    assert nodes[312]["widgets_values"] == list(named.values())
    assert (named["prompt_mode"], named["chunks"], named["chunk_seconds"]) == ("Auto", 2, 8)
    assert named["run_storage"] == "Off"
    assert named["project_id"] != "1fefd563-68c4-45f7-a33f-8a2911850a9c"
    assert nodes[317]["mode"] == 0
    assert next(i for i in nodes[312]["inputs"] if i["name"] == "first_frame")["link"] == 382
    prompt = nodes[188]["widgets_values"][0]
    assert prompt == nodes[188]["widgets_values_named"]["value"]
    assert prompt.startswith("[Chunk 1]\nFor the target video")
    assert "<Picture 1>" in prompt and "[Chunk 2]\n" in prompt
    assert "Continuation of Chunk 1." in prompt
    assert prompt.count("<d>[Thai]") == 2
    assert "background unchanged" in prompt
    enabled = [v for v in nodes[286]["widgets_values"] if isinstance(v, dict) and v.get("on")]
    assert len(enabled) == 1 and "turbo_4step" in enabled[0]["lora"]
    assert nodes[150]["widgets_values"][0] is False
    assert "models" not in nodes[147]["properties"]
    assert nodes[191]["widgets_values"][0].endswith("_Turbo_Sample")
