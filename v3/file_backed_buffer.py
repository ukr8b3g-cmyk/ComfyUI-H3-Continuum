"""V3.5 adapter for the accepted P2-0 file-backed Tensor backend.

The storage and lifetime implementation remains in the P2-0 module so the
Windows-tested locking, sidecar, cancellation, and alias-lifetime contracts
have one implementation.  This module only exposes the small Production API
needed by the V3.5 assembler.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
import threading

import torch

from ..tools.p20_file_backed_tensor_poc import (
    FileBackedAllocation,
    StorageLifetimeManager,
    cleanup_stale_files,
    get_process_lifetime_manager,
)


BUFFER_BACKEND_AUTO = "Auto"
BUFFER_BACKEND_RAM = "RAM"
BUFFER_BACKEND_DISK = "Disk-backed"
BUFFER_BACKEND_OPTIONS = (
    BUFFER_BACKEND_AUTO,
    BUFFER_BACKEND_RAM,
    BUFFER_BACKEND_DISK,
)
AUTO_RAM_IMAGE_LIMIT_BYTES = 4 * 1024**3
AUTO_RAM_RESERVE_MIN_BYTES = 4 * 1024**3
AUTO_RAM_RESERVE_FRACTION = 0.10
AUTO_DISK_RESERVE_BYTES = 2 * 1024**3
_BACKING_DIRECTORY_NAME = "h3-continuum-v35-file-backed"
_CLEANED_ROOTS: set[str] = set()
_CLEANED_ROOTS_LOCK = threading.Lock()


def validate_buffer_backend(value: str) -> str:
    """Validate the explicit or automatic V3.5 IMAGE backend request."""

    if value not in BUFFER_BACKEND_OPTIONS:
        raise ValueError(f"unknown Buffer Backend: {value!r}")
    return value


@dataclass(frozen=True)
class AutoBufferDecision:
    selected_backend: str
    final_image_bytes: int
    backing_root: Path
    available_memory_bytes: int | None
    total_memory_bytes: int | None
    memory_reserve_bytes: int | None
    ram_image_limit_bytes: int
    disk_free_bytes: int | None
    disk_reserve_bytes: int
    reason: str


def _system_memory_bytes() -> tuple[int | None, int | None]:
    try:
        import psutil

        counters = psutil.virtual_memory()
        return int(counters.available), int(counters.total)
    except Exception:
        return None, None


def _existing_disk_anchor(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    if not candidate.exists():
        raise OSError(f"no existing filesystem anchor for backing root: {path}")
    return candidate


def _disk_free_bytes(path: Path) -> int:
    return int(shutil.disk_usage(_existing_disk_anchor(path)).free)


def select_auto_buffer_backend(
    final_image_bytes: int,
    *,
    backing_root: str | os.PathLike[str] | None = None,
) -> AutoBufferDecision:
    """Choose RAM only when both output size and physical headroom are safe.

    Auto never converts a Disk-backed decision into RAM after a disk-space or
    allocation failure. Users can still explicitly select either manual path.
    """

    final_bytes = int(final_image_bytes)
    if final_bytes <= 0:
        raise ValueError("Auto Buffer Backend requires a positive final IMAGE size")
    root = resolve_backing_root(backing_root)
    available, total = _system_memory_bytes()
    reserve = None
    if available is not None and total is not None and total > 0:
        reserve = max(
            AUTO_RAM_RESERVE_MIN_BYTES,
            int(total * AUTO_RAM_RESERVE_FRACTION),
        )

    if (
        reserve is not None
        and final_bytes <= AUTO_RAM_IMAGE_LIMIT_BYTES
        and available >= final_bytes + reserve
    ):
        return AutoBufferDecision(
            selected_backend=BUFFER_BACKEND_RAM,
            final_image_bytes=final_bytes,
            backing_root=root,
            available_memory_bytes=available,
            total_memory_bytes=total,
            memory_reserve_bytes=reserve,
            ram_image_limit_bytes=AUTO_RAM_IMAGE_LIMIT_BYTES,
            disk_free_bytes=None,
            disk_reserve_bytes=AUTO_DISK_RESERVE_BYTES,
            reason="final IMAGE fits the Auto RAM size limit and safety reserve",
        )

    if reserve is None:
        reason = "physical-memory counters are unavailable"
    elif final_bytes > AUTO_RAM_IMAGE_LIMIT_BYTES:
        reason = "final IMAGE exceeds the Auto RAM size limit"
    else:
        reason = "available physical memory is below final IMAGE plus reserve"

    try:
        disk_free = _disk_free_bytes(root)
    except Exception as exc:
        raise RuntimeError(
            "Auto Buffer Backend selected Disk-backed but disk capacity could "
            f"not be measured for {root}: {type(exc).__name__}: {exc}. "
            "Select RAM manually only if sufficient memory is known to be available."
        ) from exc
    required_disk = final_bytes + AUTO_DISK_RESERVE_BYTES
    if disk_free < required_disk:
        raise RuntimeError(
            "Auto Buffer Backend selected Disk-backed but the backing volume "
            f"has {disk_free} free bytes; {required_disk} bytes are required "
            f"for the final IMAGE plus the {AUTO_DISK_RESERVE_BYTES}-byte safety "
            "reserve. Free disk space or select RAM manually only if sufficient "
            "memory is known to be available."
        )
    return AutoBufferDecision(
        selected_backend=BUFFER_BACKEND_DISK,
        final_image_bytes=final_bytes,
        backing_root=root,
        available_memory_bytes=available,
        total_memory_bytes=total,
        memory_reserve_bytes=reserve,
        ram_image_limit_bytes=AUTO_RAM_IMAGE_LIMIT_BYTES,
        disk_free_bytes=disk_free,
        disk_reserve_bytes=AUTO_DISK_RESERVE_BYTES,
        reason=reason,
    )


def format_auto_buffer_decision(decision: AutoBufferDecision) -> str:
    def value(number: int | None) -> str:
        return "n/a" if number is None else str(int(number))

    return (
        "Auto Buffer Decision: "
        f"selected={decision.selected_backend}, "
        f"final_IMAGE={decision.final_image_bytes} bytes, "
        f"system_available={value(decision.available_memory_bytes)} bytes, "
        f"system_total={value(decision.total_memory_bytes)} bytes, "
        f"RAM_reserve={value(decision.memory_reserve_bytes)} bytes, "
        f"RAM_IMAGE_limit={decision.ram_image_limit_bytes} bytes, "
        f"disk_free={value(decision.disk_free_bytes)} bytes, "
        f"disk_reserve={decision.disk_reserve_bytes} bytes; "
        f"reason={decision.reason}."
    )


def resolve_backing_root(
    backing_root: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve the dedicated backing root without importing ComfyUI eagerly."""

    if backing_root is not None:
        return Path(backing_root).expanduser().resolve()

    try:
        import folder_paths
    except ImportError:
        base = Path(tempfile.gettempdir())
    else:
        value = folder_paths.get_temp_directory()
        if value is None or not str(value).strip():
            raise RuntimeError("ComfyUI returned an empty temporary directory")
        base = Path(value)
    return (base.expanduser().resolve() / _BACKING_DIRECTORY_NAME).resolve()


