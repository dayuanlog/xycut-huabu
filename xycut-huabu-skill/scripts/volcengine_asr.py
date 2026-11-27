from __future__ import annotations
import hashlib
import array
import base64
import json
import os
import struct
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path
from typing import Any
from build_srt_from_timestamps import assign_word_indices, normalize_timeline, source_lines, segments_from_source_lines, segments_from_words, utterances_from_payload, words_from_payload, write_srt
FLASH_URL = 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash'
SUBMIT_URL = 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit'
QUERY_URL = 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/query'
DEFAULT_SEEDASR_RESOURCE_ID = 'volc.seedasr.auc'
DEFAULT_STANDARD_RESOURCE_ID = 'volc.bigasr.auc'
DEFAULT_FLASH_RESOURCE_ID = 'volc.bigasr.auc_turbo'
VIDEO_EXTS = {'.mp4', '.mov', '.m4v', '.avi', '.mkv', '.webm'}
PCM_RISK_CODECS = {'pcm_s16be', 'pcm_s16le', 'pcm_s24be', 'pcm_s24le', 'pcm_s32be', 'pcm_s32le'}
PCM_RISK_TAGS = {'ipcm', 'lpcm', 'sowt', 'twos', 'in24', 'in32'}

def resolve_ffmpeg(context: dict[str, Any], explicit: str='') -> str:
    if explicit:
        return explicit
    tools = context.get('tools') if isinstance(context.get('tools'), dict) else {}
    configured = str(tools.get('ffmpeg_path') or '').strip()
    if configured and Path(configured).exists():
        return configured
    found = shutil.which('ffmpeg.exe') or shutil.which('ffmpeg')
    if found:
        return found
    localappdata = os.environ.get('LOCALAPPDATA', '')
    if localappdata:
        candidate = Path(localappdata) / 'com.xiaoyuan.jianji' / 'runtime' / 'ffmpeg' / 'ffmpeg' / 'ffmpeg.exe'
        if candidate.exists():
            return str(candidate)
    return ''

def resolve_ffprobe(ffmpeg: str) -> str:
    if ffmpeg:
        ffmpeg_path = Path(ffmpeg)
        candidate = ffmpeg_path.with_name('ffprobe.exe' if ffmpeg_path.suffix.lower() == '.exe' else 'ffprobe')
        if candidate.exists():
            return str(candidate)
    return shutil.which('ffprobe.exe') or shutil.which('ffprobe') or ''

def run_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')

def probe_audio_stream(input_media: Path, ffmpeg: str) -> dict[str, Any]:
    ffprobe = resolve_ffprobe(ffmpeg)
    if not ffprobe:
        return {}
    cmd = [ffprobe, '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=codec_name,codec_tag_string,sample_fmt,sample_rate,channels,duration', '-of', 'json', str(input_media)]
    result = run_command(cmd)
    if result.returncode != 0:
        return {'probe_error': result.stderr[-500:]}
    try:
        payload = json.loads(result.stdout or '{}')
    except json.JSONDecodeError:
        return {}
    streams = payload.get('streams') if isinstance(payload.get('streams'), list) else []
    return streams[0] if streams and isinstance(streams[0], dict) else {}

def is_pcm_risk_stream(stream: dict[str, Any]) -> bool:
    codec_name = str(stream.get('codec_name') or '').lower()
    codec_tag = str(stream.get('codec_tag_string') or '').lower()
    sample_fmt = str(stream.get('sample_fmt') or '').lower()
    return codec_name in PCM_RISK_CODECS or codec_tag in PCM_RISK_TAGS or (codec_name.startswith('pcm_') and sample_fmt.startswith('s'))

def zero_crossing_rate(samples: list[int]) -> float:
    if len(samples) < 2:
        return 0.0
    crossings = 0
    prev = samples[0]
    for current in samples[1:]:
        if (prev < 0) != (current < 0):
            crossings += 1
        prev = current
    return crossings / max(1, len(samples) - 1)

def peak_abs(samples: list[int]) -> int:
    return max((abs(item) for item in samples), default=0)

def raw_s16le_samples(ffmpeg: str, input_media: Path, seconds: int=20) -> list[int]:
    cmd = [ffmpeg, '-y', '-v', 'error', '-i', str(input_media), '-map', '0:a:0', '-t', str(seconds), '-ac', '1', '-ar', '16000', '-f', 's16le', '-']
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0 or not result.stdout:
        return []
    samples = array.array('h')
    samples.frombytes(result.stdout[:len(result.stdout) - len(result.stdout) % 2])
    if sys.byteorder != 'little':
        samples.byteswap()
    return samples.tolist()

