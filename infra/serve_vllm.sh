#!/usr/bin/env bash
# Serve MODEL with an OpenAI-compatible API for `cot-secret-file run --backend vllm`. Run in tmux.
#   MODEL=Qwen/Qwen3-8B bash infra/serve_vllm.sh
# Env knobs: MODEL, HOST (127.0.0.1), PORT (8000), MAX_MODEL_LEN, TP (tensor parallel, 1),
# GPU_MEM_UTIL (0.95), VLLM_API_KEY (required by the server if set), EXTRA (extra vllm flags).
# Reach it from a laptop through SSH, not an open port: ssh -N -L 8000:localhost:8000 <box>
set -euo pipefail
# uv lives in ~/.local/bin (setup_pod.sh); non-interactive shells (tmux via ssh) skip ~/.bashrc.
export PATH="$HOME/.local/bin:$PATH"

# Use the same weights cache as setup_pod.sh. A tmux session started over ssh does not inherit
# HF_HOME from ~/.bashrc, and vLLM then re-downloads every model into ~/.cache on the small root
# disk (68 GB on one box) — so pick the big disk here too.
if [ -z "${HF_HOME:-}" ]; then
  for d in /workspace /ephemeral; do
    [ -d "$d" ] && [ -w "$d" ] && { export HF_HOME="$d/hf"; break; }
  done
fi

MODEL="${MODEL:-Qwen/Qwen3-8B}"
# Loopback only: vLLM defaults to 0.0.0.0, and an open port on a cloud box gets scanned and used.
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
TP="${TP:-1}"
# A larger KV cache means fewer preemptions at high concurrency (vLLM's 0.92 left ~5 GiB unused
# on an A100 80GB with Qwen3.6-27B).
GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.95}"

# Tool-call formats differ per family: Qwen3 emits JSON inside <tool_call>, Qwen3.5+/3.6 emits
# XML <function=...> blocks (see each model's chat template / model card).
case "$MODEL" in
  Qwen/Qwen3-*)
    TOOL_PARSER=hermes; MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"; MODEL_FLAGS=() ;;
  Qwen/Qwen3.6-*|Qwen/Qwen3.5-*)
    # Multimodal checkpoints: skip the vision tower, it only costs memory here.
    TOOL_PARSER=qwen3_coder; MAX_MODEL_LEN="${MAX_MODEL_LEN:-65536}"; MODEL_FLAGS=(--language-model-only) ;;
  *)
    echo "!! no parser mapping for $MODEL; add one here" >&2; exit 1 ;;
esac

AUTH=()
[ -n "${VLLM_API_KEY:-}" ] && AUTH=(--api-key "$VLLM_API_KEY")

# Sampling is sent explicitly in every request (configs/models/*.yaml), so saved request bodies
# record it; the server's generation_config defaults only matter for fields we leave out.
exec uv run --project envs/vllm vllm serve "$MODEL" \
  --host "$HOST" --port "$PORT" --tensor-parallel-size "$TP" --max-model-len "$MAX_MODEL_LEN" --gpu-memory-utilization "$GPU_MEM_UTIL" \
  --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser "$TOOL_PARSER" \
  "${MODEL_FLAGS[@]}" "${AUTH[@]}" ${EXTRA:-}
