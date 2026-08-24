"""Phase 2A P2-0 probe for a Windows-safe file-backed IMAGE buffer.

The accepted storage/lifetime implementation remains here as the single tested
source and is re-exported through ``v3.file_backed_buffer`` for the V3.5
assembler.  The standalone probes below continue to exercise the same code.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import sys
import threading
import time
from typing import Any, Callable, Iterator
import uuid
import weakref

import torch


SCHEMA = "h3-continuum-p20-file-backed-tensor"
SCHEMA_VERSION = 1
FILE_PREFIX = "h3c-p20-"
_ID_PATTERN = re.compile(r"^h3c-p20-([0-9a-f]{32})\.(bin|json)$")
_PARTIAL_PATTERN = re.compile(r"^h3c-p20-([0-9a-f]{32})\.json\.partial$")
_LOCK_FILE_NAME = ".h3c-p20.lock"
_ROOT_THREAD_LOCKS: dict[str, threading.RLock] = {}
_ROOT_THREAD_LOCKS_GUARD = threading.Lock()
_ROOT_LOCK_STATE = threading.local()
_PROCESS_MANAGERS: dict[str, "StorageLifetimeManager"] = {}
_PROCESS_MANAGERS_GUARD = threading.Lock()


class FileBackedPoCError(RuntimeError):
    """Raised when the P2-0 backend cannot uphold its safety contract."""


class StorageTrackingUnavailable(FileBackedPoCError):
    """Raised when the current PyTorch cannot weakly track Storage lifetime."""


class ProbeCancelled(BaseException):
    """BaseException used to verify cancellation cleanup in the standalone PoC."""


@dataclass(frozen=True)
class BackingRecord:
    allocation_id: str
    data_path: Path
    metadata_path: Path
    shape: tuple[int, ...]
    dtype: torch.dtype
    numel: int
    nbytes: int


@dataclass(frozen=True)
class CollectionResult:
    reclaimed: int
    deferred: int
    errors: tuple[str, ...]


@dataclass(frozen=True)
class StaleCleanupResult:
    removed_pairs: int
    removed_orphans: int
    retained_live: int
    retained_young: int
    invalid_metadata: int
    deferred: int
    errors: tuple[str, ...]


@dataclass(frozen=True)
class ProbeResult:
    torch_version: str
    bit_exact: bool
    file_size: int
    expected_bytes: int
    root_released_while_alias_alive: bool
    deferred_while_alias_alive: int
    reclaimed_after_last_alias: int
    files_remaining: int


def _storage_weak_ref(tensor: torch.Tensor) -> Any:
    """Create an alias-aware weak reference to the underlying Storage.

    ``weakref.finalize(tensor, ...)`` is not sufficient: a Tensor view can keep
    the Storage alive after that particular Tensor object has died.  The PoC
    feature-detects PyTorch's StorageWeakRef and fails closed when unavailable.
    """

    try:
        from torch.multiprocessing.reductions import StorageWeakRef

        reference = StorageWeakRef(tensor.untyped_storage())
        if not callable(getattr(reference, "expired", None)):
            raise TypeError("StorageWeakRef.expired is unavailable")
        return reference
    except Exception as exc:
        raise StorageTrackingUnavailable(
            "this PyTorch build cannot track the lifetime of file-backed "
            "Tensor storage aliases"
        ) from exc


def _process_create_time(pid: int) -> float | None:
    try:
        import psutil

        return float(psutil.Process(int(pid)).create_time())
    except Exception:
        return None


_CURRENT_PROCESS_CREATE_TIME = _process_create_time(os.getpid())


def _same_live_process(pid: int, expected_create_time: float | None) -> bool:
    """Return True conservatively when a sidecar may belong to a live process."""

    pid = int(pid)
    if pid <= 0:
        return False
    try:
        import psutil

        process = psutil.Process(pid)
        actual_create_time = float(process.create_time())
        if expected_create_time is None:
            return bool(process.is_running())
        return bool(process.is_running()) and abs(
            actual_create_time - float(expected_create_time)
        ) <= 1.0
    except ImportError:
        pass
    except Exception as exc:
        try:
            import psutil

            if isinstance(exc, psutil.NoSuchProcess):
                return False
            if isinstance(exc, psutil.AccessDenied):
                return True
        except Exception:
            return True
        return True

    if pid == os.getpid():
        if expected_create_time is None or _CURRENT_PROCESS_CREATE_TIME is None:
            return True
        return abs(
            float(expected_create_time) - _CURRENT_PROCESS_CREATE_TIME
        ) <= 1.0
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    partial_path = path.with_suffix(path.suffix + ".partial")
    with partial_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial_path, path)


def _dtype_name(dtype: torch.dtype) -> str:
    value = str(dtype)
    return value[6:] if value.startswith("torch.") else value


def _validate_shape(shape: tuple[int, ...]) -> tuple[int, ...]:
    normalized_values: list[int] = []
    for value in shape:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("file-backed Tensor dimensions must be integers")
        normalized_values.append(value)
    normalized = tuple(normalized_values)
    if not normalized or any(value <= 0 for value in normalized):
        raise ValueError("file-backed Tensor shape must contain positive dimensions")
    return normalized


def _known_path(root: Path, path: Path) -> bool:
    try:
        return path.parent.resolve() == root.resolve() and bool(
            _ID_PATTERN.fullmatch(path.name) or _PARTIAL_PATTERN.fullmatch(path.name)
        )
    except OSError:
        return False


def _unlink_known(root: Path, path: Path) -> bool:
    if not _known_path(root, path):
        raise FileBackedPoCError(f"refusing to unlink an unknown path: {path}")
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def _thread_lock_for_root(root: Path) -> threading.RLock:
    key = os.path.normcase(str(root.resolve()))
    with _ROOT_THREAD_LOCKS_GUARD:
        lock = _ROOT_THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _ROOT_THREAD_LOCKS[key] = lock
        return lock


@contextmanager
def _root_lock(root: Path):
    """Serialize allocation and cleanup across threads and ComfyUI processes."""

    root.mkdir(parents=True, exist_ok=True)
    key = os.path.normcase(str(root.resolve()))
    thread_lock = _thread_lock_for_root(root)
    with thread_lock:
        depths = getattr(_ROOT_LOCK_STATE, "depths", None)
        if depths is None:
            depths = {}
            _ROOT_LOCK_STATE.depths = depths
        depth = int(depths.get(key, 0))
        if depth > 0:
            depths[key] = depth + 1
            try:
                yield
            finally:
                remaining = int(depths[key]) - 1
                if remaining > 0:
                    depths[key] = remaining
                else:
                    depths.pop(key, None)
            return

        lock_path = root / _LOCK_FILE_NAME
        try:
            with lock_path.open("a+b") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    depths[key] = 1
                    try:
                        yield
                    finally:
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                    depths[key] = 1
                    try:
                        yield
                    finally:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            depths.pop(key, None)


class _TrackedStorage:
    __slots__ = ("record", "storage_reference")

    def __init__(self, record: BackingRecord, tensor: torch.Tensor):
        self.record = record
        self.storage_reference = _storage_weak_ref(tensor)

    def expired(self) -> bool:
        return bool(self.storage_reference.expired())


class FileBackedAllocation:
    """Provisional allocation that is deleted unless explicitly published."""

    def __init__(
        self,
        manager: "StorageLifetimeManager",
        tensor: torch.Tensor,
        record: BackingRecord,
    ):
        self._manager = manager
        self._tensor: torch.Tensor | None = tensor
        self.record = record
        self._published = False
        self._cleanup_finalizer = weakref.finalize(
            self,
            manager._discard_unpublished,
            record,
        )

    @property
    def tensor(self) -> torch.Tensor:
        if self._tensor is None:
            raise FileBackedPoCError("file-backed allocation is no longer available")
        return self._tensor

    def publish(self) -> torch.Tensor:
        if self._published:
            raise FileBackedPoCError("file-backed allocation was already published")
        tensor = self.tensor
        try:
            self._manager._register(self.record, tensor)
        except BaseException:
            self.abort()
            raise
        self._published = True
        self._cleanup_finalizer.detach()
        self._tensor = None
        return tensor

    def abort(self) -> None:
        if self._published:
            raise FileBackedPoCError("cannot abort a published file-backed Tensor")
        self._tensor = None
        if self._cleanup_finalizer.alive:
            self._cleanup_finalizer()
        # Explicit cancellation should attempt cleanup now.  The finalizer only
        # enqueues an intent so GC never performs filesystem I/O or waits on a
        # Windows byte lock.  Cleanup failures remain queued for a later sweep
        # and must not replace the exception that caused __exit__ to abort.
        try:
            self._manager.collect_ready()
        except Exception:
            pass

    def __enter__(self) -> "FileBackedAllocation":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if not self._published:
            self.abort()
        return False


class StorageLifetimeManager:
    """Track backing files without retaining their Tensor/storage strongly."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        allocation_hook: Callable[[Path], None] | None = None,
    ):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._tracked: dict[str, _TrackedStorage] = {}
        self._pending: dict[str, tuple[Path, ...]] = {}
        self._abandoned: queue.SimpleQueue[BackingRecord] = queue.SimpleQueue()
        self._lock = threading.RLock()
        self._allocation_hook = allocation_hook

    def allocate(
        self,
        shape: tuple[int, ...],
        *,
        dtype: torch.dtype = torch.float32,
    ) -> FileBackedAllocation:
        with _root_lock(self.root):
            with self._lock:
                self._drain_abandoned_locked()
                self._collect_ready_locked()
                return self._allocate_locked(shape, dtype=dtype)

    def _allocate_locked(
        self,
        shape: tuple[int, ...],
        *,
        dtype: torch.dtype,
    ) -> FileBackedAllocation:
        normalized_shape = _validate_shape(shape)
        if not isinstance(dtype, torch.dtype):
            raise TypeError("dtype must be a torch.dtype")
        numel = math.prod(normalized_shape)
        element_size = torch.empty((), dtype=dtype).element_size()
        allocation_id = uuid.uuid4().hex
        data_path = self.root / f"{FILE_PREFIX}{allocation_id}.bin"
        metadata_path = self.root / f"{FILE_PREFIX}{allocation_id}.json"
        descriptor: int | None = None
        tensor: torch.Tensor | None = None
        try:
            descriptor = os.open(
                data_path,
                os.O_CREAT | os.O_EXCL | os.O_RDWR,
                0o600,
            )
            try:
                os.close(descriptor)
            finally:
                # close() may raise after the OS already released the handle.
                # Never retry that numeric fd: another thread could already
                # have reused it for an unrelated file.
                descriptor = None
            flat = torch.from_file(
                str(data_path),
                shared=True,
                size=numel,
                dtype=dtype,
            )
            tensor = flat.reshape(normalized_shape)
            del flat
            if tensor.device.type != "cpu" or not tensor.is_contiguous():
                raise FileBackedPoCError(
                    "torch.from_file did not create a contiguous CPU Tensor"
                )
            if self._allocation_hook is not None:
                self._allocation_hook(data_path)
            record = BackingRecord(
                allocation_id=allocation_id,
                data_path=data_path,
                metadata_path=metadata_path,
                shape=normalized_shape,
                dtype=dtype,
                numel=numel,
                nbytes=numel * element_size,
            )
            _atomic_write_json(
                metadata_path,
                {
                    "schema": SCHEMA,
                    "schema_version": SCHEMA_VERSION,
                    "allocation_id": allocation_id,
                    "data_file": data_path.name,
                    "shape": list(normalized_shape),
                    "dtype": _dtype_name(dtype),
                    "numel": numel,
                    "nbytes": record.nbytes,
                    "owner_pid": os.getpid(),
                    "owner_create_time": _CURRENT_PROCESS_CREATE_TIME,
                    "created_at": time.time(),
                },
            )
            return FileBackedAllocation(self, tensor, record)
        except BaseException:
            tensor = None
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except BaseException:
                    # Preserve the original cancellation/error.  On Windows an
                    # actually-live descriptor will also make unlink fail, so
                    # the backing paths remain in the retryable pending set.
                    pass
            paths = (
                metadata_path.with_suffix(metadata_path.suffix + ".partial"),
                metadata_path,
                data_path,
            )
            failed = False
            for path in paths:
                try:
                    _unlink_known(self.root, path)
                except BaseException:
                    failed = True
            if failed:
                self._pending[allocation_id] = paths
            raise

    def _register(self, record: BackingRecord, tensor: torch.Tensor) -> None:
        with _root_lock(self.root):
            with self._lock:
                if record.allocation_id in self._tracked:
                    raise FileBackedPoCError("duplicate file-backed allocation ID")
                if not record.data_path.is_file() or not record.metadata_path.is_file():
                    raise FileBackedPoCError("file-backed allocation files are missing")
                self._tracked[record.allocation_id] = _TrackedStorage(record, tensor)

    def _discard_unpublished(self, record: BackingRecord) -> None:
        """Queue GC cleanup without taking locks or touching the filesystem."""

        self._abandoned.put(record)

    def _drain_abandoned_locked(self) -> None:
        """Move finalizer intents into the retryable pending set."""

        while True:
            try:
                record = self._abandoned.get_nowait()
            except queue.Empty:
                return
            paths = (
                record.metadata_path.with_suffix(
                    record.metadata_path.suffix + ".partial"
                ),
                record.metadata_path,
                record.data_path,
            )
            if record.allocation_id not in self._tracked:
                self._pending[record.allocation_id] = paths

    def collect_ready(self) -> CollectionResult:
        with _root_lock(self.root):
            with self._lock:
                self._drain_abandoned_locked()
                return self._collect_ready_locked()

    def _collect_ready_locked(self) -> CollectionResult:
        reclaimed = 0
        deferred = 0
        errors: list[str] = []
        for allocation_id, paths in list(self._pending.items()):
            failed = False
            for path in paths:
                try:
                    _unlink_known(self.root, path)
                except OSError as exc:
                    failed = True
                    errors.append(f"{path.name}: {type(exc).__name__}: {exc}")
            if failed:
                deferred += 1
                continue
            del self._pending[allocation_id]
            reclaimed += 1
        for allocation_id, tracked in list(self._tracked.items()):
            try:
                expired = tracked.expired()
            except Exception as exc:
                deferred += 1
                errors.append(
                    f"{allocation_id}: storage lifetime unavailable: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue
            if not expired:
                deferred += 1
                continue
            failed = False
            for path in (tracked.record.data_path, tracked.record.metadata_path):
                try:
                    _unlink_known(self.root, path)
                except OSError as exc:
                    failed = True
                    errors.append(
                        f"{path.name}: {type(exc).__name__}: {exc}"
                    )
            if failed:
                deferred += 1
                continue
            del self._tracked[allocation_id]
            reclaimed += 1
        return CollectionResult(reclaimed, deferred, tuple(errors))

    def tracked_count(self) -> int:
        with self._lock:
            return len(self._tracked)

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)


