#!/usr/bin/env bash
# Bootstrap a fresh GPU box (Sesterce / Runpod / Vast). Idempotent; re-run after restarts.
#   git clone <repo> && cd <repo> && MODEL=Qwen/Qwen3-8B bash infra/setup_pod.sh
# Env knobs: PERSIST (cache root; auto-detected), MODEL (weights to prefetch).
# Adapted from interptemp/infra/setup_pod.sh; the main env here is stdlib-only, so only the
# vLLM env needs CUDA.
set -euo pipefail

MIN_DRIVER_CUDA="12.8"   # vLLM's +cu129 build runs on any 12.x driver >= 12.8, see envs/vllm

die() { echo "!! $*" >&2; exit 1; }

# Big disk for caches: a mounted volume if present, else the provider's scratch disk, else $HOME.
pick_persist() {
  for d in /workspace /ephemeral; do
    [ -d "$d" ] && [ -w "$d" ] && { echo "$d"; return; }
  done
  echo "$HOME"
}
PERSIST="${PERSIST:-$(pick_persist)}"
export HF_HOME="${HF_HOME:-$PERSIST/hf}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PERSIST/uv-cache}"
MODEL="${MODEL:-Qwen/Qwen3-8B}"
mkdir -p "$HF_HOME" "$UV_CACHE_DIR"
echo ">> caches under $PERSIST ($(df -h "$PERSIST" | awk 'NR==2 {print $4}') free)"

# Fail early on an old driver: CUDA wheels newer than the driver import fine but die on first use.
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
driver_cuda=$(nvidia-smi | grep -oP 'CUDA Version: \K[0-9.]+')
[ "$(printf '%s\n' "$MIN_DRIVER_CUDA" "$driver_cuda" | sort -V | head -1)" = "$MIN_DRIVER_CUDA" ] \
  || die "driver supports CUDA $driver_cuda < $MIN_DRIVER_CUDA: pick an image with a newer driver"

if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# Persist env vars for new shells; the marked block is rewritten so PERSIST changes stick.
sed -i '/# >>> setup_pod >>>/,/# <<< setup_pod <<</d' ~/.bashrc 2>/dev/null || true
cat >> ~/.bashrc <<RC
# >>> setup_pod >>>
export HF_HOME=$HF_HOME
export UV_CACHE_DIR=$UV_CACHE_DIR
export PATH="\$HOME/.local/bin:\$PATH"
# <<< setup_pod <<<
RC

# tmux: mouse-wheel scrolling and a long history for reading logs; same marked-block rewrite.
touch ~/.tmux.conf
sed -i '/# >>> setup_pod >>>/,/# <<< setup_pod <<</d' ~/.tmux.conf
cat >> ~/.tmux.conf <<'TMUX'
# >>> setup_pod >>>
set -g mouse on              # wheel scrolls history; hold Shift to select text for the system clipboard
set -g history-limit 100000  # default is 2000 lines
# <<< setup_pod <<<
TMUX
tmux source-file ~/.tmux.conf 2>/dev/null || true  # apply to a running tmux server, if any

uv sync --locked
[ -f .env ] || { cp .env.example .env; echo ">> fill in .env (HF_TOKEN; OPENROUTER_API_KEY only for Kimi runs)"; }
set -a; source .env; set +a

uv sync --project envs/vllm --locked
# Run a real kernel: torch.cuda.is_available() can be True while kernels still fail.
echo ">> CUDA check (vLLM env)"
uv run --project envs/vllm python - <<'PY' || die "CUDA kernels fail in the vLLM env (driver vs torch CUDA mismatch?)"
import torch
x = torch.ones(2, device="cuda")
assert (x * 2).sum().item() == 4.0
print(f"   torch {torch.__version__} (CUDA {torch.version.cuda}) on {torch.cuda.get_device_name(0)}: ok")
PY

uv run --project envs/vllm hf download "$MODEL" --exclude "*.pth" --exclude "original/*" >/dev/null
echo ">> $MODEL cached in $HF_HOME"

command -v tmux >/dev/null || echo ">> tmux missing: install it, long runs must survive SSH drops"
echo ">> next: MODEL=$MODEL bash infra/serve_vllm.sh   (in tmux; 'source ~/.bashrc' first)"
