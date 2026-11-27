"""Local MP3/MP4 ASR; preserve source time and expose token-boundary precision honestly."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave

from prepare_local_asr import prepare
from normalize_timeline import normalize


def chunks(samples, sr, seconds=25):
    """Bound memory and prefer low-energy boundaries; never remove time from the source."""
    import numpy as np
    start, cap, frame = 0, int(seconds * sr), int(.02 * sr)
    while start < len(samples):
        end = min(len(samples), start + cap)
        if end < len(samples):
            begin = start + cap // 2
            region = samples[begin:end]
            count = len(region) // frame
            rms = np.sqrt(np.mean(region[:count * frame].reshape(count, frame) ** 2, axis=1))
            quiet = np.flatnonzero(rms < .008)
            if len(quiet):
                end = begin + int(quiet[-1] + 1) * frame
        yield start, end
        start = end


def decode_result(result, offset, span, sequence):
    text = str(getattr(result, 'text', '')).strip()
    if not text:
        return [], [], False
    tokens = list(getattr(result, 'tokens', []) or [])
    timestamps = list(getattr(result, 'timestamps', []) or [])
    if not tokens or len(tokens) != len(timestamps):
        return [dict(line_id=f'line_{sequence:04d}', text=text, start=offset, end=offset + span, words=[])], [], True
    clean = []
    for token, ts in zip(tokens, timestamps):
        token = str(token).replace('\u2581', ' ')
        if not token.strip() or token.startswith('<|'):
            continue
        ts = float(ts)
        if not 0 <= ts < span or (clean and ts < clean[-1][1]):
            raise ValueError('ASR returned invalid or unordered token timestamps')
        clean.append((token, ts))
    if not clean:
        return [dict(line_id=f'line_{sequence:04d}', text=text, start=offset, end=offset + span, words=[])], [], True
    lines, current, log = [], [], []
    for i, (token, ts) in enumerate(clean):
        next_ts = clean[i + 1][1] if i + 1 < len(clean) else span
        # CTC gives token time points, not exact end boundaries. Keep this estimate explicit.
        end = min(span, max(ts + .02, min(next_ts, ts + .4)))
        current.append(dict(text=token, start=round(offset + ts, 3), end=round(offset + end, 3)))
        log.append(dict(token=token, timestamp=round(offset + ts, 3)))
        gap = next_ts - ts
        if token.rstrip().endswith(tuple('，。！？；,.!?;')) or len(current) >= 22 or gap > .7 or i == len(clean) - 1:
            lines.append(dict(line_id=f'line_{sequence + len(lines):04d}', text=''.join(w['text'] for w in current),
                              start=current[0]['start'], end=current[-1]['end'], words=current))
            current = []
    return lines, log, not bool(clean)


def transcribe(media, task, model_dir=None, cache_dir=None, ffmpeg=None, threads=2):
    import numpy as np
    import sherpa_onnx
    media, task = Path(media).resolve(strict=True), Path(task).resolve(strict=True)
    if media.suffix.lower() not in ('.mp3', '.mp4'):
        raise ValueError('Standalone speech input must be MP3 or MP4')
    if not (task / 'task_manifest.json').is_file():
        raise ValueError('Create a task workspace first')
    speech, output = task / 'speech', task / 'output'
    paths = [speech / 'asr.local.raw.json', speech / 'segments.json', output / 'final-timeline.json', output / 'voice.srt']
    if any(p.exists() for p in paths):
        raise FileExistsError('ASR outputs already exist; use a new task, or explicitly archive old outputs first')
    executable = ffmpeg or shutil.which('ffmpeg')
    if not executable:
        raise ValueError('FFmpeg is required; pass --ffmpeg or add it to PATH')
    model = prepare(cache_dir, model_dir)
    with tempfile.TemporaryDirectory(prefix='canvas-asr-') as temporary:
        wav = Path(temporary) / 'source.wav'
        subprocess.run([str(executable), '-v', 'error', '-nostdin', '-i', str(media), '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(wav)], check=True, capture_output=True)
        with wave.open(str(wav), 'rb') as handle:
            sr = handle.getframerate()
            samples = np.frombuffer(handle.readframes(handle.getnframes()), dtype='<i2').astype(np.float32) / 32768
        duration = len(samples) / sr
        # Some ONNX builds cannot open non-ASCII model paths: stage only in that case.
        inference_model = dict(model)
        if not (model['model'] + model['tokens']).isascii():
            folder = Path(temporary) / 'model'
            folder.mkdir()
            for key in ('model', 'tokens'):
                dest = folder / Path(model[key]).name
                shutil.copy2(model[key], dest)
                inference_model[key] = str(dest)
            if not str(folder).isascii():
                raise ValueError('Use an ASCII model/cache directory or set TMPDIR to an ASCII path for this ONNX build')
        recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(model=inference_model['model'], tokens=inference_model['tokens'],
            num_threads=threads, sample_rate=16000, use_itn=False, language='auto', provider='cpu', debug=False)
        lines, raw, coarse = [], [], False
        for start, end in chunks(samples, sr):
            audio = samples[start:end]
            if float(np.max(np.abs(audio), initial=0)) < .004:
                continue
            stream = recognizer.create_stream()
            stream.accept_waveform(sr, audio)
            recognizer.decode_stream(stream)
            result = stream.result
            decoded, times, fallback = decode_result(result, start / sr, len(audio) / sr, len(lines) + 1)
            lines.extend(decoded)
            coarse |= fallback
            raw.append(dict(start=start / sr, end=end / sr, text=str(result.text), token_time_points=times))
    if not lines:
        raise ValueError('No speech recognized; check the source audio. No timeline was fabricated.')
    document = dict(duration_ms=round(duration * 1000), lines=lines)
    timeline = normalize(document)
    precision = 'mixed-segment-and-token' if coarse else 'ctc-token-time-points'
    metadata = dict(provider='sherpa-onnx-sensevoice', model=model, timing_precision=precision,
                    end_boundary_method='next token time capped at 400ms; estimated, not forced alignment',
                    chunking='energy-aware bounded chunks; original offsets retained', source_media=str(media))
    timeline['speech_metadata'] = metadata
    speech.mkdir(exist_ok=True)
    output.mkdir(exist_ok=True)
    raw_doc = dict(metadata=metadata, duration=duration, chunks=raw)
    def clock(ms):
        h, rem = divmod(ms, 3600000)
        m, rem = divmod(rem, 60000)
        s, ms = divmod(rem, 1000)
        return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
    srt = '\n\n'.join(f'{i}\n{clock(l["target_start_ms"])} --> {clock(l["target_end_ms"])}\n{l["text"]}' for i, l in enumerate(timeline['lines'], 1)) + '\n'
    for path, data in zip(paths, (raw_doc, dict(segments=lines, metadata=metadata), timeline, srt)):
        with path.open('x', encoding='utf-8') as handle:
            handle.write(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return dict(task_dir=str(task), duration=duration, lines=len(lines), timing_precision=precision,
                timeline=str(paths[2]), warnings=['Review English names, numbers and keyword timing; CTC ends are estimated.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-media', type=Path, required=True)
    parser.add_argument('--task-dir', type=Path, required=True)
    parser.add_argument('--model-dir', type=Path)
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--ffmpeg')
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error('--threads must be positive')
    try:
        print(json.dumps(transcribe(args.input_media, args.task_dir, args.model_dir, args.cache_dir, args.ffmpeg, args.threads), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Local ASR failed: {exc}\n')


if __name__ == '__main__':
    main()
