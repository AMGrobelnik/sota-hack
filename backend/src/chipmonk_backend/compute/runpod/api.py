"""Direct RunPod REST v2 client (control plane).

The key is ``RUNPOD_API_KEY``, read by name, sent only in the
``Authorization`` header, never put on a pod and never logged.

The client keeps the endpoint table and a rate limiter in this module. The
base URL and every field name were checked against RunPod's published schema
(``https://api.runpod.io/v2/openapi.json``, server ``https://api.runpod.io``,
paths under ``/v2``) on 2026-11-21.

API traps this client absorbs:

* ``status == RUNNING`` is not a running container: :attr:`PodInfo.is_running`
  also needs ``runtime.uptime``, which ``GET /pods`` (the listing) never
  carries; only ``GET /pods/{id}`` does.
* Collections are wrapped (``{"pods": [...]}``) and paginated by cursor.
* HTTP ports report an unroutable proxy ip; only ``tcp`` ports are dialable.
* A network volume has no default mount path: one must be given.
* ``POST /pods`` is never retried (no idempotency key: a replay after a 5xx
  can bill twice). ``GET`` and ``DELETE`` are retried on 429/5xx with
  ``Retry-After`` honoured.
* A 404 proves a pod gone only when its body says ``pod not found``; a route
  404 means the client is wrong and raises.

Safety: :meth:`RunPodAPI.create_pod` is the only call that costs money and is
reached only when ``compute.runpod.dry_run`` is false.
"""

from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx
from loguru import logger
from tenacity import AsyncRetrying, RetryCallState, retry_if_exception_type, stop_after_attempt

RUNPOD_REST_BASE = "https://api.runpod.io/v2"
RUNPOD_KEY_ENV = "RUNPOD_API_KEY"

#: Control-plane hiccups worth asking again (measured by the source: 503
#: "Upstream temporarily unavailable", 500 "failed to create pod").
TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})
#: Safe to replay: a read, or a delete of something already gone.
_RETRYABLE_METHODS = frozenset({"GET", "DELETE"})
#: Statuses in which a pod still holds (and bills for) its machine.
LIVE_STATUSES = frozenset({"PROVISIONING", "STARTING", "RUNNING"})
#: Statuses after which a pod will not run again.
TERMINAL_STATUSES = frozenset({"EXITED", "ERROR", "TERMINATED"})
_POD_ABSENT_DETAIL = "pod not found"
_MAX_LIST_PAGES = 50
_RATELIMIT_WINDOW = re.compile(r'"?(\w+)"?;r=(\d+);t=(\d+)')


class RunPodError(RuntimeError):
    """A RunPod request failed for good (or no key is configured)."""


