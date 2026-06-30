# Push to cPanel

Deploy a repo to cPanel/shared hosting over SSH.

The workflow builds on GitHub Actions, then uploads the completed app to cPanel. The shared server does not run `git pull`, `ssh-agent`, Composer installs, Node installs, or frontend builds.

## Install

Copy the workflow into the target repo:

```txt
.github/workflows/push-to-cpanel.yml
```

The workflow is environment-aware: the job runs in the GitHub Environment named after the branch that was pushed (`environment: ${{ github.ref_name }}`). Store the secrets below as **Environment secrets**, not repository secrets, so the same workflow can deploy staging and production from their own branches with their own credentials.

## Environments (staging and production)

The recommended setup is one branch per stage, each matched by an Environment of the same name:

| Branch       | Environment  | Deploys to            |
| ------------ | ------------ | --------------------- |
| `staging`    | `staging`    | the staging cPanel    |
| `production` | `production` | the production cPanel |

For each stage:

1. Create the Environment in GitHub: `Settings -> Environments -> New environment`. Name it exactly like the branch (e.g. `staging`, `production`).
2. Add the secrets below to that Environment (`Settings -> Environments -> <name> -> Environment secrets`). Each environment gets its own `DOT_ENV`, auth secret, etc.
3. In that Environment's `DOT_ENV`, set `DEPLOY_BRANCH` to the same branch name (see below). This is required for any branch other than the repository default branch.

Pushing to `staging` then resolves the `staging` Environment's secrets; pushing to `production` resolves the `production` Environment's secrets. The workflow file is identical for both.

### How environment resolution works

- `environment: ${{ github.ref_name }}` selects the Environment dynamically from the pushed branch name. No per-stage workflow copies are needed.
- `secrets.*` then resolves against that Environment first, then falls back to repository and organization secrets for any name the Environment does not define. So an Environment secret overrides a repository secret of the same name.
- A push to a branch with no configured Environment (no `DOT_ENV`) is skipped, not failed.
- Add **deployment branch policies** on each Environment (`Settings -> Environments -> <name> -> Deployment branches`) so, for example, only the `production` branch can use the `production` Environment. Required reviewers and wait timers also apply once set.

### Repository secrets (optional)

You can keep shared, non-stage-specific values as repository secrets. They act as a fallback for any name an Environment does not define. Prefer Environment secrets for anything that differs between staging and production (host, credentials, target dir).

## Required Secrets

Add each of these to the relevant Environment (`Settings -> Environments -> <name> -> Environment secrets`), or as repository secrets for a single shared stage.

### `DOT_ENV`

Single-line deploy config in `KEY=value` format. Copy this template and replace the required values:

```env
# Required
CPANEL_HOST=example.com
CPANEL_USERNAME=cpanel_user
CPANEL_TARGET_DIR=/home/cpanel_user/public_html

# Defaults
CPANEL_PORT=22
CPANEL_PHP_BIN=php
CPANEL_DEPLOY_METHOD=auto
PHP_VERSION=8.2
NODE_VERSION=22
RSYNC_DELETE=true
RUN_LARAVEL_MIGRATIONS=true
RUN_LARAVEL_OPTIMIZE=true
RUN_LARAVEL_STORAGE_LINK=true

# Branch this environment deploys. Must match the pushed branch.
# Required for any branch other than the repository default branch.
# Example: set DEPLOY_BRANCH=staging in the staging environment.
DEPLOY_BRANCH=production
```

`DEPLOY_BRANCH` is the safety gate that ties an environment to a branch: if the pushed branch does not match `DEPLOY_BRANCH`, the deploy is skipped. In the per-environment setup, set it to the same name as the branch and environment. It defaults to the repository default branch when omitted.

Required keys:

```env
CPANEL_HOST=example.com
CPANEL_USERNAME=cpanel_user
CPANEL_TARGET_DIR=/home/cpanel_user/public_html
```

`DOT_ENV` supports blank lines, comments, `export KEY=value`, and simple quoted values. Keep every value on one line.

### Authentication (choose one)

Provide exactly one of the following. If both are set, `CPANEL_PASSWORD` takes precedence.

#### `CPANEL_SSH_KEY`

Private SSH key used by GitHub Actions to connect to cPanel.

The matching public key must be authorized for the cPanel SSH user.

Keep this separate from `DOT_ENV` because it is multiline.

#### `CPANEL_PASSWORD`

Password for the cPanel SSH user. With this set, the workflow authenticates using the username, host, and password (no private key).

Notes:

- Password auth is less secure than a key. The password is exposed to `sshpass` and the environment on the runner. Prefer `CPANEL_SSH_KEY` when possible.
- Many cPanel hosts disable password SSH. Confirm `PasswordAuthentication yes` is allowed for your account.
- `sshpass` is installed on the runner at deploy time, so password auth requires an Ubuntu runner.

## Optional Secrets

### `CPANEL_EXCLUDES`

Extra newline-separated upload exclude patterns:

```txt
public/uploads/
backups/
private_uploads/
```

