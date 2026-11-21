#!/usr/bin/env bash
# chipin.space chip lab installer for macOS (Apple Silicon or Intel) and Linux (x86_64 or arm64).
#
#   scripts/install.sh                 # everything: Python env, OSS CAD Suite, PDKs, LibreLane image, Tiny Tapeout tools
#   scripts/install.sh --skip-docker   # (or --no-docker) skip the LibreLane image (no layout, timing/power or TT harden)
#   scripts/install.sh --skip-pdk      # (or --no-pdk) skip the PDK download (no area numbers)
#   scripts/install.sh --pdks sky130   # only some PDKs (sky130 gf180mcu ihp-sg13g2)
#   scripts/install.sh --mcp           # also install the optional MCP server extra
#
# Everything goes under ~/.chiplab (override with CHIPLAB_USER_DIR) and the paths are written to
# ~/.config/chiplab/config.json, which the lab reads. Existing tools are reused: set CHIPLAB_OSS / PDK_ROOT first.
set -euo pipefail

PREFIX="${CHIPLAB_USER_DIR:-$HOME/.chiplab}"
OSS_DIR="${CHIPLAB_OSS:-$PREFIX/oss-cad-suite}"
PDK_ROOT="${PDK_ROOT:-$PREFIX/pdk}"
TT_DIR="${CHIPLAB_TT_TOOLS:-$PREFIX/tt}"
LIBRELANE_IMAGE="${CHIPLAB_LIBRELANE_IMAGE:-ghcr.io/librelane/librelane:3.0.14}"
OSS_FALLBACK_TAG="2026-11-21"
OSS_TAG="${CHIPLAB_OSS_TAG:-$OSS_FALLBACK_TAG}"      # pinned; CHIPLAB_OSS_TAG=latest opts in to the newest release
OSS_SHA256_2026_11_21_darwin_arm64=f1afeda6cbbc0df119ee1339a5a42a43c0636688d2978d28a63ad3e805bf9a88
TT_COMMIT=0922544e6c7f6126047c3fba720b0437fa32a1b8  # tt-support-tools, as installed and tested on 2026-11-21
# PDK versions are pinned to LibreLane 3.0.14's (librelane/pdk_hashes.yaml), see step 4
PDKS="sky130 gf180mcu ihp-sg13g2"; DO_DOCKER=1; DO_PDK=1; DO_TT=1; EXTRAS="--extra dev --extra sim --extra ingest"

while [ $# -gt 0 ]; do
  case "$1" in
    --no-docker|--skip-docker) DO_DOCKER=0 ;;
    --no-pdk|--skip-pdk) DO_PDK=0 ;;
    --no-tt|--skip-tt) DO_TT=0 ;;
    --pdks) PDKS="$2"; shift ;;
    --mcp) EXTRAS="$EXTRAS --extra mcp" ;;
    -h|--help) sed -n 2,13p "$0"; exit 0 ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac; shift
done

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
HERE="$(cd "$(dirname "$0")/.." && pwd)"        # the chiplab project folder
mkdir -p "$PREFIX"

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) PLAT=darwin-arm64 ;; Darwin-x86_64) PLAT=darwin-x64 ;;
  Linux-x86_64) PLAT=linux-x64 ;; Linux-aarch64|Linux-arm64) PLAT=linux-arm64 ;;
  *) echo "unsupported platform $(uname -s)-$(uname -m)"; exit 1 ;;
esac

say "1/6 uv (Python package manager)"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
uv --version

if [ "$(uname -s)" = Darwin ]; then
  # XGBoost (tree models) needs the OpenMP runtime; Tiny Tapeout's PNG export needs cairo
  if command -v brew >/dev/null 2>&1; then
    brew list libomp >/dev/null 2>&1 || brew install libomp
    brew list cairo >/dev/null 2>&1 || brew install cairo
  else echo "note: Homebrew not found; install it, then: brew install libomp cairo"; fi
fi

say "2/6 Python environment ($EXTRAS)"
( cd "$HERE" && uv sync --locked $EXTRAS )
"$HERE/.venv/bin/python" -c "import torch; d='cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu'); print('torch', torch.__version__, 'device', d)"

say "3/6 OSS CAD Suite ($PLAT) -> $OSS_DIR"
if [ -x "$OSS_DIR/bin/yosys" ]; then
  echo "already present: $("$OSS_DIR/bin/yosys" -V)"
