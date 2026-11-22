# ChipIn

ChipIn is an AI-scientist environment that designs the small, single-purpose
chip at the core of a medical sensing device. A person describes the device.
An agent works through a chip lab of command-line tools: it proposes designs,
trains them, compiles them to logic gates, checks the gates against the model,
and reports which chip to build and where it fails. It is for people who build
sensing devices and want to see what a dedicated chip could do for them.

Site: <https://chipin.space>

## What is in the repo

| Folder      | What it holds                                |
| ----------- | -------------------------------------------- |
| `backend/`  | runs the agents, records runs, serves the UI |
| `chiplab/`  | the chip lab: model in, verified chip out    |
| `m3/`       | lab speed, install, proof and layout checks  |
| `context/`  | the team's working notes                     |
| `.github/`  | lab tests and the Tiny Tapeout build         |

The site lives on the `gh-pages` branch and is served from there.

## See it without installing anything

- Landing page: <https://chipin.space>
- Dashboard: <https://chipin.space/dashboard/variants/i1.html>
- How it works: <https://chipin.space/how-it-works/>

In the dashboard, **Past runs** plays back recorded real runs from their own
events. Nothing is run again and no model is called. All five recorded runs
used synthetic data (`dashboard/data/runs/` on `gh-pages`).

The dashboard also has three example cases, labelled on the page as follows:

| Case                       | Label on the site         |
| -------------------------- | ------------------------- |
| AF patch                   | Measured feasibility run  |
| Neonatal EEG brain monitor | Measured on open data     |
| Incubator Watch            | Simulated run, demo data  |

## Run it yourself

Prerequisites: a Mac or a Linux machine, `git`, `uv` and Python 3.12. Docker
is needed only for the lab's layout, timing and power steps and the local
Tiny Tapeout build.

Get the code, and a checkout of the site for the server to serve:

```bash
git clone https://github.com/AMGrobelnik/sota-hack
git clone --branch gh-pages https://github.com/AMGrobelnik/sota-hack PATH_TO_SITE_CHECKOUT
```

Install the chip lab. From `chiplab/`:

```bash
scripts/install.sh                 # flags: --skip-docker, --skip-pdk, --skip-tt, --pdks "sky130", --mcp
.venv/bin/chiplab doctor           # JSON; every required check green = ready, otherwise it prints the fix
```

`install.sh` is safe to re-run and already adds the development extras. Run
the lab's tests with `uv run pytest`. The lab's default install needs no
settings in the backend: the lab is on whenever `chiplab` is on the agent's
`PATH`. The tool reference is [chiplab/AGENT.md](chiplab/AGENT.md): on branch
`ant/chip-lab` it lists 44 tools, 36 core and 8 optional extras for data and
training.

Install the backend. From `backend/`:

```bash
uv sync --extra dev
source .venv/bin/activate
cp .env.example .env                # then fill in the values you need
python -m chipin_backend run --backend stub --prompt "hello"     # no model
pytest && ruff check . && ruff format --check .
```

A first run with no key: start the server with the stub agent, a scripted
agent that calls no model.

```bash
python -m chipin_backend serve --agent stub --site PATH_TO_SITE_CHECKOUT
```

It prints one link, `http://127.0.0.1:8797/#token=<token>`. Open the
dashboard on that address with the same token:
`http://127.0.0.1:8797/dashboard/variants/i1.html#token=<token>`. The
sidebar reads "Connected to local backend". Type a brief, press Chip in,
walk the five steps, pick Lite and press Run.

A real run uses the default agent, a command-line coding agent on this
machine's own login: install it and log in once, as `backend/README.md`
describes under "Run it". Then:

```bash
.venv/bin/chipin-backend serve --site PATH_TO_SITE_CHECKOUT --env-file PATH_TO_KEYS_FILE
```

Keys are read by name from the environment, `backend/.env` or `--env-file`.

| Name                 | Needed for                          |
| -------------------- | ----------------------------------- |
| `OPENROUTER_API_KEY` | summaries, the other agent, helper  |
| `CHIPIN_CHIPLAB_BIN` | optional: a lab installed elsewhere |
| `CHIPLAB_CONFIG`     | optional: the lab's config file     |
| `CHIPLAB_USER_DIR`   | optional: the lab's tool folder     |

