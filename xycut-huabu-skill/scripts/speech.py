"""Prepare or resume TTS and ASR inside one standalone project."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import uuid

import doubao_tts
import volcengine_asr
from local_settings import effective_settings, atomic_json, scrub
from normalize_timeline import normalize
from project import artifact, file_hash, project_lock, read_project, update_project


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def safe_error(error, settings):
    secrets = [settings['speech'][kind]['api_key'] for kind in ('tts', 'asr')]
    return scrub(str(error), secrets)[:1200]


def check_environment(config_dir=None, input_type='mp3', asr_provider=None):
    settings = effective_settings(config_dir)
    provider = asr_provider or settings['speech']['asr']['provider']
    issues = []
    if input_type == 'text' and not settings['speech']['tts']['api_key']:
        issues.append('TTS is not configured: configure Doubao locally, use XYCut to prepare speech, or provide MP3/MP4')
    if provider == 'cloud' and not settings['speech']['asr']['api_key']:
        issues.append('Cloud ASR is not configured; local ASR remains available')
    ffmpeg = settings['tools']['ffmpeg_path'] or shutil.which('ffmpeg')
    if not ffmpeg or not Path(ffmpeg).is_file():
        issues.append('FFmpeg is required')
    dependencies = {name: importlib.util.find_spec(name) is not None for name in ('numpy', 'sherpa_onnx')}
    if provider == 'local' and not all(dependencies.values()):
        issues.append('Prepare the local-ASR virtual environment and run this command with its Python')
    return {'input_type': input_type, 'asr_provider': provider, 'tts_configured': bool(settings['speech']['tts']['api_key']),
            'cloud_asr_configured': bool(settings['speech']['asr']['api_key']), 'credentials_verified': False,
            'ffmpeg': ffmpeg, 'python_dependencies': dependencies, 'ready': not issues, 'issues': issues}


def import_input(task, source, stem):
    source = Path(source).expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError('Input must be a file')
    target = task / 'input' / (stem + '-' + file_hash(source)[:16] + source.suffix.lower())
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        if file_hash(target) != file_hash(source):
            raise ValueError('An imported input changed; preserve it and use an explicit new input')
    else:
        with target.open('xb') as output, source.open('rb') as input_stream:
            shutil.copyfileobj(input_stream, output)
    return target


def recorded_path(task, record):
    path = (task / record['path']).resolve()
    if not path.is_relative_to(task) or not path.is_file() or file_hash(path) != record['sha256']:
        raise ValueError('Recorded input or output is missing/changed; inspect it before regenerating')
    return path


def cached(task, record, expected, regenerate):
    if not regenerate and record.get('fingerprint') == expected:
        for item in record['files'].values():
            recorded_path(task, item)
        return True
    return False


def publish_file(source, destination):
    destination.parent.mkdir(exist_ok=True)
    temporary = destination.with_name('.' + destination.name + '-' + uuid.uuid4().hex + '.tmp')
    try:
        shutil.copyfile(source, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def clock(milliseconds):
    hours, rest = divmod(milliseconds, 3600000)
    minutes, rest = divmod(rest, 60000)
    seconds, milliseconds = divmod(rest, 1000)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}'


def cloud_asr(media, run, settings, source_text, mode, job_file=None):
    section = settings['speech']['asr']
    config = {'api_key': section['api_key'], 'submit_url': volcengine_asr.SUBMIT_URL, 'query_url': volcengine_asr.QUERY_URL,
              'flash_url': volcengine_asr.FLASH_URL, 'seedasr_resource_id': section['resource_id'],
              'standard_resource_id': section['fallback_resource_id'], 'flash_resource_id': section['flash_resource_id']}
    audio = volcengine_asr.extract_audio_if_needed(media, run / 'speech', settings['tools']['ffmpeg_path'] or shutil.which('ffmpeg') or '')
    job_id = fingerprint({'media': file_hash(media), 'mode': mode, 'resources': [section['resource_id'], section['fallback_resource_id']]})
    job_file = job_file or run.parent / 'cloud-jobs' / (job_id + '.json')
    raw = volcengine_asr.transcribe_flash(audio, config) if mode == 'flash' else volcengine_asr.transcribe_standard(audio, config, mode, 3.0, 120, state_file=job_file)
    raw = scrub(raw, [section['api_key']])
    segments = volcengine_asr.build_segments(raw, str(source_text) if source_text else '')
    if not segments:
        raise ValueError('Cloud ASR returned no usable speech; no timeline was fabricated')
    timeline = normalize({'lines': segments})
    metadata = {'provider': 'volcengine', 'mode': mode, 'timing_precision': 'provider-word-or-segment-timestamps', 'source_media': str(media)}
    timeline['speech_metadata'] = metadata
    atomic_json(run / 'speech/asr.cloud.raw.json', raw)
    atomic_json(run / 'speech/segments.json', {'segments': segments, 'metadata': metadata})
    atomic_json(run / 'output/final-timeline.json', timeline)
    srt = '\n\n'.join(f'{index}\n{clock(line["target_start_ms"])} --> {clock(line["target_end_ms"])}\n{line["text"]}' for index, line in enumerate(timeline['lines'], 1)) + '\n'
    (run / 'output/voice.srt').write_text(srt, encoding='utf-8')


def prepare(task_dir, *, config_dir=None, text_file=None, input_media=None, source_text_file=None,
            asr_provider=None, voice_id=None, speech_rate=None, volume=None, regenerate=False,
            model_dir=None, cache_dir=None, threads=2):
    task, manifest = read_project(task_dir)
    settings = effective_settings(config_dir)
    if text_file and input_media:
        raise ValueError('Choose text for TTS or existing media, not both; use source_text_file to accompany media')
    if source_text_file and not input_media:
        raise ValueError('source_text_file accompanies an explicit input_media')
    with project_lock(task, '.speech.lock'):
        try:
            if text_file:
                text_path = import_input(task, text_file, 'script')
                if not text_path.read_text(encoding='utf-8-sig').strip():
                    raise ValueError('TTS text is empty')
                inputs = {'kind': 'text', 'text': artifact(task, text_path)}
            elif input_media:
                media_path = import_input(task, input_media, 'source')
                if media_path.suffix.lower() not in ('.mp3', '.mp4'):
                    raise ValueError('Provide MP3 or MP4, or explicitly convert other formats with FFmpeg first')
                inputs = {'kind': 'media', 'media': artifact(task, media_path)}
                if source_text_file:
                    inputs['text'] = artifact(task, import_input(task, source_text_file, 'script'))
                else:
                    inputs['text'] = None
            else:
                inputs = copy.deepcopy(manifest['input'])
                if inputs.get('kind') not in ('text', 'media'):
                    raise ValueError('First use requires --text-file or --input-media')
            update_project(task, {'input': inputs}, 'speech_input_selected')
            text_path = recorded_path(task, inputs['text']) if inputs.get('text') else None
            tts_reused = False
            if inputs['kind'] == 'text':
                section = settings['speech']['tts']
                parameters = {key: section[key] for key in ('voice_id', 'resource_id', 'speech_rate', 'volume')}
                old_tts = manifest['speech'].get('tts', {})
                pending_tts = manifest['speech'].get('tts_pending') or {}
                if old_tts.get('text_sha256') == inputs['text']['sha256']:
                    parameters.update(old_tts.get('parameters', {}))
                if pending_tts.get('text_sha256') == inputs['text']['sha256']:
                    parameters.update(pending_tts['parameters'])
                parameters.update({key: value for key, value in {'voice_id': voice_id, 'speech_rate': speech_rate, 'volume': volume}.items() if value is not None})
                if not parameters['voice_id'] or not .5 <= parameters['speech_rate'] <= 2 or not .1 <= parameters['volume'] <= 3:
                    raise ValueError('Invalid voice, speech rate or volume')
                tts_fingerprint = fingerprint({'text': inputs['text']['sha256'], **parameters})
                tts_reused = pending_tts.get('fingerprint') != tts_fingerprint and cached(task, old_tts, tts_fingerprint, regenerate)
                if tts_reused:
                    media_path = recorded_path(task, old_tts['files']['audio'])
                else:
                    if not section['api_key']:
                        raise ValueError('Configure Doubao TTS locally, or prepare audio in XYCut and provide MP3/MP4')
                    run = task / 'speech' / ('tts-' + uuid.uuid4().hex)
                    run.mkdir(parents=True)
                    media_path = run / 'source.mp3'
                    config = {'api_key': section['api_key'], 'appid': section['appid'], 'speaker': parameters['voice_id'], 'resource_id': parameters['resource_id']}
                    update_project(task, {'speech': {'tts_pending': {'fingerprint': tts_fingerprint, 'text_sha256': inputs['text']['sha256'], 'parameters': parameters, 'attempt_dir': str(run.relative_to(task))}}}, 'tts_started')
                    doubao_tts.post_tts(text_path.read_text(encoding='utf-8-sig').strip(), config, media_path, run / 'timestamps.json', run / 'tts.raw.json',
                                        doubao_tts.speech_rate_to_api_value(parameters['speech_rate']), doubao_tts.volume_to_api_value(parameters['volume']))
                    if not media_path.is_file() or not media_path.stat().st_size:
                        raise ValueError('TTS did not produce a nonempty audio file')
                    for path in [run / 'timestamps.json', run / 'tts.raw.json']:
                        atomic_json(path, scrub(json.loads(path.read_text(encoding='utf-8')), [section['api_key']]))
                    record = {'fingerprint': tts_fingerprint, 'text_sha256': inputs['text']['sha256'], 'parameters': parameters,
                              'files': {name: artifact(task, path) for name, path in [('audio', media_path), ('timestamps', run / 'timestamps.json'), ('raw', run / 'tts.raw.json')]}}
                    update_project(task, {'speech': {'tts': record, 'tts_pending': None}}, 'tts_completed')
                update_project(task, {'input': {'media': artifact(task, media_path)}}, 'tts_audio_selected')
            else:
                media_path = recorded_path(task, inputs['media'])
            old_asr = manifest['speech'].get('asr', {})
            pending_asr = manifest['speech'].get('asr_pending') or {}
            provider = asr_provider or pending_asr.get('provider') or old_asr.get('provider') or settings['speech']['asr']['provider']
            if provider not in ('local', 'cloud'):
                raise ValueError('Unknown ASR provider')
            mode = settings['speech']['asr']['mode']
            selected_model = model_dir or old_asr.get('parameters', {}).get('model_dir')
            asr_parameters = {'provider': provider, 'media_sha256': file_hash(media_path), 'source_text_sha256': file_hash(text_path) if text_path else None,
                              'mode': mode if provider == 'cloud' else 'sensevoice-local',
                              'resources': {key: settings['speech']['asr'][key] for key in ('resource_id', 'fallback_resource_id', 'flash_resource_id')} if provider == 'cloud' else None,
                              'model_dir': str(Path(selected_model).resolve()) if selected_model else None}
            old_parameters = pending_asr.get('parameters') or old_asr.get('parameters', {})
            if not regenerate and asr_provider is None and model_dir is None and old_parameters.get('media_sha256') == asr_parameters['media_sha256'] and old_parameters.get('source_text_sha256') == asr_parameters['source_text_sha256']:
                asr_parameters = old_parameters
            asr_fingerprint = fingerprint(asr_parameters)
            asr_reused = pending_asr.get('fingerprint') != asr_fingerprint and cached(task, old_asr, asr_fingerprint, regenerate)
            if not asr_reused:
                if provider == 'cloud' and not settings['speech']['asr']['api_key']:
                    raise ValueError('Cloud ASR needs its own configured access; choose local ASR or configure it')
                run = task / 'speech' / ('asr-' + uuid.uuid4().hex)
                (run / 'speech').mkdir(parents=True)
                (run / 'output').mkdir()
                atomic_json(run / 'task_manifest.json', {'kind': 'internal-speech-attempt', 'parent_task_id': task.name})
                job_path = pending_asr.get('job_file') if pending_asr.get('fingerprint') == asr_fingerprint and not regenerate else None
                if not job_path:
                    job_path = 'speech/cloud-jobs/' + (uuid.uuid4().hex if regenerate else asr_fingerprint) + '.json'
                job_file = (task / job_path).resolve()
                if not job_file.is_relative_to(task):
                    raise ValueError('Cloud request record must stay inside this project')
                update_project(task, {'speech': {'asr_pending': {'fingerprint': asr_fingerprint, 'provider': provider, 'parameters': asr_parameters, 'job_file': job_path, 'attempt_dir': str(run.relative_to(task))}}}, 'asr_started')
                if provider == 'local':
                    from transcribe_local_asr import transcribe
                    transcribe(media_path, run, model_dir=asr_parameters['model_dir'], cache_dir=cache_dir,
                               ffmpeg=settings['tools']['ffmpeg_path'] or None, threads=threads)
                else:
                    call_settings = copy.deepcopy(settings)
                    call_settings['speech']['asr'].update(asr_parameters['resources'])
                    cloud_asr(media_path, run, call_settings, text_path, asr_parameters['mode'], job_file)
                timeline_path = run / 'output/final-timeline.json'
                timeline = json.loads(timeline_path.read_text(encoding='utf-8'))
                if not timeline.get('lines'):
                    raise ValueError('ASR produced an empty timeline')
                metadata = timeline.get('speech_metadata', {})
                for name in ('final-timeline.json', 'voice.srt'):
                    publish_file(run / 'output' / name, task / 'output' / name)
                publish_file(run / 'speech/segments.json', task / 'speech/segments.json')
                raw = run / 'speech' / ('asr.local.raw.json' if provider == 'local' else 'asr.cloud.raw.json')
                record = {'fingerprint': asr_fingerprint, 'provider': provider, 'parameters': asr_parameters, 'metadata': metadata,
                          'attempt_dir': str(run.relative_to(task)), 'files': {name: artifact(task, path) for name, path in [
                              ('timeline', task / 'output/final-timeline.json'), ('subtitles', task / 'output/voice.srt'),
                              ('segments', task / 'speech/segments.json'), ('raw', raw)]}}
                update_project(task, {'speech': {'asr': record, 'asr_pending': None}}, 'asr_completed')
            _, current = read_project(task)
            artifacts = dict(current['speech']['asr']['files'])
            artifacts['audio'] = artifact(task, media_path)
            if not asr_reused:
                for key in ('preview', 'video'):
                    if key in current['artifacts']:
                        artifacts[key] = {**current['artifacts'][key], 'stale': True}
            status = current['status'] if asr_reused and current['status'] in ('planning', 'preview_ready', 'awaiting_confirmation', 'preview_confirmed', 'completed') else 'speech_ready'
            update_project(task, {'status': status, 'artifacts': artifacts, 'speech': {'last_error': None}}, 'speech_ready')
            return {'task_dir': str(task), 'audio_file': str(media_path), 'timeline': str(task / 'output/final-timeline.json'),
                    'subtitles': str(task / 'output/voice.srt'), 'asr_provider': provider, 'tts_reused': tts_reused, 'asr_reused': asr_reused}
        except Exception as error:
            message = safe_error(error, settings)
            update_project(task, {'status': 'speech_failed', 'speech': {'last_error': message}}, 'speech_failed')
            raise RuntimeError(message) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-dir', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('check')
    check.add_argument('--input-type', choices=['text', 'mp3', 'mp4'], default='mp3')
    check.add_argument('--asr-provider', choices=['local', 'cloud'])
    run = commands.add_parser('prepare')
    run.add_argument('--task-dir', type=Path, required=True)
    group = run.add_mutually_exclusive_group()
    group.add_argument('--text-file', type=Path)
    group.add_argument('--input-media', type=Path)
    run.add_argument('--source-text-file', type=Path)
    run.add_argument('--asr-provider', choices=['local', 'cloud'])
    run.add_argument('--voice-id')
    run.add_argument('--speech-rate', type=float)
    run.add_argument('--volume', type=float)
    run.add_argument('--model-dir', type=Path)
    run.add_argument('--cache-dir', type=Path)
    run.add_argument('--threads', type=int, default=2)
    run.add_argument('--regenerate', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'check':
            result = check_environment(args.config_dir, args.input_type, args.asr_provider)
        else:
            if args.threads < 1:
                raise ValueError('threads must be positive')
            result = prepare(args.task_dir, config_dir=args.config_dir, text_file=args.text_file, input_media=args.input_media,
                             source_text_file=args.source_text_file, asr_provider=args.asr_provider, voice_id=args.voice_id,
                             speech_rate=args.speech_rate, volume=args.volume, regenerate=args.regenerate,
                             model_dir=args.model_dir, cache_dir=args.cache_dir, threads=args.threads)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as error:
        parser.exit(1, 'Speech error: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
