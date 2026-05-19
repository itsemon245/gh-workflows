# Push to cPanel

Deploy a repo to cPanel/shared hosting over SSH with `rsync`.

The workflow builds on GitHub Actions, then uploads the completed app to cPanel. The shared server does not run `git pull`, `ssh-agent`, Composer installs, Node installs, or frontend builds.

## Install

Copy the workflow into the target repo:

```txt
.github/workflows/push-to-cpanel.yml
```

Then add the secrets below in GitHub: `Settings -> Secrets and variables -> Actions`.

## Required Secrets

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
PHP_VERSION=8.2
NODE_VERSION=22
RSYNC_DELETE=true
RUN_LARAVEL_MIGRATIONS=true
RUN_LARAVEL_OPTIMIZE=true
RUN_LARAVEL_STORAGE_LINK=true

# Optional. If omitted, the repository default branch is used.
# DEPLOY_BRANCH=main
```

Required keys:

```env
CPANEL_HOST=example.com
CPANEL_USERNAME=cpanel_user
CPANEL_TARGET_DIR=/home/cpanel_user/public_html
```

`DOT_ENV` supports blank lines, comments, `export KEY=value`, and simple quoted values. Keep every value on one line.

### `CPANEL_SSH_KEY`

Private SSH key used by GitHub Actions to connect to cPanel.

The matching public key must be authorized for the cPanel SSH user.

Keep this separate from `DOT_ENV` because it is multiline.

## Optional Secrets

### `CPANEL_EXCLUDES`

Extra newline-separated `rsync` exclude patterns:

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
- Uploads files with `rsync`.
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

For existing sites, start with:

```env
RSYNC_DELETE=false
```

After verifying the exclude list, switch back to:

```env
RSYNC_DELETE=true
```

## Server Requirements

- SSH access.
- `rsync` on the cPanel server.
- Writable `CPANEL_TARGET_DIR`.
- PHP on the server if Laravel post-deploy commands are enabled.

The server does not need GitHub access, Git, Composer, Node, npm, pnpm, or yarn for the default workflow.

## First Deploy Checklist

- Add `DOT_ENV` and `CPANEL_SSH_KEY`.
- Put the production `.env` file on cPanel.
- Confirm the SSH key works for the cPanel user.
- Confirm `rsync` exists on the cPanel server.
- Add persistent upload directories to `CPANEL_EXCLUDES`.
- Use `RSYNC_DELETE=false` for the first run if the target directory already has important files.

## Why This Is Safer For Shared Hosting

The workflow does not start `ssh-agent` or run `git pull` on cPanel. GitHub Actions builds the app and uploads it with a temporary SSH key file, which avoids leaked background processes on shared servers.
