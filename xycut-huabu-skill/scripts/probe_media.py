#!/usr/bin/env python3
"""只读探测用户提供的图片、视频和音频素材。"""

from __future__ import annotations

import argparse
import json
import mimetypes
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


class ProbeError(ValueError):
    pass


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json_new(path: Path, data: Any) -> None:
    if path.exists():
        raise ProbeError(f"拒绝覆盖已有输出：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def get_materials(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        materials = document
    elif isinstance(document, dict):
        materials = document.get("materials")
    else:
        materials = None
    if not isinstance(materials, list):
        raise ProbeError("输入 JSON 必须是 materials 数组，或包含 materials 数组的对象")
    result = []
    for index, item in enumerate(materials):
        if isinstance(item, str):
            result.append({"material_id": f"material_{index + 1:03d}", "path": item})
        elif isinstance(item, dict):
            if not item.get("path"):
                raise ProbeError(f"materials[{index}] 缺少 path")
            copy = dict(item)
            copy.setdefault("material_id", f"material_{index + 1:03d}")
            result.append(copy)
        else:
            raise ProbeError(f"materials[{index}] 必须是路径字符串或对象")
    return result


def ratio_string(width: int | None, height: int | None) -> str | None:
    if not width or not height:
        return None
    from math import gcd

    divisor = gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def parse_fraction(value: Any) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        return round(float(Fraction(str(value))), 6)
    except (ValueError, ZeroDivisionError):
        return None


def run_ffprobe(path: Path, ffprobe: str) -> dict[str, Any]:
    command = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError(f"ffprobe 执行失败：{exc}") from exc
    if completed.returncode != 0:
        message = completed.stderr.strip()[-1000:] or f"退出码 {completed.returncode}"
        raise ProbeError(f"ffprobe 无法读取素材：{message}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError("ffprobe 返回了无效 JSON") from exc


def probe_image_pillow(path: Path) -> dict[str, Any] | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as image:
            width, height = image.size
            return {
                "media_type": "image",
                "width": width,
                "height": height,
                "aspect_ratio": ratio_string(width, height),
                "image_format": image.format,
                "color_mode": image.mode,
                "animated": bool(getattr(image, "is_animated", False)),
                "frame_count": int(getattr(image, "n_frames", 1)),
                "probe_backend": "Pillow",
            }
    except Exception as exc:  # Pillow 为多种格式抛出不同异常类型
        raise ProbeError(f"Pillow 无法读取图片：{exc}") from exc


def summarize_ffprobe(raw: dict[str, Any]) -> dict[str, Any]:
    streams = raw.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    format_info = raw.get("format", {})
    duration_value = format_info.get("duration")
    if duration_value in (None, "N/A") and video:
        duration_value = video.get("duration")
    duration_ms = None
    if duration_value not in (None, "N/A"):
        try:
            duration_ms = int(round(float(duration_value) * 1000))
        except (TypeError, ValueError):
            duration_ms = None
    width = int(video["width"]) if video and video.get("width") else None
    height = int(video["height"]) if video and video.get("height") else None
    if video and duration_ms and duration_ms > 0:
        media_type = "video"
    elif video and not audio:
        media_type = "image"
    elif audio:
        media_type = "audio"
    else:
        media_type = "unknown"
    return {
        "media_type": media_type,
        "width": width,
        "height": height,
        "aspect_ratio": ratio_string(width, height),
        "duration_ms": duration_ms,
        "fps": parse_fraction(video.get("avg_frame_rate")) if video else None,
        "frame_count": int(video["nb_frames"]) if video and str(video.get("nb_frames", "")).isdigit() else None,
        "video_codec": video.get("codec_name") if video else None,
        "pixel_format": video.get("pix_fmt") if video else None,
        "has_audio": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "sample_rate": int(audio["sample_rate"]) if audio and str(audio.get("sample_rate", "")).isdigit() else None,
        "format_name": format_info.get("format_name"),
        "probe_backend": "ffprobe",
    }


def probe_one(material: dict[str, Any], base_dir: Path, ffprobe: str | None) -> dict[str, Any]:
    raw_path = Path(str(material["path"]))
    path = raw_path if raw_path.is_absolute() else (base_dir / raw_path)
    path = path.resolve()
    result: dict[str, Any] = {
        "material_id": str(material["material_id"]),
        "path": str(path),
        "description": material.get("description"),
        "preferred_usage": material.get("preferred_usage"),
        "exists": path.is_file(),
        "status": "error",
    }
    if not path.is_file():
        result["error"] = "文件不存在或不是普通文件"
        return result
    result["size_bytes"] = path.stat().st_size
    result["mime_type"] = mimetypes.guess_type(path.name)[0]
    try:
        details = None
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            details = probe_image_pillow(path)
        if details is None:
            if not ffprobe:
                raise ProbeError("未找到 ffprobe，且 Pillow 无法探测该素材")
            details = summarize_ffprobe(run_ffprobe(path, ffprobe))
        result.update(details)
        result["status"] = "ok"
    except ProbeError as exc:
        result["error"] = str(exc)
    return result


def probe(document: Any, base_dir: Path, ffprobe: str | None) -> dict[str, Any]:
    materials = get_materials(document)
    probed = [probe_one(material, base_dir, ffprobe) for material in materials]
    ok_count = sum(1 for item in probed if item["status"] == "ok")
    return {
        "schema_version": "1.0",
        "materials": probed,
        "summary": {
            "material_count": len(probed),
            "ok_count": ok_count,
            "error_count": len(probed) - ok_count,
            "ffprobe": ffprobe,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="只读探测 materials JSON 中的图片、视频和音频，不修改素材。")
    parser.add_argument("input", type=Path, help="包含 materials 数组的输入 JSON")
    parser.add_argument("output", type=Path, help="新建的探测结果 JSON；已存在时拒绝覆盖")
    parser.add_argument("--ffprobe", help="ffprobe 可执行文件路径；省略时从 PATH 查找")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.input.resolve() == args.output.resolve():
            raise ProbeError("输出不能覆盖输入")
        ffprobe = args.ffprobe or shutil.which("ffprobe")
        if ffprobe and not Path(ffprobe).is_file() and shutil.which(ffprobe) is None:
            raise ProbeError(f"ffprobe 不存在：{ffprobe}")
        result = probe(read_json(args.input), args.input.resolve().parent, ffprobe)
        write_json_new(args.output, result)
    except (OSError, json.JSONDecodeError, ProbeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    print(f"素材探测结果：{args.output}")
    print(f"ok={result['summary']['ok_count']}，errors={result['summary']['error_count']}")
    return 0 if result["summary"]["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
