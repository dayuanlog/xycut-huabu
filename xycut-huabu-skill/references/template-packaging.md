# 将满意的项目保存为模板

用户要求将项目保存为模板时使用。本阶段整理可独立运行的项目副本，不改变原工程，不把用户内容上传服务端。沿用当前项目的风格、组件和示例过程；新任务仍按新文案和 ASR 改编。

1. 确认用户已满意本版 HTML（并已接入统一深色工作台 `viewer-panel.css` 与封面/标题/字幕试调面板 `preview-settings.js`）；需要新渲染预览视频时，先遵守 HTML 预览确认节点。准备与本版对应的 PNG 封面和 MP4 预览，不用旧视频冒充新版：
   - **`preview.mp4` 通用兼容与时长规范**：平台前端预览统一截取**前 30 秒**（末尾约 `0.7–0.8s` 音画平滑淡出），编码必须使用全平台（含老旧 Windows 电脑）通用的 **`H.264 (Main Profile, Level 3.1) + yuv420p + 64k AAC + faststart`**，**严禁使用 H.265/HEVC 或 AV1**。竖屏预览推荐 `406×720`（CRF 28），横屏推荐 `960×540`（CRF 28），按原分辨率渲染后缩放以防固定像素排版溢出。
2. 检查工程的 index.html、画布计划、全部脚本、样式、字体、图标许可和必要媒体。保留播放依赖的单轨 AAC 混音（如 `preview-mix.m4a`，64k）及人物视频，不因文件大就删掉；人物视频可在打包副本中压制为无声 H.264 Main L3.1 版（人物主导 `540×960` CRF 29 / 人物小窗 `406×720` CRF 28）以控制体积。仅清理明确的缓存、日志、临时文件和未引用的冗余 `.wav` / 重复音轨/旧脚本，在打包副本中整理，不修改原工程。
3. **字体轻量打包与复用说明**：
   - 为避免数十 MB 中文字体撑大模板 ZIP，建议在打包副本中使用 `fontTools` 按示例工程实际出现的字符（含 ASCII 与常用标点）生成**迷你子集字体**覆盖同名文件，保持原有 `@font-face` 与离线预览效果不变；同时清除 CSS 中未随本模板分发的其他主题 `@font-face` 引用，避免静态依赖校验失败（详见[字体与子集规范](fonts-and-subsetting.md)）。
   - 推荐在 `project/` 下附带一份 `TEMPLATE_GUIDE.md`，写明主题 Token、封面构图法、可复用组件词汇表、运镜/引导线规则，以及内置子集字体对应的完整商免字体名，便于 AI 在新任务中精准复刻。
4. 将本机绝对路径改为工程内相对路径。注意 canvas-plan.js 可能还含 ASR、字幕和重点词数据，必须完整保留。用户自有素材、字体的分发权限由实际素材来源决定，保留必要开源许可。
5. **统一命名与服务端字段对齐**：
   - 目录名、ZIP 文件名与 `canvas-template.json` 中的 `id` 建议三者保持一致，采用纯小写英文短横线格式 **`{视觉风格}-{presenter|window|voice}-{9x16|16x9}`**（例：`tech-purple-presenter-9x16`、`blueprint-dark-voice-16x9`）；中文展示名 `name` 统一为 **`{视觉风格} · {人物主导|人物小窗|纯配音}`**（横屏后缀 `（横屏）`）。
   - **服务端校验硬约束**：`canvas-template.json` 中 `narrative_mode` 仅允许 **`canvas-led`** 或 **`presenter-led`**（纯配音模板必须写 `"narrative_mode": "canvas-led"` 且 `"presenter": false`，**禁止写 `audio-led`**）。打包后的目录与 ZIP 内禁止嵌套残留旧 `.zip` 文件。
   - 使用下列工具输出新 ZIP：

```text
python scripts/package_canvas_template.py --project <工程目录> --output <工程外的新ZIP路径> --id <模板ID> --name <模板名> --theme dark --cover <封面PNG> --preview <预览MP4>
```

有人物时加 `--presenter`；人物主导再加 `--narrative-mode presenter-led`。默认是画布主导。脚本保留项目运行文件，跳过明确的缓存目录与临时文件，检查静态资源依赖、包大小和输出规格；不能代替真实浏览器验证动态生成的资源路径。

包根目录包含 `canvas-template.json`、`project/`、`cover.png` 和 `preview.mp4`。完成后在新目录解压，打开 `project/index.html` 验证播放、声音、字幕、跳转及人物同步，核对没有依赖原工程或模板缓存。

交付 ZIP 路径，按当前 Skill 的[模板入口](external-resources.md)导入或登记复用。包的格式和 ID 保持一致，发布位置由当前入口决定；打包工具不负责上传、导入或覆盖用户已有模板。
