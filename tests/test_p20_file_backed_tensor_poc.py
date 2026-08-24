from __future__ import annotations

import gc
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import weakref

import pytest
import torch


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "p20_file_backed_tensor_poc.py"
)
SPEC = importlib.util.spec_from_file_location("h3c_p20_file_backed_tensor_poc", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _known_files(root: Path) -> list[Path]:
    return sorted(path for path in root.iterdir() if path.name.startswith(MODULE.FILE_PREFIX))


def test_shared_mapping_is_bit_exact_contiguous_and_write_through(tmp_path):
    manager = MODULE.StorageLifetimeManager(tmp_path)
    reference = torch.arange(120, dtype=torch.float32).reshape(2, 3, 4, 5)

    with manager.allocate(tuple(reference.shape), dtype=reference.dtype) as allocation:
        allocation.tensor.copy_(reference)
        record = allocation.record
        output = allocation.publish()

    assert output.shape == reference.shape
    assert output.dtype == reference.dtype
    assert output.device.type == "cpu"
    assert output.is_contiguous()
    assert output.contiguous().data_ptr() == output.data_ptr()
    assert record.data_path.stat().st_size == reference.numel() * reference.element_size()
    assert record.data_path.read_bytes() == reference.numpy().tobytes(order="C")
    assert torch.equal(output, reference)

    storage_pointer = output.untyped_storage().data_ptr()
    assert output[1].untyped_storage().data_ptr() == storage_pointer
    assert output.detach().untyped_storage().data_ptr() == storage_pointer
    assert output.reshape(6, 4, 5).untyped_storage().data_ptr() == storage_pointer
    assert output.clone().untyped_storage().data_ptr() != storage_pointer

    del output
    gc.collect()
    result = manager.collect_ready()
    assert result.reclaimed == 1
    assert result.deferred == 0
    assert not _known_files(tmp_path)


def test_lifetime_waits_for_last_storage_alias_and_not_root_tensor(tmp_path):
    manager = MODULE.StorageLifetimeManager(tmp_path)
    with manager.allocate((4, 3, 2), dtype=torch.float32) as allocation:
        allocation.tensor.copy_(torch.arange(24, dtype=torch.float32).reshape(4, 3, 2))
        record = allocation.record
        output = allocation.publish()

    view = output[1:]
    cache = {"images": view}
    root_reference = weakref.ref(output)
    del output
    gc.collect()

    assert root_reference() is None
    assert float(cache["images"].sum()) == pytest.approx(261.0)
    first = manager.collect_ready()
    assert first.reclaimed == 0
    assert first.deferred == 1
    assert record.data_path.exists()
    assert record.metadata_path.exists()

    del view
    cache.clear()
    gc.collect()
    second = manager.collect_ready()
    assert second.reclaimed == 1
    assert second.deferred == 0
    assert not record.data_path.exists()
    assert not record.metadata_path.exists()


@pytest.mark.parametrize("exception_type", [RuntimeError, MODULE.ProbeCancelled])
def test_unpublished_exception_and_cancel_remove_provisional_files(
    tmp_path,
    exception_type,
):
    manager = MODULE.StorageLifetimeManager(tmp_path)
    with pytest.raises(exception_type):
        with manager.allocate((2, 2), dtype=torch.float32) as allocation:
            allocation.tensor.fill_(1.0)
            raise exception_type("stop before publish")

    assert manager.tracked_count() == 0
    assert not _known_files(tmp_path)


def test_mapping_creation_failure_removes_reserved_file(tmp_path, monkeypatch):
    manager = MODULE.StorageLifetimeManager(tmp_path)

    def fail_from_file(*args, **kwargs):
        raise RuntimeError("synthetic mapping failure")

    monkeypatch.setattr(MODULE.torch, "from_file", fail_from_file)
    with pytest.raises(RuntimeError, match="synthetic mapping failure"):
        manager.allocate((2, 2), dtype=torch.float32)
    assert not _known_files(tmp_path)


def test_temporary_unlink_failure_preserves_cancel_and_is_retried(
    tmp_path,
    monkeypatch,
):
    manager = MODULE.StorageLifetimeManager(tmp_path)
    original_unlink = MODULE._unlink_known
    fail_unlink = {"enabled": True}

    def sharing_violation(root, path):
        if fail_unlink["enabled"]:
            raise PermissionError(32, "synthetic sharing violation", str(path))
        return original_unlink(root, path)

    monkeypatch.setattr(MODULE, "_unlink_known", sharing_violation)
    with pytest.raises(MODULE.ProbeCancelled, match="original cancel"):
        with manager.allocate((2, 2), dtype=torch.float32) as allocation:
            allocation.tensor.fill_(1.0)
            raise MODULE.ProbeCancelled("original cancel")

    assert manager.pending_count() == 1
    assert len(_known_files(tmp_path)) == 2
    fail_unlink["enabled"] = False
    result = manager.collect_ready()
    assert result.reclaimed == 1
    assert result.deferred == 0
    assert manager.pending_count() == 0
    assert not _known_files(tmp_path)


def test_cancel_after_backing_file_create_does_not_leave_orphan(
    tmp_path,
    monkeypatch,
):
    manager = MODULE.StorageLifetimeManager(tmp_path)
    original_close = MODULE.os.close
    injected = False
    sentinel_path = tmp_path / "unrelated-live-descriptor.bin"
    sentinel_descriptor = None

    def cancel_after_real_close(descriptor):
        nonlocal injected, sentinel_descriptor
        original_close(descriptor)
        if not injected:
            injected = True
            opened = MODULE.os.open(
                sentinel_path,
                MODULE.os.O_CREAT | MODULE.os.O_EXCL | MODULE.os.O_RDWR,
                0o600,
            )
            if opened != descriptor:
                MODULE.os.dup2(opened, descriptor)
                original_close(opened)
                opened = descriptor
            sentinel_descriptor = opened
            raise MODULE.ProbeCancelled("cancel after backing file create")

    try:
        monkeypatch.setattr(MODULE.os, "close", cancel_after_real_close)
        with pytest.raises(MODULE.ProbeCancelled, match="after backing file create"):
            manager.allocate((2, 2), dtype=torch.float32)
    finally:
        monkeypatch.setattr(MODULE.os, "close", original_close)

    assert sentinel_descriptor is not None
    MODULE.os.write(sentinel_descriptor, b"still-open")
    original_close(sentinel_descriptor)
    assert sentinel_path.read_bytes() == b"still-open"
    manager.collect_ready()
    assert manager.pending_count() == 0
    assert not _known_files(tmp_path)


def test_dropped_unpublished_allocation_is_finalized(tmp_path):
    manager = MODULE.StorageLifetimeManager(tmp_path)
    allocation = manager.allocate((2, 2), dtype=torch.float32)
    allocation.tensor.fill_(3.0)
    allocation_reference = weakref.ref(allocation)
    del allocation
    gc.collect()

    assert allocation_reference() is None
    manager.collect_ready()
    assert manager.pending_count() == 0
    assert not _known_files(tmp_path)


def test_cache_requeue_keeps_backing_file_count_bounded(tmp_path):
    manager = MODULE.StorageLifetimeManager(tmp_path)
    cache = {}

    for index in range(20):
        with manager.allocate((2, 2), dtype=torch.float32) as allocation:
            allocation.tensor.fill_(float(index))
            output = allocation.publish()
        cache["same_node_output"] = output
        del output
        gc.collect()
        assert len(list(tmp_path.glob(f"{MODULE.FILE_PREFIX}*.bin"))) <= 2

    same_requeue = cache["same_node_output"]
    assert same_requeue is cache["same_node_output"]
    manager.collect_ready()
    assert len(list(tmp_path.glob(f"{MODULE.FILE_PREFIX}*.bin"))) == 1
    cache.clear()
    del same_requeue
    gc.collect()
    result = manager.collect_ready()
    assert result.reclaimed == 1
    assert not _known_files(tmp_path)


def test_published_downstream_error_keeps_cache_then_reclaims_after_eviction(tmp_path):
    manager = MODULE.StorageLifetimeManager(tmp_path)
    cache = {}
    try:
        with manager.allocate((2, 2), dtype=torch.float32) as allocation:
            allocation.tensor.fill_(4.0)
            output = allocation.publish()
        cache["assembler_output"] = output
        raise RuntimeError("downstream node failed")
    except RuntimeError:
        pass

    del output
    gc.collect()
    held = manager.collect_ready()
    assert held.reclaimed == 0
    assert held.deferred == 1
    assert len(list(tmp_path.glob(f"{MODULE.FILE_PREFIX}*.bin"))) == 1

    cache.clear()
    gc.collect()
    released = manager.collect_ready()
    assert released.reclaimed == 1
    assert released.deferred == 0
    assert not _known_files(tmp_path)


def test_process_global_manager_survives_node_local_scope(tmp_path):
    first = MODULE.get_process_lifetime_manager(tmp_path)
    second = MODULE.get_process_lifetime_manager(tmp_path)
    assert first is second

    with first.allocate((2, 2), dtype=torch.float32) as allocation:
        output = allocation.publish()
    manager_reference = weakref.ref(first)
    del first
    del second
    gc.collect()
    assert manager_reference() is not None

    del output
    gc.collect()
    manager = MODULE.get_process_lifetime_manager(tmp_path)
    assert manager.collect_ready().reclaimed == 1
    assert not _known_files(tmp_path)


def test_stale_child_files_are_reclaimed_but_live_and_unknown_files_are_kept(tmp_path):
    subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--root",
            str(tmp_path),
            "--crash-child",
        ],
        check=True,
    )
    assert len(list(tmp_path.glob(f"{MODULE.FILE_PREFIX}*.bin"))) == 1
    assert len(list(tmp_path.glob(f"{MODULE.FILE_PREFIX}*.json"))) == 1

    unknown = tmp_path / "unrelated.bin"
    unknown.write_bytes(b"do not delete")
    outside = tmp_path.parent / "outside.bin"
    outside.write_bytes(b"outside root")
    malicious_id = "f" * 32
    malicious_metadata = tmp_path / f"{MODULE.FILE_PREFIX}{malicious_id}.json"
    malicious_data = tmp_path / f"{MODULE.FILE_PREFIX}{malicious_id}.bin"
    malicious_data.write_bytes(b"protected")
    malicious_metadata.write_text(
        json.dumps(
            {
                "schema": MODULE.SCHEMA,
                "schema_version": MODULE.SCHEMA_VERSION,
                "allocation_id": malicious_id,
                "data_file": "..\\outside.bin",
                "owner_pid": -1,
                "created_at": 0,
            }
        ),
        encoding="utf-8",
    )

    result = MODULE.cleanup_stale_files(tmp_path, grace_seconds=0.0)
    assert result.removed_pairs == 1
    assert result.invalid_metadata == 1
    assert unknown.read_bytes() == b"do not delete"
    assert outside.read_bytes() == b"outside root"
    assert malicious_data.read_bytes() == b"protected"
    assert malicious_metadata.exists()


