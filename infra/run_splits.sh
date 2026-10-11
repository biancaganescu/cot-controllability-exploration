#!/usr/bin/env bash
# Run the secret_file pipeline for each split in order: manipulation check, trials, summaries.
# Stops at the first failure (a wrongly-routed or unexpected response stops `run` by design).
#   MODEL_CFG=qwen3-8b-vllm bash infra/run_splits.sh train validation
# Env knobs: MODEL_CFG (configs/models/<name>.yaml), OUT (outputs/<model>), CONCURRENCY (32),
# SAMPLES_TRAIN (1) / SAMPLES_VALIDATION (3) / SAMPLES_TEST (3), CONDITIONS (comma list, default all),
# ALLOW_TEST=1 to run the frozen test split (only after review and `git tag experiment-v1`).
set -euo pipefail
# uv lives in ~/.local/bin (setup_pod.sh); non-interactive shells (tmux via ssh) skip ~/.bashrc.
export PATH="$HOME/.local/bin:$PATH"

MODEL_CFG="${MODEL_CFG:-qwen3-8b-vllm}"
OUT="${OUT:-outputs/${MODEL_CFG%-vllm}}"
CONCURRENCY="${CONCURRENCY:-32}"
BASE_URL="${VLLM_BASE_URL:-http://localhost:8000/v1/}"

die() { echo "!! $*" >&2; exit 1; }
stamp() { echo ">> $(date -u +%H:%M:%S) $*"; }

[ "$#" -gt 0 ] || die "usage: bash infra/run_splits.sh train [validation] [test]"
curl -sf "${BASE_URL%/}/models" >/dev/null || die "no vLLM server at $BASE_URL (start infra/serve_vllm.sh first)"
mkdir -p logs "$OUT"

for split in "$@"; do
  case "$split" in
    train) samples="${SAMPLES_TRAIN:-1}" ;;
    validation) samples="${SAMPLES_VALIDATION:-3}" ;;
    test)
      [ "${ALLOW_TEST:-0}" = 1 ] || die "test is frozen until review; rerun with ALLOW_TEST=1 after tagging"
      samples="${SAMPLES_TEST:-3}" ;;
    *) die "unknown split: $split" ;;
  esac
  tag="$MODEL_CFG-$split"
  start=$(date +%s)

  stamp "$split: manipulation check"
  uv run cot-secret-file check --model "$MODEL_CFG" --split "$split" --concurrency "$CONCURRENCY" ${CONDITIONS:+--conditions "$CONDITIONS"} \
    --out "$OUT/$split-check" 2>&1 | tee "logs/$tag-check.log"
  uv run cot-secret-file score-check "$OUT/$split-check" > "logs/$tag-check-summary.json"

  stamp "$split: trials ($samples sample(s) per case and condition)"
  uv run cot-secret-file run --model "$MODEL_CFG" --split "$split" --samples "$samples" ${CONDITIONS:+--conditions "$CONDITIONS"} \
    --concurrency "$CONCURRENCY" --out "$OUT/$split" 2>&1 | tee "logs/$tag-run.log"
  uv run cot-secret-file score "$OUT/$split" > "logs/$tag-score.json"
  uv run cot-unpack "$OUT/$split" > /dev/null

  stamp "$split: done in $(( ($(date +%s) - start) / 60 )) min; summaries in logs/$tag-*.json"
done
stamp "all done: $*"
