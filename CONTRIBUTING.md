# Contributing

Bug reports, documentation fixes and focused pull requests are welcome in English or Chinese. Explain the behavior being changed and how it was verified. Discuss large new features in an issue before implementing them.

## Development

Use a Mac with zsh and Python 3.9+ for tests. Runtime code is zsh and macOS system tools; Python is only a development dependency. `bin/` contains the canonical scripts. Never edit their copies in `workflows/` independently.

```sh
scripts/sync-workflows
scripts/check
scripts/package-release
```

`scripts/check` runs syntax/plist checks, bundle consistency and the regression suite. Tests use temporary folders and HandBrakeCLI/ffprobe replacements; they must not process a contributor's real videos or install over their real Services. Volume-policy tests require working macOS DiskManagement services; a sandbox blocking `diskutil` can cause expected-safe rejection instead of a successful fixture encode.

Keep source-preservation, no-overwrite output publishing, safe argument quoting and recoverable installation behavior intact. Add focused tests for changes to these boundaries. Preserve executable modes on entry points. Document user-visible changes in both quick starts where relevant and in CHANGELOG.

CI uses macOS 15 on Apple Silicon and Intel. A passing mock suite proves those tested paths, not real Finder permissions, hardware encoding quality or every filesystem. For changes affecting the launch/encode path, also validate a tiny synthetic video and a freshly launched Finder action on a target Mac; record what was actually tested.

## Releases

1. Update `VERSION`, both workflow `CFBundleShortVersionString` values, and `CHANGELOG.md`.
2. Run the checks above, inspect the ZIP and verify it excludes local backups, logs and credentials. Confirm installation/upgrade/uninstall in a temporary `--services-dir`.
3. Merge the reviewed change after CI passes. Tag that commit `v<version>` and push the tag.
4. The Release workflow checks the tag/version match, runs verification, packages the explicit file allowlist, and publishes a release with the ZIP and `SHA256SUMS`. Inspect the completed Actions run and downloaded assets before announcing it.

The release job alone has repository content-write permission. Actions are pinned to commit SHAs and Dependabot checks them monthly. Releases include only project files, never HandBrake/FFmpeg binaries.

## Local materials

`reviews/`, `.local/`, `dist/`, personal configuration and logs are ignored. Keep machine-specific notes and backups there rather than in public documentation. Do not put personal paths or original videos in issues, fixtures or release assets. Updates to the source repository do not update installed Finder workflows until `scripts/install` runs.