def get_process_lifetime_manager(
    root: str | os.PathLike[str],
) -> StorageLifetimeManager:
    """Return a process-global manager so cache lifetime outlives one node call."""

    resolved = Path(root).expanduser().resolve()
    key = os.path.normcase(str(resolved))
    with _PROCESS_MANAGERS_GUARD:
        manager = _PROCESS_MANAGERS.get(key)
        if manager is None:
            manager = StorageLifetimeManager(resolved)
            _PROCESS_MANAGERS[key] = manager
        return manager


def _sidecar_age(metadata_path: Path, payload: dict[str, Any], now: float) -> float:
    created_at = payload.get("created_at")
    if isinstance(created_at, (int, float)) and math.isfinite(float(created_at)):
        return max(0.0, now - float(created_at))
    return max(0.0, now - metadata_path.stat().st_mtime)


def _valid_sidecar(
    metadata_path: Path,
    payload: dict[str, Any],
) -> tuple[bool, Path]:
    match = _ID_PATTERN.fullmatch(metadata_path.name)
    if match is None or match.group(2) != "json":
        return False, metadata_path.with_suffix(".bin")
    expected_data = metadata_path.with_suffix(".bin")
    shape = payload.get("shape")
    owner_pid = payload.get("owner_pid")
    owner_create_time = payload.get("owner_create_time")
    created_at = payload.get("created_at")
    numel = payload.get("numel")
    nbytes = payload.get("nbytes")
    dtype = payload.get("dtype")
    shape_valid = (
        isinstance(shape, list)
        and bool(shape)
        and all(type(value) is int and value > 0 for value in shape)
    )
    ownership_valid = (
        type(owner_pid) is int
        and owner_pid > 0
        and "owner_create_time" in payload
        and (
            owner_create_time is None
            or (
                isinstance(owner_create_time, (int, float))
                and not isinstance(owner_create_time, bool)
                and math.isfinite(float(owner_create_time))
                and float(owner_create_time) > 0.0
            )
        )
        and isinstance(created_at, (int, float))
        and not isinstance(created_at, bool)
        and math.isfinite(float(created_at))
        and float(created_at) > 0.0
    )
    size_valid = (
        type(numel) is int
        and numel > 0
        and shape_valid
        and numel == math.prod(shape)
        and type(nbytes) is int
        and nbytes > 0
        and isinstance(dtype, str)
        and bool(dtype)
    )
    valid = (
        payload.get("schema") == SCHEMA
        and payload.get("schema_version") == SCHEMA_VERSION
        and payload.get("allocation_id") == match.group(1)
        and payload.get("data_file") == expected_data.name
        and ownership_valid
        and size_valid
    )
    return bool(valid), expected_data


