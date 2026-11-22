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
- Fan-out stage batches: one real Lite run (a Claude orchestrator, three
  Claude subagents per batch, chip lab on) ran all five batches with the
  three subagents of each running at once, merged each batch and ended
  with a verified chip. Two more runs put the subagents on OpenRouter for
  the propose and compile batches: on `deepseek/deepseek-v4-flash-0731`
  they ran in parallel and produced the chosen chip; on
  `openai/gpt-oss-20b` they ran in parallel but got stuck on the tools.

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
budget. The settings are in `src/chipin_backend/llm/summaries.yaml`; set
`llm.summaries_file` in the config to use another file of the same shape.
Every summary goes through `summarise()` in `llm/summarise.py`, so a new
summary kind inherits the chain.

- `result.summary.run`: three bullets on what the run did, built from a
  digest of its events, with the run's end pinned first.
- `result.summary.output_label`: a one-line label, added when the agent's
  final answer is longer than 300 characters.

Each entry records its text, cost, tokens, model and provider; the cost is
added to the record's `llm_cost_usd`. With no OpenRouter key the summary is
skipped with one log line and the run is unaffected. `run --no-summary`
skips it too.

## Levels of summaries

Every dashboard run (`serve`, `run --preset`) also gets a short line for
everything that happens, and lines for those lines, so a long run with many
subagents stays readable: the reader sees one line per level and opens any
line down to the full message or tool call. `api/summaries.py`, settings in
`src/chipin_backend/api/summaries.yaml`.

| Level   | One per                       | Built from          |
| ------- | ----------------------------- | ------------------- |
| `item`  | message, tool call, metric... | the event's text    |
| `group` | run of one agent's items      | its item lines      |
| `agent` | subagent, when it finishes    | its group lines     |
| `batch` | fan-out batch of a stage      | its subagent lines  |
| `stage` | stage, when it closes         | its groups, batches |
| `run`   | the run                       | the stage lines     |

- An item is an agent message, a tool call with its result (one item for
  both), a metric, an artifact, a chosen chip or an error. A one-line
  message of up to 100 characters, and a tool whose own line says it all
  (`Read brief.md`), keep their own words; the rest go to the model.
- A group is a run of consecutive items of one agent in one stage. It
  closes when the stage changes, the agent starts subagents, a user message
  arrives, it reaches 12 items, an item comes more than 120 s after the
  last one (event time), the agent writes a message once the group has 4
  items, its subagent finishes, or the run ends. These rules read only the
  event sequence, so a replay gives the same summaries as the live run.
- `agent` and `batch` exist only with the fan-out events
  (`subagent.started`, `subagent.finished`, `stage.merged`); without them
  a stage is built from the orchestrator's groups alone. A batch with no
  merge event is summarised when its stage closes.
- A stage gets interim summaries (`final: false`) every 4 new groups or
  subagents while it runs; the run gets one each time a stage closes. The
  final ones come when the stage closes and when the run ends, before
  `run.finished`. The newest summary with an id replaces older ones.

Each is one `summary` event on the stream and in `events.jsonl`, and one
line in `summaries.jsonl`:

```json
{"type": "summary", "id": "g3", "level": "group", "covers": ["i12", "i14"],
 "parent": "stage:propose", "agent": "a2", "stage": "propose",
 "text": "Fitted thresholds, 100% on held-out windows",
 "model": "openai/gpt-oss-120b", "final": true, "source": "model"}
```

- Ids: `e<seq>` a stream event, `i<seq>` an item (the seq of the event
  that completes it), `g<n>` a group, `agent:<id>`, `batch:<stage>:<k>`,
  `stage:<name>`, `run`. `covers` lists the ids one level down; `parent`
  is the id that will cover this one. `agent` and `parent` are left out for
  the orchestrator and the run.
