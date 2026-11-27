"""Bounded KJ Preview Override identity; no provider imports or preview execution.

Only the source profiles shipped with this adapter can omit ``frames``. Other
wrappers keep the ordinary observer, including its existing safety decisions.
"""
from __future__ import annotations

import ast
import hashlib
import json
import marshal
import sys
import types
from functools import lru_cache
from pathlib import Path

_PROFILE = json.loads(Path(__file__).with_name("preview_override_provider_v1.json").read_text(encoding="utf-8"))


def _load_public_profile(path, *, existing_profiles=None):
    # A partial update must not break the old profile or ordinary generation.
    existing_profiles = (_PROFILE,) if existing_profiles is None else existing_profiles
    try:
        profile = json.loads(Path(path).read_text(encoding="utf-8"))
        if (type(profile) is not dict or profile.keys() != _PROFILE.keys()
                or type(profile["id"]) is not str or type(profile["source_sha256"]) is not str
                or any(profile["id"] == existing["id"]
                       or (profile["source_sha256"], profile["core_preview_sha256"], profile["core_dispatch_sha256"])
                       == (existing["source_sha256"], existing["core_preview_sha256"], existing["core_dispatch_sha256"])
                       for existing in existing_profiles)):
            return None
        return profile
    except (OSError, ValueError):
        return None


_PUBLIC_PROFILE = _load_public_profile(Path(__file__).with_name("preview_override_provider_public_v1.json"))
_PROFILES = (_PROFILE,) + ((_PUBLIC_PROFILE,) if _PUBLIC_PROFILE is not None else ())
_AUDIO_SCALE_PROFILE = _load_public_profile(
    Path(__file__).with_name("preview_override_provider_audio_scale_v1.json"),
    existing_profiles=_PROFILES,
)
_PROFILES += ((_AUDIO_SCALE_PROFILE,) if _AUDIO_SCALE_PROFILE is not None else ())
_CORE046_PROFILE = _load_public_profile(
    Path(__file__).with_name("preview_override_provider_audio_scale_core046_v1.json"), existing_profiles=_PROFILES,
)
_PROFILES += ((_CORE046_PROFILE,) if _CORE046_PROFILE is not None else ())
_FIELDS = frozenset(("max_resolution", "node_id", "jpeg_quality", "suppress_default",
                     "preview_frames", "preview_fps", "vae", "tiny_vae", "audio_vae", "frames"))

_PREVIEW_REASONS = {
    "provider source is outside the audited profile": "KJ/Core preview implementation is outside the audited source profiles",
    "VAE preview is outside Phase A": "KJ preview VAE/Audio VAE or Tiny VAE is outside the supported configuration",
    "Core approximate VAE is outside Phase A": "Core approximate-VAE preview is outside the supported configuration",
}
_UNKNOWN_PREVIEW_REASON = "KJ preview runtime code or state could not be verified"
PREVIEW_REUSE_REASONS = frozenset((*_PREVIEW_REASONS.values(), _UNKNOWN_PREVIEW_REASON))


def _normalized_code(code):
    return code.replace(co_filename="<audited-provider>", co_consts=tuple(
        _normalized_code(value) if isinstance(value, types.CodeType) else value
        for value in code.co_consts))


def _literal(node):
    # The audited source has one literal default expressed as 256 << 20.
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.LShift):
        return ast.literal_eval(node.left) << ast.literal_eval(node.right)
    return ast.literal_eval(node)


@lru_cache(maxsize=8)
def _compiled(source):
    tree = ast.parse(source)
    code = compile(source, "<audited-provider>", "exec", dont_inherit=True)
    codes = {}

    def collect(item):
        for child in item.co_consts:
            if isinstance(child, types.CodeType):
                codes[child.co_qualname] = child
                collect(child)
    collect(code)
    functions = {}
    classes = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            classes[node.name] = node
    return codes, functions, classes


def _source(path, expected):
    data = Path(path).read_bytes()
    # Match the audited file contents across Git's LF/CRLF checkout policies.
    data = data.replace(b"\r\n", b"\n")
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("provider source is outside the audited profile")
    return data.decode("utf-8-sig")


def _provider_source(path):
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(data).hexdigest()
    matches = [profile for profile in _PROFILES if profile.get("source_sha256") == digest]
    if len(matches) > 1:
        # The same KJ source can be audited against several Core implementations.
        for module_name, field in (("latent_preview", "core_preview_sha256"),
                                   ("comfy.patcher_extension", "core_dispatch_sha256")):
            module = sys.modules.get(module_name)
            path = getattr(module, "__file__", None)
            if not path:
                raise ValueError("provider source is outside the audited profile")
            core_data = Path(path).read_bytes().replace(b"\r\n", b"\n")
            core_digest = hashlib.sha256(core_data).hexdigest()
            matches = [profile for profile in matches if profile[field] == core_digest]
    if len(matches) != 1:
        raise ValueError("provider source is outside the audited profile")
    return matches[0], data.decode("utf-8-sig")