def cleanup_stale_files(
    root: str | os.PathLike[str],
    *,
    grace_seconds: float,
    now: float | None = None,
    process_is_live: Callable[[int, float | None], bool] = _same_live_process,
) -> StaleCleanupResult:
    """Remove only dead-process artifacts inside the dedicated P2-0 root."""

    root_path = Path(root).expanduser().resolve()
    root_path.mkdir(parents=True, exist_ok=True)
    with _root_lock(root_path):
        return _cleanup_stale_files_locked(
            root_path,
            grace_seconds=grace_seconds,
            now=now,
            process_is_live=process_is_live,
        )


def _cleanup_stale_files_locked(
    root_path: Path,
    *,
    grace_seconds: float,
    now: float | None,
    process_is_live: Callable[[int, float | None], bool],
) -> StaleCleanupResult:
    grace_seconds = max(0.0, float(grace_seconds))
    current_time = time.time() if now is None else float(now)
    removed_pairs = 0
    removed_orphans = 0
    retained_live = 0
    retained_young = 0
    invalid_metadata = 0
    deferred = 0
    errors: list[str] = []
    referenced_data: set[str] = set()
    protected_data: set[str] = set()

    for metadata_path in sorted(root_path.glob(f"{FILE_PREFIX}*.json")):
        if not _known_path(root_path, metadata_path):
            continue
        expected_data = metadata_path.with_suffix(".bin")
        protected_data.add(expected_data.name)
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("metadata root is not an object")
        except Exception as exc:
            invalid_metadata += 1
            errors.append(
                f"{metadata_path.name}: invalid metadata: {type(exc).__name__}: {exc}"
            )
            continue
        valid, data_path = _valid_sidecar(metadata_path, payload)
        if not valid:
            invalid_metadata += 1
            errors.append(f"{metadata_path.name}: metadata contract mismatch")
            continue
        referenced_data.add(data_path.name)
        try:
            age = _sidecar_age(metadata_path, payload, current_time)
        except OSError as exc:
            deferred += 1
            errors.append(f"{metadata_path.name}: {type(exc).__name__}: {exc}")
            continue
        try:
            pid = int(payload.get("owner_pid"))
        except (TypeError, ValueError):
            pid = -1
        create_time_value = payload.get("owner_create_time")
        create_time = (
            float(create_time_value)
            if isinstance(create_time_value, (int, float))
            else None
        )
        if process_is_live(pid, create_time):
            retained_live += 1
            continue
        if age < grace_seconds:
            retained_young += 1
            continue
        pair_failed = False
        for path in (data_path, metadata_path):
            try:
                _unlink_known(root_path, path)
            except OSError as exc:
                pair_failed = True
                errors.append(f"{path.name}: {type(exc).__name__}: {exc}")
        if pair_failed:
            deferred += 1
        else:
            removed_pairs += 1

    for data_path in sorted(root_path.glob(f"{FILE_PREFIX}*.bin")):
        if not _known_path(root_path, data_path):
            continue
        if data_path.name in referenced_data or data_path.name in protected_data:
            continue
        try:
            age = max(0.0, current_time - data_path.stat().st_mtime)
            if age < grace_seconds:
                retained_young += 1
                continue
            _unlink_known(root_path, data_path)
            removed_orphans += 1
        except OSError as exc:
            deferred += 1
            errors.append(f"{data_path.name}: {type(exc).__name__}: {exc}")

    for partial_path in sorted(root_path.glob(f"{FILE_PREFIX}*.json.partial")):
        if not _known_path(root_path, partial_path):
            continue
        try:
            age = max(0.0, current_time - partial_path.stat().st_mtime)
            if age < grace_seconds:
                retained_young += 1
                continue
            _unlink_known(root_path, partial_path)
            removed_orphans += 1
        except OSError as exc:
            deferred += 1
            errors.append(f"{partial_path.name}: {type(exc).__name__}: {exc}")

    return StaleCleanupResult(
        removed_pairs=removed_pairs,
        removed_orphans=removed_orphans,
        retained_live=retained_live,
        retained_young=retained_young,
        invalid_metadata=invalid_metadata,
        deferred=deferred,
        errors=tuple(errors),
    )


