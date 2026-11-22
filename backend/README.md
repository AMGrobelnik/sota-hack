# ChipIn backend

Runs ChipIn's AI-scientist agents and records every run as a folder on disk.
The interface lives on its own branch, `amg/frontend`; this branch holds the
backend only.

The code is adapted from AI Inventor, an earlier product by one of the team
(Apache-2.0, see `LICENSE` and `NOTICE`). Only its agent-running layer was
taken. The ChipIn tools come later: proposing designs, fine-tuning many
small models at once on a GPU, compiling to logic gates and checking the chip.

## Status

Built and proven by a real run on a Mac:

- `claude_cli` backend: the `claude` CLI under a terminal, on the machine's
  own Claude login. One documented end-to-end run (`config/example.yaml`)
  wrote its files, its events and a full `run.json`.
- `openrouter` agent backend (OpenHands on any paid OpenRouter model): one
  real run wrote a file and reported its cost.
- `ask`: one OpenRouter chat call, with its cost logged.
- Run summaries: after every run through `orchestrate.run_agent` (the `run`
  command and the local API server alike), an OpenRouter model writes three
  bullets on the whole run into `run.json` (one real call, about $0.0001).
- The `local` runner, and `flex` (the same, on a team Mac).
- The local API server (`serve`) for the dashboards: see
  "Local API for the dashboards".

Built and tested, dry run only:

- `on_demand` (RunPod): the runner, the worker, the API client and the
  leftover-pod reaper run against a fake RunPod and real local workers.
  Against RunPod itself only read-only calls and dry runs were made; no pod
  has been created.

### RunPod

- Paid pods are off by default. The launcher refuses to create one unless
  `compute.runpod.allow_paid_pods` is true, and `compute.runpod.dry_run`
  (on by default) only writes the create request into the run folder.
- Only the `stub` backend can run on a pod: a pod gets no Claude login and
  no OpenRouter key, so the launcher refuses any other backend there.
- The pod's timer ends the worker process, not the pod: the agent stops but
  the pod, and its bill, keep running until something terminates it.
- The launcher terminates its pod when the run ends, on every path. The
  safety net is `python -m chipin_backend.compute.runpod reap --delete`;
  by default it ends only pods older than the longest a live pod can run,
  so it never ends a pod that a run still uses. Without `--delete` it only
  reports.

Every part has tests: `pytest` runs them all with no network and no keys;
`pytest -m live` adds the real calls (Claude, OpenRouter), which cost money.

## Run it

From `backend/`:

