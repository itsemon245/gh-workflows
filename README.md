# GitHub Workflows

Reusable GitHub Actions workflows. Each one lives in `.github/workflows/` and is consumed from other repos with `uses:`. Copy the matching caller from `examples/` into your repo as a thin wrapper.

## Workflows

- [Push to cPanel](docs/push-to-cpanel.md) - deploy a repository to cPanel/shared hosting with GitHub-built assets, using `rsync` when available or an archive upload fallback.
  - Reusable: `.github/workflows/push-to-cpanel.yml`
  - Example caller: [`examples/push-to-cpanel.yml`](examples/push-to-cpanel.yml)
