# Chipmonk backend

Runs Chipmonk's AI-scientist agents and records every run as a folder on disk.
The interface lives on its own branch, `amg/frontend`; this branch holds the
backend only.

The code is adapted from AI Inventor, an earlier product by one of the team
(Apache-2.0, see `LICENSE` and `NOTICE`). Only its agent-running layer was
taken. The Chipmonk tools come later: proposing designs, fine-tuning many
small models at once on a GPU, compiling to logic gates and checking the chip.

## Status

Built and proven by a real run on a Mac:

- `claude_cli` backend: the `claude` CLI under a terminal, on the machine's
  own Claude login. One documented end-to-end run (`config/example.yaml`)
  wrote its files, its events and a full `run.json`.
- `openrouter` agent backend (OpenHands on any paid OpenRouter model): one
  real run wrote a file and reported its cost.
- `ask`: one OpenRouter chat call, with its cost logged.
- Run summaries: after `run`, an OpenRouter model writes three bullets on the
  whole run into `run.json` (one real call, about $0.0001).
- The `local` runner, and `flex` (the same, on a team Mac).

Built and tested, dry run only:

- `on_demand` (RunPod): the runner, the worker, the API client and the
  leftover-pod reaper run against a fake RunPod and real local workers.
  Against RunPod itself only read-only calls and dry runs were made; no pod
  has been created. A pod is created only when `compute.runpod.dry_run` is
  false AND `compute.runpod.allow_paid_pods` is true. A pod gets no Claude
  login and no API key, so only the `stub` backend runs there today.

Every part has tests: `pytest` runs them all with no network and no keys;
`pytest -m live` adds the real calls (Claude, OpenRouter), which cost money.

## Run it

From `backend/`:

```bash
uv sync --extra dev                 # add --extra openhands for the OpenRouter agent
source .venv/bin/activate
cp .env.example .env                # then fill in the values you need
python -m chipmonk_backend run --backend stub --prompt "hello"     # no model
python -m chipmonk_backend run --config config/example.yaml \
    --prompt-file examples/seizure_eeg_prompt.md                   # real agent
pytest && ruff check . && ruff format --check .
```

`uv.lock` pins every dependency. For `claude_cli`, install the `claude` CLI
(version 2.1.322 or newer) and log in once with `claude`.

Keys are read from the environment by name: the process environment, then
`backend/.env`, or a file given with `--env-file <path>`. Their values are
never printed or logged.

What one `run` does:

1. The config loads: `config/backend.yaml`, then the `--config` file on top.
   `config/example.yaml` picks `claude_cli` (Sonnet, low effort), the `local`
   runner and `openrouter_tool: true`.
2. A fresh folder `runs/<run_id>/` is made; the agent works in its
   `workspace/`.
3. Each event goes to the console, `logs/backend.log` and
   `runs/<run_id>/events.jsonl` as it happens.
4. With `openrouter_tool` on, the agent may run
   `python -m chipmonk_backend ask --model cheap "<question>"`; each call is
   logged to `runs/<run_id>/llm_calls.jsonl` with its cost.
5. `runs/<run_id>/run.json` ends up holding the prompt, the resolved config,
   the result, the timings, the costs and the summary. The command prints
   the result as JSON and exits 1 if the agent failed.

Other commands:

```bash
python -m chipmonk_backend ask --model cheap "One EEG feature for seizures?"
python -m chipmonk_backend run --no-summary --backend stub --prompt "hi"
python -m chipmonk_backend run --mode on_demand --tier gpu_basic --prompt "hi"
python -m chipmonk_backend config                    # the resolved config
python -m chipmonk_backend.compute.runpod check      # pods and prices, read-only
```

`ask` exits 1 when the model returned no text because it hit `--max-tokens`.

## Summaries

As in AI Inventor, every summary uses one OpenRouter model,
`openai/gpt-oss-120b`, walked provider by provider: each tier pins one
provider, the next tier is the fallback, and the whole walk has one time
budget. The settings are in `src/chipmonk_backend/llm/summaries.yaml`.

- `result.summary.run`: three bullets on what the run did, built from a
  digest of its events, with the run's end pinned first.
- `result.summary.output_label`: a one-line label, added when the agent's
  final answer is longer than 300 characters.

