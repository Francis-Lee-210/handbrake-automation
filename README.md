# HandBrake Finder Automation

macOS Finder 右键批量整理并压缩视频的自动化脚本，使用 zsh 原生实现，提供自然名称排序、批次进度和可重试的输出发布流程。

## 运行条件

- 运行依赖 macOS、zsh 和 HandBrakeCLI；Python 3.9+ 仅用于测试，不是产品运行依赖。
- 仅支持启用 POSIX 所有权的本地卷。脚本只读调用 `diskutil info -plist` 检查 `GlobalPermissionsEnabled`，不会修改卷设置；网络卷、关闭所有权或无法确认的卷不受支持。
- 路径必须满足下文的所有权、权限与 ACL 限制；共享可写目录可能被拒绝。

默认配置：

| 项目 | 默认值 |
| --- | --- |
| HandBrakeCLI | `/opt/homebrew/bin/HandBrakeCLI` |
| ffprobe（可选） | `/opt/homebrew/bin/ffprobe`，不可用时尝试从 PATH 查找 |
| HandBrake GUI 自定义预设 | `1080 原帧率 硬件加速` |
| 输出容器 | MP4 |

可通过 `HANDBRAKECLI`、`FFPROBE`、`HANDBRAKE_PRESET` 环境变量覆盖相应配置。

## 右键入口

- `压缩视频-当前文件夹`：只处理所选文件夹最外层的视频。
- `压缩视频-所有视频`：递归处理所选文件夹及其子文件夹中的视频。

两个入口都按大小写不敏感的自然名称顺序处理文件夹和视频，例如 `1、2、10`。递归扫描跳过管理目录 `原始视频/`、`压缩视频/`；每个处理目录仍会检查已归档到其 `原始视频/` 的文件，以便重试。

## 命令行使用

在仓库根目录运行：

```zsh
bin/video-compress --flat "/path/to/folder"
bin/video-compress --recursive "/path/to/folder"
SHOW_PROGRESS=1 bin/video-compress --flat "/path/to/folder"
```

## 进度与 ETA

- Finder 启动器启用 `SHOW_PROGRESS=1`；命令行直接运行默认不显示进度。
- 启用后，TTY 使用单行刷新显示文件序号、当前视频百分比、整批进度、粗略剩余时间和文件名；按终端宽度截断并替换控制字符。非 TTY 输出普通逐行文本，不发送光标控制序列。
- 整批进度按视频时长加权。部分时长未知时以已知时长的平均值代替；全部未知或没有 ffprobe 时退化为按文件数量估算。
- ETA 是按已耗时与加权进度直接外推的粗略值：`已耗时 × (1 - 进度) / 进度`，没有平滑算法。编码开始至少 10 秒且总体进度达到 3% 后才显示估值；短批次可能一直显示“计算中”，不同视频的编码速度也会让估值跳动。
- 完整 HandBrake 输出保存在对应的 `压缩视频/video-compress.log`，终端进度不是完整日志。

## 输出与完成记录

每个有待处理视频的目录使用以下位置：

| 路径 | 用途 |
| --- | --- |
| `原始视频/` | 保存移动后的源视频，成功或失败都不删除原视频 |
| `压缩视频/` | 保存最终 MP4 与日志 |
| `压缩视频/.video-compress-state/` | 保存 receipt v1（`.done`）、`job.*` 暂存目录及 `lock/` 目录锁；新建状态目录权限为 0700 |

1. HandBrake 先写入状态目录内独立的 staging 暂存目录，不直接写最终输出路径。
2. 仅在 HandBrake 成功退出、暂存结果为非空且符合安全要求的普通文件后发布；若 ffprobe 可执行，还必须成功确认存在视频流。这不是完整解码或逐帧质量验证。发布前再次核对源文件身份未变。
3. 发布时不覆盖已有目标，随后写入 receipt v1。记录包含预设名称、输出文件名，以及源文件和输出的身份信息：device、inode、size、mtime、ctime。
4. 重跑仅在 receipt 版本、预设名称、源文件身份和非空输出身份均匹配时跳过。身份核对不是加密学内容保证；receipt 文件名中的 SHA-256 仅映射源文件名，并未对视频内容做哈希校验。

没有有效 receipt 的旧输出不会被认定为完成，也不会被覆盖或删除；原视频会重新编码到空闲的编号路径，例如 `片段 [2].mp4`。已有输出仅仅存在或非空，不足以跳过。

最终输出的发布与 receipt 的写入不是同一个原子事务：两者之间崩溃可能留下无有效记录的输出。这类未知输出会被保留，不自动认定成功或清理；解除残留锁并满足安全检查后，重跑为它另选空闲路径。

## 安全边界与中断恢复

- 目标目录及逐级祖先必须由 root 或当前有效 UID 所有，且位于上述启用所有权的本地卷。
- 拒绝 group/other 可写目录。唯一例外是可信的 sticky 祖先目录，其直接下一级路径也必须已确认由 root 或当前 UID 所有；目标目录本身不能借 sticky 位获得豁免。
- 目录、祖先及受检文件拒绝任何 ACL `allow` 条目，包括只读授权；并非只拒绝可写 ACL。允许可识别的 `deny` 条目，无法确认的 ACL 也拒绝。
- 受检原视频、输出、日志和 receipt 必须是当前 UID 所有、非 group/other 可写、硬链接数为 1 的普通文件；管理路径不接受静态符号链接或多重硬链接文件。
- 这些限制提供受保护路径的静态链接攻击与其他 UID 边界保证，不防御恶意同 UID、root、此前已授予的文件或目录句柄，也不覆盖运行期间并发修改 ACL 或权限策略的情况。
- 正常退出及可捕获中断会尝试清理本任务的暂存与锁；崩溃或强制终止仍可能遗留 `lock/`、`job.*`。脚本不会按时间或 PID 自动判定陈旧锁，也不会自动抢锁。
- 遇到锁提示，先确认没有相关压缩任务或 HandBrake 进程仍在运行，再检查并手工移除确认失效的 `压缩视频/.video-compress-state/lock/`。仅清理确认无用的暂存目录；不要为解锁删除 receipt、原视频或未知输出。

## 源码、打包与检查

`bin/` 是唯一规范源码，四个文件为 `video-compress`、`launch-in-terminal`、`video-compress-fs.zsh`、`video-compress-progress.zsh`。`workflows/` 中两个 Finder Quick Action 的 `Contents/Resources/` 打包这些文件的副本，不应单独编辑副本。`tests/` 保存回归测试，`test-bin/` 提供 HandBrakeCLI 和 ffprobe 替身。

维护者可在仓库根目录运行（测试需要 Python 3.9+）：

```zsh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
scripts/sync-workflows          # 将四个规范文件同步到仓库内两个 workflow 包
scripts/sync-workflows --check  # 只检查副本内容及可执行位是否一致，不写入
git diff --check
```

`.github/workflows/ci.yml` 配置了 macOS 上的 zsh 语法检查、workflow 元数据检查、副本一致性检查、差异空白检查及回归测试；实际结果以对应运行记录为准。

同步命令仅更新仓库内的打包副本，不更新已安装的 Finder Quick Action。合并 PR 不会自动安装或更新 Finder 工作流；安装是另行执行的操作。
