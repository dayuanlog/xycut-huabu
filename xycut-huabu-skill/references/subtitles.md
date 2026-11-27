# 底部字幕与重点强调

字幕是否启用由制作模式和用户选择决定：横屏按任务需求或已有设置，竖屏默认启用底部字幕。没有口播文本的纯素材不编造字幕，画布里的重点文字也不等于完整字幕。用户指定后续由XYCut/剪映加字幕时关闭本层，避免重复。

## 时间与显示

- 复用`normalize_timeline.py`输出的最终`lines/tokens`，毫秒转换为正文秒数。与镜头、配音共用同一映射；有前置封面时播放器先将最终播放时间减去封面时长，再调用字幕render。不要重新识别旧音频，也不修改ASR原件来适配字幕动画。
- 字词齐全时可以按实际字词时间逐步显示；英文单词没有逐字母ASR时整词显示。仅有行级时间则整句出现，明确精度，不平均编造逐字时间。
- 单句提前占据完整排版宽度，未到时刻的字词不可见但保留版面，避免每多一个字整句就左右跳动。长句重新断行或按语义拆分，检查最多两行是否可读，不把字号不断缩小来塞内容。
- 光标紧跟已显示内容，轻微闪动，句末短暂停留后退出；不要让所有字连续弹跳。打字、光标和扫光均由`t`计算，暂停时冻结，前后跳转应得到相同状态。
- 显示文案与ASR词存在已确认的专名修正时，用`display_aliases`将正确显示词映射到原token ID及其时间范围。多个误识别词可合并成一个正确专名，不据此虚构字母级时间。

## 主题适配、动效多样化与用户自定义

不要让所有模板和项目的底部字幕都套用完全一样的白字样式和单一打字机动效。底部字幕的视觉包装与动效属于整体美术风格的一部分，应随主题适配并支持用户自由定制：

- **样式随主题适配**：按项目视觉体系（暗黑科技、暖白板、黑板粉笔、奶油手账、森系绿白、潮酷撞色等）独立设定字幕字体、字重、主色、描边/阴影、底衬/胶囊条与关键词强调手法（如下划线、荧光色块、双色反白、手绘划重点、暖色印章等）；浅色画布优先深墨色文字配轻微高光，人物全屏实拍段确保文字高对比度可读。
- **动效按风格多样化**：除「逐字打字机 + 光标」外，可根据视频节奏与主题选用**逐词弹入（pop-in）、柔和上浮淡入（fade-up）、高光/墨迹扫过（highlight sweep）、整句切入 + 关键词变色/轻放大**等不同动效。无论采用哪种动效，均须满足确定性时间契约：完全由绝对时间 `t` 计算、暂停即冻结、随机跳转状态一致、且单句提前占位避免左右跳动。
- **用户自定义优先**：用户明确指定字幕样式、字体、颜色、位置、动效，或要求替换自定义字幕组件时，优先按用户要求覆盖默认样式，不强行回退到共享 `subtitles.js` 的默认外观。

## 普通、关键词和重点句

以普通字幕为主，按语义挑少量重点，不要求每句都强调。

| 类型 | 建议表现 |
|---|---|
| 普通说明 | 偏白色、适当加粗、轻阴影或细描边；按字词显示，或整句显示 |
| 关键词 | 品牌/主题强调色，可加短下划线；读到该词时再强调 |
| 少数核心句 | 短暂扫光或轻发光，随后恢复清晰；不循环闪烁、不整片持续放大 |

强调词必须来自本次文案。示例中的“复制提示词”“素材库”“批量生成”只是工具介绍案例的选择，不应照搬到其他行业。配色跟随主题，不把青色规定为所有资源库的通用色。

## 画面与镜头