@pytest.mark.parametrize(
    ("field", "value", "remove"),
    [
        ("owner_pid", None, True),
        ("owner_pid", -1, False),
        ("owner_create_time", float("nan"), False),
        ("created_at", float("nan"), False),
    ],
)
def test_invalid_ownership_metadata_never_deletes_live_mapping(
    tmp_path,
    field,
    value,
    remove,
):
    manager = MODULE.StorageLifetimeManager(tmp_path)
    with manager.allocate((2, 2), dtype=torch.float32) as allocation:
        record = allocation.record
        output = allocation.publish()

    payload = json.loads(record.metadata_path.read_text(encoding="utf-8"))
    if remove:
        payload.pop(field)
    else:
        payload[field] = value
    record.metadata_path.write_text(json.dumps(payload), encoding="utf-8")

    result = MODULE.cleanup_stale_files(tmp_path, grace_seconds=0.0)
    assert result.invalid_metadata == 1
    assert result.removed_pairs == 0
    assert record.data_path.exists()
    assert record.metadata_path.exists()
    assert float(output.sum()) == pytest.approx(0.0)

    del output
    gc.collect()
    assert manager.collect_ready().reclaimed == 1
    assert not _known_files(tmp_path)


def test_cleanup_waits_for_in_progress_allocation_root_lock(tmp_path):
    allocation_entered = threading.Event()
    allow_allocation = threading.Event()
    output_holder = []
    cleanup_holder = []

    def allocation_hook(_path):
        allocation_entered.set()
        assert allow_allocation.wait(timeout=5.0)

    manager = MODULE.StorageLifetimeManager(
        tmp_path,
        allocation_hook=allocation_hook,
    )

    def allocate_output():
        with manager.allocate((2, 2), dtype=torch.float32) as allocation:
            output_holder.append(allocation.publish())

    def cleanup():
        cleanup_holder.append(
            MODULE.cleanup_stale_files(tmp_path, grace_seconds=0.0)
        )

    allocation_thread = threading.Thread(target=allocate_output)
    allocation_thread.start()
    assert allocation_entered.wait(timeout=5.0)
    cleanup_thread = threading.Thread(target=cleanup)
    cleanup_thread.start()
    assert cleanup_thread.is_alive()
    allow_allocation.set()
    allocation_thread.join(timeout=5.0)
    cleanup_thread.join(timeout=5.0)

    assert not allocation_thread.is_alive()
    assert not cleanup_thread.is_alive()
    assert cleanup_holder[0].retained_live == 1
    assert len(list(tmp_path.glob(f"{MODULE.FILE_PREFIX}*.bin"))) == 1

    output_holder.clear()
    gc.collect()
    assert manager.collect_ready().reclaimed == 1
    assert not _known_files(tmp_path)


