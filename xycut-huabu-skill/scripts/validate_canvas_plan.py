"""校验世界坐标、组件关注框、镜头窗口与局部动作；不修改输入。"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def validate(plan):
    errors = []
    warnings = []

    def check(ok, message):
        if not ok:
            errors.append(message)

    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    def box(value, name, parent=None):
        keys = ('x', 'y', 'width', 'height')
        valid = isinstance(value, dict) and all(number(value.get(k)) for k in keys)
        check(valid, name + '必须包含有限数值x/y/width/height')
        if not valid:
            return False
        check(value['width'] > 0 and value['height'] > 0, name + '尺寸必须大于零')
        check(value['x'] >= 0 and value['y'] >= 0, name + '位置不能为负')
        if parent:
            check(value['x'] + value['width'] <= parent['width'] + .01 and value['y'] + value['height'] <= parent['height'] + .01, name + '超出父级边界')
        return True

    if not isinstance(plan, dict):
        return {'ok': False, 'errors': ['顶层必须为JSON对象'], 'warnings': []}
    duration = plan.get('duration')
    check(number(duration) and duration > 0, 'duration必须为正秒数')
    duration = duration if number(duration) and duration > 0 else 0
    output, world = plan.get('output', {}), plan.get('world', {})
    for label, obj in [('output', output), ('world', world)]:
        for key in ('width', 'height'):
            check(number(obj.get(key)) and obj[key] > 0, label + '.' + key + '必须大于零')
    check(number(output.get('fps')) and output['fps'] > 0, 'fps必须为正数')
    if errors:
        return {'ok': False, 'errors': errors, 'warnings': warnings}
    mode = plan.get('presentation_mode')
    if mode is not None:
        check(mode in ('landscape', 'portrait', 'custom'), 'presentation_mode必须为landscape、portrait或custom')
        if mode in ('landscape', 'portrait'):
            ratio = 16 / 9 if mode == 'landscape' else 9 / 16
            check(abs(output['width'] / output['height'] - ratio) < .000001, 'presentation_mode与output比例不一致')
    intro = plan.get('intro')
    lead = 0
    if intro is not None:
        check(isinstance(intro, dict), 'intro必须为对象')
        if isinstance(intro, dict):
            value = intro.get('duration')
            valid_lead = number(value) and value >= 0
            check(valid_lead, 'intro.duration必须为非负秒数')
            lead = value if valid_lead else 0
            if 'frames' in intro:
                frames = intro['frames']
                valid_frames = isinstance(frames, int) and not isinstance(frames, bool) and frames >= 0
                check(valid_frames, 'intro.frames必须为非负整数')
                if valid_frames and valid_lead:
                    check(abs(lead - frames / output['fps']) < .000001, 'intro.duration必须等于intro.frames/output.fps')
    content = plan.get('content_duration')
    valid_content = number(content) and content > 0
    if content is not None or lead > 0:
        check(valid_content, '有片头时需提供正数content_duration')
        if valid_content:
            check(abs(duration - content - lead) < .001, 'duration必须等于content_duration+intro.duration')
    time_limit = content if valid_content else duration
    framing = plan.get('framing')
    if framing is not None:
        check(isinstance(framing, dict), 'framing必须为对象')
        if isinstance(framing, dict):
            rect = framing.get('content_rect')
            if box(rect, 'framing.content_rect', output) and framing.get('mode') == 'center-square':
                side = min(output['width'], output['height'])
                check(abs(rect['width']-side)<.01 and abs(rect['height']-side)<.01, 'center-square必须为输出内最大正方形')
                check(abs(rect['x']+rect['width']/2-output['width']/2)<.01 and abs(rect['y']+rect['height']/2-output['height']/2)<.01, 'center-square必须位于输出中心')
    boards, components, targets = {}, {}, {'overview'}
    for board in plan.get('boards', []):
        key = board.get('id')
        check(bool(key) and key not in targets, '区域ID为空或重复：' + str(key))
        if box(board, '区域 ' + str(key), world):
            boards[key] = board
            targets.add(key)
    check(bool(boards), '至少需要一个区域')
    for component in plan.get('components', []):
        key = component.get('id')
        check(bool(key) and key not in targets, '组件ID为空或重复：' + str(key))
        parent = boards.get(component.get('board_id'))
        check(parent is not None, '组件引用不存在的区域：' + str(key))
        if not box(component.get('bounds'), '组件 ' + str(key), parent):
            continue
        components[key] = component
        targets.add(key)
        if component.get('kind') == 'library':
            check(isinstance(component.get('module_id'), str) and bool(component['module_id']), '库组件必须指定module_id：' + str(key))
            motion = component.get('motion', {})
            start, span, cues = motion.get('start'), motion.get('duration'), motion.get('cues')
            valid_motion = number(start) and number(span) and start >= 0 and span > 0
            check(valid_motion, '库组件motion.start/duration无效：' + str(key))
            if valid_motion:
                check(start + span <= time_limit + .001, '库组件动作超过正文时长：' + str(key))
            valid_cues = isinstance(cues, list) and bool(cues) and all(number(v) and v >= 0 for v in cues)
            check(valid_cues, '库组件必须提供非负局部cues：' + str(key))
            if valid_cues:
                check(all(cues[i] > cues[i-1] for i in range(1, len(cues))), '库组件cues必须递增：' + str(key))
                if valid_motion:
                    check(cues[-1] < span, '库组件最后cue需早于动作结束：' + str(key))
        for focus in component.get('focuses', []):
            focus_id = str(key) + '/' + str(focus.get('id'))
            check(bool(focus.get('id')) and focus_id not in targets, '关注框ID为空或重复：' + focus_id)
            box(focus.get('bounds'), '关注框 ' + focus_id, component['bounds'])
            targets.add(focus_id)
    shots = plan.get('shots', [])
    check(bool(shots), '至少需要一个镜头')
    previous = -1
    ids = set()
    for i, shot in enumerate(shots):
        key = shot.get('id')
        check(bool(key) and key not in ids, '镜头ID为空或重复：' + str(key))
        ids.add(key)
        check(shot.get('target') in targets, '镜头目标不存在：' + str(shot.get('target')))
        at, move = shot.get('at'), shot.get('move')
        valid = number(at) and number(move)
        check(valid, '镜头at/move必须为有限秒数：' + str(key))
        if not valid:
            continue
        check(at > previous and 0 <= at < time_limit, '镜头时间必须递增且在正文范围内：' + str(key))
        check(move >= 0 and at + move <= time_limit, '镜头移动窗口无效：' + str(key))
        if i == 0:
            check(at == 0 and move == 0, '第一镜头需从0秒稳定构图开始')
        if i + 1 < len(shots) and number(shots[i+1].get('at')):
            check(at + move <= shots[i+1]['at'], '镜头移动越过下一个镜头：' + str(key))
        padding = shot.get('padding', .12)
        check(number(padding) and 0 <= padding < .45, '镜头padding需在[0,.45)之间：' + str(key))
        if 'travel_scale' in shot:
            check(number(shot['travel_scale']) and shot['travel_scale'] > 0, 'travel_scale必须为正数')
        previous = at
    for beat in plan.get('beats', []):
        check(beat.get('component_id') in components, '局部动作引用不存在的组件')
        start, end = beat.get('start'), beat.get('end')
        check(number(start) and number(end) and 0 <= start < end <= time_limit, '局部动作窗口无效')
    if plan.get('timing_precision') == 'demo':
        warnings.append('当前为未绑定真实配音的演示时钟；正式项目必须使用最终ASR锚点。')
    return {'ok': not errors, 'errors': errors, 'warnings': warnings, 'counts': {'boards': len(boards), 'components': len(components), 'shots': len(shots)}}


def main():
    parser = argparse.ArgumentParser(description='校验画布视频计划')
    parser.add_argument('plan', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = validate(json.loads(args.plan.read_text(encoding='utf-8-sig')))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
