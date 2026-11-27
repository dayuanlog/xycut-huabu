from __future__ import annotations
import base64
import json
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any
TTS_URL = 'https://openspeech.bytedance.com/api/v3/tts/unidirectional'

def read_json(path: Path) -> Any:
    with path.open('r', encoding='utf-8-sig') as f:
        return json.load(f)

def int_value(value: Any, default: int=0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default

def float_value(value: Any, default: float=1.0) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default

def speech_rate_to_api_value(value: Any) -> int:
    raw = float_value(value, 1.0)
    if raw <= 0 and float(raw).is_integer():
        return int(raw)
    ratio = max(0.5, min(2.0, raw))
    return int(round((ratio - 1.0) * 100))

def volume_to_api_value(value: Any) -> int:
    """豆包 TTS 2.0 的 audio_params.volume 使用整数，小数配置先取整。"""
    raw = float_value(value, 1.0)
    if raw <= 0:
        return 1
    if raw <= 3:
        return max(1, min(3, int(round(raw))))
    return max(1, min(100, int(round(raw))))

def post_tts(text: str, config: dict[str, str], output_audio: Path, output_timestamps: Path, raw_output: Path, speech_rate: int, volume: float) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    headers = {'Content-Type': 'application/json', 'X-Api-Key': config['api_key'], 'X-Api-Resource-Id': config['resource_id'] or 'seed-tts-2.0', 'X-Api-Request-Id': request_id}
    if config.get('appid'):
        headers['X-Api-App-Id'] = config['appid']
    payload = {'user': {'uid': config.get('appid') or 'xiaoying'}, 'req_params': {'text': text, 'speaker': config['speaker'], 'audio_params': {'format': 'mp3', 'sample_rate': 24000, 'speech_rate': speech_rate, 'volume': volume}, 'enable_subtitle': True}}
    request = urllib.request.Request(TTS_URL, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers=headers, method='POST')
    chunks: list[bytes] = []
    responses: list[dict[str, Any]] = []
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw_lines = response.read().decode('utf-8', errors='replace').splitlines()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'豆包 TTS 请求失败 HTTP {exc.code}: {body[:500]}') from exc
    frontend: dict[str, Any] = {}
    duration = ''
    for line in raw_lines:
        if not line.strip():
            continue
        item = json.loads(line)
        responses.append({key: value for key, value in item.items() if key != 'data'})
        code = item.get('code', 0)
        if code and code != 20000000:
            raise RuntimeError(f"豆包 TTS 返回错误: code={code}, message={item.get('message', '')}")
        data = str(item.get('data') or '').strip()
        if data:
            chunks.append(base64.b64decode(data))
        addition = item.get('addition') if isinstance(item.get('addition'), dict) else {}
        duration = str(addition.get('duration') or duration)
        raw_frontend = addition.get('frontend')
        if isinstance(raw_frontend, str) and raw_frontend.strip():
            try:
                frontend = json.loads(raw_frontend)
            except json.JSONDecodeError:
                pass
        elif isinstance(raw_frontend, dict):
            frontend = raw_frontend
    if not chunks:
        raise RuntimeError('豆包 TTS 未返回音频数据')
    output_audio.parent.mkdir(parents=True, exist_ok=True)
    output_audio.write_bytes(b''.join(chunks))
    raw_output.write_text(json.dumps({'request_id': request_id, 'responses': responses}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    output_timestamps.write_text(json.dumps({'provider': 'volcengine_doubao_tts', 'request_id': request_id, 'duration': duration, 'addition': {'frontend': frontend}, 'words': frontend.get('words') if isinstance(frontend, dict) else []}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'request_id': request_id, 'duration': duration, 'word_count': len(frontend.get('words') or []) if isinstance(frontend, dict) else 0}
