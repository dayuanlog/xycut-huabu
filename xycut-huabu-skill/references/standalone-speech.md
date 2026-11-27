# 独立语音：文案、音频与口播视频

本页负责开源版的语音与本机配置；不调用客户端，不使用客户端账号、密钥或付费权限。命令在 Skill 安装目录执行，`python` 指本次使用的 Python；本地 ASR 采用[识别环境](standalone-local-asr.md)中的虚拟环境 Python。

## 首次配置

先运行 `python scripts/local_settings.py show`，输出只显示是否配置，不显示密钥，也不验证服务是否开通。已有有效配置直接复用，不反复向用户索要。

只有文案但未配置 TTS 时，让用户选择：

1. 使用自己的豆包语音：用户在[火山语音控制台](https://console.volcengine.com/speech/new/overview)开通所需服务、选择音色并取得对应项目的 API Key；操作参考[官方控制台说明](https://docs.volcengine.com/docs/doubao-voice/console-guidance?lang=zh)。不要替用户开通、充值或承诺免费。
2. 使用 [XYCut 客户端](https://www.xycut.com/#download)设置和管理语音，准备好音频后提供给本 Skill；也可改用客户端的画布制作流程。
3. 用户自行提供 MP3／带声音的 MP4，直接进入识别。

让用户通过本机环境变量或自己编辑私有配置设置 Key，不要求把 Key 发进聊天，不把它写成命令参数、项目记录、记忆、截图或日志。以下环境变量值由用户在本机设置，示例不包含真实密钥：

```text
python scripts/local_settings.py configure --api-key-env XYCUT_HUABU_TTS_API_KEY --voice-id <用户选择的音色ID>
python scripts/local_settings.py show
```

配置默认保存在 `~/.xycut-huabu/settings.json`，工程默认在 `~/xycut-huabu-projects/`。`~` 按当前系统用户解析。可用 `XYCUT_HUABU_CONFIG_DIR` 或所有新脚本的全局参数 `--config-dir <目录>` 指定私有配置目录（必须放在子命令之前）。私有配置与工程必须位于 Skill／仓库之外；文件含密钥，请保存在当前用户的私有目录。不要加入 Git 或模板包。配置损坏会报错并保留原文件，不自动清空用户配置。

临时运行可只设置 `XYCUT_HUABU_TTS_API_KEY`／`XYCUT_HUABU_ASR_API_KEY`；也兼容用户主动设置的 `VOLCENGINE_API_KEY`。读取优先级为对应服务的环境变量、本地保存值、通用环境变量。TTS 与 ASR 的开通权限分别检查，不从客户端拷贝。配置保存的是使用方式和密钥，不保存“已经授权”的结论。

默认 TTS 资源为 `seed-tts-2.0`，默认音色 `zh_female_vv_uranus_bigtts` 仅为初始值，按用户实际可用音色调整；可用 `--tts-resource-id` 修改。`--speech-rate` 范围 0.5–2，`--volume` 范围 0.1–3（接口会转换为支持的整数音量）；可用 `--ffmpeg <完整路径>` 和 `--projects-root <目录>` 保存本机工具及工程位置。重配置只更新指定字段，保留其余设置。

豆包配音、云端识别使用用户自己的服务额度，计费以[服务方说明](https://docs.volcengine.com/docs/doubao-voice/billing-overview?lang=zh)为准。配置成功不代表凭据已通过验证；第一次真实调用前说明将发送文案或音频到所选服务，并遵循用户已有授权。

## 在一个工程中准备声音

先用 `project.py create` 创建工程，或 `project.py resume --task-dir <原工程>` 恢复。把聊天中的文案以 UTF-8 保存为文件（不改写用户原文），使用返回的任务目录：

```text
python scripts/speech.py check --input-type text
python scripts/speech.py prepare --task-dir <任务目录> --text-file <文案.txt>
```

已有声音不做 TTS：

```text
python scripts/speech.py prepare --task-dir <任务目录> --input-media <音频.mp3>
python scripts/speech.py prepare --task-dir <任务目录> --input-media <口播.mp4> --source-text-file <可选原文.txt>
```

`--source-text-file` 可省略；适用于已有媒体附原文，不能代替真实 ASR。TTS 生成的 MP3 同样需要 ASR，不能用字数、示例时间或 TTS 返回的估计时长编造正式时间轴。返回值中的 `audio_file` 是本次最终声音文件；口播输入保留 MP4，后续按画面规范使用其视频和声音。

默认使用本地 SenseVoice，保留其原始结果、CTC 估计边界与精度说明。只需要本地识别时按[本地 ASR](standalone-local-asr.md)准备依赖和模型，可传 `--model-dir`／`--cache-dir`。模型未安装时脚本会按该规范下载；不要将模型放入 Skill 仓库。

## 可选云端 ASR

仅在用户明确选择时启用。用户需开通对应识别服务；云端会发送本次声音到服务方。保存 API Key 与选择后：

```text
python scripts/local_settings.py configure --asr-api-key-env XYCUT_HUABU_ASR_API_KEY --asr-provider cloud
python scripts/speech.py prepare --task-dir <任务目录> --input-media <音频.mp3> --asr-provider cloud
```

默认 `seedasr_standard` 使用 Seed ASR 异步提交／查询；配置文件的 `speech.asr.mode` 可为 `standard` 或 `flash`，按已开通服务设置对应 `resource_id`、`fallback_resource_id`、`flash_resource_id`，不自动尝试其他付费服务。标准资源可用 `--asr-resource-id` 修改。名称含 fallback 的字段只用于明确选择 `standard` 模式，不触发失败回退。

切回本地：`python scripts/local_settings.py configure --asr-provider local`；已有工程继续保留原识别选择，如需更换显式传 `speech.py prepare ... --asr-provider local`。云端返回的字词或分句时间据实记录，不能声称比服务返回的精度更高。若没有可用时间轴则报错，不生成假字幕。

## 复用与故障

同一工程重新运行 `python scripts/speech.py prepare --task-dir <原工程>` 会校验并复用已完成的配音和识别。只改画面不重新配音。改了全局默认音色不会悄悄改变已有工程；用户明确换音色可传 `--voice-id`／`--speech-rate`／`--volume`，修改文案传新的 `--text-file`。`--regenerate` 明确要求重做语音，会再次请求服务，先确认本次意图。

ASR 失败后保留已生成的 TTS，修复问题再运行会从识别继续。密钥、权限、额度、网络或本地依赖异常应报告具体原因；不偷偷切服务或连续重试付费请求。历史结果保留在 `speech/` 的不同尝试目录；已记录文件丢失或被改动时先检查，不静默重做收费语音。项目细则见[记录与恢复](project-records.md)。

异步云端 ASR 保存请求 ID，超时或进程中断后继续查询同一个任务，成功结果也可复用；不会每次恢复都重新提交。已明确失败的请求先检查，再决定是否用 `--regenerate` 重做。TTS 和极速 ASR 属于一次请求，连接异常时不保证服务端未处理；只有已完成并保存的结果能直接复用，不要盲目连续请求。
