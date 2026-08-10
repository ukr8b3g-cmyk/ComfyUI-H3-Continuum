"""Atomic safetensors + JSON persistence for V2 sessions."""
from __future__ import annotations
import json, logging, os, re, uuid
from pathlib import Path
from typing import Any
from safetensors import safe_open
from safetensors.torch import save_file
from .session import validate_session
LOG=logging.getLogger("h3_continuum_join")
_SAFE_PREFIX=re.compile(r"[^A-Za-z0-9._-]+")
_HEADER_KEY="h3_continuum_session_json"
def sanitize_prefix(prefix:str)->str:
    value=_SAFE_PREFIX.sub("_",str(prefix).strip()).strip("._"); return value or "h3_continuum_session"
def session_directory()->Path:
    try:
        import folder_paths; root=Path(folder_paths.get_output_directory())
    except Exception: root=Path.cwd()
    path=root/"h3_continuum_sessions"; path.mkdir(parents=True,exist_ok=True); return path
def session_paths(prefix:str,slot:int)->tuple[Path,Path]:
    slot=int(slot)
    if not 1<=slot<=9999: raise ValueError("session slot must be between 1 and 9999")
    name=f"{sanitize_prefix(prefix)}_slot{slot:04d}"; root=session_directory(); return root/f"{name}.safetensors",root/f"{name}.json"
def _fsync_file(path):
    try:
        with path.open("rb") as handle: os.fsync(handle.fileno())
    except OSError: pass
def _fsync_directory(path):
    if os.name=="nt": return
    try:
        descriptor=os.open(str(path),os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    except OSError: pass
def _metadata_without_tensors(session):
    metadata={k:v for k,v in session.items() if k!="chunks"}; chunks=[]
    for entry in session["chunks"]: chunks.append({k:v for k,v in entry.items() if k not in ("video","audio")})
    metadata["chunks"]=chunks; return metadata
def save_session(session,*,prefix,slot):
    session=validate_session(session); tensor_path,json_path=session_paths(prefix,slot); token=uuid.uuid4().hex
    tensor_tmp=tensor_path.with_name(f".{tensor_path.name}.{token}.tmp"); json_tmp=json_path.with_name(f".{json_path.name}.{token}.tmp")
    tensors={}
    for index,entry in enumerate(session["chunks"],start=1):
        tensors[f"chunk_{index:04d}_video"]=entry["video"].detach().to("cpu").contiguous(); tensors[f"chunk_{index:04d}_audio"]=entry["audio"].detach().to("cpu").contiguous()
    metadata=_metadata_without_tensors(session); metadata["_session_commit_id"]=token
    serialized=json.dumps(metadata,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    try:
        save_file(tensors,str(tensor_tmp),metadata={_HEADER_KEY:serialized}); _fsync_file(tensor_tmp)
        with json_tmp.open("w",encoding="utf-8",newline="\n") as handle:
            json.dump(metadata,handle,ensure_ascii=False,indent=2,sort_keys=True); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(json_tmp,json_path); os.replace(tensor_tmp,tensor_path); _fsync_directory(tensor_path.parent)
    finally:
        for path in (tensor_tmp,json_tmp):
            try: path.unlink(missing_ok=True)
            except OSError: pass
    return tensor_path,json_path
def load_session(*,prefix,slot):
    tensor_path,json_path=session_paths(prefix,slot)
    if not tensor_path.is_file(): raise FileNotFoundError(f"session slot does not exist: {tensor_path.name}")
    with safe_open(str(tensor_path),framework="pt",device="cpu") as handle:
        serialized=(handle.metadata() or {}).get(_HEADER_KEY)
        if serialized is None: raise ValueError("session safetensors has no embedded Continuum metadata")
        session=json.loads(serialized)
        for index,entry in enumerate(session.get("chunks") or [],start=1):
            entry["video"]=handle.get_tensor(f"chunk_{index:04d}_video"); entry["audio"]=handle.get_tensor(f"chunk_{index:04d}_audio")
    if json_path.is_file():
        try:
            with json_path.open("r",encoding="utf-8") as handle: mirror=json.load(handle)
            if mirror.get("_session_commit_id")!=session.get("_session_commit_id"): LOG.warning("Ignoring stale Continuum session JSON mirror: %s",json_path.name)
        except (OSError,ValueError,TypeError) as exc: LOG.warning("Ignoring unreadable session JSON mirror %s: %s",json_path.name,exc)
    return validate_session(session)
def session_mtime(*,prefix,slot):
    tensor_path,json_path=session_paths(prefix,slot); return (tensor_path.stat().st_mtime if tensor_path.exists() else -1.0,json_path.stat().st_mtime if json_path.exists() else -1.0)
