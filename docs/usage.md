# Behavior and recovery / 使用细节

## Selection and ordering

Pass folders, not individual files. `--flat` scans only the top level; `--recursive` includes subfolders. Supported filename extensions are `mp4`, `m4v`, `mov`, `mkv`, `avi`, `wmv`, `webm`, `flv`, `ts`, `mts` and `m2ts`. Actual decoding support depends on HandBrake.

Folders and videos are sorted case-insensitively in natural order (`1`, `2`, `10`). Overlapping selections are deduplicated. Recursive traversal does not follow descendant directory symlinks and skips the configured originals/compressed directories. Each selected processing folder also checks its existing originals directory to allow retries.

## Files and completion records

| Location in each processing folder | Purpose |
| --- | --- |
| `原始视频/` | Source videos moved here before encoding; never deleted by the script |
| `压缩视频/` | Final MP4 files and `video-compress.log` |
| `压缩视频/.video-compress-state/` | Completion receipts, `job.*` staging directories and a `lock/` directory |

Encoding writes into a private staging directory. A successful exit and a nonempty, safe regular output file are required. When ffprobe is executable, it must also confirm a video stream. This is not a full decode or perceptual quality check. The source file's identity is checked again before publishing.

Publishing never overwrites an existing output. A receipt v1 then records the preset name, output filename, and source/output device, inode, size, mtime and ctime. A rerun skips an output only if these values still match. These are identity checks, not cryptographic content checks; the SHA-256 in a receipt's filename maps the source filename, not its video contents.

Unknown/legacy outputs, even nonempty ones, are preserved and are not marked complete automatically. The next encode uses a free numbered name such as `clip [2].mp4`. Different source extensions sharing a stem get separate output names. Publication and receipt writing are not one atomic transaction: a crash between them can leave an output without a receipt. A retry preserves it and chooses another name.

## Progress and logs

Finder enables progress. On a TTY, a single line shows file number, file percentage, weighted batch progress, approximate ETA and a sanitized filename. Non-TTY output uses ordinary lines without cursor controls. Full HandBrake output stays in each compressed folder's log.

Batch progress uses video durations when ffprobe is available. Missing durations use the known average; if all durations are missing, it uses equal file weights. ETA extrapolates elapsed time and progress without smoothing, appearing only after 10 seconds and 3% progress. Different encode speeds can make it jump.

## Terminal startup

The launcher creates a private `/tmp/handbrake-progress.XXXXXX/` task with mode 0700 and a `.terminal` document. Terminal runs `/bin/zsh -f` directly, avoiding interactive `.zshrc` prompts that can consume command text. This does not change shell configuration or the default Terminal profile.

The window stays open on success and failure. Its transcript path and exit status are displayed; `transcript.log` may include progress control characters. Temporary transcripts can disappear when macOS cleans `/tmp`. The compressed folder's log is the persistent encoding log.

Terminal may retain an imported task profile. Do not make it your default. A task's `started/` guard prevents replay from an old window/profile. Start each new attempt from Finder, not an old temporary file.

## Filesystem boundaries

On volumes with POSIX ownership enabled, directories and ancestors must be owned by root or the effective user, and must not be group/other writable. Trusted sticky ancestors allow the immediate child only when owned by root or the current user; a target directory itself is not exempt merely because it is sticky.

Writable external APFS/HFS+ volumes mounted under `/Volumes/` with ownership disabled use personal-drive compatibility mode. The script queries `diskutil info -plist` without changing volume settings. The relaxed UID/mode checks apply only inside the verified external mount; outside ancestors are checked strictly. This mode is for personal, trusted directories and does not isolate users on a shared drive. Network volumes, unidentified volumes and exFAT/FAT are unsupported.

All modes reject static symlinks in managed paths, multi-link regular files and ACL `allow` entries (including read-only ACL grants). Recognizable `deny` entries are allowed; unrecognized ACL output fails closed. Strict mode additionally requires files to belong to the effective user and not be group/other writable. Publishing requires hard links.

The checks address static unsafe paths and, in strict mode, other-user boundaries. They do not defend against malicious same-UID/root processes, previously granted file handles, or concurrent ACL/policy changes. Compatibility mode also does not protect against other users/processes replacing paths during a run. Do not use it in shared or untrusted writable directories.

## Interruptions and stale locks

Normal exits and catchable interrupts attempt to remove this task's staging directories and locks. A crash or force quit can leave `lock/` or `job.*`. Locks are not stolen automatically based on age or PID.

If a folder is locked, first confirm in Activity Monitor that no relevant compression task or HandBrake process is running. Inspect that folder's log and state directory, then remove only the confirmed stale `lock/` directory. Preserve receipts, original videos and unknown outputs. Remove a `job.*` directory only after confirming it belongs to an abandoned task. Retry from Finder.

中文提示：不能为了“解锁”删除整个 `.video-compress-state/`、`原始视频/` 或未知输出；这样会丢失完成记录或视频。先确认无任务运行，再处理确认失效的锁。更多故障处理见 [troubleshooting](troubleshooting.md)。