def byteswap_samples(samples: list[int]) -> list[int]:
    swapped: list[int] = []
    for sample in samples:
        raw = struct.pack('<h', sample)
        swapped.append(struct.unpack('<h', raw[::-1])[0])
    return swapped

def zcr_from_interleaved_s16le(raw: bytes, channels: int) -> float:
    if channels <= 0:
        channels = 1
    frame_size = 2 * channels
    values: list[int] = []
    for offset in range(0, len(raw) - frame_size + 1, frame_size):
        values.append(struct.unpack('<h', raw[offset:offset + 2])[0])
    return zero_crossing_rate(values)

def write_wav_s16le(path: Path, samples: list[int], sample_rate: int=16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b''.join((struct.pack('<h', max(-32768, min(32767, item))) for item in samples))
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)

def write_wav_raw_s16le(path: Path, raw: bytes, sample_rate: int, channels: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if channels <= 0:
        channels = 1
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(raw[:len(raw) - len(raw) % (2 * channels)])

def extract_raw_s16le(ffmpeg: str, input_media: Path) -> list[int]:
    cmd = [ffmpeg, '-y', '-v', 'error', '-i', str(input_media), '-map', '0:a:0', '-ac', '1', '-ar', '16000', '-f', 's16le', '-']
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 提取 PCM 音频失败：{result.stderr.decode('utf-8', errors='replace')[-800:]}")
    samples = array.array('h')
    samples.frombytes(result.stdout[:len(result.stdout) - len(result.stdout) % 2])
    if sys.byteorder != 'little':
        samples.byteswap()
    if not samples:
        raise RuntimeError('FFmpeg 提取 PCM 音频为空。')
    return samples.tolist()

def copy_raw_audio_packets(ffmpeg: str, input_media: Path, seconds: int | None=None) -> bytes:
    cmd = [ffmpeg, '-y', '-v', 'error', '-i', str(input_media), '-map', '0:a:0']
    if seconds is not None:
        cmd.extend(['-t', str(seconds)])
    cmd.extend(['-c:a', 'copy', '-f', 'data', '-'])
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        return b''
    return result.stdout

def make_pcm_packet_rescue_candidate(input_media: Path, work_dir: Path, ffmpeg: str, stream: dict[str, Any], normal_zcr: float) -> dict[str, Any] | None:
    if not is_pcm_risk_stream(stream):
        return None
    sample_rate = int(str(stream.get('sample_rate') or '48000').strip() or '48000')
    channels = int(str(stream.get('channels') or '1').strip() or '1')
    probe_raw = copy_raw_audio_packets(ffmpeg, input_media, seconds=20)
    if not probe_raw:
        return None
    packet_zcr = zcr_from_interleaved_s16le(probe_raw, channels)
    info = {'packet_little_endian_zcr': round(packet_zcr, 4), 'normal_zcr': round(normal_zcr, 4), 'sample_rate': sample_rate, 'channels': channels}
    if normal_zcr < 0.35 and packet_zcr >= normal_zcr:
        return {'path': '', 'kind': 'pcm_packet_le_skipped', 'info': info}
    full_raw = copy_raw_audio_packets(ffmpeg, input_media)
    if not full_raw:
        return None
    rescue_path = work_dir / f'{input_media.stem}.asr.packet-le.wav'
    write_wav_raw_s16le(rescue_path, full_raw, sample_rate, channels)
    return {'path': str(rescue_path), 'kind': 'pcm_packet_little_endian', 'info': info}

def make_pcm_rescue_candidate(input_media: Path, work_dir: Path, ffmpeg: str, stream: dict[str, Any]) -> dict[str, Any] | None:
    if not is_pcm_risk_stream(stream):
        return None
    probe_samples = raw_s16le_samples(ffmpeg, input_media)
    if not probe_samples:
        return None
    swapped_probe = byteswap_samples(probe_samples)
    normal_zcr = zero_crossing_rate(probe_samples)
    swapped_zcr = zero_crossing_rate(swapped_probe)
    info = {'codec_name': stream.get('codec_name'), 'codec_tag_string': stream.get('codec_tag_string'), 'normal_zcr': round(normal_zcr, 4), 'byteswap_zcr': round(swapped_zcr, 4), 'normal_peak': peak_abs(probe_samples), 'byteswap_peak': peak_abs(swapped_probe)}
    if normal_zcr < 0.35 and swapped_zcr >= normal_zcr:
        return {'path': '', 'kind': 'pcm_rescue_skipped', 'info': info}
    samples = byteswap_samples(extract_raw_s16le(ffmpeg, input_media))
    rescue_path = work_dir / f'{input_media.stem}.asr.byteswap.wav'
    write_wav_s16le(rescue_path, samples)
    return {'path': str(rescue_path), 'kind': 'pcm_byteswap', 'info': info}

def extract_audio_candidates(input_media: Path, work_dir: Path, ffmpeg: str) -> list[dict[str, Any]]:
    if input_media.suffix.lower() not in VIDEO_EXTS:
        return [{'path': str(input_media), 'kind': 'original_audio', 'info': {}}]
    if not ffmpeg:
        raise RuntimeError('输入是视频文件，但没有找到 FFmpeg，无法先提取音频给 ASR。')
    work_dir.mkdir(parents=True, exist_ok=True)
    audio_path = work_dir / f'{input_media.stem}.asr.mp3'
    cmd = [ffmpeg, '-y', '-i', str(input_media), '-vn', '-ac', '1', '-ar', '16000', '-b:a', '64k', str(audio_path)]
    result = run_command(cmd)
    if result.returncode != 0:
        raise RuntimeError(f'FFmpeg 提取音频失败：{result.stderr[-800:]}')
    stream = probe_audio_stream(input_media, ffmpeg)
    candidates: list[dict[str, Any]] = [{'path': str(audio_path), 'kind': 'standard_mp3', 'info': {'stream': stream}}]
    normal_probe = raw_s16le_samples(ffmpeg, input_media) if is_pcm_risk_stream(stream) else []
    normal_zcr = zero_crossing_rate(normal_probe) if normal_probe else 0.0
    packet_rescue = make_pcm_packet_rescue_candidate(input_media, work_dir, ffmpeg, stream, normal_zcr)
    if packet_rescue and packet_rescue.get('path'):
        info = packet_rescue.get('info') if isinstance(packet_rescue.get('info'), dict) else {}
        if float(info.get('packet_little_endian_zcr') or 1) + 0.08 < float(info.get('normal_zcr') or 0):
            candidates.insert(0, packet_rescue)
        else:
            candidates.append(packet_rescue)
    elif packet_rescue:
        candidates[0]['info']['pcm_packet_rescue'] = packet_rescue.get('info', {})
    rescue = make_pcm_rescue_candidate(input_media, work_dir, ffmpeg, stream)
    if rescue and rescue.get('path'):
        info = rescue.get('info') if isinstance(rescue.get('info'), dict) else {}
        if float(info.get('byteswap_zcr') or 1) + 0.08 < float(info.get('normal_zcr') or 0):
            candidates.insert(0, rescue)
        else:
            candidates.append(rescue)
    elif rescue:
        candidates[0]['info']['pcm_rescue'] = rescue.get('info', {})
    return candidates

def extract_audio_if_needed(input_media: Path, work_dir: Path, ffmpeg: str) -> Path:
    return Path(extract_audio_candidates(input_media, work_dir, ffmpeg)[0]['path'])

def request_body(audio_path: Path) -> dict[str, Any]:
    data = base64.b64encode(audio_path.read_bytes()).decode('ascii')
    return {'user': {'uid': 'xiaoying'}, 'audio': {'format': audio_path.suffix.lower().lstrip('.') or 'mp3', 'data': data}, 'request': {'model_name': 'bigmodel', 'enable_itn': True, 'enable_punc': True, 'enable_ddc': False, 'show_utterances': True, 'enable_speaker_info': False}}

def post_json(url: str, api_key: str, resource_id: str, request_id: str, body: dict[str, Any], extra_headers: dict[str, str] | None=None) -> tuple[dict[str, Any], dict[str, str]]:
    headers = {'Content-Type': 'application/json', 'X-Api-Key': api_key, 'X-Api-Resource-Id': resource_id, 'X-Api-Request-Id': request_id, 'X-Api-Sequence': '-1'}
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            text = response.read().decode('utf-8', errors='replace')
            response_headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'火山 ASR 请求失败 HTTP {exc.code}: {body_text[:500]}') from exc
    payload = json.loads(text) if text.strip() else {}
    return (payload, response_headers)

