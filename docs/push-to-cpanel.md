# Push to cPanel

Deploy a repo to cPanel/shared hosting over SSH. GitHub Actions builds the app and uploads the result. The server runs no `git pull`, `ssh-agent`, Composer, Node, or builds.

## Install

This is a **reusable workflow**. Add a small caller in your app repo at `.github/workflows/deploy.yml` (see [`examples/push-to-cpanel.yml`](../examples/push-to-cpanel.yml)):

```yaml
name: Deploy

on:
  push:
    branches:
      - staging
      - production
  workflow_dispatch:

jobs:
  deploy:
    uses: itsemon245/gh-workflows/.github/workflows/push-to-cpanel.yml@v0.1.0
    secrets: inherit
```

- The caller owns the triggers. List the branches you deploy under `on.push.branches`.
- `secrets: inherit` is required — it forwards your secrets to the reusable workflow.
- The project is pre-1.0: pin an exact tag (`@v0.1.0`). Minor `0.x` bumps may include breaking changes, so review before upgrading. Avoid `@main` in production — it changes on every push. See [Versioning](#versioning).

### Inputs (optional, via `with:`)

| Input             | Default         | Purpose                                      |
| ----------------- | --------------- | -------------------------------------------- |
| `environment`     | the branch name | Override the GitHub Environment to deploy in |
| `runs-on`         | `ubuntu-latest` | Runner label                                 |
| `timeout-minutes` | `30`            | Job timeout                                  |

All other config lives in `DOT_ENV`, not inputs.

## Environments

The job runs in the GitHub Environment named after the pushed branch (`environment: ${{ inputs.environment || github.ref_name }}`), so one workflow serves every stage. Recommended: one branch per stage with a matching Environment.

| Branch       | Environment  | Deploys to     |
| ------------ | ------------ | -------------- |
| `staging`    | `staging`    | staging cPanel |
| `production` | `production` | prod cPanel    |

Per stage (`Settings -> Environments -> New environment`, named like the branch):

1. Add `DOT_ENV` (and optional `CPANEL_EXCLUDES`, `CPANEL_REMOTE_POST_DEPLOY`) as Environment **Variables or Secrets**.
2. Add `CPANEL_SSH_KEY` or `CPANEL_PASSWORD` as an Environment **Secret**.
3. Set `DEPLOY_BRANCH` in `DOT_ENV` to the branch name.

Notes:

- `vars.*`/`secrets.*` resolve Environment-first, then fall back to repo/org. For non-sensitive config a **Variable wins over a Secret of the same name** (`vars.X || secrets.X`) — set each in one place.
- A push to a branch with no `DOT_ENV` is skipped, not failed.
- Add **deployment branch policies** per Environment so only the intended branch can use it. Required reviewers / wait timers also apply once set.

## Values

### `DOT_ENV` (required, Variable or Secret)

Single-line `KEY=value` config. Supports blank lines, comments, `export KEY=value`, and simple quotes. One value per line.

```env
# Required
CPANEL_HOST=example.com
CPANEL_USERNAME=cpanel_user
CPANEL_TARGET_DIR=/home/cpanel_user/public_html

# Branch this environment deploys (must match the pushed branch;
# defaults to the repo default branch when omitted)
DEPLOY_BRANCH=production

# Defaults (override only if needed)
CPANEL_PORT=22
CPANEL_PHP_BIN=php
CPANEL_DEPLOY_METHOD=auto
PHP_VERSION=8.2
NODE_VERSION=22
RSYNC_DELETE=true
RUN_LARAVEL_MIGRATIONS=true
RUN_LARAVEL_OPTIMIZE=true
RUN_LARAVEL_STORAGE_LINK=true
```

`DEPLOY_BRANCH` is a safety gate: if the pushed branch doesn't match it, the deploy is skipped.

Optional command overrides (single-line):

```env
COMPOSER_INSTALL_COMMAND=composer install --no-dev --prefer-dist --no-interaction --optimize-autoloader
NODE_INSTALL_COMMAND=npm ci --legacy-peer-deps
NODE_BUILD_COMMAND=npm run build
```

### Credentials (required, Secret — choose one)

Provide exactly one. If both are set, `CPANEL_PASSWORD` wins.

- **`CPANEL_SSH_KEY`** — private SSH key; its public key must be authorized for the cPanel user.
- **`CPANEL_PASSWORD`** — password auth via `sshpass`. Less secure (exposed to the runner) and many hosts disable password SSH; requires an Ubuntu runner. Prefer the key.

### `CPANEL_EXCLUDES` (optional, Variable or Secret)

Extra newline-separated upload exclude patterns, for server-only files that must never be deleted or overwritten:

```txt
public/uploads/
backups/
```

### `CPANEL_REMOTE_POST_DEPLOY` (optional, Variable or Secret)

Extra multiline commands run on cPanel (from `CPANEL_TARGET_DIR`) after upload and the default Laravel commands:

```sh
php artisan queue:restart
```

## What it does

- Checks out the repo, runs Composer if `composer.json` exists, runs Node install + build if `package.json` exists.
- Uploads via `rsync`, or an archive (`tar`) fallback when remote `rsync` is missing.
- Runs Laravel post-deploy commands when `artisan` exists on the server: create writable directories, run migrations, clear optimized caches, refresh the storage link, then warm optimized caches.
- Serializes deploys per environment via `concurrency` plus a remote lock.

The full built tree is uploaded each deploy, so the artifact is always complete and never trusts server state.

**Caching:** `vendor/` is cached by `composer.lock` (+ PHP version) and `node_modules/` by the lockfile (+ Node version). When the lockfile is unchanged the install is skipped and the cached deps are reused; the frontend build still runs every time. Change the lockfile to force a fresh install.

**Package manager:** the Node step auto-detects `pnpm-lock.yaml`, `yarn.lock`, or `package-lock.json`. To use pnpm (fastest with caching), commit a `pnpm-lock.yaml` — it's picked up automatically.

Always excluded from upload: `.git/`, `.github/`, `.env`, `.env.*`, `node_modules/`, `storage/`, `public/storage`, `bootstrap/cache/`.

## `RSYNC_DELETE`

Default `true`: remote files not present locally are deleted unless excluded — add persistent server paths to `CPANEL_EXCLUDES`. Only applies to `rsync`; the archive fallback overwrites but never deletes. For existing sites, start with `RSYNC_DELETE=false`, verify excludes, then switch back to `true`.

## Troubleshooting

**`rsync: command not found`** — the server lacks `rsync`. With `CPANEL_DEPLOY_METHOD=auto` (default) it falls back to archive upload (`tar` required). For exact delete behavior, ask the host to enable `rsync` and set `CPANEL_DEPLOY_METHOD=rsync`.

**`SSH authentication succeeded, but the server did not execute remote commands`** — the host accepted authentication but shell access is disabled or a forced SSH command blocked execution. This workflow needs a working non-interactive shell to create the target directory, extract archive uploads, and run post-deploy commands. Ask the host to enable shell access for the cPanel account, or use an FTP/cPanel-API deployment method instead.

**`protocol version mismatch -- is your shell clean?`** — `rsync` needs the remote SSH shell to print nothing on connect. Output from `ssh-agent`, banners, etc. in `~/.bashrc`, `~/.bash_profile`, `~/.profile`, or `~/.ssh/rc` breaks it (`auto` falls back to archive). Guard startup files to interactive shells only:

```sh
case $- in
  *i*) ;;
  *) return ;;
esac
```

Test it: `ssh -T cpanel_user@example.com 'printf "__clean__\n"'` must output exactly `__clean__`.

## Server requirements

SSH access, `rsync` or `tar`, a writable `CPANEL_TARGET_DIR`, and PHP if Laravel post-deploy commands run. No Git/Composer/Node needed on the server.

## First deploy checklist

- Add the caller workflow and keep `secrets: inherit`.
- Create an Environment named after the deploy branch; list that branch in the caller's `on.push.branches`.
- Add `DOT_ENV` and one of `CPANEL_SSH_KEY` / `CPANEL_PASSWORD` to the Environment.
- Set `DEPLOY_BRANCH` in `DOT_ENV` to the branch name.
- Put the production `.env` on cPanel; confirm SSH auth and `rsync`/`tar` work.
- Add persistent upload dirs to `CPANEL_EXCLUDES`; use `RSYNC_DELETE=false` for the first run if the target already has files.

## Versioning

Released with SemVer tags. The project is **pre-1.0** (`0.x`), so:

- Every release is an immutable, exact tag — e.g. `v0.1.0`.
- Pin an exact tag (`@v0.1.0`). There is **no sliding tag** yet, because in `0.x` a minor bump (`0.1.0` → `0.2.0`) may include breaking changes.
- A change is **breaking** if it: renames/removes an input, requires a new secret or `DOT_ENV` key, changes a default that alters deploy behavior, or moves/renames the workflow file. In `0.x` these go in a **minor** bump; backward-compatible fixes go in a **patch**.

Cut a release with the helper, which generates `CHANGELOG.md`, commits it, creates an annotated tag, and pushes the current branch plus the tag:

```sh
./release --patch
# Preview without changing files:
./release --dry-run --patch
```

Once the API stabilizes at `v1.0.0`, this switches to the usual SemVer + sliding major tag (pin `@v1` for automatic backward-compatible updates), and breaking changes move to a new major (`v2`).