def _raw_float32_bytes(tensor: torch.Tensor) -> bytes:
    value = tensor.detach().to(device="cpu", dtype=torch.float32)
    if not value.is_contiguous():
        value = value.contiguous()
    return value.numpy().tobytes(order="C")


def _remaining_known_files(root: Path) -> Iterator[Path]:
    for path in root.iterdir():
        if _known_path(root, path):
            yield path


def run_probe(root: str | os.PathLike[str]) -> ProbeResult:
    manager = get_process_lifetime_manager(root)
    cleanup_stale_files(manager.root, grace_seconds=0.0)
    reference = torch.arange(2 * 3 * 4 * 5, dtype=torch.float32).reshape(2, 3, 4, 5)
    with manager.allocate(tuple(reference.shape), dtype=reference.dtype) as allocation:
        allocation.tensor.copy_(reference)
        record = allocation.record
        output = allocation.publish()

    bit_exact = torch.equal(output, reference) and (
        record.data_path.read_bytes() == _raw_float32_bytes(reference)
    )
    actual_file_size = record.data_path.stat().st_size
    alias = output[1]
    cache = {"output": alias}
    output_reference = weakref.ref(output)
    del output
    gc.collect()
    deferred = manager.collect_ready()
    root_released = output_reference() is None and float(cache["output"].sum()) >= 0.0
    del alias
    cache.clear()
    gc.collect()
    reclaimed = manager.collect_ready()
    return ProbeResult(
        torch_version=str(torch.__version__),
        bit_exact=bool(bit_exact),
        file_size=actual_file_size,
        expected_bytes=reference.numel() * reference.element_size(),
        root_released_while_alias_alive=root_released,
        deferred_while_alias_alive=deferred.deferred,
        reclaimed_after_last_alias=reclaimed.reclaimed,
        files_remaining=sum(1 for _ in _remaining_known_files(manager.root)),
    )


