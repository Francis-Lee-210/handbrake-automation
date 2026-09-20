# HandBrake Finder Automation

[![Checks](https://github.com/Francis-Lee-210/handbrake-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/Francis-Lee-210/handbrake-automation/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[简体中文](README.zh-CN.md) · [Download](https://github.com/Francis-Lee-210/handbrake-automation/releases/latest) · [Configuration](docs/configuration.md) · [Troubleshooting](docs/troubleshooting.md)

Batch-compress videos from the macOS Finder context menu, powered by HandBrakeCLI. Select folders, choose a Quick Action, and follow progress in Terminal.

- Process one folder or include all its subfolders, in natural filename order (`1`, `2`, `10`).
- Keep originals, show batch progress, and retry interrupted jobs.
- Preserve existing outputs and skip completed files only after checking their completion records.
- Run from Finder or directly from the command line. No Python dependency at runtime.

**The script moves source videos into `原始视频/` (originals) inside each selected folder.** Outputs go into `压缩视频/` (compressed). It never deletes source videos. Try a folder containing copies first. Encoding can change quality, dimensions, frame rate, audio and subtitles; a smaller file is not guaranteed.

```text
My videos/                 My videos/
├── clip.mov       →       ├── 原始视频/clip.mov
└── another.mp4            ├── 原始视频/another.mp4
                          └── 压缩视频/
                              ├── clip.mp4
                              ├── another.mp4
                              └── video-compress.log
```

## Requirements

- macOS with `/bin/zsh`, Terminal and Automator. CI targets macOS 15 on Apple Silicon and Intel; other macOS versions are not continuously tested. Windows and Linux are unsupported.
- [HandBrakeCLI](https://handbrake.fr/docs/en/latest/cli/command-line-reference.html). The HandBrake GUI alone does not install the CLI.
- Optional: `ffprobe` from FFmpeg, for duration-based progress and checking that an output contains a video stream.
- A personal, writable local volume. Ownership-disabled external APFS/HFS+ volumes have a compatibility mode. Network volumes and exFAT/FAT are unsupported. See [filesystem and recovery details](docs/usage.md).

With [Homebrew](https://brew.sh/) already installed:

```sh
brew install handbrake
brew install ffmpeg  # optional; provides ffprobe
```

The script discovers executables in `PATH`, `/opt/homebrew/bin` and `/usr/local/bin`. You can also specify their paths in your configuration. HandBrake and FFmpeg are separate dependencies and are not included in this project.

## Install

1. Download `handbrake-automation-<version>.zip` and `SHA256SUMS` from the [latest release](https://github.com/Francis-Lee-210/handbrake-automation/releases/latest). In the download directory, verify with `shasum -a 256 -c SHA256SUMS`, then extract the ZIP.
2. In Terminal, `cd` into the extracted directory and run:

   ```sh
   bin/video-compress --doctor
   scripts/install
   ```

Alternatively, install from source:

```sh
git clone https://github.com/Francis-Lee-210/handbrake-automation.git
cd handbrake-automation
bin/video-compress --doctor
scripts/install
```

Installation uses your `~/Library/Services` directory; it needs no `sudo` and does not edit shell or Terminal defaults. Existing matching workflows are backed up before replacement. `scripts/install --dry-run` previews the destination without installing. Installed workflows contain their own scripts, so you can move or remove the downloaded project folder afterward.

## Use

Select one or more **folders** in Finder, right-click, and open **Quick Actions** (or **Services**):

| Menu item | Meaning |
| --- | --- |
| `压缩视频-当前文件夹` | Compress videos directly inside the selected folders |
| `压缩视频-所有视频` | Also process videos in subfolders |

Menu names, runtime progress and notifications are currently in Chinese. Folder names can be [configured](docs/configuration.md). Terminal opens with progress and stays open at the end. Launch a new task from Finder for each retry; old task windows cannot replay a job. See [troubleshooting](docs/troubleshooting.md) if the menu is missing or macOS asks for access.

From the project directory:

```sh
bin/video-compress --flat "/path/to/folder"
SHOW_PROGRESS=1 bin/video-compress --recursive "/path/to/folder"
bin/video-compress --help
```

The default preset is **`Fast 1080p30`**: H.264/AAC in MP4, up to 1080p and 30 fps. It does not preserve higher source frame rates or enable hardware encoding. Choose a suitable custom preset if those properties matter; see [HandBrake's preset descriptions](https://handbrake.fr/docs/en/latest/technical/official-presets.html).

## Configure and update

Configuration is optional. To create it without overwriting an existing file:

```sh
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/handbrake-automation"
cp -n config.example "${XDG_CONFIG_HOME:-$HOME/.config}/handbrake-automation/config"
```

Edit that file, then run `bin/video-compress --doctor`. Precedence is **non-empty environment variable → configuration file → built-in default**. Configuration is literal `KEY=VALUE` data, not a shell script. See the [complete reference](docs/configuration.md), including how to retain an older GUI preset.

To update, download a new release and rerun `scripts/install`. The installer preserves your configuration. Old workflows are kept under `~/Library/Services/.handbrake-automation-backups/`; see [rollback](docs/troubleshooting.md#rollback).

To uninstall, run `scripts/uninstall`. It moves this project's installed workflows into the backup directory. Videos, logs, configuration and unrelated Quick Actions remain available.

## Development and project references

`bin/` is the source of truth. `scripts/sync-workflows` copies it into both workflow bundles. See [CONTRIBUTING](CONTRIBUTING.md) for checks and releases, [CHANGELOG](CHANGELOG.md) for changes, and [SECURITY](SECURITY.md) for reporting security issues.

The repository design draws on [HandBrake](https://github.com/HandBrake/HandBrake), [Homebrew](https://github.com/Homebrew/brew), [mas](https://github.com/mas-cli/mas) and [yt-dlp](https://github.com/yt-dlp/yt-dlp). The [design notes](docs/open-source-design.md) explain which practices were adopted and why.

Licensed under [MIT](LICENSE). This is an independent automation project, not an official HandBrake product. HandBrake and FFmpeg retain their own licenses.
