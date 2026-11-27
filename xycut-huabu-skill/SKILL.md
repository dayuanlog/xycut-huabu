---
name: xycut-huabu-skill
description: 根据 MP3 或带声音的 MP4 独立制作 HTML 画布讲解视频，使用本地 SenseVoice 识别、按需下载开源模板，支持横竖屏、动画运镜与本地 MP4 渲染；先交付预览并等待确认。
metadata:
  version: "0.10.0"
---

# XYCUT画布视频

固定独立运行，不读取 XYCut Agent Context、不调用 XYCut 后端，不要求客户端、登录或会员。用户提供 MP3 或带声音的 MP4，使用本地 SenseVoice 识别；只有文案时先请用户准备音视频，本 Skill 不提供自动配音。

先按[独立环境准备](references/environment-routing.md)检测本机能力并创建新任务，所有入口显式使用 `--mode standalone`：

```text
python scripts/detect_environment.py --mode standalone --speech local --input-type mp3
python scripts/create_task_workspace.py --tasks-root <用户工作目录>/xycut-tasks --label <短名> --mode standalone
```

MP4 输入把 `--input-type` 改为 `mp4`。使用命令返回的任务目录，已有项目修改沿用原目录，然后执行[共用制作流程](references/workflow.md)和[本地识别规范](references/standalone-local-asr.md)。安装位置按当前 Agent 环境解析，不硬编码开发机器路径。

开源项目：https://github.com/dayuanlog/xycut-huabu 。只安装仓库中的 `xycut-huabu-skill` 目录，不预先下载全部模板。按[模板索引与按需下载](references/external-resources.md#模板索引与按需下载)选择单个模板，也可使用用户提供的 ZIP 或通用运行时创作。

| 任务 | 读取规范 |
|---|---|
| 制作视频、改编模板 | [外部模板](references/external-resources.md)、[共用规则](references/common-rules.md)、[画布契约](references/canvas-contract.md) |
| 横屏／竖屏 | [横屏](references/landscape-framing.md)／[竖屏](references/portrait-framing.md) |
| 人物出镜 | [人物叙事与窗口交接](references/presenter-video.md) |
| 本地 ASR 与工具准备 | [独立环境与 SenseVoice](references/standalone-local-asr.md) |
| 封面、标题、字幕、音效 | [标题与封面](references/series-titles-and-covers.md)、[字幕](references/subtitles.md)、[表现与声音](references/presentation-and-sound.md) |
| Motion 快节奏白板流（按需） | [Motion 快节奏白板流](references/motion-whiteboard.md)（仅选定极客白板流模板或要求快节奏框选动效时读） |
| 字体选用、缺字补全与子集打包 | [字体与子集规范](references/fonts-and-subsetting.md) |
| 项目保存为模板 ZIP | [模板打包](references/template-packaging.md) |

模板是风格和组件参考：根据新文案及 ASR 重新规划画面、动画和镜头，既不能只换文字，也不必全部重写。运行时、图标和预览面板在 `assets`，使用时复制到本次工程，保留所用图标许可。

**必须停下来确认：**生成 HTML 后先检查实际播放，再打开项目 `index.html` 并提供入口，请用户确认本版效果；收到确认后才执行 MP4 渲染。此前笼统要求“做成视频／渲染成品”不替代对本版预览的确认。有修改则重新交付预览并等待确认。确认标题的规则见执行流程。