```bash
uv sync --extra dev                 # add --extra openhands for the OpenRouter agent
source .venv/bin/activate
cp .env.example .env                # then fill in the values you need
python -m chipin_backend run --backend stub --prompt "hello"     # no model
python -m chipin_backend run --config config/example.yaml \
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
   `python -m chipin_backend ask --model cheap "<question>"`; each call is
   logged to `runs/<run_id>/llm_calls.jsonl` with its cost.
5. `runs/<run_id>/run.json` ends up holding the prompt, the resolved config,
   the result, the timings, the costs and the summary. The command prints
   the result as JSON and exits 1 if the agent failed.

Other commands:

```bash
python -m chipin_backend ask --model cheap "One EEG feature for seizures?"
python -m chipin_backend run --no-summary --backend stub --prompt "hi"
python -m chipin_backend run --mode on_demand --tier gpu_basic --prompt "hi"
python -m chipin_backend config                    # the resolved config
python -m chipin_backend.compute.runpod check      # pods and prices, read-only
```

`ask` exits 1 when the model returned no text because it hit `--max-tokens`.

## Providers

The `openrouter` agent backend and `ask` can use any OpenAI-compatible
provider listed under `providers:` in `config/backend.yaml`. Each entry is a
base URL, the NAME of the environment variable that holds its key, and a
default model. Pick one with `--provider`:

```bash
chipin-backend ask --provider tinker "Say hi in one sentence"
chipin-backend run --provider tinker --model <model id> --prompt "..."
chipin-backend serve --agent openrouter   # POST /api/runs accepts "provider" and "model"
```

| Provider | Key variable | Default model |
| --- | --- | --- |
| `openrouter` | `OPENROUTER_API_KEY` | as before |
| `tinker` | `TINKER_API_KEY` | `thinkingmachines/Inkling-2-Mini` |
| `callosum` | `CALLOSUM_API_KEY` | none |

Keys come from the environment or `--env-file` only and are never printed or
logged. A missing key stops the command with one line naming the variable.
`GET /api/health` lists each provider by name with `configured` and
`key_present`. Events and log lines that name a model also name the provider.

Inkling 2 (Thinking Machines) runs through OpenRouter by default: the ids
`thinkingmachines/inkling-2-mini` and `thinkingmachines/inkling-2-small`, or
the presets `inkling-mini` and `inkling-small` for `ask`. Both take tools and
reasoning effort, so the agent's defaults need no change. The direct Tinker
route below needs `TINKER_API_KEY`.

Tinker's OpenAI-compatible endpoint is
`https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1`; the
Small model is `thinkingmachines/Inkling-2-Small`. `callosum` is a
placeholder: it has no public endpoint, so it refuses to run until a base
URL, model and key are filled in under `providers.callosum`.

## Summaries

Every summary uses one OpenRouter model,
`openai/gpt-oss-120b`, walked provider by provider: each tier pins one
provider, the next tier is the fallback, and the whole walk has one time
budget. The settings are in `src/chipin_backend/llm/summaries.yaml`.

- `result.summary.run`: three bullets on what the run did, built from a
  digest of its events, with the run's end pinned first.
- `result.summary.output_label`: a one-line label, added when the agent's
  final answer is longer than 300 characters.

Each entry records its text, cost, tokens, model and provider; the cost is
added to the record's `llm_cost_usd`. With no OpenRouter key the summary is
skipped with one log line and the run is unaffected. `run --no-summary`
skips it too.

## Local API for the dashboards

`serve` starts a local HTTP server that lets a dashboard page start a real
agent run on this Mac and follow it live.

```bash
python -m chipin_backend serve --agent stub --frontend <site folder>
python -m chipin_backend serve           # the Claude agent, port 8797
```

- It binds 127.0.0.1 only, on port 8797 (`--port` or
  `src/chipin_backend/api/api.yaml` change it).
- It prints one link, `http://127.0.0.1:8797/#token=<token>`. The token is
  new at every start and is never written to disk. A page sends it in the
  `X-ChipIn-Token` header; the event stream may pass it as `?token=`.
- Browsers may call it from `https://chipin.space` and from
  `http://127.0.0.1` or `http://localhost` on any port; any other origin is
  refused. `--frontend <folder>` serves a static site at `/`, so a page
  opened through the link needs no other setup; open a dashboard as
  `http://127.0.0.1:8797/dashboard/variants/g1.html#token=<token>`.
- A page on `https://chipin.space` reaches this server with
  `?api=http://127.0.0.1:8797` plus the token. Chrome asks first with a
  Private Network Access preflight; the server answers it with
  `Access-Control-Allow-Private-Network: true`.
- `--agent claude` (the default) runs the `claude_cli` backend on the
  Mac's own Claude login; `--agent stub` runs a scripted agent with no model
  calls. Every run goes through `orchestrate.run_agent`, so it gets a
  `runs/<run_id>/` folder, a full `run.json` and the OpenRouter summary.
- `--stub-step <seconds>` slows the stub's steps (default 0.4 s, about
  10 s a run) so a demo can be followed, messaged and stopped.

