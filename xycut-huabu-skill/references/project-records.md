# 项目记录与恢复

一个视频对应一个独立工程，使用当前用户的本机配置，不依赖客户端数据库或 Agent 对话记忆。Skill 更新和重装不应清掉工程、配音或私有配置。

## 创建、查找与继续

```text
python scripts/project.py create --label <短名>
python scripts/project.py list
python scripts/project.py resume --task-dir <原工程目录>
```

默认工程在 `~/xycut-huabu-projects/`；可在配置中设置 `projects_root`，或创建时传 `--projects-root <目录>`。目录必须在仓库之外。使用 create 返回的 `task_dir`，不要自行猜路径。用户从官网返回选好的模板、换一轮对话或修改同一视频时沿用原工程，不再 create。找不到目标时只询问工程位置或从 list 中确认，避免扫描整台电脑。

`resume` 返回素材、模板选择、声音、时间轴、当前状态、输出路径及文件校验结果；它只读取记录，不触发 TTS、ASR、下载或渲染。发现文件丢失、变化或旧预览已失效时先处理对应问题。状态记录不代替本轮对当前版本预览的用户确认。

## 工程内容

- `task_manifest.json`：当前输入、模板 ID、比例、状态、语音参数、产物路径和 SHA256，以及操作历史；不保存 Key。
- `input/`：带内容摘要的原始文案／音视频副本；不覆盖用户原文件。人物视频仍作为本次源画面。
- `speech/`：TTS 和 ASR 每次尝试的原始响应与产物；历史目录保留，失败也不删已有配音。识别内部尝试目录不作为独立用户项目。
- `output/final-timeline.json`、`output/voice.srt`、`speech/segments.json`：当前成功识别的统一时间轴和字幕。
- `planning/`：画布规划和环境记录；`planning/records/` 保存每次记录更新时的 manifest 快照，便于追溯。它们是元数据历史，恢复旧成品应使用保留的对应文件，不能仅改状态字段冒充回滚。

记录选模与关键产物：

```text
python scripts/project.py record --task-dir <目录> --template-id <ID> --orientation landscape --status planning
python scripts/project.py record --task-dir <目录> --preview-file <工程内/index.html> --status awaiting_confirmation
python scripts/project.py record --task-dir <目录> --video-file <工程内/成品.mp4> --status completed
```

竖屏使用 `portrait`。可用 `--title` 保存当前标题；其他规划保存在本次 planning 文件中。产物必须在工程目录内。重新记录产物会更新校验摘要；仅在对应制作步骤完成后才记录该状态。重要的画面修改保留版本副本，脚本不会自动备份所有 HTML 和 MP4。

## 声音如何复用

通过 `speech.py prepare` 操作（见[独立语音](standalone-speech.md)），由脚本记录输入及声音摘要、音色、资源、语速、音量、识别方式和模型路径。相同输入与声音要求优先复用已校验的 TTS／ASR，不因新对话或全局默认配置改变而重复生成。只有文案、声音参数、输入媒体、识别方式明确变动，或用户要求重新生成时才重做相关步骤。

重新生成声音成功后，已有预览／视频标记为 `stale`，状态回到 `speech_ready`；Agent 必须重新编排音画并交付预览，用户确认后才能导出。识别失败时记录 `speech_failed` 和去除凭据的错误，保留已成功的 TTS 供重试使用。并发操作有锁，锁未释放时报错；先确认没有进程仍在运行，再处理遗留锁，不能盲目删除。

项目和音视频可能包含用户内容，保存在用户指定位置；共享工程前自行检查素材与隐私。私有配置不跟随工程打包。不得把密钥写进项目、Skill、README、模板、Git 或 Agent 记忆。
