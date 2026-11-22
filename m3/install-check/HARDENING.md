# Hardening notes for the lab's owner

Neutral list of points found by reading the code on `origin/ant/chip-lab` (021f68d) during the P1 install check.
Each was confirmed against the code, with file and line. None was exercised against a machine: they are
read-and-confirm only. Paths are relative to the repository root.

| # | Point | Where | Suggested one-line fix | Patch |
| --- | --- | --- | --- | --- |
| 1 | Default install folder is new, in the home directory | see 1 | Default to a folder inside the repo checkout | none |
| 2 | OSS CAD Suite fetched as "latest", no checksum, quarantine flag removed | see 2 | Pin the tag, verify a sha256 | 04 |
| 3 | `uv sync` without `--locked` | see 3 | Use `uv sync --locked` | 04 |
| 4 | Tiny Tapeout repo cloned at HEAD | see 4 | Check out a pinned commit | 04 |
| 5 | HTTP mode: no auth on loopback, DNS-rebinding protection off | see 5 | Turn protection on for loopback | 03 |
| 6 | `torchlogix` ingest unpickles a local file | see 6 | Keep behind `trusted`; add a trust prompt | none |
| 7 | Unvalidated `top` pasted into Yosys scripts | see 7 | Require a plain identifier | 02 |
| 8 | Verilog checker runs on the host without the image | see 8 | Refuse unless opted in | none |
| 9 | `timing-power` reports `status: ok` when layout failed | see 9 | Pass the error through | 01 |

Status on b77cc76 (checked by reading the merged code, and for 8 and 9 by the re-check run in REPORT.md):

| # | Status on b77cc76 | Where |
| --- | --- | --- |
| 1 | Open; f0c296c also writes `~/.local/bin/chiplab` | `scripts/install.sh:14,127,137` |
| 2 | Fixed: pinned tag, sha256 checked first | `scripts/install.sh:19,81,85` |
| 3 | Fixed: `uv sync --locked` | `scripts/install.sh:64` |
| 4 | Fixed: pinned commit checked out | `scripts/install.sh:22,111` |
| 5 | Fixed: protection on, loopback hosts only | `chiplab/mcp_server.py:96-97` |
| 6 | Mitigated: pickle refused remotely by default | `chiplab/tools_hw.py:99-100` |
| 7 | Fixed: `top` must be an identifier | `chiplab/verify/sandbox.py:74` |
| 8 | Fixed: host run refused unless `allow_host` | `chiplab/verify/sandbox.py:52` |
| 9 | Fixed: error passed through | `chiplab/tools_hw.py:386` |

Line numbers in the sections below are from 021f68d.

Patches are in `proposed/` (apply from the repo root with `git apply`); `git apply --check` passed on all four.

## 1. Install folder is a new folder in the home directory

- `chiplab/scripts/install.sh:14`: `PREFIX="${CHIPLAB_USER_DIR:-$HOME/.chiplab}"`.
- `chiplab/scripts/install.sh:102`: the config goes to `${CHIPLAB_CONFIG:-$HOME/.config/chiplab/config.json}`.
- `chiplab/chiplab/config.py:14-15` repeat both defaults for the Python side.
- Variables that redirect it: `CHIPLAB_USER_DIR`, `CHIPLAB_CONFIG`; per tool `CHIPLAB_OSS`, `PDK_ROOT`,
  `CHIPLAB_TT_TOOLS` (`install.sh:15-17`; `config.py` reads the same names through `setting()`).
- Measured here: with `CHIPLAB_USER_DIR` and `CHIPLAB_CONFIG` set (and `PDK_ROOT` set to a folder under the
  same root) nothing was written to `~/.chiplab` or `~/.config/chiplab`; both stayed absent after the full install.
- Places that ignore the variables: step 1 runs the uv installer (`install.sh:47`, writes `~/.local/bin`) only
  if uv is missing; Homebrew `libomp` is installed at `install.sh:54` if missing; uv's own package cache lives in
  uv's default cache folder. None of these were triggered here (uv and libomp were already present).
- Suggested fix: default the prefix to a folder inside the checkout (gitignored), or state the home-folder
  default in the README next to the variable names.

## 2. OSS CAD Suite: "latest", no checksum, quarantine cleared

- `chiplab/scripts/install.sh:66`: the tag comes from the GitHub `releases/latest` API; the fallback tag is a
  constant at `install.sh:19`.
- `install.sh:70`: `curl -fL` download, then `tar -xzf` at line 71 with no digest check.
- `install.sh:72`: `xattr -dr com.apple.quarantine` removes the macOS download flag from everything it unpacked.
- Release installed here: 2026-11-21; tarball sha256 `f1afeda6cbbc0df119ee1339a5a42a43c0636688d2978d28a63ad3e805bf9a88`
  (computed locally, not compared against any upstream value).
