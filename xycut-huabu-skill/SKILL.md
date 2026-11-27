---
name: xycut-huabu-skill
description: 根据 MP3 或带声音的 MP4 独立制作 HTML 画布讲解视频，使用本地 SenseVoice 识别、按需下载开源模板，支持横竖屏、动画运镜与本地 MP4 渲染；先交付预览并等待确认。
metadata:
  version: "0.10.0"
---

# XYCUT画布视频

自有代码按 [MIT License](LICENSE) 授权，版权人为大圆（dayuanlog）；[第三方组件与素材说明](THIRD_PARTY_NOTICES.md)另行规定各资源的许可范围。复制模板后保留其许可文件，读取包内和工程内的素材说明；示例字体、数字人、配音和音效不因代码开源而自动获得 MIT 授权，未确认的事项不得描述成已授权。

固定独立运行，不读取 XYCut Agent Context、不调用 XYCut 后端，不要求客户端、登录或会员。用户提供 MP3 或带声音的 MP4，使用本地 SenseVoice 识别；只有文案时先请用户准备音视频，本 Skill 不提供自动配音。

## 开始时确认模板和比例

先沿用用户已有的明确要求，不重复询问已指定的模板、输出比例或已授权 Agent 自行决定的事项。新任务尚未说明怎么选模板或比例时，把缺少的选择合并成一次简短询问，例如：

> 模板由我根据内容挑选，还是你去官网自己选？视频做横屏还是竖屏？也可以都交给我决定。

- **交给 Agent：**根据内容、素材和用途选择模板及比例，简要说明后继续；没有足够比例线索时沿用横屏默认，不为每个选择反复确认。
- **用户自己选：**用当前可用浏览器打开 [官网画布视频](https://www.xycut.com/canvas.html)，请用户选好后把页面复制的模板提示词发回来。无法打开浏览器时提供同一可点击链接。等用户选定条目后继续；用户选中的模板比例可作为默认，不再无故重复问横竖屏。等待选择时可先进行不依赖模板的素材检查与环境准备，不替用户下载另一个模板。
- **已经指定：**官网提示词已有模板 ID、用户提供模板 ZIP，或明确说了“自动挑选／你决定”时，直接按对应要求继续。已选模板且用户未另定比例时，沿用该模板的示例比例；已有工程修改沿用原工程及已确认比例，不重新走首次选择。

README 通用提示词与官网模板提示词都属于本 Skill 的同一流程。用户从官网返回并粘贴模板提示词时，将其视为当前任务的选模结果，沿用此前的素材、任务目录和已确认要求；不重新询问选择方式，也不新建第二份任务。已有明确输出要求时优先沿用，用户本次明确修改的要求再更新。

## 环境与制作

按[独立环境准备](references/environment-routing.md)检测本机能力并创建新任务，所有入口显式使用 `--mode standalone`：

```text
python scripts/detect_environment.py --mode standalone --speech local --input-type mp3
python scripts/create_task_workspace.py --tasks-root <用户工作目录>/xycut-tasks --label <短名> --mode standalone
```

命令中的 `scripts/` 相对当前 Skill 安装目录，必要时使用脚本绝对路径。MP4 输入把 `--input-type` 改为 `mp4`。使用命令返回的任务目录，已有项目修改沿用原目录，然后执行[共用制作流程](references/workflow.md)和[本地识别规范](references/standalone-local-asr.md)。安装位置按当前 Agent 环境解析，不硬编码开发机器路径。检测的 `ready` 或 Skill 安装完成都不表示 ASR 和渲染依赖已安装，按实际检测及运行结果准备缺项。

开源项目：https://github.com/dayuanlog/xycut-huabu 。只安装仓库中的 `xycut-huabu-skill` 目录，不预先下载全部模板。按上面的选择结果进入[模板索引与按需下载](references/external-resources.md#模板索引与按需下载)：已有 ID 时使用该条目，交给 Agent 时读取目录自主选一个，用户手动选时使用其返回的 ID。只下载选中的一个 ZIP；也可使用用户提供的 ZIP 或通用运行时创作。

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
