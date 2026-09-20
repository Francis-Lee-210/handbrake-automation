# 开源仓库设计依据

研究日期：2026-09-21。本文记录开源化改造的取舍与第一方参考；具体安装命令和已实现行为以 [README](../README.md) 与源码为准。参考资料的在线内容可能继续更新。

## 项目定位与范围

这是一个调用 HandBrakeCLI 的 macOS Finder / zsh 自动化工具。它的价值是文件整理、批量处理、自然排序、可见进度和失败重试。开源化应首先让新用户能够完成安装、配置、首次压缩和卸载，并保留维护者原有安装与个人配置。

改造前的直接障碍来自本仓库：默认依赖 `/opt/homebrew/bin/HandBrakeCLI` 和一项个人 GUI 预设，README 混有维护者机器的搬迁记录，缺少用户安装入口。已有的规范源码、workflow 副本同步、macOS CI 和回归测试值得保留。当前实现：[编码入口](../bin/video-compress)、[同步脚本](https://github.com/Francis-Lee-210/handbrake-automation/blob/main/scripts/sync-workflows)、[CI](https://github.com/Francis-Lee-210/handbrake-automation/blob/main/.github/workflows/ci.yml)。

以下“采纳”是本项目的设计取舍，不表示参考项目提供了本项目的兼容性保证。

## 参考的四个开源项目

| 参考项目 | 第一方证据 | 本项目采纳的做法 |
| --- | --- | --- |
| [HandBrake](https://github.com/HandBrake/HandBrake) | CLI 提供预设选择、预设列表、GUI 预设导入、JSON 预设导入；官方将 `Fast 1080p30` 列为入门默认预设。[CLI 文档](https://handbrake.fr/docs/en/latest/cli/command-line-reference.html)、[官方预设](https://handbrake.fr/docs/en/latest/technical/official-presets.html) | 公共默认采用随 HandBrake 提供的预设；保留自定义 GUI 预设配置。README 明确 `Fast 1080p30` 的最大分辨率为 1080p、最大帧率为 30 fps，避免将它描述为原帧率硬件加速预设。使用本机 `HandBrakeCLI --help` / `--preset-list` 核实实际支持情况。 |
| [Homebrew](https://github.com/Homebrew/brew) | 默认 macOS 前缀在 Apple Silicon 为 `/opt/homebrew`，Intel 为 `/usr/local`；GUI 应用默认可能找不到 Homebrew 的 PATH。`handbrake` formula 安装 `HandBrakeCLI`。[FAQ](https://docs.brew.sh/FAQ)、[handbrake formula](https://formulae.brew.sh/formula/handbrake) | 文档提供 `brew install handbrake`，自动发现覆盖 PATH 与两个常见前缀，并允许显式指定。Finder 启动路径由脚本自行处理；安装步骤不修改全局 shell 或 launchctl 环境。 |
| [mas](https://github.com/mas-cli/mas) | README 开头列安装渠道与 macOS 要求，随后给命令概览、`--help` 入口与已知问题；仓库提供贡献和安全政策。[项目 README](https://github.com/mas-cli/mas#readme) | 用户入口前置为“是什么 → 依赖 → 安装 → 首次使用”；详细文件系统行为与维护者说明放入独立文档。CLI 的帮助必须可用，并把平台限制写成明确边界。无需照搬其 Swift 构建链或全部分发渠道。 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 文档明确配置文件位置、配置忽略方式；发行资产附 SHA-256 / SHA-512 清单，并区分源码与打包产物的许可证情况。[配置说明](https://github.com/yt-dlp/yt-dlp#configuration)、[发行文件](https://github.com/yt-dlp/yt-dlp#release-files) | 用户配置与仓库源码分离，明确环境变量和配置文件的优先级；更新不覆盖已有配置。给发布包提供 SHA-256 清单，并写清打包内容。仅借鉴这些小型工具也需要的机制，不引入插件体系、夜间版或自动更新器。 |

## 适合本项目的最小仓库方案

以下是基于本仓库规模的建议，属于设计判断。

1. **清楚的用户入口。** 保留简洁的中文 README，同时提供英文快速开始。两种语言至少覆盖系统要求、依赖、安装、配置、文件移动行为、重试、卸载。详细实现与安全边界有明确链接，首页不包含维护者账号、绝对路径或历史任务记录。
2. **可重放的用户级安装。** 一个安装脚本复制自包含的 Finder workflow 到当前用户的 Services 目录。升级前备份旧包；个人配置在版本控制之外，已有配置默认保留。提供卸载命令，仅移除本项目安装的入口，不清理视频和日志。直接从源码运行仍然可用。
3. **可移植配置。** 默认不依赖个人预设名或单一芯片的路径；环境变量显式覆盖个人配置，个人配置覆盖公共默认。配置示例说明哪些设置会影响编码结果，尤其是预设、输出目录和可选 ffprobe。解析配置时应只接受受支持键值，避免把普通配置文件当任意 shell 代码执行。
4. **单一规范源码。** `bin/` 保持为源码来源，workflow 中的副本只由同步脚本生成。CI 检查复制结果、可执行位和 plist；避免发布包与源码各自演进。
5. **小型、可验证发布包。** 发布包包含必要脚本、两个 workflow、用户文档、配置示例、许可证和版本说明；排除本地审查资料、备份、日志、`.git` 和测试替身。每次按固定标签构建，附 SHA-256 清单。校验和用于检查下载内容，不单独宣称发布者身份认证。
6. **有限的维护约定。** 增加贡献说明、简短安全报告政策、问题模板和 PR 模板。问题模板优先收集 macOS / CPU、HandBrake 版本、安装方式、复现步骤和脱敏日志；无需索取原视频或完整个人路径。初期不建立多分支发布体系、自动版本机器人、Homebrew tap 或独立文档网站。

## GitHub 配置与发布

GitHub 官方支持通过基于 Git tag 的 Release 提供发行说明与下载资产；源码 ZIP 是仓库快照，专门的用户安装包仍需项目构建。因此本项目应保留 tag 对应源码，并另附经过验证的安装 ZIP。[GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)

建议保留现有 macOS 检查，在其基础上增加安装到临时目录、保留配置、备份/卸载范围与发布包内容的检查。真实 Finder 启动、权限提示与 HandBrake 编码需在目标 Mac 验收；CI 使用替身通过只说明相应自动化分支通过，不等价于这些真实环境验证。这是本项目的验证范围划分。

Actions 默认只授予 `contents: read`；仅发布 job 获得必要的写权限。第三方 action 使用完整 commit SHA，避免 PR 检查执行带仓库写权限的不可信代码。GitHub 官方建议最小权限并将 action 固定到完整 SHA。[GitHub Actions 安全参考](https://docs.github.com/en/actions/reference/security/secure-use)

增加低频 Dependabot 检查 GitHub Actions 引用即可；配置使用 `package-ecosystem: github-actions` 和根目录 `/`。GitHub 官方定义了该 ecosystem 与目录位置；无需为没有依赖清单的 zsh 脚本伪造语言包管理器配置。[Dependabot 配置参考](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)

贡献说明、安全政策和 Issue / PR 模板采用 GitHub 识别的位置与名称，避免多份重复规则。GitHub 列出了这些社区文件及其用途。[GitHub 社区文件](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file)

仓库简介、topics、Issues 和分支保护属于仓库服务器端设置，不能仅靠提交文件确认已生效。它们应在实际应用后核验；发布说明同样应区分“本地打包验证完成”和“Release 已发布”。这一点是本项目的交付验收约定。

## 许可证与第三方边界

GitHub 明确说明，公开仓库需要开源许可证才能明确给予他人使用、修改和分发软件的权利。本项目应在根目录放置其自身源码的许可证，并在 README 标注；许可证选择必须基于项目自身代码的权利来源。[GitHub 仓库许可说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)

HandBrake 官方 `LICENSE` 说明其编译产物适用 GPLv2，内部文件与第三方组件存在不同许可证。不能把本项目选定的许可证描述成适用于 HandBrake 的许可证。[HandBrake LICENSE](https://github.com/HandBrake/HandBrake/blob/master/LICENSE)

本项目的分发边界采用以下设计：

- 发行包仅包含本项目脚本与文档。HandBrakeCLI 和可选的 ffprobe 由用户从各自上游或包管理器安装。
- 不复制 HandBrake / yt-dlp / mas / Homebrew 的实现代码、图标或品牌资产；参考其公开文档组织与配置做法，并保留出处。
- 文档注明本项目是第三方自动化工具，不暗示由 HandBrake 官方维护或背书。
- 如果未来决定捆绑第三方二进制，另行检查具体版本、构建选项、许可证和分发要求；现有“仅调用用户安装的工具”方案不覆盖这种变化。yt-dlp 对源码和含第三方代码的发行产物分别说明许可，也说明了为什么需要按实际打包内容判断。[yt-dlp 发行许可说明](https://github.com/yt-dlp/yt-dlp#licensing)

## 本地版本保留原则

这是本项目迁移的验收约定：源码改造、公共仓库提交和已安装 Finder 入口的更新分别核验。维护者当前可用 workflow 与个人预设应保留可恢复副本；本地搬迁记录留在忽略目录。公共默认的变化通过个人配置兼容现有使用方式，不强迫维护者采用新默认编码参数。

发布前至少确认：新用户不需要维护者的家目录、首次运行不要求已有个人 GUI 预设、安装升级保留配置、既有视频和完成记录保持可用、发布包不包含本地资料。最终 README 只陈述已实现和实际验证过的行为。
