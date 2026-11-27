#!/usr/bin/env python3
"""将 XYCUT 常见时间线 JSON 归一化为语义动画使用的最终目标时钟。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


TIME_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[,.](\d{1,3}))?$")


class TimelineError(ValueError):
    pass


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json_new(path: Path, data: Any) -> None:
    if path.exists():
        raise TimelineError(f"拒绝覆盖已有输出：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_clock(value: Any, *, milliseconds: bool = False) -> int:
    if isinstance(value, bool) or value is None:
        raise TimelineError(f"无效时间值：{value!r}")
    if isinstance(value, (int, float)):
        result = float(value) if milliseconds else float(value) * 1000
        return int(round(result))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise TimelineError("时间字符串不能为空")
        match = TIME_RE.match(stripped)
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2))
            seconds = int(match.group(3))
            fraction = (match.group(4) or "0").ljust(3, "0")[:3]
            return ((hours * 60 + minutes) * 60 + seconds) * 1000 + int(fraction)
        try:
            number = float(stripped)
        except ValueError as exc:
            raise TimelineError(f"无法解析时间：{value!r}") from exc
        return int(round(number if milliseconds else number * 1000))
    raise TimelineError(f"不支持的时间类型：{type(value).__name__}")


def pick_time(item: dict[str, Any], side: str) -> int:
    candidates = (
        f"target_{side}_ms",
        f"{side}_ms",
        f"target_{side}",
        side,
    )
    for key in candidates:
        if key in item and item[key] is not None:
            return parse_clock(item[key], milliseconds=key.endswith("_ms"))
    raise TimelineError(f"缺少 {side} 时间")


def get_lines(document: Any) -> tuple[list[Any], dict[str, Any]]:
    if isinstance(document, list):
        return document, {}
    if not isinstance(document, dict):
        raise TimelineError("输入必须是 JSON 对象或 line 数组")
    value = document.get("lines", document.get("line_timeline"))
    if isinstance(value, dict):
        value = value.get("lines", value.get("items"))
    if not isinstance(value, list):
        raise TimelineError("未找到 lines 或 line_timeline 数组")
    return value, document


def normalize_tokens(line: dict[str, Any], line_start: int, line_end: int) -> list[dict[str, Any]]:
    source = line.get("tokens")
    if source is None:
        source = line.get("words")
    if source is None:
        source = line.get("chars")
    if source is None:
        return []
    if not isinstance(source, list):
        raise TimelineError("tokens/words/chars 必须是数组")

    normalized: list[dict[str, Any]] = []
    char_cursor = 0
    parent_text = str(line.get("text", line.get("content", line.get("sentence", ""))))
    for index, raw in enumerate(source):
        if not isinstance(raw, dict):
            raise TimelineError(f"第 {index + 1} 个 token 不是对象")
        text = raw.get("text", raw.get("word", raw.get("char")))
        if text is None:
            raise TimelineError(f"第 {index + 1} 个 token 缺少 text/word/char")
        text = str(text)
        start = pick_time(raw, "start")
        end = pick_time(raw, "end")
        if start < line_start or end > line_end or end <= start:
            raise TimelineError(
                f"token {text!r} 时间 [{start}, {end}] 超出父句 [{line_start}, {line_end}]"
            )
        char_start = raw.get("source_char_start", raw.get("char_start"))
        if char_start is None:
            located = parent_text.find(text, char_cursor)
            char_start = located if located >= 0 else char_cursor
        char_end = raw.get("source_char_end", raw.get("char_end", int(char_start) + len(text)))
        token = {
            "token_id": str(raw.get("token_id", raw.get("word_id", f"token_{index + 1:03d}"))),
            "text": text,
            "target_start_ms": start,
            "target_end_ms": end,
            "source_word_index": int(raw.get("source_word_index", raw.get("word_index", index))),
            "source_char_start": int(char_start),
            "source_char_end": int(char_end),
        }
        normalized.append(token)
        char_cursor = token["source_char_end"]

    for previous, current in zip(normalized, normalized[1:]):
        if current["target_start_ms"] < previous["target_start_ms"]:
            raise TimelineError("token 时间必须按 target_start_ms 递增")
    return normalized


def normalize(document: Any) -> dict[str, Any]:
    lines, root = get_lines(document)
    normalized_lines: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(lines):
        if not isinstance(raw, dict):
            raise TimelineError(f"第 {index + 1} 个 line 不是对象")
        line_id = str(raw.get("line_id", raw.get("id", f"line_{index + 1:04d}")))
        if line_id in seen_ids:
            raise TimelineError(f"重复 line_id：{line_id}")
        seen_ids.add(line_id)
        text = str(raw.get("text", raw.get("content", raw.get("sentence", ""))))
        start = pick_time(raw, "start")
        end = pick_time(raw, "end")
        if start < 0 or end <= start:
            raise TimelineError(f"{line_id} 时间无效：[{start}, {end}]")
        try:
            tokens = normalize_tokens(raw, start, end)
        except TimelineError as exc:
            raise TimelineError(f"{line_id}: {exc}") from exc
        normalized_lines.append(
            {
                "line_id": line_id,
                "text": text,
                "target_start_ms": start,
                "target_end_ms": end,
                "tokens": tokens,
            }
        )

    normalized_lines.sort(key=lambda item: (item["target_start_ms"], item["target_end_ms"], item["line_id"]))
    duration = max((line["target_end_ms"] for line in normalized_lines), default=0)
    root_duration = None
    if isinstance(root, dict):
        root_duration = root.get("duration_ms", root.get("timeline_duration_ms"))
    if root_duration is not None:
        duration = parse_clock(root_duration, milliseconds=True)
        if normalized_lines and duration < normalized_lines[-1]["target_end_ms"]:
            raise TimelineError("duration_ms 小于最后一条 line 的结束时间")

    revision_payload = {
        "duration_ms": duration,
        "lines": normalized_lines,
    }
    canonical = json.dumps(revision_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    revision = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    result = {
        "schema_version": "1.0",
        "timeline_revision": revision,
        "duration_ms": duration,
        "lines": normalized_lines,
    }
    if isinstance(root, dict) and root.get("canvas") is not None:
        result["canvas"] = deepcopy(root["canvas"])
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="归一化 XYCUT 最终时间线，不修改输入文件。")
    parser.add_argument("input", type=Path, help="输入 JSON，可包含 lines 或 line_timeline")
    parser.add_argument("output", type=Path, help="新建的归一化 JSON；已存在时拒绝覆盖")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.input.resolve() == args.output.resolve():
            raise TimelineError("输入和输出不能是同一路径")
        normalized = normalize(read_json(args.input))
        write_json_new(args.output, normalized)
    except (OSError, json.JSONDecodeError, TimelineError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    print(f"已写入：{args.output}")
    print(f"timeline_revision：{normalized['timeline_revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