- `source`: `model`; `verbatim` (its own words, or a single child's line);
  `fallback` (no model answer: the text's own first line). `model` names
  what wrote a `model` line.
- `GET /api/runs/{id}/summaries` returns `summaries.jsonl`; the event
  stream replays the live ones on reconnect.

Limits, per run:

- One model call at a time. Waiting items go together, up to 20 a call
  (a lone batch waits 3 s for company); closed groups up to 8 a call. So
  a wide run makes bigger calls, not more of them.
- At most 30 calls a minute, and at most `max_usd_per_run` ($0.05) of
  model spend. Past the limit one `summary.limit` event (`reason`,
  `text`, `spent_usd`, `limit_usd`) is written and every later line is the
  text's own first line. Three failed calls in a row (`model failing`), no
  key (`no key`) or the 90 s left at the run's end running out (`time`) do
  the same. A summary never blocks or fails a run.
- The model reads the run's text as quoted JSON, told never to follow
  instructions in it; values of secret-named environment variables and
  key-shaped strings are replaced by `[redacted]` first.
- The model is the summary model above (`openai/gpt-oss-120b` on the fast
  tiers), or `model` in `summaries.yaml`; the key is `OPENROUTER_API_KEY`.
- Off: `enabled: false`, or `run --preset ... --no-summary`; the run is
  then exactly as without this feature.

A recorded run, old or new:

```bash
chipin-backend summarise <run id or folder> [--items] [--no-model] --env-file <keys>
```

It builds every level from the folder's `events.jsonl`, rewrites
`summaries.jsonl`, prints the outline (items with `--items`) and the
calls, seconds and cost per level. `--no-model` makes no calls.

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
| `GET /api/runs/{id}/evidence`  | run evidence, once finished  |
| `GET /api/runs/{id}/summaries` | levels of summaries so far   |
| `GET /api/runs/{id}/files`     | `path`, `size` per file      |
| `GET /api/runs/{id}/file`      | `?path=`: one file as text   |
| `GET /api/history`             | runs with picker facts       |
| `GET /api/runs/{id}/history`   | all events, or a page        |
| `POST /api/transcribe`         | one spoken phrase to text    |
| `run.started`                  | prompt, agent, runner        |
| `stage`                        | `name`, `state`, `reason`    |
| `stage.merged`                 | fan-out: a batch's merge     |
| `status`                       | one "ChipIn is ..." line     |
| `message`                      | agent or user text           |
| `tool`                         | a tool call, started or done |
| `metric`                       | `key`, `value`, opt. `chip`  |
| `chosen`                       | `chip`: the run's chosen one |
| `artifact`                     | a file, such as the report   |
| `cost`                         | agent cost and tokens        |
| `error`                        | what went wrong              |
| `evidence`                     | the three evidence summaries |
| `summary`                      | one summary, see "Levels"    |
| `summary.limit`                | summaries hit a limit        |
| `run.finished`                 | status, summary, `bullets`   |

Stages, in order: `spec`, `reference`, `propose`, `finetune`, `compile`,
`verify`, `report`. Each is `started`, `done` or `skipped`; a skipped stage
carries a short reason. The agent reports them with `./progress` in its
working folder. With fan-out on, the backend may close a merged stage the
agent left open (see "Fan-out"); that `done` carries
`"closed_by": "backend"`. Accuracy-like metrics (accuracy, sensitivity,
specificity, pass rates) are asked for as a fraction between 0 and 1 with
no unit; runs recorded before this rule are left as they are. `run.finished` carries the agent's last message as
`summary` and, when OpenRouter wrote one, the three-bullet run summary as
`bullets`. `./progress metric <key> <number> [unit] --chip <design_id>`
(the flag after the number or the unit) adds `chip` to the metric event,
naming the design the number measures; without it the event is as before.
`./progress chosen <design_id>` writes a `chosen` event with `chip`, the
run's chosen chip; a later one replaces an earlier one. Presets map to agent effort: `lite`, `pro`, `max`, `ultra`;
with fan-out on they also set the subagents per stage batch (see "Fan-out").
A run cut short ends `stopped`, its summary saying whether the user
stopped it or the server was shut down.

### Talking to the agent

`POST /api/runs/{id}/messages` with `{"text": "..."}` (the token header,
at most 4,000 characters) talks to the run's agent, the orchestrator only.
It answers 202 with `id` (`m1`, `m2`, ...) and `delivery`: `live` (it went
to the running agent), `after_run` (the agent was between its last step
and the end of the run; it goes as a follow-up then) or `follow_up`.

- The message is recorded at once as
  `{"type": "message", "role": "user", "author": "you", "text", "message_id"}`.
- When the agent has it, a `status` event follows with
  `"text": "Your message reached the agent"` and the same `message_id`.
  The agent's answer and what it does next are ordinary events. Several
  messages are delivered in the order sent; the run is never restarted.
- After the run ended (`succeeded` or `stopped`), a message is a
  follow-up: the same session continues in the same folder, in the same
  event stream. The run goes back to `running` and ends with another
  `run.finished` carrying `follow_up: <n>`; the delivery status comes when
  the agent starts answering. The `cost` event and the run's cost are the
  totals so far (`turn_usd` is the follow-up's own); `run.json` lists each
  follow-up under `result.follow_ups`. A stream that closed at the first
  `run.finished` must be opened again with `from=<next seq>`. A follow-up's
  first status line is "ChipIn is continuing the conversation".
- A follow-up whose agent cannot be started (after the backend's own
  retries) ends with an `error` event and a `run.finished` with
  `follow_up_failed: true` and the run's earlier status and summary: the
  run is not failed. The next message tries again and takes the unanswered
  ones with it.
- Error text in the stream and the API names no local absolute path: a
  path inside the run folder is shown relative to it, any other by its
  last part.
- Errors: 404 unknown run, 400 empty text, 413 too long, 409 a failed run,
  429 too many runs in progress (for a follow-up), 401 no token.
- The standing instructions say a user message takes priority over the
  plan where they conflict: answer briefly, say what changes, carry on.

What "delivered" means per harness:

- `claude_cli`: the message is typed into the running CLI, which queues
  it and hands it to the model as soon as the running tool calls finish,
  inside the same turn (Claude Code docs, "Queue messages while Claude
  works"). Delivered is the transcript record that hands it over
  (`queue-operation` `remove` with `absorbed_mid_turn`, or the user record
  of the next turn when it came as a turn ended). A follow-up resumes the
  session with `--resume <session id>`; the cost is this turn's share.
- `openrouter`: `Conversation.send_message` while the loop runs; the
  agent's next step reads it. Delivered is when it is in the conversation.
  A follow-up continues the conversation kept in memory (the last four);
  after a server restart it starts a new one in the same folder, told to
  read the files there.
- `stub`: answered at its next step and noted in `report.md`.

The files routes cover the agent's working folder only. Paths are
run-folder paths such as `workspace/report.md`, the same as an `artifact`
event's `path`; the `progress` and `subagent` helpers and hidden files
are neither listed nor served (404), a path outside `workspace/` is
refused (400), and a file over
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

Both agents get the same standing instructions (`api/instructions.md`,
plus the training and chip-lab paragraphs when each is on): `claude` as a tagged
system prompt ahead of its first prompt, `openrouter` appended to the
OpenHands system message (`AgentContext.system_message_suffix`), which
keeps OpenHands' own tool rules. `run.json` records them under
`agent.system_prompt`.

```bash
chipin-backend run --preset pro --env-file <keys> \
    --prompt-file examples/seizure_eeg_prompt.md --prompt-file <more brief>
```

## Fan-out: stage batches of parallel subagents

Off by default. With fan-out on, the run's agent is an orchestrator. Spec
and report are its own. Each of the other five stages (reference,
propose, finetune, compile, verify) is ONE BATCH: the orchestrator writes
down as many different strategies as the batch size, starts one subagent
per strategy, all at once, waits for all of them, merges the best results
into the stage's result and records the merge, and only then moves on.
Every subagent is the same four layers as the orchestrator (a model, a
harness, its own prompt, the chip lab), usually on a smaller model.

The preset is the run-size control: it sets the effort and the number of
subagents in each stage batch.

| Preset  | Effort | Batch size | Per run | Each   |
| ------- | ------ | ---------- | ------- | ------ |
| `lite`  | low    | 3          | 17      | 10 min |
| `pro`   | high   | 10         | 52      | 20 min |
| `max`   | xhigh  | 15 (a)     | 78      | 25 min |
| `ultra` | max    | 20         | 104     | 30 min |

(a) The owner did not name a batch size for `max`; 15 is an assumption to
confirm. A run with no preset gets 3. "Per run" is five batches plus a few
spare starts for retries; "Each" is the wall-clock limit per subagent.

Models: when the request leaves them on automatic, the orchestrator runs
the large Claude model (`agents.claude_cli.model`, `claude-opus-5-5`) and
its subagents the smaller one (`fanout.subagent.model`,
`claude-sonnet-5-5`), both on the `claude` harness. A request may name
either: `model` for the orchestrator, `fanout.subagent.model` for the
subagents, or put the subagents on the other harness
(`fanout.subagent.agent: "openrouter"`, a small OpenRouter model).

```bash
chipin-backend run --preset lite --fanout --prompt "..."     # 3 per stage batch
chipin-backend run --preset lite --fanout --subagent-agent openrouter \
    --subagent-model openai/gpt-oss-20b --subagent-max-usd 0.2 --prompt "..."
```

`POST /api/runs` takes the same as an optional object: `"fanout": true`
(the preset's batch size), or `{"width": 3, "max_usd": 0.2, "subagent":
{"agent": "openrouter", "model": "inkling-mini"}}` (any field turns it on;
`max_usd` may only lower the limit). `GET /api/runs/{id}` then shows
`fanout` (batch size, batch stages, limits, the orchestrator's and the
subagents' harness, model and effort), `subagents` (each one's id, name,
stage, strategy, harness, model, state, seconds, cost, result and folder)
and `merges` (one per merged batch).

The helper. The orchestrator's folder gets `./subagent` next to
`./progress`:

```text
./subagent start <stage> "<brief>" [--name <label>] [--agent <harness>] [--model <id>]
./subagent wait <id> [<id> ...] | --stage <stage> | --all [--timeout <s>]
./subagent merge <stage> --kept <id>[,<id> ...] --why "<one line>"
./subagent list
```

`start` prints the new id (`a1`, `a2`, ...) and returns; the brief's first
line is the subagent's strategy. `wait` returns when they have finished or
after `wait_timeout_s` (100 s, under the agents' 2-minute command limit)
and prints each one's state (`done`, `failed`, `timed out`, `stopped`),
result and folder; it says plainly when some are still running. `merge`
writes the batch's `stage.merged` event; it is refused while a subagent of
that stage is still running, for a stage with no batch, for an id outside
the batch and for a stage already merged (`--kept none` when nothing is
worth keeping). Subagents of a stage started after its merge (a retry
batch) are merged on their own, with a second `stage.merged`. Like `./progress`, the helper only writes a request line
(`subagents.jsonl`) and reads `subagents.json`; the backend starts each
subagent through the same runner and agent backends as the run's own
agent, with the same environment allowlist and chip-lab settings, keys
never written into a folder. A subagent works in `workspace/agents/<id>/`
with its own `./progress` (which refuses `stage` and `chosen`), its own
instructions (`api/subagent.md`, plus the training and chip-lab paragraphs
when each is on, delivered as the orchestrator's are), the chip-lab skill
installed in its folder exactly as for the orchestrator (when the lab is
on) and its brief in `brief.md`; its last message is saved there as
`subagent-result.md`. Its raw events and progress lines are under
`subagents/<id>/` in the run folder. A subagent has no `./subagent` and
the helper refuses to run inside one. A subagent may still work from the
orchestrator's folder, where the lab tools find the orchestrator's
`./progress`; with fan-out on, that helper passes any call made from a
subagent's environment to the subagent's own helper, so the lines carry
the subagent's id and it cannot mark the orchestrator's stages.

The instructions. With fan-out on, the orchestrator's standing
instructions get `api/orchestrator.md`: it is the orchestrator; spec and
report are its alone; at each batch stage it writes down that many
different strategies in `decisions.md` (examples per stage: baseline
families at reference, design families at propose, training settings at
finetune, designs and compile choices at compile, designs and checks at
verify, each verified by a subagent that did not build it), starts the
whole batch before waiting, waits, merges on the lab's numbers against the
user's targets, records the merge, marks the stage done and carries the
merged result on; it never does a batch's work itself. A subagent gets
`api/subagent.md`: it is one of a batch trying different strategies for
one stage; it does exactly its strategy, never invents a measurement and
returns the short result asked for.

Stages left open. An orchestrator may merge a batch and move on without
marking the stage done. The backend then closes it itself, with an
ordinary `stage` event (`state: done`, `closed_by: backend`), when a later
stage is marked started (the `done` comes first) or when the run ends. A
stage is closed only if the orchestrator marked it started, recorded a
merge for it and never marked it done or skipped; while a batch of it is
still queued, running or not yet merged (a retry batch), a later stage
does not close it; the merge of that batch, or the run's end, does. A
`done` or `skipped` from the orchestrator itself is left as it is.

The events. Everything a subagent causes (`status`, `tool`, `metric` with
its optional `chip`, `artifact`, `message`, `cost`) lands in the run's own
`events.jsonl` and stream with `"agent": "<id>"`; the orchestrator's events
carry no such field, so old readers and old runs are unchanged. A
subagent's failure is not an `error` of the run and does not block the
merge. Three new events:

| Event               | Fields                                    |
| ------------------- | ----------------------------------------- |
| `subagent.started`  | `id`, `name`, `stage`, `strategy`, ...    |
| `subagent.finished` | `id`, `stage`, `state`, `seconds`, ...    |
| `stage.merged`      | `stage`, `started`, `ids`, `kept`, ...    |

`subagent.started` also carries `harness`, `model` and `brief` (cut to 200
characters); `subagent.finished` carries `cost`, `result` and `error`.
`stage.merged` also carries `done` (how many ended `done`), `why` and
`seconds` (first start to last finish of the batch). A subagent's artifact
paths are run-folder paths such as `workspace/agents/a1/note.md`, served
by the files routes like any other. When subagents ran, a last `cost`
event (no `agent`) carries the run's total with `subagents_usd`;
`api.json`'s `cost` is that total, and `run.json` lists the subagents
(`subagents`, `subagent_cost_usd`).

The settings (`fanout` in `src/chipin_backend/api/api.yaml`):

| Setting                     | Default                  |
| --------------------------- | ------------------------ |
| `enabled`                   | false                    |
| `width`                     | null: the preset's       |
| `widths`                    | 3 / 10 / 15 / 20         |
| `default_width`             | 3                        |
| `max_parallel`              | null: the batch size     |
| `max_total`                 | null: 5 x width + spare  |
| `spare_starts`              | null: width / 5, min 2   |
| `usd_per_subagent`          | 0.05                     |
| `max_usd`                   | null: 0.05 x max_total   |
| `wait_timeout_s`            | 100                      |
| `subagent.agent`            | null: the orchestrator's |
| `subagent.model`            | `claude-sonnet-5-5`      |
| `subagent.openrouter_model` | null: harness default    |
| `subagent.effort`           | null: the preset's       |
| `subagent.timeout_s`        | null: per preset         |
| `subagent.timeouts`         | 600 / 1200 / 1500 / 1800 |

The limits. The whole batch runs at once; a start beyond `max_parallel`
is accepted and queued until a running subagent finishes. A start beyond
`max_total`, or on the `openrouter` harness once the run's subagents have
spent `max_usd` on API models, is refused: the helper prints why and exits
1 (the orchestrator is told to carry on with what it has). A subagent past
its time limit ends `timed out`. When the run ends or is stopped, every
subagent still queued or running is stopped first, its processes with it;
their `subagent.finished` events come before `run.finished`. Spend is
counted when a subagent ends, so subagents already running can carry the
total a little past `max_usd`. With fan-out off nothing changes: no
helper, no extra instructions, no new events or fields.

## Playback of recorded runs

A dashboard plays an old run back from its events (`api/history.py`).

- `GET /api/history`: every run, newest first, with what a picker shows:
  `id`, `title` (the brief's first line), `prompt`, `started_at`,
  `finished_at`, `duration_s` (first to last event), `state`, `preset`,
  `agent`, `chosen` (the latest chosen chip), `counts` (events, designs,
  stages done, messages, tools, artifacts, metrics, subagents), `cost_usd`.
- `GET /api/runs/{id}/history`: all of a run's events with their `seq` and
  `ts` in one response. `?from=<seq>&limit=<n>` (n up to 5,000) gives one
  page; `next` is the next page's `from`, `null` on the last one.

`export` writes a recorded run as one static JSON file, so the public site
can play it back without a server:

```bash
chipin-backend export <run id or folder> --out <site>/dashboard/data/runs/<name>.json \
    --index <site>/dashboard/data/runs/index.json
```

- The file holds the run's facts (as above), its summary, every event and
  the small text artifacts its events name (`--artifact-max-bytes`, default
  64 KB each, the report first).
- Home folder paths become `~`; anything shaped like a key or token, every
  e-mail address and this machine's host and user names are replaced.
  `redactions` counts what was replaced.
- `--max-bytes` (default 1.5 MB) bounds the file: tool details and long
  texts are cut first, then artifacts dropped; a run that still does not
  fit is refused (exit 2).
- `--index` adds or replaces the run's line in an index file, newest first.

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

What the agent can do with it: when the lab is on, the agent gets the
chip-lab skill (below) and the standing instructions get a short paragraph
(`api/chiplab.md`) naming the skill, the required `chip-report` call and a
fallback. The agent calls `chiplab <tool> --json '{...}'` from its working
folder: compile (`ingest-model` or `compile-ir`, `synthesize`,
`count-luts`, `map-to-process`), verify (`simulate`, `prove-equivalence`,
`rtl-simulate`, `verification-level`) and the chip part of report
(`layout`, `timing-power`, `tt-package`, `bitstream`, `estimate-cost`,
and always `chip-report` on the one chosen chip before report is done). It marks the compile and verify stages itself, or passes
`"progress_stages": true`.

### The chip-lab skill

The lab's tools also reach the agent as a skill named `chiplab`
(`src/chipin_backend/skills/chiplab/`, shipped in the package): `SKILL.md`
says when to use the lab, the call shape, the exit codes, which tools serve
compile, verify and report, the required `chip-report` call and how
results go through `./progress`; `references/` holds a worked sequence
and, per run, `tools.md`: the installed lab's own reference
(`chiplab agent-doc`) under a header naming the lab's version and commit,
so it never drifts from the lab. If the lab's reference cannot be read,
the skill is installed without it, the agent is told to run
`chiplab agent-doc`, and a warning is logged.

When the lab is on, the runner installs the skill into each run's
working folder before the agent starts, and into each fan-out subagent's
folder (`workspace/agents/<id>/`, same paths below) before it starts;
nothing is written outside the run folder, and with the lab off nothing
is installed.

| Harness      | Installed at                        | How it loads   |
| ------------ | ----------------------------------- | -------------- |
| `claude_cli` | `workspace/.claude/plugins/chipin`  | `Skill` tool   |
| `openrouter` | `workspace/.agents/skills/chiplab`  | `invoke_skill` |

- `claude_cli`: the skill sits in a session-only plugin (manifest
  `.claude-plugin/plugin.json`, skill under `skills/chiplab`), passed
  with `--plugin-dir`; the CLI lists it as `chipin:chiplab`.
  `--setting-sources` stays as configured (`[]` by default): the
  `project` source would also find `.claude/skills`, but it loads every
  `CLAUDE.md` above the working folder and the user's own, which a run
  must not see.
- `openrouter`: the folder's skills go into the OpenHands agent's
  `AgentContext`; the SDK lists name and description under
  `<available_skills>` and returns the body when the agent calls
  `invoke_skill`. Only this folder is read, not the SDK's wider project
  loading.

To use the skill in another project:

```bash
chipin-backend skill export <project>/.claude/skills   # writes .../chiplab
```

It writes the same folder, with the lab's reference when the lab is on
here, only where it is told; it refuses a tool folder in the home
directory (`~/.claude`, `~/.agents` and the like).

What reaches the dashboard: the lab runs `./progress` as a program, so
its lines go through the same checks as the agent's and become ordinary
`status`, `metric` and `artifact` events in `events.jsonl` and on the
event stream. Metrics use the lab's fixed keys (`gates`, `luts_ice40`,
`area_um2`, `vectors_checked`, `mismatches`, `verification_level`,
`timing_slack_ns`, `power_uw_at_rate`, `cost_eur` and the rest; table in
section 2 of the guide), each with its unit. Chip files land under
`workspace/chips/<design_id>/`. The helper and the tailer refuse a metric
that is not a finite number; the lab treats a refused line as non-fatal.

## Training Python

The agent's own `python3` may have no numpy or torch, and then the
reference and finetune stages are skipped. Name a Python that can train
(a path, not a secret):

| Name                  | What it is                             |
| --------------------- | -------------------------------------- |
| `CHIPIN_TRAIN_PYTHON` | a Python interpreter that can train    |

- It passes to the agent as `CHIPIN_TRAIN_PYTHON`; it is not put on the
  agent's `PATH`. The chip lab's `.venv/bin/python` will do: it has
  numpy, torch, scikit-learn and xgboost, the libraries behind the lab's
  `ingest-model` formats.
- When it is set, the standing instructions get the training paragraph
  (`api/training.md`): run training and data scripts with
  `"$CHIPIN_TRAIN_PYTHON"`; with no recordings attached, simulate them and
  write the assumptions down; split by patient before training; score
  sensitivity and false alarms per hour on held-out patients only, per
  patient and pooled, labelled "synthetic data"; hand the trained weights
  to the lab with `ingest-model`. The pooled figures of the chosen design
  arrive as the metrics `synthetic_sensitivity` (a fraction between 0
  and 1; runs before this rule used `synthetic_sensitivity_pct`) and
  `synthetic_false_alarms_per_h`, with `patients_pass` / `patients_total`.
- Unset, or not an executable file (one warning in the log), training is
  off: the environment and instructions are as before, and the agent
  skips reference and finetune with its reason.

## Run evidence

Three measurements computed only from a finished run's own folder, with
no network and no model calls (`evidence.py`):

```bash
chipin-backend evidence <run id or run folder> [--json]
```

The command prints the markdown (or JSON) and writes `evidence.json` and
`evidence.md` into the run folder. `GET /api/runs/{id}/evidence` returns
the same dict for a finished run (409 while it runs). At the end of every
dashboard run the backend computes it once and emits one `evidence` event
with the three summaries, just before `run.finished`; a failure there is
logged and never fails the run.

- **Number check.** Every number in `workspace/report.md` lands in one
  of three classes, never added together: *no source*, *value found,
  unit or meaning unclear* (for a human to check) and *source found*
  (a machine-produced source in this run holds this value in this unit);
  plus *excluded* (dates, times, numbering, versions, file names, ids,
  code blocks, numbers quoted from the prompt). The output lists the no
  source numbers first, then the unclear ones, then the source found
  ones with the named source (a path or an event sequence number). JSON
  keys: `no_source`, `value_found_unclear`, `source_found`, `excluded`,
  and a `limits` string. What the check establishes, word for word:

  > A "no source" number means nothing the tools measured in this run has this value: treat it as unsupported until shown otherwise. "Source found" means a machine-produced source in this run holds this value in this unit. It does not establish which design or stage the sentence gives the value to, which of several quantities sharing that unit it means, nor relations between numbers, nor negations, nor the direction of a margin. The check reads only the run folder.

  Sources are `metric` events, the stored weight count of each model
  file, and the numeric fields of files the chip lab wrote. The value
  must round to the digits shown. When both the number and the source
  carry a unit, they must agree after both are converted to the base
  unit (20 ms is not 20 ns; a rate in words is in hertz, so 1 per minute
  is not 1 Hz; minutes, hours and days, and the noun seconds after a
  number, are time units with their scale, so 1.35 seconds is not
  1.35 ns); when only one carries a unit, the unit is unclear.
  Spelled-out units (microwatts, nanoseconds, picojoules), both micro
  signs, and "k" or "thousand" after a number are read as scales. A
  negative source (a timing slack) matches only a negative number or a
  sentence of shortfall ("misses by", "short by", "negative slack",
  "late"); a sentence of a margin met ("to spare", "positive slack")
  does not match, and one with neither is unclear. A width in bits about
  weights matches only a weight width, not a port width. The unit or
  noun next to the number must match the source through a small synonym
  table (gates/cells, ns/slack/period, uW/power, um2/area, levels/depth,
  parameters/params, ...), or, with no such noun, the number's words
  must share a whole non-generic word with the source key's last
  segment. A percent matches only a percentage or a 0-to-1 ratio. A noun
  that agrees with no source leaves the number with no source.
  Structural fields (line counts, sizes, tool durations, seeds, indices)
  count only when the claim names them. Metric events can also come from
  the agent's own `./progress metric` calls, and lab answers echo the
  agent's inputs.
- **Weight bytes per decision.** For one chip, named in the output with
  the reason it was picked (the one the report names most; otherwise the
  first laid-out design with weights): the bytes of weights software must
  read for one decision, by one rule for every design (each stored array
  in the smallest machine integer type, float32 for decimals; and,
  separately, packed at the fewest bits), the stored value count and the
  declared parameter count where they differ, and the memory cells and
  flip-flops in the chip's netlist (`net.json`, else `gates.v`). No memory
  cells means 0 weight bytes fetched: the weights are constants in the
  logic. A memory is reported with its bits, never 0. It claims nothing
  about energy or speed.
- **Stage timings.** Wall time per stage from the `stage` events, each
  stage's share, counts of what it processed, and for the largest stage
  both bounds: if every other stage cost nothing, the run is at most
  1/share faster; if this stage cost nothing, at most 1/(1-share) faster.
  No per-second rates: stage time includes the agent's thinking. It also
  reports per-tool-call wall times and the longest call, for one run on
  one machine.

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
    cli.py                   chipin-backend run / ask / serve / config / evidence / summarise / skill
    evidence.py              run evidence: number check, weights, timings
    export.py                a recorded run as one scrubbed static file
    chiplab.py               the optional chip lab: agent PATH, settings, skill
    skills/chiplab/          the chip-lab agent skill (SKILL.md, references/)
    training.py              the optional training Python for the agent
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
  The grant is renewed at every start, and the start answers the folder
  trust prompt if it shows anyway (another CLI on the same login can
  rewrite that file in between). A start that fails is tried again, three
  tries in all.
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

| Name                  | Needed for                          |
| --------------------- | ----------------------------------- |
| `OPENROUTER_API_KEY`  | `ask`, summaries, `openrouter`      |
| `RUNPOD_API_KEY`      | `on_demand` mode and RunPod checks  |
| `CLAUDE_CONFIG_DIR`   | optional: another CLI login folder  |
| `CHIPIN_CONFIG`       | optional: another config file       |
| `HF_TOKEN`            | optional: passed to agents          |
| `CHIPIN_CHIPLAB_BIN`  | optional: the chip lab, see above   |
| `CHIPLAB_CONFIG`      | optional: the lab's config file     |
| `CHIPLAB_USER_DIR`    | optional: the lab's tool folder     |
| `CHIPIN_TRAIN_PYTHON` | optional: training Python, above    |

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