Each entry records its text, cost, tokens, model and provider. With no
OpenRouter key the entry records why instead, and the run is unaffected.

## Layout

```text
backend/
  config/backend.yaml        commented defaults; backend.local.yaml overlays it
  config/example.yaml        a cheap end-to-end run (see "Run it")
  examples/                  example prompts
  src/chipmonk_backend/
    config.py                schema and loader (YAML, local overlay, .env)
    log.py                   loguru: stderr plus logs/backend.log
    runs.py                  run folders: run.json, events.jsonl, workspace/
    orchestrate.py           run_agent(spec, config): one run end to end
    cli.py                   chipmonk-backend run / ask / config
    llm/                     OpenRouter client, key, retry, presets, summaries
    agents/                  AgentBackend interface and the backends
    compute/                 Runner interface: local, flex, on_demand
      runpod/                RunPod client, worker protocol, runner, reaper
  tests/
```

The subpackages meet at a few types:

- `agents.AgentSpec` says what to run: prompts, tools, a working folder, an
  output schema.
- `AgentBackend.run(spec, sink)` streams `AgentEvent`s into an `EventSink`
  and returns an `AgentResult`.
- `compute.Runner.run(spec, run_dir, tier=...)` decides which machine that
  happens on.

## Run modes

| Mode        | Where the agent runs        | Costs          |
| ----------- | --------------------------- | -------------- |
| `local`     | this process, any machine   | model use only |
| `flex`      | a team Mac, logged-in user  | model use only |
| `on_demand` | one RunPod pod per agent    | pod $/hr too   |

Pick the mode with `compute.run_mode` or `--mode`, the hardware with
`compute.tier`: `cpu_basic`, `cpu_plus`, `gpu_basic` or `gpu_plus`. A GPU
tier never falls back to a CPU machine.

## Agent backends

- `claude_cli` drives the interactive `claude` CLI under a terminal and
  reads its session transcript. It uses the CLI's own Claude login, not an
  API key; `ANTHROPIC_API_KEY` is removed from the agent's environment. For
  the length of a run it marks the run's folder trusted in the CLI's
  `.claude.json` (an atomic rewrite) and removes that entry afterwards.
- `openrouter` is an OpenHands agent loop on a paid OpenRouter model. It
  needs the `openhands` extra and `tmux`. Its conversation state stays in
  memory, so the key is never written into the workspace.
- `stub` uses no model. Tests and dry runs use it.

Agents run with permissions bypassed, so their environment is an allowlist
(`agents/env.py`); `RUNPOD_API_KEY` never reaches an agent or a pod.

Paid chat calls retry only failures that happened before the request reached
OpenRouter, and 429 or 5xx answers; a connection lost after sending is not
retried, so one answer is never paid for twice.

## Environment variables

Names only; values go in the gitignored `backend/.env`.

| Name                 | Needed for                          |
| -------------------- | ----------------------------------- |
| `OPENROUTER_API_KEY` | `ask`, summaries, `openrouter`      |
| `RUNPOD_API_KEY`     | `on_demand` mode and RunPod checks  |
| `CLAUDE_CONFIG_DIR`  | optional: another CLI login folder  |
| `CHIPMONK_CONFIG`    | optional: another config file       |
| `HF_TOKEN`           | optional: passed to agents          |

The backend sets two more itself: `CHIPMONK_LLM_CALLS` (where `ask` logs a
call) and `CHIPMONK_WORKER_TOKEN` (a pod's worker token).

## What was left out and why

- AI Inventor's research pipeline and its workflow engine and database: a
  Chipmonk run is one agent and a folder, so `orchestrate.run_agent` does it.
- The web server, accounts and credential handling: the interface lives on
  its own branch and is not connected yet.
- Spend metering and budgets: each call's cost comes from the response and
  goes into the run record.
- Free-model routing: Chipmonk uses paid OpenRouter models only.
- The macOS virtual-machine isolation of Flex: it needs a server and Apple
  VMs; here Flex runs on the Mac itself.
- Email, analytics, deployment tooling and the gallery: not needed to run
  agents.

## Open decisions

- How agents on a RunPod pod log in. A pod has no Claude login; the options
  are the `openrouter` backend with a key passed to pods, an Anthropic API
  key let through the allowlist, or shipping a CLI login.
- Where the worker image (`Dockerfile.worker`) is pushed.