def _crash_child(root: str | os.PathLike[str]) -> None:
    manager = StorageLifetimeManager(root)
    with manager.allocate((2, 3, 4), dtype=torch.float32) as allocation:
        allocation.tensor.fill_(1.0)
        output = allocation.publish()
        if float(output.sum()) <= 0.0:
            os._exit(3)
        os._exit(0)


def _lock_order_child(root: str | os.PathLike[str]) -> None:
    """Regression child for root/manager lock order and GC finalizer safety."""

    root_path = Path(root).expanduser().resolve()
    manager = StorageLifetimeManager(root_path)
    gc.disable()
    allocation = manager.allocate((2, 2), dtype=torch.float32)
    abandoned_cycle: list[Any] = [allocation]
    abandoned_cycle.append(abandoned_cycle)
    del allocation
    del abandoned_cycle

    manager_lock_acquired = threading.Event()
    cleanup_callback_entered = threading.Event()
    collector_started = threading.Event()
    failures: list[BaseException] = []
    original_manager_lock = manager._lock

    class SignalingLock:
        def __enter__(self):
            original_manager_lock.acquire()
            manager_lock_acquired.set()
            return self

        def __exit__(self, exc_type, exc, traceback):
            original_manager_lock.release()
            return False

    manager._lock = SignalingLock()  # type: ignore[assignment]

    def process_is_live(_pid: int, _create_time: float | None) -> bool:
        cleanup_callback_entered.set()
        if not collector_started.wait(timeout=2.0):
            raise RuntimeError("collector did not start")
        # With root-before-manager ordering the collector must still be waiting
        # for the root lock here.  The GC finalizer must only enqueue cleanup.
        manager_lock_acquired.wait(timeout=0.25)
        gc.collect()
        return True

    def run_cleanup() -> None:
        try:
            cleanup_stale_files(
                root_path,
                grace_seconds=0.0,
                process_is_live=process_is_live,
            )
        except BaseException as exc:
            failures.append(exc)

    def run_collector() -> None:
        collector_started.set()
        try:
            manager.collect_ready()
        except BaseException as exc:
            failures.append(exc)

    cleanup_thread = threading.Thread(target=run_cleanup, daemon=True)
    cleanup_thread.start()
    if not cleanup_callback_entered.wait(timeout=2.0):
        os._exit(90)
    collector_thread = threading.Thread(target=run_collector, daemon=True)
    collector_thread.start()
    cleanup_thread.join(timeout=3.0)
    collector_thread.join(timeout=3.0)
    if cleanup_thread.is_alive() or collector_thread.is_alive():
        os._exit(91)
    if failures:
        os._exit(92)
    manager.collect_ready()
    if any(_remaining_known_files(root_path)):
        os._exit(93)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--crash-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--lock-order-child",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    arguments = parser.parse_args(argv)
    if arguments.crash_child:
        _crash_child(arguments.root)
        return 0
    if arguments.lock_order_child:
        _lock_order_child(arguments.root)
        return 0
    result = run_probe(arguments.root)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(
        (
            result.bit_exact,
            result.file_size == result.expected_bytes,
            result.root_released_while_alias_alive,
            result.deferred_while_alias_alive == 1,
            result.reclaimed_after_last_alias == 1,
            result.files_remaining == 0,
        )
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