def get_file_backed_image_manager(
    backing_root: str | os.PathLike[str] | None = None,
) -> StorageLifetimeManager:
    """Return the accepted process-global manager for one resolved root."""

    root = resolve_backing_root(backing_root)
    key = os.path.normcase(str(root))
    with _CLEANED_ROOTS_LOCK:
        if key not in _CLEANED_ROOTS:
            # The P2-0 root lock prevents cleanup from observing an allocation
            # between its data-file and sidecar publication.  A live owner is
            # always retained; only prior abnormal-exit artifacts are removed.
            cleanup_stale_files(root, grace_seconds=0.0)
            _CLEANED_ROOTS.add(key)
    return get_process_lifetime_manager(root)


def allocate_file_backed_image(
    shape: tuple[int, ...],
    *,
    dtype: torch.dtype,
    backing_root: str | os.PathLike[str] | None = None,
) -> FileBackedAllocation:
    """Create a provisional Disk-backed IMAGE allocation.

    The caller must use the returned context manager and call ``publish()``
    only after every output element has been written.  Backend failures are
    propagated; this manual Disk-backed path never falls back to RAM.
    """

    manager = get_file_backed_image_manager(backing_root)
    return manager.allocate(shape, dtype=dtype)


__all__ = [
    "AUTO_DISK_RESERVE_BYTES",
    "AUTO_RAM_IMAGE_LIMIT_BYTES",
    "AUTO_RAM_RESERVE_FRACTION",
    "AUTO_RAM_RESERVE_MIN_BYTES",
    "AutoBufferDecision",
    "BUFFER_BACKEND_AUTO",
    "BUFFER_BACKEND_DISK",
    "BUFFER_BACKEND_OPTIONS",
    "BUFFER_BACKEND_RAM",
    "allocate_file_backed_image",
    "format_auto_buffer_decision",
    "get_file_backed_image_manager",
    "resolve_backing_root",
    "select_auto_buffer_backend",
    "validate_buffer_backend",
]