class RunPodTransientError(RunPodError):
    """A RunPod request failed in a way worth retrying (429, 5xx, timeout)."""

    def __init__(self, message: str, *, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class PodNotFoundError(RunPodError):
    """RunPod says the pod does not exist (``404 pod not found``)."""


@dataclass(frozen=True)
class PodInfo:
    """One pod as the control plane reports it."""

    id: str
    name: str
    desired_status: str  # PROVISIONING, STARTING, RUNNING, EXITED, ERROR, TERMINATED
    machine: str  # GPU type id or CPU flavor id
    usd_per_hr: float | None = None
    uptime_s: int | None = None  # None until the container is really up
    public_ip: str | None = None
    ports: dict[str, int] = field(default_factory=dict)  # "22/tcp" -> public port
    created_at: str | None = None  # ISO-8601, as RunPod reports it

    @property
    def is_running(self) -> bool:
        """Container really up: desired RUNNING and a runtime uptime reported."""
        return self.desired_status == "RUNNING" and self.uptime_s is not None

    @property
    def is_terminal(self) -> bool:
        """The pod will not run again (exited, errored or terminated)."""
        return self.desired_status in TERMINAL_STATUSES

    def age_s(self, now: datetime | None = None) -> float | None:
        """Seconds since creation, or ``None`` when RunPod gave no time."""
        if not self.created_at:
            return None
        try:
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        return ((now or datetime.now(UTC)) - created).total_seconds()

    @classmethod
    def from_v2(cls, pod: dict[str, Any]) -> PodInfo:
        """Map a v2 ``Pod`` object. HTTP ports are skipped: their ip is a proxy's."""
        runtime = pod.get("runtime") or {}
        tcp_ports = [p for p in runtime.get("ports") or [] if _is_tcp_public(p)]
        direct = (pod.get("ssh") or {}).get("direct") or {}
        machine = (pod.get("gpu") or {}).get("id") or (pod.get("cpu") or {}).get("id") or ""
        uptime = runtime.get("uptime")
        cost = pod.get("cost")
        return cls(
            id=str(pod.get("id") or ""),
            name=str(pod.get("name") or ""),
            desired_status=str(pod.get("status") or ""),
            machine=str(machine),
            usd_per_hr=float(cost) if cost is not None else None,
            uptime_s=int(uptime) if uptime is not None else None,
            public_ip=direct.get("host") or next((p["ip"] for p in tcp_ports), None),
            ports={f"{p['private']}/tcp": int(p["public"]) for p in tcp_ports},
            created_at=pod.get("createdAt"),
        )


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


@dataclass(frozen=True)
class Offer:
    """What RunPod sells for one machine id right now."""

    stock: str  # "LOW" | "MEDIUM" | "HIGH"; "" when out of stock
    usd_per_hr: float | None  # list price for one pod of this machine, if known


def is_cpu_instance(machine: str) -> bool:
    """CPU instance ids look like ``cpu3g-2-8`` (flavor, vCPUs, GB RAM)."""
    return machine.lower().startswith("cpu")


def cpu_flavor_and_vcpus(machine: str) -> tuple[str, int]:
    """``"cpu3g-2-8"`` -> ``("cpu3g", 2)``; a bare flavor gets 4 vCPUs (as in the source)."""
    parts = machine.split("-")
    try:
        vcpus = int(parts[1]) if len(parts) >= 2 else 4
    except ValueError:
        raise ValueError(f"bad CPU instance id {machine!r}; expected like cpu3g-2-8") from None
    return parts[0], vcpus


def stock_label(availability: object) -> str:
    """v2 availability enum -> stock label; ``NONE``/missing is ``""`` (out of stock)."""
    label = str(availability or "").strip()
    return "" if label.upper() in ("", "NONE") else label


def _is_tcp_public(port: object) -> bool:
    """Is this runtime port dialable at ``ip:public``? Only ``tcp`` ports are."""
    return isinstance(port, dict) and bool(
        port.get("type") == "tcp" and port.get("public") and port.get("ip")
    )


def _is_pod_absent_404(status: int, body: str) -> bool:
    """A 404 that proves the POD is gone, as opposed to a route that moved."""
    return status == 404 and _POD_ABSENT_DETAIL in body.lower()


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    """Seconds a ``Retry-After`` header asks for (delay-seconds or HTTP-date), else ``None``."""
    text = (value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None  # neither RFC 9110 form: fall back to our own backoff
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - (now or datetime.now(UTC))).total_seconds())


def server_wait_s(headers: httpx.Headers) -> float | None:
    """The wait RunPod asked for: ``Retry-After``, else an exhausted ``RateLimit`` window's reset."""
    wait = parse_retry_after(headers.get("retry-after"))
    if wait is not None:
        return wait
    resets = [float(t) for _n, r, t in _RATELIMIT_WINDOW.findall(headers.get("ratelimit", "")) if r == "0"]
    return min(resets) if resets else None


