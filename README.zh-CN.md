# HandBrake Finder Automation

[English](README.md) · [下载最新版](https://github.com/Francis-Lee-210/handbrake-automation/releases/latest) · [配置说明](docs/configuration.md) · [常见问题](docs/troubleshooting.md)

在 macOS Finder 中右键选择文件夹，调用 HandBrakeCLI 批量压缩视频，并在 Terminal 中查看进度。

- 支持当前文件夹和递归处理，按自然名称顺序运行，例如 `1、2、10`。
- 保留原视频，提供批次进度和失败重试。
- 不覆盖已有输出，只有完成记录与文件身份匹配时才跳过。
- 提供 Finder 和命令行入口，运行不依赖 Python。

**脚本会把源视频移动到各文件夹内的 `原始视频/`，将结果写入 `压缩视频/`。** 不会删除源视频。初次使用请用少量视频的副本验证。编码可能改变画质、分辨率、帧率、音轨和字幕，输出不保证比原文件小。

## 安装

需要 macOS 自带的 zsh、Terminal、Automator，以及单独安装的 HandBrakeCLI。CI 覆盖 macOS 15 的 Apple Silicon 和 Intel；其他 macOS 版本未持续测试，不支持 Windows/Linux。

已经安装 [Homebrew](https://brew.sh/) 时：

```sh
brew install handbrake
brew install ffmpeg  # 可选，提供 ffprobe，用于时长估算和输出视频流检查
```

只安装 HandBrake 图形应用并不会同时提供 CLI。脚本会检查 PATH，以及 Apple Silicon 和 Intel 常用的 Homebrew 路径。

从 [Releases](https://github.com/Francis-Lee-210/handbrake-automation/releases/latest) 下载 `handbrake-automation-<版本>.zip` 与 `SHA256SUMS`，在下载目录执行 `shasum -a 256 -c SHA256SUMS`，解压后进入该目录：

```sh
bin/video-compress --doctor
scripts/install
```

也可以从源码安装：

```sh
git clone https://github.com/Francis-Lee-210/handbrake-automation.git
cd handbrake-automation
bin/video-compress --doctor
scripts/install
```

安装到当前用户的 `~/Library/Services`，无需 `sudo`。`scripts/install --dry-run` 可先预览。升级前会备份同名且属于本项目的工作流，不修改 shell 或 Terminal 默认设置。安装后的工作流自带脚本，移动或删除下载目录不影响它。

## 使用

在 Finder 中选中一个或多个**文件夹**，右键 → **快速操作**（或“服务”）：

| 入口 | 处理范围 |
| --- | --- |
| 压缩视频-当前文件夹 | 所选文件夹最外层的视频 |
| 压缩视频-所有视频 | 所选文件夹及子文件夹中的视频 |

Terminal 会显示进度，结束后保留窗口供查看。重试请从 Finder 重新发起，旧临时任务只允许运行一次。

命令行也可以直接运行：

```sh
bin/video-compress --flat "/path/to/folder"
SHOW_PROGRESS=1 bin/video-compress --recursive "/path/to/folder"
bin/video-compress --help
```

公共默认预设为 **`Fast 1080p30`**：H.264/AAC、MP4、最高 1080p 和 30fps。它与旧版本使用的“原帧率硬件加速”个人预设不同；若需要高帧率或硬件编码，应选择合适的自定义预设。[HandBrake 官方预设说明](https://handbrake.fr/docs/en/latest/technical/official-presets.html)

## 保留个人配置

```sh
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/handbrake-automation"
cp -n config.example "${XDG_CONFIG_HOME:-$HOME/.config}/handbrake-automation/config"
```

编辑生成的 `config`，然后运行 `bin/video-compress --doctor`。优先级为：**非空环境变量 > 配置文件 > 默认值**。配置采用普通 `KEY=VALUE`，不会执行 shell 命令。

如需沿用自己在 HandBrake 图形应用里保存的旧预设，将以下两行写入配置文件，名称替换为自己的预设：

```text
HANDBRAKE_PRESET=1080 原帧率 硬件加速
HANDBRAKE_IMPORT_GUI=1
```

完整参数、Finder 配置位置及目录命名见[配置说明](docs/configuration.md)。改变预设名称会重新编码，已有输出仍被保留；仅修改同名 GUI 预设的内容不会自动使旧完成记录失效。

## 更新、卸载与恢复

下载新版后重新运行 `scripts/install`，个人配置不会被覆盖。旧工作流保存在 `~/Library/Services/.handbrake-automation-backups/`。

`scripts/uninstall` 将本项目安装的两个工作流移入备份目录，保留视频、日志、配置和其他快速操作。恢复步骤见[常见问题](docs/troubleshooting.md#rollback)。

支持可信的本地卷，以及关闭所有权的个人 APFS/HFS+ 外置卷。网络卷、exFAT/FAT 不受支持。完整的输出规则、权限边界、中断恢复和进度说明见[使用细节](docs/usage.md)。

## 开发与许可

规范源码在 `bin/`；通过 `scripts/sync-workflows` 同步到两个 workflow，不单独编辑副本。[贡献与发布](CONTRIBUTING.md) · [变更记录](CHANGELOG.md) · [安全报告](SECURITY.md)

项目参考 HandBrake、Homebrew、mas 和 yt-dlp 的安装、配置、文档及发行做法，具体来源和取舍见[开源设计依据](docs/open-source-design.md)。

本项目采用 [MIT 许可证](LICENSE)，是独立的第三方自动化工具。HandBrake 和 FFmpeg 由用户另行安装，分别保留其自身许可证。
