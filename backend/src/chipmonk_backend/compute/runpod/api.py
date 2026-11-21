"""Direct RunPod REST client (control plane). The key is ``RUNPOD_API_KEY``,
read by name, sent only in the ``Authorization`` header, never put on a pod.

STUB: port from AI Inventor's
``aii_runpod/src/aii_runpod/deploy/runpod_api.py``
(``RunPodAPI``: httpx + tenacity, pagination, jittered backoff, v2 field
mapping) with ``aii_lib/runpod_endpoints.py`` and ``aii_lib/runpod_rate_limit.py``.
Confirm the REST base and field names against RunPod's current API reference
before relying on them. Known traps (from the source's RunPod notes):
``desiredStatus == RUNNING`` is not a running container (read the runtime
uptime); HTTP ports report an unroutable proxy ip (dial ``tcp`` ports); a
network volume never gets a default name; creation can take 5 to 10 minutes.

Safety: :meth:`RunPodAPI.create_pod` is the only call that costs money and is
only reached when ``compute.runpod.dry_run`` is false; read-only calls
(:meth:`list_pods`, :meth:`get_pod`, :meth:`availability`) are safe to try.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: REST base as used by AI Inventor (v2). Verify against RunPod's docs.
RUNPOD_REST_BASE = "https://api.runpod.io/v2"
RUNPOD_KEY_ENV = "RUNPOD_API_KEY"


class RunPodError(RuntimeError):
    """A RunPod request failed for good."""


class RunPodTransientError(RunPodError):
    """A RunPod request failed in a way worth retrying (429, 5xx, timeout)."""


@dataclass(frozen=True)
class PodInfo:
    """One pod as the control plane reports it."""

    id: str
    name: str
    desired_status: str  # RUNNING, EXITED, TERMINATED ...
    machine: str  # GPU type id or CPU instance id
    usd_per_hr: float | None = None
    uptime_s: int | None = None  # None until the container is really up
    public_ip: str | None = None
    ports: dict[str, int] = field(default_factory=dict)  # "8080/http" -> public port

    @property
    def is_running(self) -> bool:
        """Container really up: desired RUNNING and a runtime uptime reported."""
        return self.desired_status == "RUNNING" and self.uptime_s is not None


@dataclass(frozen=True)
class PodSpec:
    """What to create. ``env`` values are sent to RunPod and never logged."""

    name: str
    image: str
    machine: str  # GPU type id ("NVIDIA RTX A4000") or CPU instance id ("cpu3g-2-8")
    cloud_type: str = "SECURE"
    data_center_id: str = ""
    disk_gb: int = 20
    ports: tuple[str, ...] = ("22/tcp", "8080/http")
    env: dict[str, str] = field(default_factory=dict)
    command: tuple[str, ...] = ()
    network_volume_id: str = ""
    volume_mount_path: str = ""


class RunPodAPI:
    """Async RunPod REST client. ``api_key`` ``None`` = ``$RUNPOD_API_KEY`` at first use."""

    def __init__(
        self, api_key: str | None = None, *, base_url: str = RUNPOD_REST_BASE, timeout_s: float = 30.0
    ) -> None:
        self._api_key = api_key
        self.base_url = base_url
        self.timeout_s = timeout_s

    async def __aenter__(self) -> RunPodAPI:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the HTTP connection pool."""
        return None

    async def list_pods(self) -> list[PodInfo]:
        """Every pod on the account (read-only; doubles as the auth check)."""
        raise NotImplementedError("RunPodAPI.list_pods: port runpod_api.list_pods")

    async def get_pod(self, pod_id: str) -> PodInfo:
        """One pod's current state (read-only)."""
        raise NotImplementedError("RunPodAPI.get_pod: port runpod_api.get_pod_status")

    async def availability(self) -> dict[str, str]:
        """Machine id -> stock label (``""`` when out of stock); read-only."""
        raise NotImplementedError("RunPodAPI.availability: port runpod_api.get_all_availability")

    def build_create_request(self, spec: PodSpec) -> dict[str, Any]:
        """The JSON body :meth:`create_pod` would send. Pure; used for dry runs."""
        raise NotImplementedError("RunPodAPI.build_create_request: port create_pod's body")

    async def create_pod(self, spec: PodSpec) -> PodInfo:
        """Create (and start paying for) a pod. Callers check ``dry_run`` first."""
        raise NotImplementedError("RunPodAPI.create_pod: port runpod_api.create_pod")

    async def terminate_pod(self, pod_id: str) -> None:
        """Terminate a pod; a pod already gone is success."""
        raise NotImplementedError("RunPodAPI.terminate_pod: port runpod_api.terminate_pod")


__all__ = [
    "RUNPOD_KEY_ENV",
    "RUNPOD_REST_BASE",
    "PodInfo",
    "PodSpec",
    "RunPodAPI",
    "RunPodError",
    "RunPodTransientError",
]