| Route or event                 | What it is                   |
| ------------------------------ | ---------------------------- |
| `GET /api/health`              | no token; version            |
| `POST /api/runs`               | start: `prompt`, `preset`    |
| `GET /api/runs`                | every run, newest first      |
| `GET /api/runs/{id}`           | status, summary, cost        |
| `GET /api/runs/{id}/events`    | the stream, `from=<seq>`     |
| `POST /api/runs/{id}/messages` | `text` to the agent          |
| `POST /api/runs/{id}/stop`     | stop the run                 |
| `GET /api/runs/{id}/files`     | `path`, `size` per file      |
| `GET /api/runs/{id}/file`      | `?path=`: one file as text   |
| `POST /api/transcribe`         | one spoken phrase to text    |
| `run.started`                  | prompt, agent, runner        |
| `stage`                        | `name`, `state`, `reason`    |
| `status`                       | one "ChipIn is ..." line     |
| `message`                      | agent or user text           |
| `tool`                         | a tool call, started or done |
| `metric`                       | `key`, `value`, opt. `chip`  |
| `chosen`                       | `chip`: the run's chosen one |
| `artifact`                     | a file, such as the report   |
| `cost`                         | agent cost and tokens        |
| `error`                        | what went wrong              |
| `run.finished`                 | status, summary, `bullets`   |

Stages, in order: `spec`, `reference`, `propose`, `finetune`, `compile`,
`verify`, `report`. Each is `started`, `done` or `skipped`; a skipped stage
carries a short reason. The agent reports them with `./progress` in its
working folder. `run.finished` carries the agent's last message as
`summary` and, when OpenRouter wrote one, the three-bullet run summary as
`bullets`. `./progress metric <key> <number> [unit] --chip <design_id>`
(the flag after the number or the unit) adds `chip` to the metric event,
naming the design the number measures; without it the event is as before.
`./progress chosen <design_id>` writes a `chosen` event with `chip`, the
run's chosen chip; a later one replaces an earlier one. Presets map to agent effort: `lite`, `pro`, `max`, `ultra`.
A run cut short ends `stopped`, its summary saying whether the user
stopped it or the server was shut down.

The files routes cover the agent's working folder only. Paths are
run-folder paths such as `workspace/report.md`, the same as an `artifact`
event's `path`; the `progress` helper and hidden files are not listed, a
path outside `workspace/` is refused (400), and a file over
`file_max_bytes` (512 KB) is cut, marked with `X-ChipIn-Truncated: true`.
The brief's `files` entries carry `name`, `size` and an optional `header`
line (up to 1,000 characters), and `answers` is any JSON object; the
dashboards put their assumptions there as `answers.assumptions`.

What is real today: the Claude agent runs on this Mac, works through the
brief, writes files and a report, reports stages, messages, tools and cost,
and takes messages and stop requests while it runs. With the chip lab
installed (see "Chip lab") it compiles and verifies real chips. What is not:
there is no fine-tuning tool yet, so an agent marks that stage skipped
unless it trains a small model itself; attached files reach the agent as
names and header lines only; runs on rented machines are not offered by
this server.

`run --preset <lite|pro|max|ultra>` makes the same run from the command
line, without the server: the same instructions, `./progress` helper and
`events.jsonl`, on this Mac. Several `--prompt`/`--prompt-file` values are
joined into one brief.

```bash
chipin-backend run --preset pro --env-file <keys> \
    --prompt-file examples/seizure_eeg_prompt.md --prompt-file <more brief>
```

## Chip lab

The chip lab (`chiplab/` on the `ant/chip-lab` branch, guide
`chiplab/docs/CHIPIN_INTEGRATION.md`) turns a trained model into a
verified, measured chip. The backend only lets the agent reach it; the lab
reports its own status lines, metrics and chip files through `./progress`.

Point the backend at a lab install (in the environment, `backend/.env` or
`--env-file`; paths, not secrets):

| Name                 | What it is                              |
| -------------------- | --------------------------------------- |
| `CHIPIN_CHIPLAB_BIN` | folder holding the `chiplab` command    |
| `CHIPLAB_CONFIG`     | the lab's config file, passed as is     |
| `CHIPLAB_USER_DIR`   | the lab's tool folder, passed as is     |

- The lab's default install (`scripts/install.sh`) needs none of them:
  it writes `~/.config/chiplab/config.json` and `~/.local/bin/chiplab`, and
  the lab is on whenever `chiplab` is on the agent's `PATH`.
