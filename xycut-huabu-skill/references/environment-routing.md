# 独立环境准备

本 Skill 固定独立运行。即使本机装有 XYCut，也不读取客户端上下文、配置或模板安装索引，不连接 XYCut 后端，不检查登录或会员。语音直接连接用户选择的服务，渲染在本机完成。

## 输入与语音

- 文案：读取本机豆包配置，先 TTS 再 ASR。未配置时合并询问用户选择本机配置豆包、用 XYCut 客户端准备配音，或提供音视频。具体按[独立语音](standalone-speech.md)执行。
- MP3／带声音的 MP4：保留原媒体，直接 ASR，不再 TTS。其他格式先转换副本，不覆盖原文件。
- 默认 ASR 为本地 SenseVoice；用户明确选用并配置后才用云端 ASR。配置了云端 Key 不等于已选择云端识别。失败后报告具体原因，不自动切换服务。
- 已有项目：先读 `project.py resume` 的记录，校验并复用原输入、配音、时间轴、模板与输出比例。用户给了新文件或明确修改声音要求时才重新处理。

用 `speech.py check --input-type text|mp3|mp4` 检查当前入口。检测不联网验证凭据、不下载模型，也不保证服务已开通。按[本地识别规范](standalone-local-asr.md)复用 Python 3.10+、Node.js、Chrome／Edge／Chromium、Playwright 和 FFmpeg／FFprobe。选择本地 ASR 时，在独立虚拟环境安装 numpy、sherpa-onnx 并准备模型；选择云端时无需安装本地识别模型。不要修改全局 Python 环境，实际成功后再报告已就绪。

项目创建和恢复按[项目记录](project-records.md)执行。后续语音、改编、预览和导出都在同一工程中；`speech/` 下的尝试目录是历史产物，不是第二个用户工程。可用原来的 `detect_environment.py --mode standalone --speech local --input-type mp3` 补充检查本地识别和渲染工具，检测结果保存到本次 `planning/` 中，避免覆盖旧记录。

保留原媒体和原始识别。用户已有匹配当前声音的最终时间轴时可复用；只有 SRT 就按行级精度处理，不能编造字词时间。识别或工具准备失败时报告具体缺项，不自动切换云服务。

模板从项目同级 `templates/index.json` 或[默认 GitHub 索引](https://raw.githubusercontent.com/dayuanlog/xycut-huabu/main/templates/index.json)中按需选取，详见[模板资源](external-resources.md)。两种入口共用本独立环境：提示词明确 ID 时按 ID 查找；未给 ID 时由 Agent 读取目录元数据自主选一个，不要求用户先安装客户端或浏览官网。索引为空时明确当前暂无可下载模板，仍可使用用户的 ZIP 或通用运行时创作。

环境准备好后进入[共用制作流程](workflow.md)，不重新判断运行模式。