def transcribe_standard(audio_path: Path, config: dict[str, str], mode: str, poll_interval: float, max_attempts: int, state_file: Path | None = None) -> dict[str, Any]:
    from local_settings import atomic_json, scrub
    resource_id = config['seedasr_resource_id'] if mode == 'seedasr_standard' else config['standard_resource_id']
    identity = {'audio_sha256': hashlib.sha256(audio_path.read_bytes()).hexdigest(), 'resource_id': resource_id, 'mode': mode}
    state = json.loads(state_file.read_text(encoding='utf-8')) if state_file and state_file.exists() else None

    def save():
        if state_file:
            atomic_json(state_file, scrub(state, [config['api_key']]))

    if state:
        if state.get('identity') != identity:
            raise ValueError('Cloud job identity changed; inspect the saved request before retrying')
        if state['status'] == 'completed':
            return state['result']
        if state['status'] == 'failed':
            raise RuntimeError('Saved cloud job failed; inspect it before explicitly regenerating: ' + state.get('error', ''))
    else:
        state = {'identity': identity, 'request_id': str(uuid.uuid4()), 'log_id': '', 'status': 'submitting'}
        save()
        submit_payload, submit_headers = post_json(config['submit_url'], config['api_key'], resource_id, state['request_id'], request_body(audio_path))
        status = submit_headers.get('x-api-status-code') or str(submit_payload.get('code') or '')
        if status and status not in {'20000000', '0'}:
            state.update(status='failed', error=str(submit_headers.get('x-api-message') or submit_payload.get('message') or status))
            save()
            raise RuntimeError('Cloud ASR submit failed: ' + state['error'])
        state.update(status='submitted', log_id=submit_headers.get('x-tt-logid', ''))
        save()
    request_id, log_id = state['request_id'], state['log_id']
    last_payload: dict[str, Any] = {}
    for _ in range(max_attempts):
        time.sleep(poll_interval)
        extra_headers = {'X-Tt-Logid': log_id} if log_id else None
        payload, headers = post_json(config['query_url'], config['api_key'], resource_id, request_id, {}, extra_headers)
        last_payload = payload
        query_status = headers.get('x-api-status-code') or str(payload.get('code') or '')
        if query_status in {'20000000', '0'}:
            result = {'request_id': request_id, 'resource_id': resource_id, 'result': payload}
            state.update(status='completed', result=result)
            save()
            return result
        if query_status not in {'20000001', '20000002', ''}:
            state.update(status='failed', error=str(headers.get('x-api-message') or payload.get('message') or query_status))
            save()
            raise RuntimeError('Cloud ASR query failed: ' + state['error'])
    raise RuntimeError(f'火山 ASR 查询超时，最后返回：{json.dumps(last_payload, ensure_ascii=False)[:500]}')