- An install elsewhere: set `CHIPIN_CHIPLAB_BIN` to the launcher's folder
  (or the lab's `.venv/bin`), and `CHIPLAB_CONFIG` / `CHIPLAB_USER_DIR` to
  where its config and tools are. The folder goes first on the agent's
  `PATH`; the two lab variables pass through the allowlist unchanged.
- When the lab is on, the agent also gets `CHIPIN_PROGRESS_CHIP=1`, which
  tells the lab that `./progress` takes `--chip` and `chosen`; the lab
  then tags each metric with its design and `chip-report` names the chosen
  chip.
- With none of this the lab is off: the agent's environment and
  instructions are as before. A `CHIPIN_CHIPLAB_BIN` with no executable
  `chiplab` in it logs one warning and leaves the lab off.
- Check it: `chiplab doctor` run inside the agent's environment must say
  ok. The lab's `chiplab doctor --agent-env` checks only the default
  install.

What the agent can do with it: when the lab is on, the standing
instructions get the lab's paragraph (`api/chiplab.md`, section 6 of the
guide). The agent calls `chiplab <tool> --json '{...}'` from its working
folder: compile (`ingest-model` or `compile-ir`, `synthesize`,
`count-luts`, `map-to-process`), verify (`simulate`, `prove-equivalence`,
`rtl-simulate`, `verification-level`) and the chip part of report
(`layout`, `timing-power`, `tt-package`, `bitstream`, `estimate-cost`,
and always `chip-report` on the one chosen chip before report is done). It marks the compile and verify stages itself, or passes
`"progress_stages": true`.

What reaches the dashboard: the lab runs `./progress` as a program, so
its lines go through the same checks as the agent's and become ordinary
`status`, `metric` and `artifact` events in `events.jsonl` and on the
event stream. Metrics use the lab's fixed keys (`gates`, `luts_ice40`,
`area_um2`, `vectors_checked`, `mismatches`, `verification_level`,
`timing_slack_ns`, `power_uw_at_rate`, `cost_eur` and the rest; table in
section 2 of the guide), each with its unit. Chip files land under
`workspace/chips/<design_id>/`. The helper and the tailer refuse a metric
that is not a finite number; the lab treats a refused line as non-fatal.

## Layout

```text
backend/
  config/backend.yaml        commented defaults; backend.local.yaml overlays it
  config/example.yaml        a cheap end-to-end run (see "Run it")
  examples/                  example prompts
  src/chipin_backend/
    config.py                schema and loader (YAML, local overlay, .env)
    log.py                   loguru: stderr plus logs/backend.log
    runs.py                  run folders: run.json, events.jsonl, workspace/
    orchestrate.py           run_agent(spec, config): one run end to end
    cli.py                   chipin-backend run / ask / serve / config
    chiplab.py               the optional chip lab: agent PATH and settings
    api/                     the local API server for the dashboards
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
| `CHIPIN_CONFIG`    | optional: another config file       |
| `HF_TOKEN`           | optional: passed to agents          |
| `CHIPIN_CHIPLAB_BIN` | optional: the chip lab, see above   |
| `CHIPLAB_CONFIG`     | optional: the lab's config file     |
| `CHIPLAB_USER_DIR`   | optional: the lab's tool folder     |

The backend sets two more itself: `CHIPIN_LLM_CALLS` (where `ask` logs a
call) and `CHIPIN_WORKER_TOKEN` (a pod's worker token).

## What was left out and why

- AI Inventor's research pipeline and its workflow engine and database: a
  ChipIn run is one agent and a folder, so `orchestrate.run_agent` does it.
- The product web server, accounts and credential handling: the interface
  lives on its own branch; it reaches this backend only through the local
  API server above.
- Spend metering and budgets: each call's cost comes from the response and
  goes into the run record.
- Free-model routing: ChipIn uses paid OpenRouter models only.
- The macOS virtual-machine isolation of Flex: it needs a server and Apple
  VMs; here Flex runs on the Mac itself.
- Email, analytics, deployment tooling and the gallery: not needed to run
  agents.

## Open decisions

- How agents on a RunPod pod log in. A pod has no Claude login; the options
  are the `openrouter` backend with a key passed to pods, an Anthropic API
  key let through the allowlist, or shipping a CLI login.
- Where the worker image (`Dockerfile.worker`) is pushed.