- Suggested fix: pin the tag, keep the sha256 per platform in the script, and clear quarantine only after the
  check passes. Patch 04 does this for darwin-arm64 and prints a note for platforms without a pinned digest;
  `CHIPLAB_OSS_TAG=latest` keeps the old behaviour on request.

## 3. `uv sync` without `--locked`

- `chiplab/scripts/install.sh:59`: `uv sync $EXTRAS`. A stale `uv.lock` is silently re-resolved instead of
  rejected.
- Measured here: `uv lock --check` on the branch passes (121 packages), so `--locked` would not have failed.
- Suggested fix: `uv sync --locked $EXTRAS` (patch 04).

## 4. Tiny Tapeout repositories cloned at HEAD

- `chiplab/scripts/install.sh:96`: `git clone -q --depth 1 https://github.com/TinyTapeout/tt-support-tools`.
- `install.sh:98`: its `requirements.txt` is installed into `tt-venv` together with `librelane==3.0.14`.
- Commit installed here: `0922544e6c7f6126047c3fba720b0437fa32a1b8`.
- Suggested fix: clone, then `git checkout` a pinned commit (patch 04, using the commit above).

## 5. HTTP server mode (`chiplab serve`)

- `chiplab/chiplab/mcp_server.py:94`: `TransportSecuritySettings(enable_dns_rebinding_protection=False)`.
- `mcp_server.py:125`: the bearer-token check is skipped when the host is `127.0.0.1` or `localhost`, so on
  loopback every tool is callable without credentials, and a web page open in a local browser can reach the
  port through a rebinding DNS name when protection is off.
- `mcp_server.py:112-124`: `/files/` serves only inside `designs/` (path-checked), `/events/` and `/health`
  are open as well.
- Suggested fix: enable rebinding protection with allowed hosts `127.0.0.1:*` and `localhost:*` when bound to
  loopback (patch 03); or require the token on loopback too. Patch 03 was syntax-checked and applies, but it
  was not run against a live server (the server was not started for this package).

## 6. `torchlogix` ingest unpickles a local file

- `chiplab/chiplab/tools_hw.py:98-102`: refuses unless `path` and `trusted=true` are given, then calls
  `torch.load(path, weights_only=False)`: a pickle can run code.
- The `trusted` flag is a parameter of the same tool call, so over HTTP (point 5) any caller sets it.
- `chiplab/chiplab/train/engine.py:122` has the same `weights_only=False` for the lab's own training state.
- Suggested fix: do not accept `trusted` from remote callers (allow it only on the CLI or by environment
  variable), or load with `weights_only=True` plus an allow-list of the torchlogix classes.

## 7. Unvalidated `top` in Yosys scripts

- `chiplab/chiplab/tools_hw.py:291-302`: `submit_verilog(verilog, top, ...)`; `top` is hashed and passed on,
  never checked.
- `chiplab/chiplab/verify/sandbox.py:71` (Verilator `--top-module`) and `:75` (the Yosys script f-string
  `hierarchy -check -top {top}; synth -top {top} ...`) paste it in. A value with `;` or a newline adds Yosys
  commands to the script. `screen()` (`sandbox.py:23-33`) checks the Verilog text only, not `top`.
- Suggested fix: reject `top` unless it matches a plain identifier (patch 02, three lines in `check_verilog`).

## 8. Verilog checker runs on the host when the image is absent

- `chiplab/chiplab/verify/sandbox.py:36-40` (`_docker_ok`) and `:47-56`: without the LibreLane image the
  check runs as a local process under `timeout`, with only the static screen as protection. The module
  docstring and the result's `sandbox` field say so, but nothing asks the caller.
- Observed here: `submit-verilog` (the AGENT.md example) passed in "local process" mode on this Mac, which
  has no Docker engine.
- Suggested fix: refuse unless an environment variable such as `CHIPLAB_ALLOW_HOST_CHECK=1` is set. No patch:
  it changes behaviour for every Docker-less user and the owner should choose the default.

## 9. Extra finding: `timing-power` hides a failed layout

- `chiplab/chiplab/tools_hw.py:379-382`: `timing_power` calls `layout`, then drops the keys `cost`, `cached`
  and `status` from the result; the tool wrapper (`chiplab/chiplab/tools.py:55`) then fills in `status: ok`.
- Observed here (no Docker): `layout` returns `status: error`, but `timing-power` returns `status: ok`
  with an `error` field and exit code 0 (`examples/timing-power.out.txt`).
- Suggested fix: return the layout result as is when its status is `error` (patch 01).
