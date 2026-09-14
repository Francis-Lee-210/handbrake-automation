# HandBrake Finder Automation

macOS Finder 右键批量整理并压缩视频的自动化脚本。

## 右键入口

- `压缩视频-当前文件夹`：只处理所选文件夹最外层的视频。
- `压缩视频-所有视频`：递归处理所选文件夹及其子文件夹中的视频。

两个入口都会：

- 按大小写不敏感的自然名称顺序处理文件夹和视频，例如 `1、2、10`。
- 在 Terminal 中显示当前文件、当前视频百分比、整批总体进度和预计剩余时间。
- 按视频时长计算总体进度，而不是让长短视频占用相同权重。
- 将完整 HandBrake 输出保存在对应的 `压缩视频/video-compress.log`。

每个待处理目录都会创建：

- `原始视频/`：保存移动后的源视频。
- `压缩视频/`：保存 HandBrake 压缩结果和日志。

## 当前配置

- HandBrakeCLI：`/opt/homebrew/bin/HandBrakeCLI`
- ffprobe：`/opt/homebrew/bin/ffprobe`
- 自定义预设：`1080 原帧率 硬件加速`
- 输出容器：MP4

如果找不到 ffprobe，压缩仍会继续，但总体进度会退化为按文件数量估算。预计剩余时间在运行至少 10 秒且进度数据足够后显示，因此短批次可能始终显示“计算中”。

## 目录

- `bin/video-compress`：整理和压缩视频的主脚本。
- `bin/launch-in-terminal`：在 Terminal 中启动任务并显示紧凑进度。
- `workflows/`：当前安装使用的两个 Finder Quick Action 备份。
- `test-bin/`：用于验证批处理循环的本地 HandBrakeCLI 测试替身。

## 命令行使用

```bash
bin/video-compress --flat "/path/to/folder"
bin/video-compress --recursive "/path/to/folder"
```

脚本默认不覆盖已经存在的压缩结果，重复运行时会跳过已完成文件。
