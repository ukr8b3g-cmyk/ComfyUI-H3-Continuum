from __future__ import annotations

import gc
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import torch

from ComfyUI_H3_Continuum_Join.v3 import file_backed_buffer as buffer


def _managed_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.iterdir()
        if path.suffix in {".bin", ".json", ".partial"}
    )


def test_backend_contract_accepts_auto_and_rejects_unknown_values():
    assert buffer.BUFFER_BACKEND_OPTIONS == (
        buffer.BUFFER_BACKEND_AUTO,
        buffer.BUFFER_BACKEND_RAM,
        buffer.BUFFER_BACKEND_DISK,
    )
    assert buffer.validate_buffer_backend("Auto") == "Auto"
    assert buffer.validate_buffer_backend("RAM") == "RAM"
    assert buffer.validate_buffer_backend("Disk-backed") == "Disk-backed"
    for value in ("disk-backed", "", None):
        with pytest.raises(ValueError, match="unknown Buffer Backend"):
            buffer.validate_buffer_backend(value)


def test_auto_selects_ram_only_with_size_and_memory_headroom(tmp_path, monkeypatch):
    gib = 1024**3
    monkeypatch.setattr(
        buffer,
        "_system_memory_bytes",
        lambda: (16 * gib, 64 * gib),
    )
    monkeypatch.setattr(
        buffer,
        "_disk_free_bytes",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("disk must not be queried for a safe RAM decision")
        ),
    )

    decision = buffer.select_auto_buffer_backend(gib, backing_root=tmp_path)

    assert decision.selected_backend == buffer.BUFFER_BACKEND_RAM
    assert decision.memory_reserve_bytes == int(64 * gib * 0.10)
    assert decision.disk_free_bytes is None
    assert "fits" in decision.reason


@pytest.mark.parametrize(
    ("final_bytes", "available", "reason"),
    (
        (5 * 1024**3, 48 * 1024**3, "exceeds"),
        (1 * 1024**3, 5 * 1024**3, "below"),
    ),
)
def test_auto_selects_disk_for_large_output_or_memory_pressure(
    tmp_path,
    monkeypatch,
    final_bytes,
    available,
    reason,
):
    gib = 1024**3
    monkeypatch.setattr(
        buffer,
        "_system_memory_bytes",
        lambda: (available, 64 * gib),
    )
    monkeypatch.setattr(buffer, "_disk_free_bytes", lambda _path: 100 * gib)

    decision = buffer.select_auto_buffer_backend(
        final_bytes,
        backing_root=tmp_path,
    )

    assert decision.selected_backend == buffer.BUFFER_BACKEND_DISK
    assert decision.disk_free_bytes == 100 * gib
    assert reason in decision.reason


def test_auto_uses_disk_when_memory_counters_are_unavailable(tmp_path, monkeypatch):
    gib = 1024**3
    monkeypatch.setattr(buffer, "_system_memory_bytes", lambda: (None, None))
    monkeypatch.setattr(buffer, "_disk_free_bytes", lambda _path: 100 * gib)

    decision = buffer.select_auto_buffer_backend(gib, backing_root=tmp_path)

    assert decision.selected_backend == buffer.BUFFER_BACKEND_DISK
    assert decision.memory_reserve_bytes is None
    assert "unavailable" in decision.reason


def test_auto_disk_shortage_is_explicit_and_never_falls_back(tmp_path, monkeypatch):
    gib = 1024**3
    monkeypatch.setattr(
        buffer,
        "_system_memory_bytes",
        lambda: (48 * gib, 64 * gib),
    )
    monkeypatch.setattr(buffer, "_disk_free_bytes", lambda _path: 6 * gib)

    with pytest.raises(RuntimeError, match="selected Disk-backed"):
        buffer.select_auto_buffer_backend(5 * gib, backing_root=tmp_path)


def test_auto_decision_report_records_selection_inputs(tmp_path, monkeypatch):
    gib = 1024**3
    monkeypatch.setattr(
        buffer,
        "_system_memory_bytes",
        lambda: (16 * gib, 64 * gib),
    )
    decision = buffer.select_auto_buffer_backend(gib, backing_root=tmp_path)

    report = buffer.format_auto_buffer_decision(decision)

    assert "selected=RAM" in report
    assert f"final_IMAGE={gib} bytes" in report
    assert "RAM_IMAGE_limit=4294967296 bytes" in report
    assert "reason=" in report


