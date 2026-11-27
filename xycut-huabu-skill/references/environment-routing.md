# 独立环境准备

本 Skill 固定独立运行。检测环境和创建任务时显式使用 `--mode standalone`；即使本机装有 XYCut，也不读取客户端上下文、配置或模板安装索引，不连接 XYCut 后端，不检查登录或会员。

用户提供 MP3 或带人声的 MP4，使用本地 SenseVoice 识别声音时间。只有文案时，简洁提示：“请提供 MP3 或带声音的 MP4；当前 Skill 不提供自动配音。”不要以安装客户端或配置云端语音作为继续条件。

入口的检测与任务创建命令见 [SKILL.md](../SKILL.md)。检测只读取本机工具和依赖，不联网验证凭据。`ready` 不代表模型、Python 依赖和渲染工具已全部安装；按[本地识别规范](standalone-local-asr.md)检查 Python 3.10+、Node.js、现有 Chrome／Edge／Chromium、Playwright 和 FFmpeg／FFprobe，复用可用安装，在独立虚拟环境中准备缺少的 ASR 依赖，不修改全局 Python 环境。只有命令实际成功后才能报告对应依赖已就绪；安装失败或尚未运行时如实说明。

使用任务创建命令返回的新目录；已有项目修改沿用原目录。需要保存检测结果时，将检测命令加上 `--output <任务目录>/planning/environment.json`，不覆盖已有记录。

按[本地识别规范](standalone-local-asr.md)识别原媒体，保留输入文件和原始识别。用户已有匹配当前声音的最终时间轴时可复用；只有 SRT 就按行级精度处理，不能编造字词时间。识别或工具准备失败时报告具体缺项，不自动切换云服务。

模板从项目同级 `templates/index.json` 或[默认 GitHub 索引](https://raw.githubusercontent.com/dayuanlog/xycut-huabu/main/templates/index.json)中按需选取，详见[模板资源](external-resources.md)。两种入口共用本独立环境：提示词明确 ID 时按 ID 查找；未给 ID 时由 Agent 读取目录元数据自主选一个，不要求用户先安装客户端或浏览官网。索引为空时明确当前暂无可下载模板，仍可使用用户的 ZIP 或通用运行时创作。

环境准备好后进入[共用制作流程](workflow.md)，不重新判断运行模式。