def _check_function(fn, node, code, namespace):
    if (type(fn) is not types.FunctionType or fn.__globals__ is not namespace
            or fn.__closure__ or vars(fn) or fn.__qualname__ != code.co_qualname
            or fn.__module__ != namespace["__name__"]):
        raise ValueError("unknown loaded callable")
    if marshal.dumps(_normalized_code(fn.__code__)) != marshal.dumps(_normalized_code(code)):
        raise ValueError("loaded code differs from audited source")
    defaults = tuple(_literal(value) for value in node.args.defaults) or None
    kwdefaults = {arg.arg: _literal(value) for arg, value in zip(node.args.kwonlyargs, node.args.kw_defaults) if value is not None} or None
    if not _same_literal(fn.__defaults__, defaults) or not _same_literal(fn.__kwdefaults__, kwdefaults):
        raise ValueError("loaded defaults differ from audited source")


def _same_literal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) in (tuple, list):
        return len(actual) == len(expected) and all(_same_literal(a, b) for a, b in zip(actual, expected))
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(_same_literal(actual[key], value) for key, value in expected.items())
    return type(expected) in (type(None), bool, int, float, str) and actual == expected


def _check_plain_class(cls, node, codes, namespace, *, sentinel=False):
    if (type(cls) is not type or cls.__bases__ != (object,)
            or cls.__module__ != namespace["__name__"]):
        raise ValueError("unknown wrapper class")
    methods = {item.name: item for item in node.body if isinstance(item, ast.FunctionDef)}
    allowed = set(methods) | {"__module__", "__doc__", "__dict__", "__weakref__",
                              "__firstlineno__", "__static_attributes__"}
    if sentinel:
        allowed.add("_STOP")
        if type(vars(cls).get("_STOP")) is not object:
            raise ValueError("unknown encoder sentinel")
    if set(vars(cls)) - allowed:
        raise ValueError("additional class attributes")
    for name, method in methods.items():
        _check_function(vars(cls).get(name), method, codes[cls.__name__ + "." + name], namespace)


def _check_selected(module, source, names):
    codes, functions, classes = _compiled(source)
    for name in names:
        value = vars(module).get(name)
        if name in functions:
            _check_function(value, functions[name], codes[name], vars(module))
            continue
        node = classes[name]
        if not isinstance(value, type) or value.__module__ != module.__name__:
            raise ValueError("unknown imported class")
        methods = {item.name: item for item in node.body if isinstance(item, ast.FunctionDef)}
        allowed = set(methods) | {"__module__", "__doc__", "__dict__", "__weakref__",
                                  "__firstlineno__", "__static_attributes__"}
        if set(vars(value)) - allowed:
            raise ValueError("unknown imported class attributes")
        expected_bases = tuple(vars(module).get(base.id) for base in node.bases if isinstance(base, ast.Name))
        if not expected_bases:
            expected_bases = (object,)
        if value.__bases__ != expected_bases:
            raise ValueError("unknown imported class bases")
        for member, definition in methods.items():
            _check_function(vars(value).get(member), definition, codes[name + "." + member], vars(module))


def _audit_provider(value):
    cls = type(value)
    module = sys.modules.get(cls.__module__)
    if (module is None or vars(module).get("_PreviewOverrideWrapper") is not cls
            or cls.__name__ != "_PreviewOverrideWrapper"):
        raise ValueError("unrecognized Preview Override provider")
    namespace = vars(module)
    profile, source = _provider_source(namespace.get("__file__"))
    codes, functions, classes = _compiled(source)
    for name, node in functions.items():
        _check_function(namespace.get(name), node, codes[name], namespace)
    for name in ("_PreviewOverrideWrapper", "_AsyncPreviewEncoder"):
        _check_plain_class(namespace.get(name), classes[name], codes, namespace,
                           sentinel=name == "_AsyncPreviewEncoder")
    for alias, name in (("torch", "torch"), ("np", "numpy"), ("queue", "queue"),
                        ("threading", "threading"), ("time", "time"), ("Image", "PIL.Image"),
                        ("ImageOps", "PIL.ImageOps")):
        if namespace.get(alias) is not sys.modules.get(name) or namespace.get(alias) is None:
            raise ValueError("substituted preview module binding")

    # Imported KJ bindings are canonical objects from the audited sibling files.
    # No importlib/exec is used here; absent or substituted modules fail closed.
    package = module.__name__.rsplit(".", 1)[0]
    for relative, bindings in profile["siblings"].items():
        sibling = sys.modules.get(package + "." + relative)
        if sibling is None:
            # ltxv_nodes is an explicitly optional import in the audited source.
            if relative == "ltxv_nodes" and all(namespace.get(alias) is None for alias in bindings):
                continue
            raise ValueError("provider dependency not loaded")
        dependency_source = _source(vars(sibling).get("__file__"), profile["sibling_sha256"][relative])
        _check_selected(sibling, dependency_source, bindings.values())
        for alias, original in bindings.items():
            if namespace.get(alias) is not vars(sibling).get(original):
                raise ValueError("substituted provider dependency")

    # KJ reaches Core's preview factory directly. Unknown get_previewer hooks
    # and an active Core approximate VAE stay outside this Phase A profile.
    core = sys.modules.get("latent_preview")
    if namespace.get("latent_preview") is not core or core is None:
        raise ValueError("unknown Core preview module")
    core_source = _source(vars(core).get("__file__"), profile["core_preview_sha256"])
    _check_selected(core, core_source, ("get_previewer", "preview_to_image", "LatentPreviewer", "Latent2RGBPreviewer"))
    patcher = sys.modules.get("comfy.patcher_extension")
    if patcher is None:
        raise ValueError("Core wrapper dispatcher not loaded")
    dispatch_source = _source(vars(patcher).get("__file__"), profile["core_dispatch_sha256"])
    _check_selected(patcher, dispatch_source, ("get_all_wrappers",))
    method = getattr(vars(core).get("args"), "preview_method", None)
    if (type(method) is not vars(core).get("LatentPreviewMethod")
            or getattr(method, "name", None) not in ("NoPreviews", "Auto", "Latent2RGB")):
        raise ValueError("Core approximate VAE is outside Phase A")
    size = vars(core).get("MAX_PREVIEW_RESOLUTION")
    if type(size) is not int or size <= 0:
        raise ValueError("unknown Core preview setting")
    return profile, {"method": method.name, "max_resolution": size}