class RunPodAPI:
    """Async RunPod REST v2 client. ``api_key`` ``None`` = ``$RUNPOD_API_KEY`` at first use.

    ``transport`` is for tests (``httpx.MockTransport``).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = RUNPOD_REST_BASE,
        timeout_s: float = 30.0,
        retries: int = 3,
        backoff_s: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.retries = retries
        self.backoff_s = backoff_s
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> RunPodAPI:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the HTTP connection pool. Idempotent."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            key = self._api_key or os.environ.get(RUNPOD_KEY_ENV, "")
            if not key:
                raise RunPodError(f"{RUNPOD_KEY_ENV} is not set")
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=self.timeout_s,
                transport=self._transport,
            )
        return self._client

    async def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        """One REST call; GET and DELETE are retried on transient failures, POST never."""
        attempts = self.retries if method in _RETRYABLE_METHODS else 1

        def _wait(state: RetryCallState) -> float:
            exc = state.outcome.exception() if state.outcome else None
            asked = exc.retry_after_s if isinstance(exc, RunPodTransientError) else None
            delay = self.backoff_s * 2 ** (state.attempt_number - 1)
            # Jitter keeps callers refused together from returning together.
            return (asked if asked is not None else delay) + random.uniform(0, delay)

        def _log(state: RetryCallState) -> None:
            exc = state.outcome.exception() if state.outcome else None
            logger.debug(
                "RunPod {} {} transient ({}), retry {}/{}",
                method,
                path,
                exc,
                state.attempt_number,
                attempts - 1,
            )

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((RunPodTransientError, httpx.TransportError)),
            stop=stop_after_attempt(attempts),
            wait=_wait,
            before_sleep=_log,
            reraise=True,
        ):
            with attempt:
                return await self._request_once(method, path, body)
        raise AssertionError("unreachable: tenacity reraises")  # pragma: no cover

    async def _request_once(self, method: str, path: str, body: dict[str, Any] | None) -> Any:
        resp = await self._http().request(method, path, json=body)
        if resp.status_code >= 400:
            msg = f"RunPod {method} {path} -> HTTP {resp.status_code}: {resp.text[:500]}"
            if resp.status_code in TRANSIENT_STATUSES:
                raise RunPodTransientError(msg, retry_after_s=server_wait_s(resp.headers))
            if _is_pod_absent_404(resp.status_code, resp.text):
                raise PodNotFoundError(msg)
            raise RunPodError(msg)
        if not resp.content.strip():
            return None  # DELETE answers 204 with no body
        return resp.json()

    async def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        """:meth:`_request` with transport failures surfaced as :class:`RunPodError`."""
        try:
            return await self._request(method, path, body)
        except httpx.TransportError as exc:
            raise RunPodTransientError(f"RunPod {method} {path}: {type(exc).__name__}: {exc}") from exc

    async def list_pods(self) -> list[PodInfo]:
        """Every pod on the account (read-only; doubles as the auth check).

        Follows ``pagination.nextCursor``; a truncated walk raises, because
        callers (the reaper) infer absence from this list. The listing carries
        no ``runtime``, so ``uptime_s`` is ``None`` here: use :meth:`get_pod`.
        """
        pods: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(_MAX_LIST_PAGES):
            path = "/pods" if cursor is None else f"/pods?cursor={quote(cursor, safe='')}"
            payload = await self._call("GET", path)
            page = (
                list((payload or {}).get("pods") or []) if isinstance(payload, dict) else list(payload or [])
            )
            pods.extend(page)
            pagination = payload.get("pagination") if isinstance(payload, dict) else None
            has_next = bool(pagination and pagination.get("hasNextPage"))
            next_cursor = pagination.get("nextCursor") if pagination else None
            if (has_next and not next_cursor) or (cursor is not None and not page):
                raise RunPodError("RunPod GET /pods: truncated listing")
            if not has_next:
                return [PodInfo.from_v2(p) for p in pods]
            cursor = next_cursor
        raise RunPodError(f"RunPod GET /pods: more than {_MAX_LIST_PAGES} pages")

    async def get_pod(self, pod_id: str) -> PodInfo:
        """One pod's current state (read-only). :class:`PodNotFoundError` when it is gone."""
        raw = await self._call("GET", f"/pods/{quote(pod_id, safe='')}")
        # A body without id or status is not evidence the pod is gone: raise.
        if not isinstance(raw, dict) or not raw.get("id") or not raw.get("status"):
            raise RunPodError(f"RunPod GET /pods/{pod_id}: answer without a pod id and status")
        return PodInfo.from_v2(raw)

    async def offers(self, *, cloud: str = "SECURE") -> dict[str, Offer]:
        """Stock and list price per machine (read-only, two catalog calls).

        GPU entries are keyed by GPU type id, CPU entries by flavor id
        (``cpu3g``) with the price per vCPU; :meth:`offer_for` resolves a
        full machine id. A stock reading orders a chain; it is never a veto.
        """
        gpus = await self._call("GET", f"/catalog/gpus?include=AVAILABILITY&product=POD&cloud={cloud}")
        cpus = await self._call("GET", "/catalog/cpus?include=AVAILABILITY&product=POD")
        price_key = "community" if cloud == "COMMUNITY" else "secure"
        result: dict[str, Offer] = {}
        for gpu in (gpus or {}).get("gpus") or []:
            price = (gpu.get("price") or {}).get(price_key)
            result[str(gpu["id"])] = Offer(stock_label(gpu.get("availability")), _as_price(price))
        for cpu in (cpus or {}).get("cpus") or []:
            per_vcpu = (cpu.get("price") or {}).get("securePerVcpu")
            result[str(cpu["id"])] = Offer(stock_label(cpu.get("availability")), _as_price(per_vcpu))
        return result

    async def availability(self, *, cloud: str = "SECURE") -> dict[str, str]:
        """Machine id (GPU type or CPU flavor) -> stock label (``""`` when out); read-only."""
        return {machine: offer.stock for machine, offer in (await self.offers(cloud=cloud)).items()}

    def build_create_request(self, spec: PodSpec) -> dict[str, Any]:
        """The JSON body :meth:`create_pod` would send. Pure; used for dry runs."""
        body: dict[str, Any] = {
            "name": spec.name,
            "image": spec.image,
            "cloud": spec.cloud_type,
            "disk": spec.disk_gb,
            "ports": list(spec.ports),
        }
        if is_cpu_instance(spec.machine):
            flavor, vcpus = cpu_flavor_and_vcpus(spec.machine)
            body["cpu"] = {"id": flavor, "vcpuCount": vcpus}
        else:
            body["gpu"] = {"id": spec.machine, "count": 1}
        if spec.data_center_id:
            body["dataCenterIds"] = [spec.data_center_id]
        if spec.network_volume_id:
            if not spec.volume_mount_path:
                raise ValueError("a network volume needs volume_mount_path; RunPod has no default")
            body["mounts"] = {
                "network": [{"volumeId": spec.network_volume_id, "path": spec.volume_mount_path}]
            }
        if spec.env:
            body["env"] = dict(spec.env)
        if spec.command:
            body["cmd"] = list(spec.command)
        return body

    async def create_pod(self, spec: PodSpec) -> PodInfo:
        """Create (and start paying for) a pod. Callers check ``dry_run`` first. Never retried."""
        body = self.build_create_request(spec)
        logger.info("RunPod: creating pod {} on {} ({})", spec.name, spec.machine, spec.cloud_type)
        raw = await self._call("POST", "/pods", body)
        if not isinstance(raw, dict) or not raw.get("id"):
            raise RunPodError(f"RunPod POST /pods: answer without a pod id: {str(raw)[:300]}")
        return PodInfo.from_v2(raw)

    async def terminate_pod(self, pod_id: str) -> None:
        """Terminate a pod; a pod already gone is success. Retried: a DELETE is idempotent."""
        try:
            await self._call("DELETE", f"/pods/{quote(pod_id, safe='')}")
        except PodNotFoundError:
            logger.debug("RunPod pod {} already absent; terminate is a no-op", pod_id)


def offer_for(machine: str, offers: dict[str, Offer]) -> Offer | None:
    """The :class:`Offer` for a full machine id; a CPU price is scaled by its vCPU count."""
    if not is_cpu_instance(machine):
        return offers.get(machine)
    flavor, vcpus = cpu_flavor_and_vcpus(machine)
    per_vcpu = offers.get(flavor)
    if per_vcpu is None:
        return None
    price = per_vcpu.usd_per_hr * vcpus if per_vcpu.usd_per_hr is not None else None
    return Offer(per_vcpu.stock, price)


def _as_price(value: object) -> float | None:
    """A catalog price as a float, ``None`` when absent or not a number."""
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


__all__ = [
    "LIVE_STATUSES",
    "RUNPOD_KEY_ENV",
    "RUNPOD_REST_BASE",
    "TERMINAL_STATUSES",
    "Offer",
    "PodInfo",
    "PodNotFoundError",
    "PodSpec",
    "RunPodAPI",
    "RunPodError",
    "RunPodTransientError",
    "cpu_flavor_and_vcpus",
    "is_cpu_instance",
    "offer_for",
    "parse_retry_after",
    "stock_label",
]
