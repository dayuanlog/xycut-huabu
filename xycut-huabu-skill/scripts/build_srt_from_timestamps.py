from __future__ import annotations
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
SPLIT_PUNCT = set('，。！？；,.!?;')
DROP_CHARS = set(' \t\r\n，。！？、；：,.!?;:"“”‘’\'（）()《》【】[]-~～')

def read_json(path: Path) -> Any:
    with path.open('r', encoding='utf-8-sig') as f:
        return json.load(f)

def payload_result(data: Any) -> Any:
    payload = data
    for _ in range(3):
        if isinstance(payload, dict) and isinstance(payload.get('result'), dict):
            next_payload = payload['result']
            if next_payload is payload:
                break
            payload = next_payload
            continue
        break
    return payload

def visible_chars(text: str) -> list[str]:
    return [ch for ch in text.strip() if not ch.isspace()]

def normalized_text(text: str) -> str:
    out: list[str] = []
    for ch in str(text or ''):
        if ch in {'~', '～'}:
            out.append('到')
            continue
        if ch in DROP_CHARS:
            continue
        out.append(ch)
    return ''.join(out)

def source_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        parts = [item.strip().rstrip('，,。.!！?？；;') for item in re.split('(?<=[，。！？；,.!?;])', raw_line)]
        lines.extend((item for item in parts if item))
    if lines:
        return lines
    parts = [item.strip().rstrip('，,。.!！?？；;') for item in re.split('(?<=[，。！？；,.!?;])', text.strip())]
    return [item for item in parts if item]

def bucket_uses_milliseconds(bucket: list[Any]) -> bool:
    durations: list[float] = []
    for raw in bucket:
        if not isinstance(raw, dict):
            continue
        try:
            start = float(raw.get('start_time', raw.get('start', 0)) or 0)
            end = float(raw.get('end_time', raw.get('end', 0)) or 0)
        except (TypeError, ValueError):
            continue
        if end > start:
            durations.append(end - start)
    if not durations:
        return False
    durations.sort()
    median = durations[len(durations) // 2]
    return median > 10

def normalize_word(raw: dict[str, Any], force_milliseconds: bool=False) -> dict[str, Any] | None:
    text = str(raw.get('word') or raw.get('text') or '').strip()
    if not text:
        return None
    start = raw.get('start_time', raw.get('start', 0))
    end = raw.get('end_time', raw.get('end', 0))
    try:
        start_f = float(start)
        end_f = float(end)
    except (TypeError, ValueError):
        return None
    if force_milliseconds or start_f > 1000 or end_f > 1000:
        start_f /= 1000
        end_f /= 1000
    if end_f < start_f:
        return None
    return {'word': text, 'start': round(start_f, 3), 'end': round(end_f, 3)}

def words_from_payload(data: Any) -> list[dict[str, Any]]:
    payload = payload_result(data)
    utterance_buckets: list[Any] = []
    global_buckets: list[Any] = []
    frontend_buckets: list[Any] = []
    if isinstance(payload, dict):
        if isinstance(payload.get('words'), list):
            global_buckets.append(payload['words'])
        if isinstance(payload.get('utterances'), list):
            for utterance in payload['utterances']:
                if isinstance(utterance, dict) and isinstance(utterance.get('words'), list):
                    utterance_buckets.append(utterance['words'])
        addition = payload.get('addition') if isinstance(payload.get('addition'), dict) else {}
        frontend = addition.get('frontend') if isinstance(addition, dict) else None
        if isinstance(frontend, str) and frontend.strip():
            try:
                frontend = json.loads(frontend)
            except json.JSONDecodeError:
                frontend = None
        if isinstance(frontend, dict) and isinstance(frontend.get('words'), list):
            frontend_buckets.append(frontend['words'])
    out: list[dict[str, Any]] = []
    buckets = utterance_buckets or global_buckets or frontend_buckets
    for bucket in buckets:
        force_milliseconds = bucket_uses_milliseconds(bucket if isinstance(bucket, list) else [])
        for raw in bucket:
            if isinstance(raw, dict):
                item = normalize_word(raw, force_milliseconds)
                if item:
                    out.append(item)
    return sorted(out, key=lambda item: (item['start'], item['end']))

def utterances_from_payload(data: Any) -> list[dict[str, Any]]:
    payload = payload_result(data)
    if not isinstance(payload, dict) or not isinstance(payload.get('utterances'), list):
        return []
    out: list[dict[str, Any]] = []
    for raw in payload['utterances']:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get('text') or '').strip()
        raw_words = [item for item in raw.get('words') or [] if isinstance(item, dict)]
        force_milliseconds = bucket_uses_milliseconds(raw_words)
        words = [normalize_word(item, force_milliseconds) for item in raw_words]
        words = [item for item in words if item]
        if words:
            start = words[0]['start']
            end = words[-1]['end']
        else:
            start = float(raw.get('start_time', raw.get('start', 0)) or 0)
            end = float(raw.get('end_time', raw.get('end', 0)) or 0)
            if start > 1000 or end > 1000:
                start /= 1000
                end /= 1000
        if text and end > start:
            parts = source_lines(text)
            if words and len(parts) > 1:
                out.extend(segments_from_source_lines(parts, words))
            else:
                out.append({'text': text.strip().rstrip('，,。.!！?？；;'), 'start': round(start, 3), 'end': round(end, 3), 'words': words})
    return out

