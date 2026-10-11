#!/usr/bin/env bash
# Serve MODEL with an OpenAI-compatible API for `cot-secret-file run --backend vllm`. Run in tmux.
#   MODEL=Qwen/Qwen3-8B bash infra/serve_vllm.sh
# Env knobs: MODEL, PORT (8000), MAX_MODEL_LEN, TP (tensor parallel, 1), EXTRA (extra vllm flags).
set -euo pipefail
# uv lives in ~/.local/bin (setup_pod.sh); non-interactive shells (tmux via ssh) skip ~/.bashrc.
export PATH="$HOME/.local/bin:$PATH"

MODEL="${MODEL:-Qwen/Qwen3-8B}"
PORT="${PORT:-8000}"
TP="${TP:-1}"

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

# Sampling is sent explicitly in every request (configs/models/*.yaml), so saved request bodies
# record it; the server's generation_config defaults only matter for fields we leave out.
exec uv run --project envs/vllm vllm serve "$MODEL" \
  --port "$PORT" --tensor-parallel-size "$TP" --max-model-len "$MAX_MODEL_LEN" \
  --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser "$TOOL_PARSER" \
  "${MODEL_FLAGS[@]}" ${EXTRA:-}