else
  TAG="$OSS_TAG"
  if [ "$TAG" = latest ]; then
    TAG=$(curl -fsSL https://api.github.com/repos/YosysHQ/oss-cad-suite-build/releases/latest 2>/dev/null \
          | "$HERE/.venv/bin/python" -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])' 2>/dev/null || echo "$OSS_FALLBACK_TAG")
  fi
  URL="https://github.com/YosysHQ/oss-cad-suite-build/releases/download/$TAG/oss-cad-suite-$PLAT-${TAG//-/}.tgz"
  echo "downloading $URL"
  TMP="$(mktemp -d)"; curl -fL --retry 3 -o "$TMP/oss.tgz" "$URL"
  WANT_VAR="OSS_SHA256_${TAG//-/_}_${PLAT//-/_}"; WANT="${!WANT_VAR:-}"
  if [ -n "$WANT" ]; then
    GOT=$(shasum -a 256 "$TMP/oss.tgz" | cut -d' ' -f1)
    [ "$GOT" = "$WANT" ] || { echo "checksum mismatch for $TAG ($GOT)"; rm -rf "$TMP"; exit 1; }
  else echo "note: no pinned checksum for $TAG on $PLAT; download not verified"; fi
  mkdir -p "$(dirname "$OSS_DIR")"; tar -xzf "$TMP/oss.tgz" -C "$TMP"; rm -rf "$OSS_DIR"; mv "$TMP/oss-cad-suite" "$OSS_DIR"; rm -rf "$TMP"
  if [ "$(uname -s)" = Darwin ]; then xattr -dr com.apple.quarantine "$OSS_DIR" 2>/dev/null || true; fi
  "$OSS_DIR/bin/yosys" -V
fi

say "4/6 PDKs ($PDKS) -> $PDK_ROOT"
if [ "$DO_PDK" = 1 ]; then
  mkdir -p "$PDK_ROOT"
  for fam in $PDKS; do
    case "$fam" in sky130) h=8afc8346a57fe1ab7934ba5a6056ea8b43078e71 ;; gf180mcu) h=54435919abffb937387ec956209f9cf5fd2dfbee ;;
                   ihp-sg13g2) h=c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c ;; *) echo "unknown PDK $fam"; continue ;; esac
    uvx --from 'ciel>=2.3.1,<3' ciel enable --pdk-root "$PDK_ROOT" --pdk-family "$fam" "$h"
  done
else echo "skipped (--no-pdk)"; fi

say "5/6 Docker + LibreLane image ($LIBRELANE_IMAGE)"
if [ "$DO_DOCKER" = 1 ] && command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker pull "$LIBRELANE_IMAGE"
elif [ "$DO_DOCKER" = 1 ]; then
  echo "Docker not running: install/start Docker Desktop (macOS) or the docker daemon (Linux), then run: docker pull $LIBRELANE_IMAGE"
else echo "skipped (--no-docker)"; fi

say "6/6 Tiny Tapeout tools -> $TT_DIR"
TT_PY=""
if [ "$DO_TT" = 1 ]; then
  if [ ! -d "$TT_DIR/.git" ]; then
    git clone -q https://github.com/TinyTapeout/tt-support-tools "$TT_DIR"
    git -C "$TT_DIR" checkout -q "$TT_COMMIT"
  fi
  [ -d "$PREFIX/tt-venv" ] || uv venv -q -p 3.12 "$PREFIX/tt-venv"
  uv pip install -q -p "$PREFIX/tt-venv/bin/python" -r "$TT_DIR/requirements.txt" "librelane==3.0.14"
  TT_PY="$PREFIX/tt-venv/bin/python"
else echo "skipped (--no-tt)"; fi

# Docker socket for agent environments (they strip DOCKER_HOST): docker context, else known sockets
DOCKER_SOCK="${DOCKER_HOST:-}"
if [ -z "$DOCKER_SOCK" ] && command -v docker >/dev/null 2>&1; then
  DOCKER_SOCK=$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null || true)
fi
for s in "$HOME/.colima/default/docker.sock" "$HOME/.orbstack/run/docker.sock" "$HOME/.docker/run/docker.sock" /var/run/docker.sock; do
  [ -n "$DOCKER_SOCK" ] && break; [ -S "$s" ] && DOCKER_SOCK="unix://$s"
done

CFG="${CHIPLAB_CONFIG:-$HOME/.config/chiplab/config.json}"
mkdir -p "$(dirname "$CFG")"
[ -f "$CFG" ] && cp "$CFG" "$CFG.bak"
cat > "$CFG" <<CFGJSON
{"oss": "$OSS_DIR", "pdk_root": "$PDK_ROOT", "tt_tools": "$TT_DIR", "tt_python": "$TT_PY",
 "data": "$PREFIX/data", "librelane_image": "$LIBRELANE_IMAGE", "home": "$HERE/runs", "docker_host": "$DOCKER_SOCK"}
CFGJSON
echo "wrote $CFG"

# a chiplab launcher on PATH, so agents (whose environment is an allowlist) can call the lab
mkdir -p "$HOME/.local/bin"
printf '#!/bin/sh\nexec "%s/.venv/bin/chiplab" "$@"\n' "$HERE" > "$HOME/.local/bin/chiplab"
chmod +x "$HOME/.local/bin/chiplab"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "note: add ~/.local/bin to PATH so agents find the chiplab launcher";; esac

say "chiplab doctor"
"$HERE/.venv/bin/chiplab" doctor | "$HERE/.venv/bin/python" -c '
import json, sys
r = json.load(sys.stdin)
for c in r["checks"]:
    if not c["ok"]: print(("MISSING " if c["required"] else "optional ") + c["check"] + ": " + c.get("fix", ""))
print("READY" if r["ok"] else "NOT READY: fix the MISSING items above")'
