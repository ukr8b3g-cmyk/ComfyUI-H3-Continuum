from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / "examples" / "workflows"
WORKFLOWS = sorted(WORKFLOW_DIR.glob("*.json"))


@pytest.mark.parametrize("workflow_path", WORKFLOWS, ids=lambda path: path.name)
def test_public_workflow_links_are_serialization_consistent(workflow_path: Path) -> None:
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    workflow = json.loads(json.dumps(workflow, ensure_ascii=False))
    nodes = {int(node["id"]): node for node in workflow["nodes"]}
    links = {int(link[0]): link for link in workflow["links"]}

    assert len(nodes) == len(workflow["nodes"]), "duplicate node ID"
    assert len(links) == len(workflow["links"]), "duplicate link ID"

    for link_id, link in links.items():
        _, source_id, source_slot, target_id, target_slot, link_type = link
        source = nodes[int(source_id)]
        target = nodes[int(target_id)]
        outputs = source.get("outputs") or []
        inputs = target.get("inputs") or []

        assert 0 <= int(source_slot) < len(outputs), f"link {link_id}: invalid source slot"
        assert 0 <= int(target_slot) < len(inputs), f"link {link_id}: invalid target slot"
        assert link_id in (outputs[int(source_slot)].get("links") or []), (
            f"link {link_id}: source output does not reference the link"
        )
        assert inputs[int(target_slot)].get("link") == link_id, (
            f"link {link_id}: target input does not reference the link"
        )

        endpoint_types = {
            value
            for value in (
                outputs[int(source_slot)].get("type"),
                inputs[int(target_slot)].get("type"),
                link_type,
            )
            if value not in (None, "*")
        }
        assert len(endpoint_types) <= 1, f"link {link_id}: endpoint type mismatch"

    for node in nodes.values():
        for output in node.get("outputs") or []:
            for link_id in output.get("links") or []:
                assert int(link_id) in links, f"node {node['id']}: dangling output link {link_id}"
        for input_ in node.get("inputs") or []:
            link_id = input_.get("link")
            if link_id is not None:
                assert int(link_id) in links, f"node {node['id']}: dangling input link {link_id}"

    if links:
        assert int(workflow["last_link_id"]) >= max(links)
