#!/usr/bin/env bash
# Fresh GPU box to results in one command: setup, vLLM server in tmux, then the pipeline.
# Run inside tmux so it survives SSH drops (it logs itself to logs/bootstrap.log):
#   tmux new -d -s bootstrap 'bash infra/bootstrap.sh train validation'
# Env knobs: MODEL (HF id, Qwen/Qwen3-8B), MODEL_CFG (configs/models/<name>, qwen3-8b-vllm),
# READY_TIMEOUT_MIN (30). Arguments are the splits for run_splits.sh; PROFILE, CONCURRENCY,
# SAMPLES_* and CONDITIONS pass through to it (see run_splits.sh).
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

MODEL="${MODEL:-Qwen/Qwen3-8B}"
MODEL_CFG="${MODEL_CFG:-qwen3-8b-vllm}"
READY_TIMEOUT_MIN="${READY_TIMEOUT_MIN:-30}"
LOG_TAG="${MODEL_CFG%-vllm}"

die() { echo "!! $*" >&2; exit 1; }
stamp() { echo ">> $(date -u +%H:%M:%S) $*"; }

cd "$(dirname "$0")/.."
mkdir -p logs
exec > >(tee -a logs/bootstrap.log) 2>&1

stamp "setup ($MODEL)"
MODEL="$MODEL" bash infra/setup_pod.sh 2>&1 | tee "logs/setup-$LOG_TAG.log"

if curl -sf localhost:8000/v1/models >/dev/null; then
  stamp "a vLLM server is already up; reusing it"
else
  tmux has-session -t vllm 2>/dev/null && die "tmux session 'vllm' exists but the server is down; check it"
  stamp "starting vLLM in tmux session 'vllm'"
  tmux new -d -s vllm "MODEL=$MODEL bash infra/serve_vllm.sh 2>&1 | tee logs/vllm-$LOG_TAG.log"
fi

stamp "waiting for vLLM (up to $READY_TIMEOUT_MIN min)"
for _ in $(seq $((READY_TIMEOUT_MIN * 4))); do
  curl -sf localhost:8000/v1/models >/dev/null && break
  tmux has-session -t vllm 2>/dev/null || die "vLLM exited; see logs/vllm-$LOG_TAG.log"
  sleep 15
done
curl -sf localhost:8000/v1/models >/dev/null || die "vLLM not ready after $READY_TIMEOUT_MIN min; see logs/vllm-$LOG_TAG.log"

stamp "pipeline: ${*:-train}"
MODEL_CFG="$MODEL_CFG" bash infra/run_splits.sh "${@:-train}" 2>&1 | tee logs/pipeline.log