def transcribe_flash(audio_path: Path, config: dict[str, str]) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    payload, headers = post_json(config['flash_url'], config['api_key'], config['flash_resource_id'], request_id, request_body(audio_path))
    status = headers.get('x-api-status-code') or str(payload.get('code') or '')
    if status and status not in {'20000000', '0'}:
        raise RuntimeError('Cloud flash ASR failed: ' + str(headers.get('x-api-message') or payload.get('message') or status))
    return {'request_id': request_id, 'resource_id': config['flash_resource_id'], 'result': payload}

def build_segments(raw: dict[str, Any], source_text_file: str='') -> list[dict[str, Any]]:
    words = words_from_payload(raw)
    segments = []
    if source_text_file:
        lines = source_lines(Path(source_text_file).read_text(encoding='utf-8-sig'))
        segments = segments_from_source_lines(lines, words)
    if not segments:
        segments = utterances_from_payload(raw)
    if not segments:
        segments = segments_from_words(words, 24)
    return assign_word_indices(segments)

def build_srt(raw: dict[str, Any], output_srt: Path, source_text_file: str='', output_segments_json: Path | None=None) -> int:
    raw_segments = build_segments(raw, source_text_file)
    if output_segments_json:
        output_segments_json.parent.mkdir(parents=True, exist_ok=True)
        output_segments_json.write_text(json.dumps({'segments': raw_segments}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    segments = normalize_timeline(raw_segments)
    if not segments:
        raise RuntimeError('ASR 返回结果中没有可用于生成 SRT 的时间戳')
    write_srt(output_srt, segments)
    return len(segments)

def auto_source_text_file(output_json: Path, explicit: str='') -> str:
    explicit = str(explicit or '').strip()
    if explicit:
        return explicit
    task_dir = output_json.parent.parent
    candidate = task_dir / 'input' / 'script.txt'
    if candidate.is_file():
        return str(candidate)
    return ''