def preview_override_signature(value):
    """Return a finite descriptor, never relaxing an unknown provider's guard."""
    try:
        profile, core_preview = _audit_provider(value)
        state = vars(value)
        if set(state) != _FIELDS or type(state["frames"]) is not list:
            raise ValueError("unknown wrapper state")
        if (state["vae"] is not None or state["audio_vae"] is not None
                or type(state["tiny_vae"]) is not str or state["tiny_vae"] != "none"):
            raise ValueError("VAE preview is outside Phase A")
        for name, low, high in (("max_resolution", 0, 8192), ("jpeg_quality", 30, 100),
                                ("preview_frames", 1, 1024), ("preview_fps", 1, 60)):
            if type(state[name]) is not int or not low <= state[name] <= high:
                raise ValueError("invalid fixed preview setting")
        if (type(state["suppress_default"]) is not bool
                or (state["node_id"] is not None and type(state["node_id"]) is not str)):
            raise ValueError("invalid fixed preview setting")
        settings = {key: state[key] for key in sorted(_FIELDS - {"frames", "vae", "audio_vae"})}
        return {"adapter": "kj_preview_override_v1", "profile": profile["id"],
                "profile_sha256": hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                "source_sha256": profile["source_sha256"], "settings": settings,
                "core_preview": core_preview}, True
    except Exception as exc:
        return {"adapter": "kj_preview_override_v1", "unsupported": str(exc)}, False


def preview_override_reuse_reasons(observed):
    """Classify the already observed KJ slot; never inspect MODEL a second time."""
    wrappers = observed.get("wrappers") if type(observed) is dict else None
    outer = wrappers.get("outer_sample") if type(wrappers) is dict else None
    items = outer.get("kj_preview_override") if type(outer) is dict else None
    if type(items) is not list:
        return []
    reasons = []
    for item in items[:4096]:
        if (type(item) is dict and item.get("adapter") == "kj_preview_override_v1"
                and "unsupported" in item):
            failure = item["unsupported"]
            reason = _PREVIEW_REASONS.get(failure, _UNKNOWN_PREVIEW_REASON) if type(failure) is str else _UNKNOWN_PREVIEW_REASON
            if reason not in reasons:
                reasons.append(reason)
    return reasons


def observe_model_wrappers(wrappers, observe):
    """Keep the no-KJ path exact; encode Core's key/list execution order for KJ."""
    outer = wrappers.get("outer_sample") if type(wrappers) is dict else None
    if not isinstance(outer, dict) or "kj_preview_override" not in outer:
        return observe(wrappers)
    if type(outer) is not dict or any(type(key) is not str for key in outer):
        return {"unsupported": "unknown outer_sample container"}, False
    if (len(wrappers) > 4096 or len(outer) > 4096
            or any(type(key) is not str for key in wrappers)):
        return {"unsupported": "wrapper container exceeds observation bounds"}, False
    items = outer["kj_preview_override"]
    if type(items) is not list or not items or len(items) > 4096:
        return {"unsupported": "unknown kj_preview_override container"}, False
    # A local copy holds placeholders while the ordinary observer checks all
    # unrelated wrappers at their original nesting depth. Never mutate MODEL.
    copied = dict(wrappers)
    copied["outer_sample"] = dict(outer)
    copied["outer_sample"]["kj_preview_override"] = [None] * len(items)
    result, safe = observe(copied)
    adapted = []
    for value in items:
        descriptor, recognized = preview_override_signature(value)
        adapted.append(descriptor)
        safe = safe and recognized
    result["outer_sample"]["kj_preview_override"] = adapted
    # Generic dict observation sorts keys. Keep a separate ordered sequence so
    # cross-key execution order cannot disappear in canonical JSON hashing.
    return {"wrappers": result, "outer_sample_order": list(outer)}, safe