- 字幕挂在`#stage`等输出容器内，与`#world`同级，不能放进跟随镜头平移缩放的世界元素中。预览侧栏的文案仍可保留用于检查。
- 先规划底部安全区。横屏或无独立framing时，摄影机可用剩余高度适配目标、上移取景中心；竖屏中央1:1模式按独立content_rect取景，字幕不能再把主体中心推走。背景继续铺满输出，不强行给每个组件增加黑色底栏。
- 本次横屏案例的起点为1920×1080、54px字体、底部54px、预留216px；这些都是可调整参数。其他比例、两行字幕、不同字体需要按最终输出检查并重新设置。
- 竖屏中央1:1版式默认将字幕向中央靠拢：1080×1920时使用`top:1530`、`font_size:43`、`line_height:1.45`、`margin_x:85`、`safe_bottom:0`。字幕居中，最多两行；第一行上沿距正文下沿约30px，两行向下展开，不随字词揭示上下或左右跳动。`top`为可选数值，设置后优先于`bottom`；不设置时保持原底部锚定行为。检查最长句的实际字词边界及光标，避免两行字幕向上挤入正文，也避免不断缩小字号。其他尺寸等比例换算，固定片内标题的位置见[竖屏制作](portrait-framing.md)。
- 重点关注框应完整落在字幕区上方；镜头边缘可以出现虚化的次要内容。检查浅色真实截图上的字幕对比度，按需使用柔和底部渐暗，不能仅依赖发光。
- 自由浏览画布时隐藏字幕并取消预留；演示/导出时按所选模式启用。无独立framing的横屏在关闭字幕后恢复相应构图；竖屏中央取景在普通、强调、关闭三种字幕模式下保持相同主体中心。无需修改页面或组件的世界坐标。

## 可复用代码与项目设置

复制本Skill的`assets/runtime/subtitles.js`和支持可选字幕预留的`assets/runtime/camera.js`到当前项目；自定义摄影机已有其他行为时只合入`fit`与`matrix`的安全区逻辑，不直接覆盖。

字幕数据、强调词和外观记录到本次`canvas-plan.json`的`subtitle_settings`。默认值只属于该项目；不要把本次句子和时间写进共享运行时。

```javascript
// 在scene建立后、player初始化前执行。脚本本身只提供工厂，不自动添加字幕。
const params = new URLSearchParams(location.search);
const config = CANVAS_PLAN.subtitle_settings;
window.CanvasSubtitles = CanvasSubtitleTrack.create({
  stage: document.querySelector('#stage'),
  timeline: FINAL_TIMELINE,
  output: CANVAS_PLAN.output,
  config,
  mode: params.get('subtitles') || config.mode,
  requestRender: () => CanvasExplorer.getMode() === 'demo'
    ? window.renderAt(CanvasExplorer.getTime()) : undefined
});
CANVAS_PLAN.subtitle_settings = CanvasSubtitles.settings;
const previousRender = CanvasScene.render;
CanvasScene.render = t => { previousRender(t); CanvasSubtitles.render(t); };
```

项目配置示例（`line_id`和token ID均替换为本项目实际值）：

```json
{
  "mode": "emphasis",
  "reveal": "typewriter",
  "font_size": 54,
  "bottom": 54,
  "safe_bottom": 216,
  "margin_x": 120,
  "color": "#f7fafc",
  "accent": "#00c1cd",
  "keywords": {"line_008": ["复制提示词"]},
  "strong_lines": ["line_004"],
  "display_aliases": {}
}
```

`normal`为普通白字，`emphasis`为少量关键词强调，`off`为关闭；`reveal`支持`typewriter`或`sentence`。强调和扫光在普通模式下关闭。没有tokens的行自动整句显示。

专名修正只改变字幕显示，例如某句中的`Workbuddy`被ASR分成两个误识别词：

```json
{"display_aliases":{"line_012":[
  {"text":"Workbuddy","token_ids":["token_005","token_006"]}
]}}
```

预览侧栏可绑定三种模式。`await CanvasSubtitles.setMode(value)`返回重绘结果；连续操作时等待它结束，避免与媒体seek重叠。保存用户选择到项目配置，导出时使用相同模式，不能只记在当前浏览器内存中。

## 导出与核对

仍使用`render_project.mjs`逐帧调用同一`renderAt(t)`，不另做一套字幕动画。初始化代码读取查询参数后可选择：

```text
--query "render=1&subtitles=emphasis"
--query "render=1&subtitles=normal"
--query "render=1&subtitles=off"
```

先核对有代表性的长句、英文专名、关键词和句尾：无漏字、无未来文字、光标没有越界、强调不过量，关注框未被字幕挡住；检查暂停、随机跳转和关闭字幕后的构图。切换字幕模式无需更换音频。字幕烧录进画面需要重新渲染画面，不能只合成音频便声称已更新视频。

修改共享字幕运行时后，可运行`scripts/check_subtitles.mjs --playwright-module <已安装的模块路径> --browser <浏览器路径>`进行轻量行为检查；该脚本使用明确的测试时间数据，不运行ASR或下载浏览器。
