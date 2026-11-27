"""Resolve runtime mode separately from speech capabilities; never print credentials."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys


def load_helper(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def detect(context_file=None, mode='auto', input_type='mp3', speech='auto'):
    if mode not in ('auto', 'xycut', 'standalone'):
        raise ValueError('Invalid runtime mode')
    if context_file is None and mode != 'standalone':
        candidate = os.environ.get('XYCUT_AGENT_CONTEXT')
        if not candidate and os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
            default = Path(os.environ['LOCALAPPDATA']) / 'com.xiaoyuan.jianji/agent-context.json'
            candidate = str(default) if default.is_file() else None
        context_file = candidate
    selected = 'standalone' if mode == 'standalone' else ('xycut' if context_file or mode == 'xycut' else 'standalone')
    result = dict(mode=selected, input_type=input_type, speech_provider=None, tts_available=False,
                  cloud_asr_available=False, ready=True, issues=[], context_file=None,
                  companion_skill=None, ffmpeg=shutil.which('ffmpeg'),
                  node=shutil.which('node'), python_dependencies={})
    for name in ('sherpa_onnx', 'numpy'):
        result['python_dependencies'][name] = importlib.util.find_spec(name) is not None
    if selected == 'xycut':
        if not context_file or not Path(context_file).is_file():
            result['issues'].append('XYCut context is missing; regenerate the copied prompt in XYCut.')
        else:
            try:
                context = json.loads(Path(context_file).read_text(encoding='utf-8-sig'))
                if not isinstance(context, dict):
                    raise ValueError('Context must be an object')
                result['context_file'] = str(Path(context_file).resolve())
                configured_ffmpeg = context.get('tools', {}).get('ffmpeg_path')
                if configured_ffmpeg and Path(configured_ffmpeg).is_file():
                    result['ffmpeg'] = configured_ffmpeg
                companion = context.get('skills', {}).get('xycut-video-template-skill', {}).get('install_dir')
                if companion:
                    result['companion_skill'] = companion
                scripts = Path(companion) / 'scripts' if companion else None
                if not scripts or not (scripts / 'transcribe_volcengine_asr.py').is_file() or not (scripts / 'generate_doubao_tts.py').is_file():
                    result['issues'].append('XYCut companion speech Skill is missing; repair the client installation.')
                else:
                    asr = load_helper(scripts / 'transcribe_volcengine_asr.py', 'canvas_asr_config')
                    tts = load_helper(scripts / 'generate_doubao_tts.py', 'canvas_tts_config')
                    result['cloud_asr_available'] = bool(asr.load_asr_config(context).get('api_key')) and context.get('speech', {}).get('asr', {}).get('enabled', True) is not False
                    result['tts_available'] = bool(tts.load_tts_config(context).get('api_key')) and context.get('speech', {}).get('tts', {}).get('enabled', True) is not False
            except (OSError, ValueError, TypeError, AttributeError, ImportError):
                result['issues'].append('Cannot read the XYCut context or speech configuration; no automatic mode switch.')
    if input_type == 'text':
        if selected == 'standalone' or not result['tts_available']:
            result['issues'].append('Provide MP3/MP4, or configure Doubao Speech in XYCut for text-to-speech. https://www.xycut.com')
        else:
            result['speech_provider'] = 'xycut-tts'
    elif input_type == 'timeline':
        result['speech_provider'] = 'existing-timeline'
    elif speech == 'cloud':
        if not result['cloud_asr_available']:
            result['issues'].append('Cloud ASR is not configured; configure XYCut or explicitly choose local ASR.')
        else:
            result['speech_provider'] = 'xycut-asr'
    else:
        result['speech_provider'] = 'xycut-asr' if speech != 'local' and result['cloud_asr_available'] else 'sensevoice-local'
    result['ready'] = not result['issues']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent-context', type=Path)
    parser.add_argument('--mode', choices=['auto', 'xycut', 'standalone'], default='auto')
    parser.add_argument('--input-type', choices=['text', 'mp3', 'mp4', 'timeline'], required=True)
    parser.add_argument('--speech', choices=['auto', 'cloud', 'local'], default='auto')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = detect(args.agent_context, args.mode, args.input_type, args.speech)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as handle:
            handle.write(payload)
    print(payload)
    return 0 if result['ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
