# Configuration / 配置

[English quick start](../README.md) · [中文快速开始](../README.zh-CN.md)

## Location and precedence

The optional file is `${XDG_CONFIG_HOME:-$HOME/.config}/handbrake-automation/config`. For Finder, use `~/.config/handbrake-automation/config` unless XDG_CONFIG_HOME is actually present in Finder's environment; setting it only in `.zshrc` does not affect Finder. The installer never creates or replaces your configuration.

Non-empty environment variables override the file, and the file overrides built-in defaults. Set `VIDEO_COMPRESS_CONFIG=/absolute/path/to/config` to read another file, or `VIDEO_COMPRESS_CONFIG=none` to ignore configuration files. An explicitly selected missing file is an error; a missing default file is normal.

配置文件是普通数据，不会被 `source` 或 `eval` 执行。每行使用 `KEY=VALUE`；允许空行、以 `#` 开头的注释和成对的外层单/双引号。空值采用默认值。空白会从行首尾和键值两侧去掉；不支持行尾注释、`export`、变量替换、`~` 展开或命令替换。重复键、未知键、无效布尔值会报错，避免静默使用错误配置。

Values are literal text. Surrounding quotes are optional and removed; escapes, variables and commands are never evaluated. Use full paths for executables. Unknown or duplicate keys are errors. Keep comments on their own lines.

## Supported settings

| Key | Default | Purpose |
| --- | --- | --- |
| `HANDBRAKECLI` | Auto-discover | Executable path or command name; searches PATH, then `/opt/homebrew/bin`, then `/usr/local/bin` when unset |
| `FFPROBE` | Auto-discover | Optional executable; if the explicit value is unavailable, duration estimates use file counts and video-stream validation is skipped |
| `HANDBRAKE_PRESET` | `Fast 1080p30` | Exact, case-sensitive HandBrake preset name |
| `HANDBRAKE_IMPORT_GUI` | `0` | `1` imports presets saved by the HandBrake GUI; `0` uses built-in presets only |
| `ORIGINAL_DIR_NAME` | `原始视频` | Directory for moved originals |
| `COMPRESSED_DIR_NAME` | `压缩视频` | Directory for outputs, logs and state |
| `LOG_FILE_NAME` | `video-compress.log` | Encoding log filename |
| `SHOW_PROGRESS` | `0` | `1` shows progress; the Finder launcher always sets `1` |
| `DISABLE_NOTIFICATIONS` | `0` | `1` disables macOS completion/error notifications |

Boolean settings accept only `0` or `1`. Directory/log names must be single path components, without `/`, control characters, `.` or `..`. Original and compressed directories must differ. The log cannot be named `.video-compress-state`.

Output is always MP4, even when a selected GUI preset specifies a different container. A custom preset's video/audio codecs must support MP4. A failed encode keeps the source for retry.

```sh
HANDBRAKE_PRESET="HQ 1080p30 Surround" SHOW_PROGRESS=1 bin/video-compress --flat "/path/to/folder"
VIDEO_COMPRESS_CONFIG=none bin/video-compress --doctor
```

`bin/launch-in-terminal` carries supported environment overrides into the new Terminal task. Finder users should normally edit the configuration file, which is read by the installed worker when it starts.

## Existing users

Earlier versions expected a personal GUI preset named `1080 原帧率 硬件加速`. New installations default to the built-in `Fast 1080p30`; its up-to-30fps software encoding is a different choice. To keep a GUI preset you already use:

```text
HANDBRAKE_PRESET=1080 原帧率 硬件加速
HANDBRAKE_IMPORT_GUI=1
```

Run `bin/video-compress --doctor` before upgrading. It checks dependencies, configuration and preset availability without moving or encoding videos. Merely downloading new source code does not update an already installed Quick Action; `scripts/install` is the update step.

已有用户如果希望继续使用旧硬件加速预设，应先保存上述配置并通过诊断，再安装新版。原有 receipt v1 完成记录仍可读取；预设名称改变时会重新编码并为输出另选空闲名称，不覆盖旧输出。

Completion records identify the preset by **name**, not the contents of a GUI preset or the HandBrake version. Editing a preset under the same name, changing GUI-import mode, or updating HandBrake does not invalidate prior results. Use a new preset name when intentionally requesting a fresh encode. Keep directory names stable for an existing library: renaming the managed folders can cause old folders to be treated as new input in recursive mode.