## How a run works

A run has seven stages, each reported as started, done or skipped.

1. **spec**: the brief becomes targets, constraints and the data to use.
2. **reference**: baseline models to compare against.
3. **propose**: candidate design families for the chip.
4. **fine-tune**: training settings; the agent trains the models itself
   if the server has a Python that can train, otherwise it is skipped.
5. **compile**: the lab turns each model into logic gates.
6. **verify**: the lab checks the gates against the model.
7. **report**: the chosen chip, its numbers and where it fails.

With fan-out on, the agent is an orchestrator. It does spec and report
itself. Each of the other five stages is one batch of subagents, one per
strategy, all started at once. It waits for all of them, merges the best
results on the lab's numbers, and moves on. The preset sets the batch size:
3 for Lite, 10 for Pro (`backend/README.md`, "Fan-out").

The dashboard shows a run live or played back. The overview has the stages,
designs on a size chart, pass or fail against the targets, the funnel, cost
and time. "Where it fails" and "Chip" are views of their own. The log holds
every message and tool call, with short summaries at each level that open
down to the full text. The files view lists the run's files and report.
Playback replays recorded runs from their events. A helper answers
questions about the runs and moves the page.

## What is measured so far, and what is not

Every figure below comes from the file named beside it.

| Figure                                     | File (branch)      |
| ------------------------------------------ | ------------------ |
| Lab spike chip: 2,285 gates, depth 51      | A (`ant/chip-lab`) |
| Same chip: 862 iCE40 LUTs                  | A (`ant/chip-lab`) |
| Same chip optimised: 1,405 gates, 1 tile   | A (`ant/chip-lab`) |
| Gate estimator: held-out r² 0.95           | A (`ant/chip-lab`) |
| AF run: 256 trained, 119 under size cap    | B (`gh-pages`)     |
| AF chip: 2,330 gates, depth 52             | B (`gh-pages`)     |
| AF chip: 3,880 of 3,880 windows identical  | B (`gh-pages`)     |
| AF test: sensitivity 83.3%, spec. 87.6%    | B (`gh-pages`)     |
| Second AF chip: 831 GE vs 24,038 published | C (`gh-pages`)     |
| EEG: best 30 of 113 held-out events        | D (`gh-pages`)     |
| Recorded runs: 5, all 7 stages done        | E (`gh-pages`)     |

A is `chiplab/README.md`, section 9. B, C, D and E are, under
`dashboard/data/`: `af-candidates.json`, `af-baseline.json`,
`neonatal-eeg.json` and `runs/index.json`.

Limits the files state:

- The AF chip fails its 90% sensitivity target on held-out test recordings
  (83.3%). It passes the 85% specificity target. The full-precision model
  scores 96.9% and 95.3%: the gap is the model, not the hardware (B).
- The second AF chip, a separate experiment on held-out subjects, is sized
  against a published AF chip that does more and uses a different cell
  library: "not the same function made smaller". At layout it is about
  1,440 gate-equivalents. Accuracy "matches (not a
  win: the intervals are about 8 points wide)". On a second database it is
  below on specificity. A proof for every possible input is not closed (C).
- Neonatal EEG: every design misses every event in at least one held-out
  baby. It is a feasibility result on one hospital's recordings, not
  clinical evidence (D).
- The recorded agent runs use synthetic data (the run files beside E).
- The lab designs the digital core only. It is not medically certified, and
  no manufacturing route in it is (A, section 10).

## Data and credits

Agent runs use synthetic data. The measured example cases use open datasets;
each data file on `gh-pages` (B, C and D above) carries its dataset's name,
licence and credit line.

## Licence and third-party notices

- `backend/`: Apache-2.0, see [backend/LICENSE](backend/LICENSE) and
  [backend/NOTICE](backend/NOTICE).
- `chiplab/`: MIT, see `chiplab/LICENSE` and `chiplab/THIRD_PARTY_NOTICES.md`
  (on branch `ant/chip-lab` until the final merge).

Built at the SoTA Scientific Parallelism Hackathon, London, November 2026.
