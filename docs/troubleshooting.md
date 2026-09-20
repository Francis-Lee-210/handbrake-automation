# Troubleshooting / 常见问题

## Start with diagnosis

From a downloaded or cloned project, run `bin/video-compress --doctor`. It reads configuration and lists HandBrake presets without moving or encoding any video. It does not prove that a target folder has compatible permissions or that a real encode will succeed.

If HandBrakeCLI is missing, install the CLI (`brew install handbrake`) or set an executable path in the [configuration](configuration.md). Installing only the GUI is insufficient. If a preset is missing, check `HandBrakeCLI --preset-list`; GUI presets also require `HANDBRAKE_IMPORT_GUI=1` and a preset saved in the GUI.

## Quick Action is missing

Select a **folder**, then look under Finder's Quick Actions or Services submenu. Run `scripts/install --dry-run` to check the destination. If macOS provides an Extensions / Finder / Services settings panel, enable the two workflow entries there; the exact settings location varies by macOS version. Close and reopen the Finder window after installation.

The installed bundles should be in `~/Library/Services`. Renaming them manually can break their embedded entry paths; reinstall using the script instead. `--services-dir` is intended for isolated testing or managed installation, and a custom directory does not register a Finder service by itself.

## macOS access or downloaded-file prompts

The script is not signed or notarized. Downloaded workflows or scripts may trigger macOS security prompts. Verify the release source and checksum, and follow macOS's normal approval UI for the item you chose to open. This project does not disable Gatekeeper or remove quarantine recursively.

If macOS requests access to a selected folder or removable drive, grant only the access needed for that location. Do not use `sudo` to work around an error. A Finder permission failure and a filesystem-policy rejection are different; read the actual message before changing anything.

## Directory is rejected

The script refuses unsupported volumes, links, permissive ACLs or shared writable paths. See [filesystem boundaries](usage.md#filesystem-boundaries). Use a personal directory on APFS/HFS+ rather than weakening the script's checks or changing permissions broadly. Compatibility mode for ownership-disabled external drives is automatic and does not alter disk settings.

## Encoding failed, stalled or already started

Inspect `压缩视频/video-compress.log` (or your configured directory/log name). The Terminal window also prints a temporary transcript path and exit code. A source moved into `原始视频/` is retained on failure; the next task retries it.

If an old window says the task has already started, return to Finder and launch a new task. For a stale lock, follow the [interruption procedure](usage.md#interruptions-and-stale-locks). Do not delete all state or any originals to make an error disappear.

## Rollback

Installation upgrades and uninstallation keep old bundles in `~/Library/Services/.handbrake-automation-backups/` (or the equivalent under a custom services directory). The command prints the exact backup path.

To restore a previous version, stop related compression jobs, run `scripts/uninstall` to move the current matching bundles into a fresh backup, then copy the two `.workflow` bundles from the desired older backup back to the **same Services directory they originally came from**. Their entry paths point there. Keep their names unchanged. Configuration is separate; restore your preferred settings explicitly if you changed them.

回滚不会自动还原配置文件。旧版本可能仍依赖原有 GUI 预设；确认该预设仍存在。升级前备份和卸载备份都保留在本地，脚本不会自动清理它们。

## Report a problem

Use a [bug report](https://github.com/Francis-Lee-210/handbrake-automation/issues/new?template=bug_report.yml). Include the project version (`cat VERSION`), macOS version/CPU, HandBrakeCLI version, installation method, relevant configuration keys, expected/actual behavior and a short redacted log excerpt. Remove personal paths and filenames; do not upload private videos. For security-sensitive reports, see [SECURITY](../SECURITY.md).
