# 画布模板资源

Skill 保留制作规则、通用运行时和工具，模板放在开源项目同级 `templates` 目录，通过索引按需下载。只安装 `xycut-huabu-skill` 目录，不下载整个模板库。也可直接使用用户提供的模板 ZIP 或工程，或不选模板。

## 模板索引与按需下载

项目地址：https://github.com/dayuanlog/xycut-huabu 。完整项目中可读取 Skill 同级的 `templates/index.json`；只安装 Skill 时，默认读取以下公开索引，不要求本机同时拥有 `templates` 目录：

```text
https://raw.githubusercontent.com/dayuanlog/xycut-huabu/main/templates/index.json
```

索引结构为 `{"schema_version":1,"templates":[...]}`。每个模板包含 `id`、`name`、`download_url`、`sha256`，可选 `min_skill_version`；`download_url` 可以是相对于索引位置的地址或完整 HTTPS 地址。模板 ID 以索引为准，不从展示名称猜测。索引为空时明确当前暂无模板，不编造条目或下载地址；可继续使用用户提供的 ZIP 或通用运行时。

确定模板后，只下载选中的一个 ZIP：

```text
python scripts/download_template.py --template-id <ID> --index https://raw.githubusercontent.com/dayuanlog/xycut-huabu/main/templates/index.json --task-dir <已创建的新任务>
python scripts/download_template.py --template-id <ID> --index <项目路径>/templates/index.json --cache-dir <本机模板缓存目录> --task-dir <已创建的新任务>
```

按实际索引选择一条；省略 `--cache-dir` 使用工具默认缓存。工具校验索引中最低 Skill 版本、下载单个 ZIP 并核对 SHA256；传入 `--task-dir` 时再调用已有模板工具，将工程复制到任务 `output/canvas-project` 并记录 `planning/template-reference.json`。不传任务目录时只准备缓存供后续使用。下载或校验失败时停止使用该包并说明原因，不改用 XYCut 后端或绕过校验。

本地版本见 `SKILL.md` 的 `metadata.version`。兼容的已安装 Skill 和校验通过的缓存可直接复用；版本不足时按项目的实际发布说明更新当前 Agent 使用的 Skill，不删除用户任务、模板或其他配置，不猜测不存在的 Release 文件名。

## 独立模板入口

```text
python scripts/use_canvas_template.py --package <模板ZIP或解压目录> --task-dir <已创建的新任务>
```

此入口不读取 Agent Context，不需要客户端安装索引。支持 ZIP 外多包一层目录；检查路径逃逸、链接和大小限制，复制后工程不依赖临时解压位置。可使用新建空任务目录；拒绝覆盖已有工程和模板引用记录，不修改下载缓存。模板包的 `entry`、`canvas_plan`、`cover`、`preview` 都是相对包根目录的路径，不能指向包外。只有用户提供的普通 HTML 工程而没有 manifest 时，Agent 检查依赖后复制工程到任务副本，不伪造索引。

没有模板时可从 `assets/runtime`、`assets/preview` 等通用运行代码设计本次工程，补齐 `index.html`、主题、组件、计划和字幕接入；通用运行时不是完整风格模板，不声称有内置模板。仍需提供同样的预览面板、`READY`、`END` 和 `renderAt(t)` 契约。

复制的是可运行的示例，不是用户的新成品。先读 manifest 与模板内 `project/TEMPLATE_GUIDE.md`（如有），再查看预览、画布计划、所需模块及示例时间轴，理解设计与动画过程。若模板内置了示例子集字体且新文案存在缺字，按[字体与子集规范](fonts-and-subsetting.md)从本机缓存或免费可商用字体库补齐完整同名字体。新配音必须产生自己的最终 ASR，替换示例内容、素材、标题、字幕、音轨并重新绑定动画与镜头；不得把案例原始秒数、人物、金额当作新任务的默认值。修改发生在任务副本。

## 按新内容改编

模板作为风格和组件参考。复制工程只是建立可运行的起点，随后根据新文案的内容关系和最终 ASR，重新规划画板、组件布局、内部过程动画、镜头、人物窗口及声音。不能只替换文字并沿用示例节奏，也不要求把可复用代码全部推倒重做。

- 内容结构接近时，保留适合的组件与布局，调整内容、素材、动画过程和时间锚点。
- 内容结构变化时，复用合适组件，重新组合布局、关注范围和镜头路线。
- 内容完全不同时，沿用主题和通用能力，按新叙事重新设计画面。

先检查完整展开的静态画布，再验证实际播放、音画同步和随机跳转。修改承载多个数据对象的脚本时保留所需时间轴、字幕和重点词数据，不能只检查文件是否存在就认定预览可播放。

## Skill、模板与任务的职责

- Skill 保存共用制作方法、横竖屏默认版式、人物叙事规则、字幕与音效规范、通用运行能力以及统一预览面板。横竖屏与深浅色是独立选择，不互相绑定。
- 模板的 manifest 保存该模板的主题标识（如 `theme`）、示例输出比例、叙事方式及资源入口；实际背景、配色、字体、组件和动画实现保存在模板项目源码中。读取清单与源码确认风格，不仅凭模板名字猜测。模板的示例尺寸和内容不是用户新任务的固定约束。
- 本次任务保存用户确认的输出尺寸、标题、文案、素材、ASR、布局和动画镜头计划。用户要求优先；未指定风格时可沿用所选模板。跨比例或主题调整时重新检查构图、配色和安全区。
- 横屏默认不添加固定顶部视频标题、不插入5帧封面；画面中的语义大标题可按内容设计。竖屏默认采用前5帧封面、顶部主副标题、中央1:1正文和底部字幕，详见对应比例规范。人物主导的全屏区间遵守人物规范。
- 预览操作面板保持统一，不随模板画面深浅色改变；成品只渲染输出区域。

运行时复制到任务内，工程不得依赖缓存目录或 Skill 的绝对路径。记录模板 ID、Skill 最低版本与原模板 manifest 哈希。更新索引或缓存不能改变已经复制出的任务。`schema_version` 与 `min_skill_version` 用于协议和工具兼容，不是模板版本号。

## 维护与发布

完整案例和组件库是两类资源：案例保留完整叙事、示例声音与时间依据；组件库按用途和稳定模块 ID 取用。完整案例不必强行拆成固定槽位模板。

发布时整理自包含工程、封面、成品预览、时间依据与必要素材，去除本机绝对路径、客户端上下文、密钥、缓存和重复中间视频，保留依赖的许可声明。模板包发布后，在项目 `templates/index.json` 登记实际下载地址和 ZIP 的 SHA256，索引只引用已经可下载的资源；本地打包不等于已发布。

将当前项目保存为新模板时，使用[项目打包流程](template-packaging.md)，无需访问开发仓库或历史示例目录。