Use this for server-only files or directories that must never be deleted or overwritten.

### `CPANEL_REMOTE_POST_DEPLOY`

Extra multiline commands to run on cPanel after upload and default Laravel commands:

```sh
php artisan queue:restart
```

The script runs from `CPANEL_TARGET_DIR`.

Command overrides, if auto-detection is not enough:

```env
COMPOSER_INSTALL_COMMAND=composer install --no-dev --prefer-dist --no-interaction --optimize-autoloader
NODE_INSTALL_COMMAND=npm ci --legacy-peer-deps
NODE_BUILD_COMMAND=npm run build
```

Keep command overrides single-line. Put multiline remote commands in `CPANEL_REMOTE_POST_DEPLOY`.

## What It Does

- Checks out the repo on GitHub Actions.
- Runs Composer when `composer.json` exists.
- Runs Node install/build when `package.json` exists.
- Uploads files with `rsync` when available, or with an archive upload fallback when remote `rsync` is unavailable.
- Runs Laravel post-deploy commands when `artisan` exists on the server.
- Serializes deploys with GitHub Actions `concurrency` and a remote lock.

Composer and Node installs run on every deploy when their project files exist. This is intentional: the workflow always produces a complete deploy artifact instead of trusting the current server state.

## Default Excludes

The workflow always excludes:

```txt
.git/
.github/
.env
.env.*
node_modules/
storage/
public/storage
bootstrap/cache/
```

Important notes:

- `.env` should already exist on cPanel.
- `storage/` is preserved for uploads, logs, sessions, and runtime files.
- `public/storage` is usually a Laravel symlink.
- `bootstrap/cache/` is regenerated on the server.

## `rsync --delete`

`RSYNC_DELETE=true` is the default.

Remote files that are not present locally can be deleted unless they are excluded. Add any persistent server-only paths to `CPANEL_EXCLUDES`.

This only applies when the deploy uses `rsync`. If the cPanel server does not have `rsync`, the workflow falls back to an archive upload and extract. That fallback overwrites uploaded files but does not delete remote files that are no longer present locally.

For existing sites, start with:

```env
RSYNC_DELETE=false
```

After verifying the exclude list, switch back to:

```env
RSYNC_DELETE=true
```

## Troubleshooting

### `jailshell: line 1: rsync: command not found`

The cPanel server does not have `rsync` installed. By default, the workflow uses:

```env
CPANEL_DEPLOY_METHOD=auto
```

With `auto`, it falls back to archive upload when remote `rsync` is missing. The fallback requires `tar` on the cPanel server.

If you need exact delete behavior for files removed from the repo, ask the host to enable `rsync` and keep:

```env
RSYNC_DELETE=true
CPANEL_DEPLOY_METHOD=rsync
```

### `protocol version mismatch -- is your shell clean?`

`rsync` requires the remote SSH command to start without extra stdout. If the cPanel account prints anything before the command runs, rsync sees that text instead of the rsync protocol and fails. With `CPANEL_DEPLOY_METHOD=auto`, the workflow falls back to archive upload when it detects this.

Common unwanted output looks like this:

```txt
Agent pid 847221
Identity added: /home/user/.ssh/id_ed25519 (server)
```

That output usually comes from `ssh-agent`, `ssh-add`, `echo`, `printf`, banners, or similar commands in the cPanel user's startup files:

```txt
~/.bashrc
~/.bash_profile
~/.profile
~/.ssh/rc
```

Remove those commands, or guard them so they only run for an interactive shell. For Bash startup files, put this before any command that prints output:

```sh
case $- in
  *i*) ;;
  *) return ;;
esac
```

You can test the server from your machine:

```sh
ssh -T cpanel_user@example.com 'printf "__clean__\n"'
```

The output must be exactly:

```txt
__clean__
```

## Server Requirements

- SSH access.
- `rsync` or `tar` on the cPanel server.
- Writable `CPANEL_TARGET_DIR`.
- PHP on the server if Laravel post-deploy commands are enabled.

The server does not need GitHub access, Git, Composer, Node, npm, pnpm, or yarn for the default workflow.

## First Deploy Checklist

- Create an Environment named after the deploy branch (e.g. `production`, `staging`).
- Add `DOT_ENV` and one of `CPANEL_SSH_KEY` or `CPANEL_PASSWORD` to that Environment.
- Set `DEPLOY_BRANCH` in that Environment's `DOT_ENV` to the same branch name (unless it is the repository default branch).
- Optionally add a deployment branch policy so only that branch can use the Environment.
- Put the production `.env` file on cPanel.
- Confirm the SSH key or password works for the cPanel user.
- Confirm `rsync` or `tar` exists on the cPanel server.
- Add persistent upload directories to `CPANEL_EXCLUDES`.
- Use `RSYNC_DELETE=false` for the first run if the target directory already has important files.

## Why This Is Safer For Shared Hosting

The workflow does not start `ssh-agent` or run `git pull` on cPanel. GitHub Actions builds the app and uploads it with a temporary SSH key file, which avoids leaked background processes on shared servers.
