# Changelog

All notable changes to the `forja-skills` plugin. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the plugin follows [Semantic Versioning](https://semver.org/).

## [2.1.0] - 2026-11-24

### Added

- `hooks/guard-gh-repo.py`: a Claude Code `PreToolUse` hook, shipped with the plugin, that blocks `gh` writes to any
  repository other than the one of the `origin` remote, such as the parent of a fork.

### Changed

- `create-pull-request`, `create-plan-github` and `implement-plan-phase-github` pass `--repo <origin repo>` to every
  `gh` command instead of letting `gh` resolve it.
- `create-plan-gitlab` and `implement-plan-phase-gitlab` pass `--repo <origin project>` to every `glab` command.

## [2.0.0] - 2026-11-24

### Changed

- Rebrand as Forja: marketplace `forja`, plugin `forja-skills`, OpenSpec schema `forja-spec-plan`.
  Install with `forja-skills@forja` instead of `codely-skills@codely`.
