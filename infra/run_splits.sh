#!/usr/bin/env bash
# Run the secret_file pipeline for each split in order: manipulation check, trials, summaries.
# Stops at the first failure (a wrongly-routed or unexpected response stops `run` by design).
#   PROFILE=small MODEL_CFG=qwen3.6-27b-vllm bash infra/run_splits.sh train      # quick look
#   PROFILE=large MODEL_CFG=qwen3.6-27b-vllm bash infra/run_splits.sh train validation
# Profiles: small = 8 cases per split, 1 sample (every paraphrase pair once per region; for
# checking trajectories before spending hours); large = all cases, 3 / 10 / 3 samples for
# train / validation / test. Output goes to outputs/<model>/<profile>/<split>.
# Env knobs: PROFILE (small), MODEL_CFG (configs/models/<name>.yaml), OUT, CONCURRENCY (128:
# vLLM batches as many as fit in the KV cache and queues the rest, keeping the GPU busy),
# LIMIT / SAMPLES_TRAIN / SAMPLES_VALIDATION / SAMPLES_TEST to override the profile,
# CONDITIONS (comma list, default all), ALLOW_TEST=1 to run the frozen test split.
set -euo pipefail
# uv lives in ~/.local/bin (setup_pod.sh); non-interactive shells (tmux via ssh) skip ~/.bashrc.
export PATH="$HOME/.local/bin:$PATH"

PROFILE="${PROFILE:-small}"
MODEL_CFG="${MODEL_CFG:-qwen3-8b-vllm}"
OUT="${OUT:-outputs/${MODEL_CFG%-vllm}/$PROFILE}"
CONCURRENCY="${CONCURRENCY:-128}"
BASE_URL="${VLLM_BASE_URL:-http://localhost:8000/v1/}"

die() { echo "!! $*" >&2; exit 1; }
stamp() { echo ">> $(date -u +%H:%M:%S) $*"; }

case "$PROFILE" in
  small) LIMIT="${LIMIT:-8}"; defaults=(1 1 1) ;;
  large) LIMIT="${LIMIT:-}"; defaults=(3 10 3) ;;
  *) die "unknown PROFILE: $PROFILE (small or large)" ;;
esac

[ "$#" -gt 0 ] || die "usage: PROFILE=small|large bash infra/run_splits.sh train [validation] [test]"
curl -sf "${BASE_URL%/}/models" >/dev/null || die "no vLLM server at $BASE_URL (start infra/serve_vllm.sh first)"
mkdir -p logs "$OUT"

for split in "$@"; do
  case "$split" in
    train) samples="${SAMPLES_TRAIN:-${defaults[0]}}" ;;
    validation) samples="${SAMPLES_VALIDATION:-${defaults[1]}}" ;;
    test)
      [ "${ALLOW_TEST:-0}" = 1 ] || die "test is frozen until review; rerun with ALLOW_TEST=1 after tagging"
      samples="${SAMPLES_TEST:-${defaults[2]}}" ;;
    *) die "unknown split: $split" ;;
  esac
  tag="$MODEL_CFG-$PROFILE-$split"
  start=$(date +%s)
  common=(--model "$MODEL_CFG" --split "$split" --concurrency "$CONCURRENCY"
          ${LIMIT:+--limit "$LIMIT"} ${CONDITIONS:+--conditions "$CONDITIONS"})

  # The manipulation check runs alongside the trials, so the long tail of one fills the GPU
  # while the other is still busy; its log goes to a file instead of the terminal.
  stamp "$split ($PROFILE): manipulation check (background) + trials, ${LIMIT:-all} cases x $samples sample(s)"
  ( uv run cot-secret-file check "${common[@]}" --out "$OUT/$split-check" > "logs/$tag-check.log" 2>&1 \
      && uv run cot-secret-file score-check "$OUT/$split-check" > "logs/$tag-check-summary.json" ) &
  check_pid=$!
  uv run cot-secret-file run "${common[@]}" --samples "$samples" --out "$OUT/$split" 2>&1 | tee "logs/$tag-run.log"
  uv run cot-secret-file score "$OUT/$split" > "logs/$tag-score.json"
  uv run cot-unpack "$OUT/$split" > /dev/null
  wait "$check_pid" || die "$split manipulation check failed; see logs/$tag-check.log"

  stamp "$split ($PROFILE): done in $(( ($(date +%s) - start) / 60 )) min; summaries in logs/$tag-*.json"
done
stamp "all done ($PROFILE): $*"