def test_root_lock_is_reentrant_when_finalizer_runs_during_allocation(tmp_path):
    first_manager = MODULE.StorageLifetimeManager(tmp_path)
    abandoned = first_manager.allocate((2, 2), dtype=torch.float32)
    cycle = [abandoned]
    cycle.append(cycle)
    del abandoned
    del cycle

    def collect_abandoned_allocation(_path):
        gc.collect()

    second_manager = MODULE.StorageLifetimeManager(
        tmp_path,
        allocation_hook=collect_abandoned_allocation,
    )
    started = time.perf_counter()
    with second_manager.allocate((2, 2), dtype=torch.float32) as allocation:
        output = allocation.publish()
    elapsed = time.perf_counter() - started

    assert elapsed < 2.0
    first_manager.collect_ready()
    del output
    gc.collect()
    second_manager.collect_ready()
    assert not _known_files(tmp_path)


def test_cleanup_collect_and_gc_finalizer_have_no_lock_order_deadlock(tmp_path):
    subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--root",
            str(tmp_path),
            "--lock-order-child",
        ],
        check=True,
        timeout=10.0,
    )
    assert not _known_files(tmp_path)


def test_live_sidecar_is_retained_and_cleanup_is_idempotent(tmp_path):
    manager = MODULE.StorageLifetimeManager(tmp_path)
    with manager.allocate((2, 2), dtype=torch.float32) as allocation:
        allocation.tensor.fill_(2.0)
        record = allocation.record
        output = allocation.publish()

    live = MODULE.cleanup_stale_files(tmp_path, grace_seconds=0.0)
    assert live.retained_live == 1
    assert record.data_path.exists()
    assert record.metadata_path.exists()

    del output
    gc.collect()
    assert manager.collect_ready().reclaimed == 1
    empty = MODULE.cleanup_stale_files(tmp_path, grace_seconds=0.0)
    assert empty.removed_pairs == 0
    assert empty.removed_orphans == 0
    assert not _known_files(tmp_path)


