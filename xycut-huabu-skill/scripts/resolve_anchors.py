#!/usr/bin/env python3
"""依据最终字词时间线解析 visual plan 中的短语或范围锚点。"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


class AnchorError(ValueError):
    pass


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json_new(path: Path, data: Any) -> None:
    if path.exists():
        raise AnchorError(f"拒绝覆盖已有输出：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def iter_beats(plan: dict[str, Any]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    scenes = plan.get("scenes")
    if not isinstance(scenes, list):
        raise AnchorError("visual plan 缺少 scenes 数组")
    for scene in scenes:
        if not isinstance(scene, dict):
            raise AnchorError("scene 必须是对象")
        beats = scene.get("beats", scene.get("states", []))
        if not isinstance(beats, list):
            raise AnchorError(f"scene {scene.get('scene_id', '<unknown>')} 的 beats/states 必须是数组")
        for beat in beats:
            if not isinstance(beat, dict):
                raise AnchorError("beat/state 必须是对象")
            yield scene, beat


def select_line_ids(scene: dict[str, Any], beat: dict[str, Any], anchor: dict[str, Any]) -> list[str]:
    value = anchor.get("line_id", beat.get("line_id"))
    if value is not None:
        return [str(value)]
    value = anchor.get("line_ids", beat.get("line_ids", scene.get("line_ids")))
    if value is None:
        return []
    if not isinstance(value, list):
        raise AnchorError("line_ids 必须是数组")
    return [str(item) for item in value]


def normalize_anchor(beat: dict[str, Any]) -> dict[str, Any]:
    raw = beat.get("anchor")
    if isinstance(raw, str):
        anchor: dict[str, Any] = {"anchor_text": raw}
    elif isinstance(raw, dict):
        anchor = deepcopy(raw)
    elif raw is None:
        anchor = {}
    else:
        raise AnchorError("anchor 必须是字符串或对象")
    for key in (
        "anchor_text",
        "source_word_range",
        "source_word_start",
        "source_word_end",
        "source_char_range",
        "source_char_start",
        "source_char_end",
        "occurrence",
    ):
        if key not in anchor and key in beat:
            anchor[key] = beat[key]
    return anchor


def parse_range(anchor: dict[str, Any], kind: str) -> tuple[int, int] | None:
    packed = anchor.get(f"source_{kind}_range")
    if packed is not None:
        if not isinstance(packed, list) or len(packed) != 2:
            raise AnchorError(f"source_{kind}_range 必须是 [start, end]，end 为开区间")
        start, end = int(packed[0]), int(packed[1])
    elif f"source_{kind}_start" in anchor or f"source_{kind}_end" in anchor:
        if f"source_{kind}_start" not in anchor or f"source_{kind}_end" not in anchor:
            raise AnchorError(f"source_{kind}_start/end 必须同时提供")
        start = int(anchor[f"source_{kind}_start"])
        end = int(anchor[f"source_{kind}_end"])
    else:
        return None
    if start < 0 or end <= start:
        raise AnchorError(f"source_{kind}_range 无效：[{start}, {end})")
    return start, end


def span_from_tokens(line: dict[str, Any], selected: list[dict[str, Any]]) -> tuple[int, int]:
    if not selected:
        raise AnchorError(f"{line['line_id']} 的锚点没有覆盖任何 token")
    return int(selected[0]["target_start_ms"]), int(selected[-1]["target_end_ms"])


def resolve_in_line(line: dict[str, Any], anchor: dict[str, Any]) -> list[dict[str, Any]]:
    tokens = line.get("tokens", [])
    word_range = parse_range(anchor, "word")
    char_range = parse_range(anchor, "char")
    if word_range is not None:
        if not tokens:
            raise AnchorError(f"{line['line_id']} 没有 tokens，无法解析 word range")
        start, end = word_range
        chosen = [token for token in tokens if start <= int(token.get("source_word_index", -1)) < end]
        begin, finish = span_from_tokens(line, chosen)
        return [{"char_start": None, "char_end": None, "start_ms": begin, "end_ms": finish}]
    if char_range is not None:
        if not tokens:
            raise AnchorError(f"{line['line_id']} 没有 tokens，无法解析 char range")
        start, end = char_range
        chosen = [
            token
            for token in tokens
            if int(token.get("source_char_end", 0)) > start
            and int(token.get("source_char_start", 0)) < end
        ]
        begin, finish = span_from_tokens(line, chosen)
        return [{"char_start": start, "char_end": end, "start_ms": begin, "end_ms": finish}]

    phrase = anchor.get("anchor_text")
    if phrase is None:
        raise AnchorError("锚点缺少 anchor_text、source_word_range 或 source_char_range")
    phrase = str(phrase)
    if not phrase:
        raise AnchorError("anchor_text 不能为空")
    text = str(line.get("text", ""))
    matches: list[dict[str, Any]] = []
    cursor = 0
    while True:
        index = text.find(phrase, cursor)
        if index < 0:
            break
        end = index + len(phrase)
        if tokens:
            chosen = [
                token
                for token in tokens
                if int(token.get("source_char_end", 0)) > index
                and int(token.get("source_char_start", 0)) < end
            ]
            if chosen:
                start_ms, end_ms = span_from_tokens(line, chosen)
                matches.append({"char_start": index, "char_end": end, "start_ms": start_ms, "end_ms": end_ms})
        elif phrase == text:
            matches.append(
                {
                    "char_start": 0,
                    "char_end": len(text),
                    "start_ms": int(line["target_start_ms"]),
                    "end_ms": int(line["target_end_ms"]),
                }
            )
        cursor = index + max(1, len(phrase))
    return matches


def resolve_anchor(
    scene: dict[str, Any], beat: dict[str, Any], anchor: dict[str, Any], lines_by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    requested_ids = select_line_ids(scene, beat, anchor)
    candidates = []
    if requested_ids:
        for line_id in requested_ids:
            if line_id not in lines_by_id:
                raise AnchorError(f"引用不存在的 line_id：{line_id}")
            candidates.append(lines_by_id[line_id])
    else:
        candidates = list(lines_by_id.values())

    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for line in candidates:
        for match in resolve_in_line(line, anchor):
            matches.append((line, match))
    matches.sort(key=lambda pair: (pair[1]["start_ms"], pair[0]["line_id"]))
    if not matches:
        label = anchor.get("anchor_text", anchor)
        raise AnchorError(f"找不到锚点：{label!r}")
    occurrence = anchor.get("occurrence")
    if occurrence is None and len(matches) != 1:
        raise AnchorError(f"锚点匹配到 {len(matches)} 处，请指定 line_id 或 occurrence（从 1 开始）")
    index = int(occurrence or 1) - 1
    if index < 0 or index >= len(matches):
        raise AnchorError(f"occurrence={index + 1} 超出 {len(matches)} 个匹配结果")
    line, match = matches[index]
    resolved = deepcopy(anchor)
    resolved.update(
        {
            "line_id": line["line_id"],
            "anchor_start_ms": match["start_ms"],
            "anchor_end_ms": match["end_ms"],
            "source_char_start": match["char_start"],
            "source_char_end": match["char_end"],
        }
    )
    return resolved


def resolve(plan: dict[str, Any], timeline: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict) or not isinstance(timeline, dict):
        raise AnchorError("plan 和 timeline 必须是 JSON 对象")
    lines = timeline.get("lines")
    if not isinstance(lines, list):
        raise AnchorError("timeline 缺少归一化 lines 数组")
    lines_by_id = {str(line["line_id"]): line for line in lines}
    revision = timeline.get("timeline_revision")
    plan_revision = plan.get("timeline_revision")
    if plan_revision is not None and revision is not None and plan_revision != revision:
        raise AnchorError("visual plan 的 timeline_revision 与最终时间线不一致")

    output = deepcopy(plan)
    for scene, beat in iter_beats(output):
        beat_id = beat.get("beat_id", beat.get("state_id", "<unknown>"))
        try:
            anchor = normalize_anchor(beat)
            resolved = resolve_anchor(scene, beat, anchor, lines_by_id)
        except AnchorError as exc:
            raise AnchorError(f"beat {beat_id}: {exc}") from exc
        beat["anchor"] = resolved
        beat["line_id"] = resolved["line_id"]
        lead_ms = int(beat.get("lead_ms", 0))
        trigger_ms = resolved["anchor_start_ms"] - lead_ms
        if trigger_ms < 0:
            raise AnchorError(f"beat {beat_id}: lead_ms 使 trigger_ms 小于 0")
        beat["trigger_ms"] = trigger_ms
        beat["anchor_start_ms"] = resolved["anchor_start_ms"]
        beat["anchor_end_ms"] = resolved["anchor_end_ms"]
    output["timeline_revision"] = revision
    output["duration_ms"] = timeline.get("duration_ms", output.get("duration_ms"))
    output["anchors_resolved"] = True
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="把 visual plan 的短语/范围锚点解析为最终目标毫秒。")
    parser.add_argument("timeline", type=Path, help="normalize_timeline.py 生成的最终时间线 JSON")
    parser.add_argument("plan", type=Path, help="待解析的 visual_plan.json")
    parser.add_argument("output", type=Path, help="新建的已解析 visual plan；已存在时拒绝覆盖")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        output_resolved = args.output.resolve()
        if output_resolved in {args.timeline.resolve(), args.plan.resolve()}:
            raise AnchorError("输出不能覆盖输入")
        result = resolve(read_json(args.plan), read_json(args.timeline))
        write_json_new(args.output, result)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, AnchorError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    print(f"已解析锚点并写入：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
