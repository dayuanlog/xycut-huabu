# 画布、组件与镜头契约

## 坐标分层

`output`为视频像素尺寸；`world`为连续画布尺寸；`boards[]`为区域；`components[]`的`bounds`相对于所属区域，`focuses[]`相对于组件。制作模式见[横屏](landscape-framing.md)与[竖屏](portrait-framing.md)。竖屏成品也可浏览16:9横屏画板，不能把画板尺寸当成成品尺寸。

世界中元素的最终位置＝区域位置＋组件位置＋关注框位置。镜头目标采用已声明的关注框，不读取已经被镜头变换后的getBoundingClientRect作为下一帧目标，避免反馈抖动。组件移动或缩放时，关注框应随动作有明确更新规则，或为该阶段单独声明关注框。

## 计划结构

`canvas-plan.json`包含：

- `output:{width,height,fps}`、`world:{width,height}`、`duration`（秒）。
- 可选`presentation_mode:"landscape"|"portrait"|"custom"`记录本次模式。历史计划没有此字段仍可沿用，不自动迁移旧工程。
- 使用前置封面时记录`intro:{frames,duration}`和`content_duration`，最终`duration=content_duration+intro.duration`。具体标题内容保存在项目`series`等配置中，见[标题与时间偏移](series-titles-and-covers.md)。
- `boards:[{id,x,y,width,height,name}]`。
- `components:[{id,board_id,kind,bounds:{x,y,width,height},content,focuses:[{id,bounds}]}]`。
- `shots:[{id,target,at,move,padding,label}]`。target可为`overview`、区域ID、组件ID或`组件ID/关注框ID`。首镜头at=0，后续at递增，move为从上一构图到当前构图的秒数；move不能越过下一个镜头起点。padding是0至0.45之间的相对留边。
- 镜头可选`travel_scale`（大于0、不超过1）：长距离移动时临时拉远，相对于两个端点中较小的倍率计算；到达时仍按目标框适配。该值只影响途中构图，不改变元素位置。
- `beats:[{component_id,start,end,action,...}]`用于局部动作。示例默认action为reveal、progress、count、highlight或draw；正式项目可扩展，但必须有对应绝对时间实现。
- 库组件使用`kind:"library"`、`module_id`与`module_source`，其`motion:{start,duration,cues}`单独记录正文起点、局部时长与语义节点。局部时间=`正文时间-start`，不对整段示例强行等比例变速。库代码入口来自风格catalog，实例坐标来自本次计划。
- `timing_precision`与`timeline_revision`：演示填写demo；正式任务从最终时间轴读取。不得把演示默认秒数称为真实ASR锚点。

`at`与`move`定义正文中的镜头移动窗口，beat与画板起止同样使用正文时间。未插入封面时正文时间等于最终播放时间；有封面时由播放器统一减去偏移，再调用场景、镜头和字幕。元素可先在空间中存在，涉及新信息的文字仍按语义锚点显现。

## 摄影机

镜头状态为世界坐标中心`cx,cy`与缩放`scale`。由目标框和输出宽高计算适配倍率。平移使用连续缓动；倍率在对数空间插值，使推近和拉远更均匀。镜头稳定后可读停留，示例不额外添加持续漂移。

初始镜头、任意时刻镜头与元素状态都必须由`t`独立算出。自由浏览的拖动位置不能污染导出状态；`renderAt(t)`总是进入视频演示状态。`?render=1`隐藏资源操作界面，保留完整输出画面。

## 时间轴衔接

`normalize_timeline.py`读取主流程最终时间轴，输出`duration_ms/lines/tokens`。`resolve_anchors.py`接受带`scenes[].beats[]`的语义计划并解析词组锚点。Agent把解析后的毫秒时间转换为正文秒数，同时保存原line_id/token来源；该步骤仍需理解文案，不按SRT行机械生成镜头。插入封面时不改写ASR；所有固定画面层和音轨使用同一正文偏移。

## 用户素材与导出

原图、音频和视频只读；复制需要的文件到当前任务。媒体探测用`probe_media.py`。不合成人物、不提交剪映草稿。固定标题和封面按所选模式使用本期文案与项目配置，不凭空沿用其他视频的系列名或宣传结论。成品字幕的默认启用方式由横屏／竖屏模式决定，纯素材无文本时不编造字幕；实现见[底部字幕规范](subtitles.md)。

页面暴露`window.READY`、最终播放时长`window.END`与`window.renderAt(t)`。自由资源入口还提供总览、区域聚焦和组件聚焦。渲染器逐帧调用同一renderAt，审片与成品共享动画计算；集成封面和配音需要项目播放器接入，共享演示播放器不会因增加JSON字段自动具备这些行为。
