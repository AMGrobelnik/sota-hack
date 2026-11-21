# Chipmonk backend

Runs Chipmonk's AI-scientist agents and records every run as a folder on disk.
It is separate from the frontend (`../frontend/`) and not connected to it yet.

The code is adapted from AI Inventor, an earlier product by one of the team.
Only its agent-running layer was taken. The Chipmonk tools come later:
proposing designs, fine-tuning many small models at once on a GPU, compiling
to logic gates and checking the chip.

## Status

This is a skeleton. The interfaces, config schema, run folders, logging,
the `stub` backend and the `local` and `flex` runners work. Everything else
raises `NotImplementedError` and says in its docstring which AI Inventor
module to port.

| Part                         | State   |
| ---------------------------- | ------- |
| config, logging, run folders | working |
| `stub` backend, local, flex  | working |
| `claude_cli` backend         | working |
| `openrouter` agent backend   | working |
| OpenRouter chat client       | working |
| RunPod runner and worker     | dry run |

The RunPod runner, worker, client and reaper are built and tested against a
fake control plane with real local workers. Against RunPod itself only
read-only calls and dry runs have been made; no pod has been created yet.
`python -m chipmonk_backend.compute.runpod check` lists pods and prices,
`dry-run --tier gpu_basic` prints each mode's create request, and `reap`
lists leftover `chipmonk_worker_*` pods (`--delete` terminates them).
`Dockerfile.worker` builds the worker image.

## Layout

```text
backend/
  config/backend.yaml        commented defaults; backend.local.yaml overlays it
  src/chipmonk_backend/
    config.py                schema and loader (YAML, local overlay, .env)
    log.py                   loguru: stderr plus logs/backend.log
    runs.py                  run folders: run.json, events.jsonl, workspace/
    orchestrate.py           run_agent(spec, config): one run end to end
    cli.py                   chipmonk-backend run / config
    llm/                     OpenRouter client, key, retry policy, presets
    agents/                  AgentBackend interface and the backends
    compute/                 Runner interface: local, flex, on_demand
      runpod/                RunPod client, worker protocol, runner, reaper
  tests/
```

The three subpackages meet at a few types:

- `agents.AgentSpec` says what to run: prompts, tools, a working folder, an
  output schema.
- An `AgentBackend.run(spec, sink)` call streams `AgentEvent`s into an
  `EventSink` and returns an `AgentResult`.
- A `compute.Runner.run(spec, run_dir, tier=...)` call decides which machine
  that happens on.

`runs.JsonlEventSink` stores the events, so no database is needed.

## Run modes

| Mode        | Where the agent runs             | Costs          |
| ----------- | -------------------------------- | -------------- |
| `local`     | this process, any machine        | model use only |
| `flex`      | a team Mac, logged-in user       | model use only |
| `on_demand` | one RunPod pod per agent         | pod $/hr too   |

Pick the mode with `compute.run_mode` or `--mode`. Pick the hardware with
`compute.tier`: `cpu_basic`, `cpu_plus`, `gpu_basic` or `gpu_plus`. A GPU tier
never falls back to a CPU machine. In AI Inventor, Flex ran agents inside a
macOS VM on an enrolled Mac. That isolation is deferred; here Flex runs on
the Mac host. RunPod stays in dry-run mode until `compute.runpod.dry_run` is
set to false: pod requests are built and saved, never sent.

## Agent backends

- `claude_cli` drives the interactive `claude` CLI under a PTY and reads its
  session transcript. It uses the CLI's own Claude login on the machine, not
  an API key. `ANTHROPIC_API_KEY` is removed from the agent's environment, so
  a run never moves to API billing by accident.
- `openrouter` is an OpenHands agent loop on any OpenRouter model. It needs
  the `openhands` extra and `tmux`. It needs only `OPENROUTER_API_KEY`, which
  makes it the easy choice on RunPod pods.
- `stub` uses no model. Tests and dry runs use it.

Agents run with permissions bypassed. Their environment is therefore an
allowlist (`agents/env.py`); `RUNPOD_API_KEY` never reaches an agent or a pod.

## Install

```bash
cd backend
uv venv .venv --python=3.12
source .venv/bin/activate
uv pip install -e ".[dev]"          # add ,openhands for the OpenRouter agent
cp .env.example .env                # then fill in the values you need
chipmonk-backend run --backend stub --prompt "hello"
pytest && ruff check .
```

For `claude_cli`, install the `claude` CLI (version 2.1.322 or newer) and log
in once with `claude`.

## Environment variables

Names only; values go in the gitignored `backend/.env` and are never logged.

| Name                 | Needed for                       |
| -------------------- | -------------------------------- |
| `OPENROUTER_API_KEY` | OpenRouter calls and agent       |
| `RUNPOD_API_KEY`     | `on_demand` mode                 |
| `CLAUDE_CONFIG_DIR`  | optional: other CLI login folder |
| `HF_TOKEN`           | optional: Hugging Face downloads |
| `CHIPMONK_CONFIG`    | optional: other config file      |

## Left out of AI Inventor, and why

- The research pipeline: 80k lines bound to a DBOS workflow engine.
  `orchestrate.run_agent` replaces it.
- Postgres, DBOS and the event journal: a run is a folder, and its events
  go to `events.jsonl`.
- The web server, accounts, auth and Claude credential rotation: the
  frontend is not connected yet.
- Billing, spend metering and the metering proxy: the cost of a call comes
  from the response.
- Email, analytics and telemetry export.
- Deployment tooling, Docker images and the gallery: Chipmonk needs one slim
  worker image instead.
- The free-model router.
- Flex's VM layer, which needs a server, Postgres tables and Apple VMs.

## Open decisions

- How agents on a RunPod pod log in to Claude. The pod has no Claude login.
  The options are the `openrouter` backend on pods, an Anthropic API key let
  through the allowlist, or shipping a CLI login.
- The worker image: Python 3.12, the backend and the `claude` CLI, pushed to
  a registry the team owns.
