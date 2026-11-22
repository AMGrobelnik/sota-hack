"""Find plugins by kind and name: built-ins live in chiplab/plugins/<kind>/<name>.py; plugins the AI scientist
writes are registered with their sha256 in CHIPLAB_HOME/plugins.json and refused if the file changed."""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import inspect
import json
from pathlib import Path

from chiplab import config
from chiplab.plugins.base import DatasetLoader, FrontEndStage, ModelFamily, SensorSimulator, Target

KINDS = {"datasets": DatasetLoader, "frontends": FrontEndStage, "families": ModelFamily,
         "simulators": SensorSimulator, "targets": Target}


class PluginError(RuntimeError):
    pass


def _registered() -> dict:
    p = config.home() / "plugins.json"
    return json.loads(p.read_text()) if p.exists() else {}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _find_in_module(mod, base, name):
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, base) and obj is not base and getattr(obj, "name", None) == name:
            return obj()
    return None


def get(kind: str, name: str):
    """Instantiate plugin `name` of `kind`; returns (instance, provenance dict)."""
    if kind not in KINDS:
        raise PluginError(f"unknown plugin kind {kind!r}; kinds: {list(KINDS)}")
    base = KINDS[kind]
    try:
        mod = importlib.import_module(f"chiplab.plugins.{kind}.{name}")
        inst = _find_in_module(mod, base, name)
        if inst is not None:
            src = Path(mod.__file__)
            return inst, {"kind": kind, "name": name, "builtin": True, "sha256": sha256_file(src)[:12]}
    except ModuleNotFoundError as e:
        if e.name != f"chiplab.plugins.{kind}.{name}":
            raise
    reg = _registered().get(f"{kind}/{name}")
    if reg is None:
        raise PluginError(f"no {kind} plugin named {name!r}. Built-ins: {available(kind)}")
    path = Path(reg["path"])
    if not path.exists() or sha256_file(path) != reg["sha256"]:
        raise PluginError(f"{kind}/{name}: file changed since registration; run `chiplab plugin test` and `register` again")
    spec = importlib.util.spec_from_file_location(f"chiplab_ext_{kind}_{name}", path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    inst = _find_in_module(mod, base, name)
    if inst is None:
        raise PluginError(f"{path} defines no {base.__name__} named {name!r}")
    return inst, {"kind": kind, "name": name, "builtin": False, "sha256": reg["sha256"][:12], "path": str(path)}


def available(kind: str) -> list[str]:
    d = config.PKG_DIR / "plugins" / kind
    names = sorted(p.stem for p in d.glob("*.py") if p.stem != "__init__")
    names += sorted(k.split("/", 1)[1] for k in _registered() if k.startswith(kind + "/"))
    return names


def register(kind: str, name: str, path: Path, report: dict) -> dict:
    p = config.home() / "plugins.json"
    reg = _registered()
    reg[f"{kind}/{name}"] = {"path": str(Path(path).resolve()), "sha256": sha256_file(path), "report": report}
    p.write_text(json.dumps(reg, indent=1))
    return reg[f"{kind}/{name}"]