def test_default_root_is_resolved_lazily_from_comfyui_temp(tmp_path, monkeypatch):
    calls = []
    comfy_temp = tmp_path / "comfy-temp"
    fake_folder_paths = SimpleNamespace(
        get_temp_directory=lambda: calls.append(True) or str(comfy_temp)
    )
    monkeypatch.setitem(sys.modules, "folder_paths", fake_folder_paths)

    assert calls == []
    resolved = buffer.resolve_backing_root()
    assert calls == [True]
    assert resolved == (comfy_temp / "h3-continuum-v35-file-backed").resolve()


def test_default_root_has_a_non_comfy_test_fallback(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "folder_paths", None)
    monkeypatch.setattr(buffer.tempfile, "gettempdir", lambda: str(tmp_path))

    assert buffer.resolve_backing_root() == (
        tmp_path / "h3-continuum-v35-file-backed"
    ).resolve()


def test_explicit_root_bypasses_comfyui_resolution(tmp_path, monkeypatch):
    fake_folder_paths = SimpleNamespace(
        get_temp_directory=lambda: (_ for _ in ()).throw(
            AssertionError("folder_paths must not be evaluated")
        )
    )
    monkeypatch.setitem(sys.modules, "folder_paths", fake_folder_paths)

    assert buffer.resolve_backing_root(tmp_path) == tmp_path.resolve()


def test_file_backed_allocation_uses_process_global_manager_and_alias_lifetime(
    tmp_path,
):
    manager = buffer.get_file_backed_image_manager(tmp_path)
    assert manager is buffer.get_file_backed_image_manager(tmp_path)
    reference = torch.arange(4 * 3 * 2 * 3, dtype=torch.float32).reshape(4, 3, 2, 3)

    with buffer.allocate_file_backed_image(
        tuple(reference.shape),
        dtype=reference.dtype,
        backing_root=tmp_path,
    ) as allocation:
        allocation.tensor.copy_(reference)
        record = allocation.record
        output = allocation.publish()

    assert output.device.type == "cpu"
    assert output.is_contiguous()
    assert torch.equal(output, reference)
    assert record.data_path.parent == tmp_path.resolve()
    assert record.data_path.stat().st_size == reference.numel() * reference.element_size()
    assert record.data_path.exists()
    assert record.metadata_path.exists()

    alias = output[1:]
    del output
    gc.collect()
    held = manager.collect_ready()
    assert held.reclaimed == 0
    assert held.deferred == 1
    assert float(alias.sum()) == pytest.approx(float(reference[1:].sum()))
    assert record.data_path.exists()

    del alias
    gc.collect()
    released = manager.collect_ready()
    assert released.reclaimed == 1
    assert released.deferred == 0
    assert not _managed_files(tmp_path)


def test_unpublished_error_aborts_provisional_files(tmp_path):
    manager = buffer.get_file_backed_image_manager(tmp_path)

    with pytest.raises(RuntimeError, match="assembly failed"):
        with buffer.allocate_file_backed_image(
            (2, 2, 2, 3),
            dtype=torch.float32,
            backing_root=tmp_path,
        ) as allocation:
            allocation.tensor.fill_(1.0)
            raise RuntimeError("assembly failed")

    assert manager.tracked_count() == 0
    assert manager.pending_count() == 0
    assert not _managed_files(tmp_path)


def test_disk_backend_failure_is_propagated_without_ram_fallback(
    tmp_path,
    monkeypatch,
):
    class FailingManager:
        def allocate(self, *args, **kwargs):
            raise OSError("synthetic disk failure")

    monkeypatch.setattr(
        buffer,
        "get_file_backed_image_manager",
        lambda backing_root=None: FailingManager(),
    )
    with pytest.raises(OSError, match="synthetic disk failure"):
        buffer.allocate_file_backed_image(
            (2, 2, 2, 3),
            dtype=torch.float32,
            backing_root=tmp_path,
        )


def test_first_manager_access_reclaims_prior_dead_process_files(tmp_path):
    probe = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "p20_file_backed_tensor_poc.py"
    )
    subprocess.run(
        [
            sys.executable,
            str(probe),
            "--root",
            str(tmp_path),
            "--crash-child",
        ],
        check=True,
    )
    assert list(tmp_path.glob("*.bin"))
    assert list(tmp_path.glob("*.json"))

    buffer.get_file_backed_image_manager(tmp_path)

    assert not list(tmp_path.glob("*.bin"))
    assert not list(tmp_path.glob("*.json"))
