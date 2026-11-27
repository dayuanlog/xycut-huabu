# 配音与 ASR 接入

本文只供客户端入口已选定配套 TTS／云端 ASR 时读取，能力检查在当前 Skill 的[环境入口](environment-routing.md)完成。本页沿用该结果，不重新选择运行模式或语音服务；本地识别由入口直接进入[本地 SenseVoice](standalone-local-asr.md)。

集成模式先读取客户端复制提示词中的 `agent_context_file`，从中解析配套安装位置，不能硬编码开发机器路径。缺少 TTS 配置而只有文案时，提示配置豆包语音 API 或先提供音视频；没有云端识别配置不阻止已有音视频走本地识别。

1. 从上下文的 `skills["xycut-video-template-skill"].install_dir` 定位主 Skill，读取其 `SKILL.md` 和 `references/tts-doubao-flow.md`，核对当前接口与脚本用法。不能从旧工程猜测安装路径。
2. 只有文案且需要 AI 配音时，使用主 Skill 的 `scripts/generate_doubao_tts.py` 调用豆包 TTS，再对实际生成的音频做 ASR／时间戳对齐。音色与服务配置读取上下文，不凭文案长度估算时间。
3. 已有 MP3 或含人声的 MP4，使用主 Skill 的 `scripts/transcribe_volcengine_asr.py` 获取实际语音时间；已有可用最终 ASR 时直接复用。读取脚本当前帮助和主 Skill 规范确定参数，不臆造调用方式。
4. 语音产物保存到本次任务，包括原始识别结果、带词时间的 `speech/segments.json` 和字幕；本 Skill 再归一化时间轴、绑定重点词并设计画面。用户原稿作为文字校对依据，真实音频作为时间依据。

通过上下文读取 `speech.tts`、`speech.asr`、`third_party_apis` 和 `tools.ffmpeg_path` 等所需配置，不把 API Key 写入模板、Skill、日志或回复。缺少配套 Skill 时说明修复方式，不假造 ASR。已有配置但云端请求失败时，说明错误并让用户决定修复或改走本地，不把服务失败混同为未配置。TTS 成功后若只有本地 ASR 可用，也可将生成的实际音频交给本地识别。

这里只复用主 Skill 的语音阶段，不因调用 TTS／ASR 自动进入剪映草稿、素材匹配或发布流程。口播剪辑仅在本次任务需要且已获用户授权时执行；一旦音频被剪辑，画面改用剪辑后的最终时间轴。
