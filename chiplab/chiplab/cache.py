"""Content-addressed result cache (diskcache). Key = tool + canonical args + lab code version (core hash) + tool
versions, so identical designs submitted by different agents reuse results instantly, and any code change
invalidates them."""
from __future__ import annotations

import hashlib
import json

from chiplab import config

_CACHE = None


def _cache():
    global _CACHE
    if _CACHE is None:
        import diskcache
        _CACHE = diskcache.Cache(str(config.home("cache_results")), size_limit=8 * 2 ** 30)
    return _CACHE


def key(tool: str, args: dict) -> str:
    from chiplab.log import core_hash
    a = {k: v for k, v in args.items() if k not in ("session_id", "run_id", "round", "force")}
    blob = json.dumps({"tool": tool, "args": a, "core": core_hash()}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def get(tool: str, args: dict):
    return _cache().get(key(tool, args))


def put(tool: str, args: dict, result: dict) -> None:
    if result.get("status") == "ok":
        _cache().set(key(tool, args), result)


def stats() -> dict:
    c = _cache()
    hits, misses = c.stats(enable=True)
    return {"entries": len(c), "hits": hits, "misses": misses, "bytes": c.volume()}
