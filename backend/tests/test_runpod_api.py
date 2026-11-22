"""RunPodAPI against a fake HTTP transport: shapes, retries, traps. No network."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from chipin_backend.compute.runpod.api import (
    PodSpec,
    RunPodAPI,
    RunPodError,
    RunPodTransientError,
    offer_for,
    parse_retry_after,
)

Handler = Callable[[httpx.Request], httpx.Response]

RUNNING_POD = {
    "id": "p1",
    "name": "chipin_worker_r1_a_a1",
    "status": "RUNNING",
    "cost": 0.25,
    "gpu": {"id": "NVIDIA RTX A4000", "count": 1},
    "createdAt": "2026-11-21T10:00:00Z",
    "ssh": {"direct": {"host": "203.0.113.7"}},
    "runtime": {
        "uptime": 42,
        "ports": [
            {"private": 22, "public": 40022, "type": "tcp", "ip": "203.0.113.7"},
            {"private": 8080, "public": 8080, "type": "http", "ip": "100.65.0.1"},
        ],
    },
}


def _api(handler: Handler, calls: list[httpx.Request]) -> RunPodAPI:
    def record(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    return RunPodAPI("test-key", transport=httpx.MockTransport(record), backoff_s=0.0)


async def test_list_pods_follows_cursor_and_sends_the_key_in_the_header() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "cursor" not in request.url.params:
            page = {
                "pods": [{**RUNNING_POD, "runtime": None}],
                "pagination": {"hasNextPage": True, "nextCursor": "c2"},
            }
        else:
            page = {
                "pods": [{**RUNNING_POD, "id": "p2", "runtime": None}],
                "pagination": {"hasNextPage": False},
            }
        return httpx.Response(200, json=page)

    async with _api(handler, calls) as api:
        pods = await api.list_pods()

    assert [p.id for p in pods] == ["p1", "p2"]
    assert calls[0].headers["Authorization"] == "Bearer test-key"
    assert "test-key" not in str(calls[0].url)
    # The listing carries no runtime: RUNNING there is not a running container.
    assert pods[0].desired_status == "RUNNING" and not pods[0].is_running


async def test_get_pod_maps_v2_fields_and_keeps_only_tcp_ports() -> None:
    async with _api(lambda _r: httpx.Response(200, json=RUNNING_POD), []) as api:
        pod = await api.get_pod("p1")

    assert pod.is_running and pod.uptime_s == 42
    assert pod.machine == "NVIDIA RTX A4000" and pod.usd_per_hr == 0.25
    assert pod.ports == {"22/tcp": 40022}  # the http port's proxy ip is unroutable
    assert pod.public_ip == "203.0.113.7"


async def test_missing_key_is_an_error_before_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    api = RunPodAPI(transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={"pods": []})))
    with pytest.raises(RunPodError, match="RUNPOD_API_KEY is not set"):
        await api.list_pods()


async def test_reads_retry_on_503_but_create_never_retries() -> None:
    calls: list[httpx.Request] = []
    answers = iter(
        [httpx.Response(503, text="Upstream temporarily unavailable", headers={"Retry-After": "0"})]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(503, text="Upstream temporarily unavailable")
        return next(answers, httpx.Response(200, json={"pods": []}))

    async with _api(handler, calls) as api:
        assert await api.list_pods() == []
        assert len(calls) == 2
        with pytest.raises(RunPodTransientError):
            await api.create_pod(PodSpec(name="n", image="i", machine="cpu3g-2-8"))
    assert [c.method for c in calls] == ["GET", "GET", "POST"]  # one POST only: no double billing


async def test_terminate_treats_pod_not_found_as_done_but_not_a_route_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/gone"):
            return httpx.Response(404, json={"detail": "pod not found"})
        return httpx.Response(404, json={"detail": "The requested path was not found."})

    async with _api(handler, []) as api:
        await api.terminate_pod("gone")
        with pytest.raises(RunPodError, match="404"):
            await api.terminate_pod("other")


def test_create_request_for_cpu_gpu_and_volume() -> None:
    api = RunPodAPI("unused")
    cpu = api.build_create_request(
        PodSpec(name="w", image="img", machine="cpu3g-2-8", env={"K": "v"}, command=("python", "-m", "x"))
    )
    assert cpu["cpu"] == {"id": "cpu3g", "vcpuCount": 2} and "gpu" not in cpu
    assert cpu["cmd"] == ["python", "-m", "x"] and cpu["env"] == {"K": "v"}
    assert cpu["ports"] == ["22/tcp", "8080/http"] and "dataCenterIds" not in cpu
    gpu = api.build_create_request(
        PodSpec(name="w", image="img", machine="NVIDIA L4", data_center_id="DC-TEST", cloud_type="COMMUNITY")
    )
    assert gpu["gpu"] == {"id": "NVIDIA L4", "count": 1} and gpu["cloud"] == "COMMUNITY"
    assert gpu["dataCenterIds"] == ["DC-TEST"]
    with pytest.raises(ValueError, match="volume_mount_path"):
        api.build_create_request(PodSpec(name="w", image="i", machine="NVIDIA L4", network_volume_id="vol"))
    json.dumps(cpu)  # the dry-run file must be plain JSON


async def test_offers_map_stock_and_price_per_machine() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/catalog/gpus"):
            gpus = [
                {"id": "NVIDIA L4", "availability": "HIGH", "price": {"secure": 0.49}},
                {"id": "NVIDIA RTX A4000", "availability": "NONE", "price": {"secure": 0.25}},
            ]
            return httpx.Response(200, json={"gpus": gpus})
        cpus = [{"id": "cpu3g", "availability": "LOW", "price": {"securePerVcpu": 0.03}}]
        return httpx.Response(200, json={"cpus": cpus})

    async with _api(handler, []) as api:
        offers = await api.offers()
        stock = await api.availability()

    assert stock == {"NVIDIA L4": "HIGH", "NVIDIA RTX A4000": "", "cpu3g": "LOW"}
    cpu = offer_for("cpu3g-4-16", offers)
    assert cpu is not None and cpu.usd_per_hr == pytest.approx(0.12)
    assert offer_for("cpu9x-2-4", offers) is None


def test_retry_after_forms() -> None:
    assert parse_retry_after("12") == 12.0
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0
    assert parse_retry_after("soon") is None