def word_text(raw: dict[str, Any]) -> str:
    return str(raw.get('word') or raw.get('text') or '')

def words_with_source_text(line: str, chunk: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source = normalized_text(line)
    lengths = [len(normalized_text(word_text(word))) for word in chunk]
    if not source or sum(lengths) != len(source) or any((length <= 0 for length in lengths)):
        return chunk
    output: list[dict[str, Any]] = []
    cursor = 0
    for word, length in zip(chunk, lengths):
        next_word = dict(word)
        text = source[cursor:cursor + length]
        next_word['word'] = text
        next_word['text'] = text
        output.append(next_word)
        cursor += length
    return output

def segments_from_source_lines_weighted(lines: list[str], words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    weighted_lines = [(line, max(1, len(visible_chars(line)))) for line in lines if line.strip()]
    if not weighted_lines or not words:
        return []
    cursor = 0
    for index, (line, weight) in enumerate(weighted_lines):
        if cursor >= len(words):
            continue
        remaining_lines = len(weighted_lines) - index - 1
        target_text = normalized_text(line)
        end_index = cursor
        if target_text:
            consumed_text = ''
            max_end = len(words) - remaining_lines
            while end_index < max_end:
                consumed_text += normalized_text(word_text(words[end_index]))
                end_index += 1
                if consumed_text == target_text:
                    break
                if len(consumed_text) >= len(target_text) and (not target_text.startswith(consumed_text)):
                    break
            if consumed_text != target_text:
                end_index = cursor
        if end_index <= cursor:
            if remaining_lines <= 0:
                end_index = len(words)
            else:
                consumed_chars = 0
                end_index = cursor
                while end_index < len(words) - remaining_lines and consumed_chars < weight:
                    consumed_chars += max(1, len(visible_chars(word_text(words[end_index]))))
                    end_index += 1
                min_end = cursor + 1
                max_end = len(words) - remaining_lines
                end_index = min(max(end_index, min_end), max_end)
        chunk = words[cursor:end_index]
        cursor = end_index
        if not chunk:
            continue
        chunk = words_with_source_text(line, chunk)
        segments.append({'text': line, 'start': chunk[0]['start'], 'end': chunk[-1]['end'], 'words': chunk})
    return segments

def segments_from_source_lines(lines: list[str], words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean_lines = [line.strip() for line in lines if line.strip()]
    if not clean_lines or not words:
        return []
    source_units: list[tuple[str, int]] = []
    for line_index, line in enumerate(clean_lines):
        for ch in normalized_text(line):
            source_units.append((ch, line_index))
    asr_units: list[tuple[str, int]] = []
    for word_index, word in enumerate(words):
        for ch in normalized_text(word_text(word)):
            asr_units.append((ch, word_index))
    if not source_units or not asr_units:
        return segments_from_source_lines_weighted(clean_lines, words)
    source_text = ''.join((ch for ch, _line_index in source_units))
    asr_text = ''.join((ch for ch, _word_index in asr_units))
    matcher = SequenceMatcher(None, source_text, asr_text, autojunk=False)
    matched_word_indices_by_line: list[list[int]] = [[] for _ in clean_lines]
    matched_chars = 0
    for block in matcher.get_matching_blocks():
        if block.size <= 0:
            continue
        matched_chars += block.size
        for offset in range(block.size):
            _source_ch, line_index = source_units[block.a + offset]
            _asr_ch, word_index = asr_units[block.b + offset]
            matched_word_indices_by_line[line_index].append(word_index)
    coverage = matched_chars / max(1, len(source_units))
    if coverage < 0.45:
        return segments_from_source_lines_weighted(clean_lines, words)
    line_weights = [max(1, len(normalized_text(line))) for line in clean_lines]
    total_weight = sum(line_weights) or 1
    raw_starts: list[int | None] = []
    for indices in matched_word_indices_by_line:
        raw_starts.append(min(indices) if indices else None)
    starts: list[int] = []
    previous = 0
    for index, raw_start in enumerate(raw_starts):
        remaining_lines = len(clean_lines) - index
        max_start = max(0, len(words) - remaining_lines)
        if raw_start is None:
            ratio = sum(line_weights[:index]) / total_weight
            start = int(round(ratio * len(words)))
        else:
            start = int(raw_start)
        start = min(max(start, previous), max_start)
        starts.append(start)
        previous = min(len(words), start + 1)
    segments: list[dict[str, Any]] = []
    for index, line in enumerate(clean_lines):
        start = starts[index]
        end = starts[index + 1] if index + 1 < len(starts) else len(words)
        if end <= start:
            continue
        chunk = words_with_source_text(line, words[start:end])
        segments.append({'text': line, 'start': chunk[0]['start'], 'end': chunk[-1]['end'], 'words': chunk})
    return segments

def segments_from_words(words: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    chunk: list[dict[str, Any]] = []
    text = ''
    for word in words:
        chunk.append(word)
        text += word['word']
        if word['word'] in SPLIT_PUNCT or len(text) >= max_chars:
            segments.append({'text': text.strip().rstrip('，,。.!！?？；;'), 'start': chunk[0]['start'], 'end': chunk[-1]['end'], 'words': chunk})
            chunk = []
            text = ''
    if chunk:
        segments.append({'text': text.strip().rstrip('，,。.!！?？；;'), 'start': chunk[0]['start'], 'end': chunk[-1]['end'], 'words': chunk})
    return [item for item in segments if item['text']]

def normalize_timeline(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not segments:
        return []
    out = [dict(item) for item in segments]
    for item in out:
        item['start'] = max(0.0, round(float(item['start']), 3))
        item['end'] = max(item['start'] + 0.05, round(float(item['end']), 3))
    return out

def assign_word_indices(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    word_idx = 0
    for segment_index, segment in enumerate(segments, start=1):
        item = dict(segment)
        item['index'] = int(item.get('index') or segment_index)
        words = []
        for raw_word in item.get('words') or []:
            if not isinstance(raw_word, dict):
                continue
            word = dict(raw_word)
            word['idx'] = int(word.get('idx') if word.get('idx') is not None else word_idx)
            word['word'] = str(word.get('word') or word.get('text') or '')
            word['text'] = str(word.get('text') or word.get('word') or '')
            words.append(word)
            word_idx = max(word_idx, int(word['idx']) + 1)
        item['words'] = words
        output.append(item)
    return output

def srt_time(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    hour = ms // 3600000
    ms %= 3600000
    minute = ms // 60000
    ms %= 60000
    second = ms // 1000
    milli = ms % 1000
    return f'{hour:02d}:{minute:02d}:{second:02d},{milli:03d}'

def write_srt(path: Path, segments: list[dict[str, Any]]) -> None:
    blocks = []
    for index, item in enumerate(segments, start=1):
        blocks.append(f"{index}\n{srt_time(item['start'])} --> {srt_time(item['end'])}\n{item['text']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n\n'.join(blocks) + '\n', encoding='utf-8')
