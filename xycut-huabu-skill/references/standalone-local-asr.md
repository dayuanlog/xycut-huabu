# 本地 SenseVoice 识别

用于当前 Skill 入口已经选定的本地识别流程。输入为 MP3 或含人声的 MP4，不提供文案自动配音。原媒体只读，MP4 仅抽取声音用于识别，保留原文件供后续人物窗口使用，不自动剪口播。

## 准备任务和运行工具

沿用 `SKILL.md` 固定入口已创建的任务目录及运行模式，已有项目修改沿用原目录。本页不重新选择环境或创建第二个任务。输入、原始 ASR、计划和输出分别放在 `input/speech/planning/output`。

需要 Python 3.10+、Node.js、Chrome／Edge／Chromium、Playwright、FFmpeg／FFprobe。先检测现有安装并复用，路径可由用户显式提供；独立模式不从开发仓库或另一个 Skill 借工具。缺少 Python／Node 时说明具体缺项，不把环境异常当成 ASR 空结果。

Agent 可在用户缓存或本项目工具目录创建专用虚拟环境，安装本地识别依赖；不改全局 Python 环境：

```text
python -m venv <缓存目录>/asr-venv
<虚拟环境Python> -m pip install sherpa-onnx==1.12.18 "numpy>=1.24,<3"
```

Windows 虚拟环境 Python 在 `Scripts/python.exe`，其他系统在 `bin/python`。如平台没有该版本的 wheel，说明平台和安装错误，再选择支持版本测试，不反复盲装。模型与推理库不打进 Git 仓库。需要安装浏览器驱动时可在专用工具目录安装 `playwright-core`，优先控制现有 Chrome／Edge；只有没有可用浏览器时才准备 Chromium。FFmpeg／FFprobe 按系统官方安装渠道准备，不能把当前开发机路径写入发布配置。

## 模型准备

```text
<虚拟环境Python> scripts/prepare_local_asr.py
<虚拟环境Python> scripts/prepare_local_asr.py --model-dir <已有SenseVoice模型目录>
```

默认自动下载已固定版本的 int8 模型、`tokens.txt` 和许可说明，约239 MB模型；缓存命中不重复下载。默认缓存位于当前用户的本地缓存目录，也可用 `--cache-dir` 或 `XYCUT_CANVAS_CACHE` 指定。下载显示进度，支持 `.part` 续传，逐文件 SHA256 校验并完成后原子改名。下载锁存在时不并发写入；确认上次进程已退出后才清理残留锁。损坏缓存不覆盖用户文件，按错误路径明确清理后重试。

用户已有模型可含 `model.int8.onnx`、`model_q8.onnx` 或 `model.onnx`，必须有配套词表；记录哈希并以实际加载结果验证兼容性，不能只凭文件名假设等价。模型来源和许可随缓存保留：[固定模型发布仓库](https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17)。

## 转写和时间轴

```text
<虚拟环境Python> scripts/transcribe_local_asr.py --input-media <MP3或MP4> --task-dir <任务目录> --ffmpeg <FFmpeg路径>
```

模型未缓存时自动下载；可传 `--model-dir`／`--cache-dir`，`--threads` 默认2。原声音不裁切，统一抽为16kHz单声道，按能量低点分为有上限的连续块；每块结果加回原音频偏移。纯静音块跳过但时间不压缩。输出已存在时拒绝覆盖，重新识别需在用户授权下归档旧结果或创建新任务。

产物：`speech/asr.local.raw.json`、`speech/segments.json`、`output/final-timeline.json` 和 `output/voice.srt`。使用与现有动画流程相同的归一化句子／token结构，记录模型、版本、源媒体、时间精度与边界估计方式。原始声音、原始识别和用户原文各自保留。

**识别精度必须如实说明：**SenseVoice 返回 CTC token 时间点，脚本结合下一点和时长上限估计结束边界，不等同于强制对齐后的精确字词起止时间。没有 token 时间则降级为片段级，不能平均分配字幕时间。无识别结果时停止并检查音轨，不编造时间轴。

本地初始分行只是机械长度／标点分组。Agent 后续结合用户文案按语义重分字幕、校对英文名称、数字和重点词，继承原 token 时间与来源；必要的显示修正用 `display_aliases`，不为追求正确文字篡改原始 ASR。长静音、块边界及重点动画需实际试听检查。保留 `speech_metadata.timing_precision`，在项目计划说明本地精度；不能把英文 token 拆成字母并声称是逐字母 ASR。

得到最终时间依据后，回到 [共用制作流程](workflow.md)。模板可直接读取用户提供的工程或 ZIP，按 [外部资源规范](external-resources.md) 处理；没有模板也可以从通用运行时代码设计本次画面，不要求先安装 XYCut。
