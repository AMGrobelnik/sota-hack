"""Act as a remote AI scientist: connect over MCP streamable HTTP, submit the spike model, run jobs, read events.
usage: .venv/bin/python scripts/mcp_client_demo.py http://HOST:8765/mcp [token]"""
import asyncio, json, sys, time
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/mcp"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else None


def spike_ir():
    m = json.load(open(Path(__file__).parent.parent / "fixtures" / "spike_best.json")); c = m["cfg"]
    return {"ir": "chipir/1", "name": "spike_af", "inputs": [{"name": "x", "lanes": c["L"], "bits": c["bits"], "signed": c["feat"] == "drr"}],
            "nodes": [{"id": "h0", "op": "matvec", "src": "x", "W": m["W1"], "b": m["b1"]}, {"id": "h1", "op": "shift", "src": "h0", "k": m["shift"]},
                      {"id": "h2", "op": "clip", "src": "h1", "lo": 0, "hi": m["amax"]}, {"id": "s", "op": "matvec", "src": "h2", "W": [m["W2"]], "b": [m["b2"]]},
                      {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}], "outputs": [{"name": "y", "src": "y"}], "meta": {}}


async def main():
    import httpx2 as httpx
    client = httpx.AsyncClient(headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}, timeout=120)
    async with streamable_http_client(URL, http_client=client) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as s:
            await s.initialize()
            tools = await s.list_tools(); print("tools:", len(tools.tools))

            async def call(name, **args):
                r = await s.call_tool(name, args)
                txt = r.content[0].text if r.content else json.dumps(r.structured_content)
                return json.loads(txt)
            run = f"demo-{int(time.time())}"
            c = await call("compile_ir", ir=spike_ir(), run_id=run, session_id="agent-A")
            did = c["design_id"]; print("compiled", did, c["status"], "lint ok:", c["lint"]["ok"])
            jobs = {}
            for tool, args in (("synthesize", {"design_id": did}), ("simulate", {"design_id": did, "inputs": "random", "n": 200000, "device": "cuda"}),
                               ("prove_equivalence", {"design_id": did}), ("map_to_process", {"design_id": did, "pdk": "sky130"}),
                               ("count_luts", {"design_id": did, "family": "ice40"})):
                j = await call("submit_job", tool=tool, args={**args, "run_id": run}, session_id="agent-A"); jobs[tool] = j["job_id"]
            print("submitted:", jobs)
            pending = dict(jobs)
            while pending:
                await asyncio.sleep(2)
                for tool, jid in list(pending.items()):
                    r = await call("job_result", job_id=jid)
                    if r.get("ready"):
                        res = r["result"]; pending.pop(tool)
                        keep = {k: res.get(k) for k in ("status", "metrics", "bit_exact", "n", "proved", "against", "cached", "error") if k in res}
                        print(f"{tool}: {json.dumps(keep)[:300]}")
            lb = await call("list_jobs", limit=5); print("lanes:", lb["lanes"])
    ev = (await client.get(URL.replace("/mcp", f"/events/{run}") + "?format=jsonl")).text.strip().splitlines()
    print("events:", [json.loads(e)["type"] for e in ev])

asyncio.run(main())
