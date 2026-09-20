# Changelog

## 0.2.0 — 2026-09-21

First packaged open-source release.

- Add user-level installation, upgrade backups, recoverable uninstallation, and a ZIP with SHA-256 checksums.
- Remove user-specific Finder paths; installed workflows are self-contained.
- Discover HandBrakeCLI and ffprobe on Apple Silicon and Intel, including Finder's minimal PATH.
- Add literal configuration files, explicit GUI preset import, and `--doctor`.
- Use the built-in `Fast 1080p30` preset by default. Existing users can keep their GUI preset through configuration; see [migration instructions](docs/configuration.md#existing-users).
- Add English and Chinese quick starts, usage and recovery guides, contribution guidance and the MIT license.
- Add installation/configuration coverage, CI on both Mac architectures, and a tag-triggered release workflow.

The file-moving, no-overwrite publishing, completion-record, volume-policy and direct Terminal launch behavior from the earlier local version is retained.
