#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$ROOT/.github/workflows/push-to-cpanel.yml"
HARNESS_DIR="$(mktemp -d)"
HARNESS_BIN="$HARNESS_DIR/bin"

cleanup() {
  rm -rf "$HARNESS_DIR"
}
trap cleanup EXIT

mkdir -p "$HARNESS_BIN"

cat > "$HARNESS_BIN/sshpass" <<'SCRIPT'
#!/bin/sh
if [ "$1" = "-e" ]; then
  shift
fi
exec "$@"
SCRIPT

cat > "$HARNESS_BIN/ssh" <<'SCRIPT'
#!/bin/sh
printf '%s\n' 'Shell access is not enabled on your account!'
printf '%s\n' 'If you need shell access please contact support.'
SCRIPT

cat > "$HARNESS_BIN/scp" <<'SCRIPT'
#!/bin/sh
exit 0
SCRIPT

cat > "$HARNESS_BIN/tar" <<'SCRIPT'
#!/bin/sh
exit 0
SCRIPT

chmod 700 "$HARNESS_BIN/sshpass" "$HARNESS_BIN/ssh" "$HARNESS_BIN/scp" "$HARNESS_BIN/tar"

deploy_script="$(awk '
  /^      - name: Deploy to cPanel$/ { in_step = 1; next }
  in_step && /^      - name: / { exit }
  in_step && /^        run: \|$/ { in_run = 1; next }
  in_run {
    sub(/^          /, "")
    print
  }
' "$WORKFLOW")"

if [ -z "$deploy_script" ]; then
  echo "Could not extract the cPanel deployment script." >&2
  exit 1
fi

output_file="$HARNESS_DIR/output"
if env \
  PATH="$HARNESS_BIN:$PATH" \
  CPANEL_PASSWORD_SECRET=test-password \
  CPANEL_USERNAME=test-user \
  CPANEL_HOST=example.test \
  CPANEL_PORT=1157 \
  CPANEL_TARGET_DIR=/home/test-user/public_html \
  CPANEL_DEPLOY_METHOD=auto \
  RSYNC_DELETE=false \
  RUNNER_TEMP="$HARNESS_DIR" \
  RUN_LARAVEL_MIGRATIONS=false \
  RUN_LARAVEL_OPTIMIZE=false \
  RUN_LARAVEL_STORAGE_LINK=false \
  CPANEL_PHP_BIN=php \
  GITHUB_RUN_ID=123 \
  GITHUB_RUN_ATTEMPT=1 \
  bash -c "$deploy_script" > "$output_file" 2>&1; then
  cat "$output_file" >&2
  echo "Expected deployment to fail when the server rejects shell commands." >&2
  exit 1
fi

grep -Fq 'SSH authentication succeeded, but the server did not execute remote commands.' "$output_file"
grep -Fq 'Shell access is not enabled on your account!' "$output_file"

echo "PASS: deployment rejects an SSH transport that cannot execute remote commands."