def test_orphan_and_partial_cleanup_respects_grace_period(tmp_path):
    allocation_id = "a" * 32
    orphan = tmp_path / f"{MODULE.FILE_PREFIX}{allocation_id}.bin"
    partial = tmp_path / f"{MODULE.FILE_PREFIX}{allocation_id}.json.partial"
    orphan.write_bytes(b"orphan")
    partial.write_text("partial", encoding="utf-8")
    now = time.time()

    young = MODULE.cleanup_stale_files(
        tmp_path,
        grace_seconds=60.0,
        now=now,
    )
    assert young.retained_young == 2
    assert orphan.exists()
    assert partial.exists()

    old = MODULE.cleanup_stale_files(
        tmp_path,
        grace_seconds=60.0,
        now=now + 61.0,
    )
    assert old.removed_orphans == 2
    assert not orphan.exists()
    assert not partial.exists()


@pytest.mark.parametrize("shape", [(2.5, 2), (True, 2), ("2", 2), ()])
def test_shape_contract_rejects_lossy_or_empty_dimensions(tmp_path, shape):
    manager = MODULE.StorageLifetimeManager(tmp_path)
    with pytest.raises((TypeError, ValueError)):
        manager.allocate(shape, dtype=torch.float32)
    assert not _known_files(tmp_path)


def test_standalone_probe_passes(tmp_path):
    result = MODULE.run_probe(tmp_path)
    assert result.bit_exact
    assert result.file_size == result.expected_bytes
    assert result.root_released_while_alias_alive
    assert result.deferred_while_alias_alive == 1
    assert result.reclaimed_after_last_alias == 1
    assert result.files_remaining == 0
