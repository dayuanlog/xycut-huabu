"""Private per-user settings for standalone speech and projects."""
import argparse
import copy
import json
import os
from pathlib import Path
import tempfile

REPOSITORY = Path(__file__).resolve().parents[2]
SECRET_FIELDS = {'api_key', 'access_token', 'api_secret', 'authorization', 'password'}
DEFAULTS = {
    'schema_version': 1,
    'projects_root': str(Path.home() / 'xycut-huabu-projects'),
    'tools': {'ffmpeg_path': ''},
    'speech': {
        'tts': {'api_key': '', 'appid': '', 'voice_id': 'zh_female_vv_uranus_bigtts', 'resource_id': 'seed-tts-2.0', 'speech_rate': 1.0, 'volume': 1.0},
        'asr': {'provider': 'local', 'api_key': '', 'mode': 'seedasr_standard', 'resource_id': 'volc.seedasr.auc', 'fallback_resource_id': 'volc.bigasr.auc', 'flash_resource_id': 'volc.bigasr.auc_turbo'},
    },
}


def outside_repository(path):
    path = Path(path).expanduser().resolve()
    if path.is_relative_to(REPOSITORY):
        raise ValueError('Keep private settings and projects outside the Skill repository')
    return path


def settings_file(config_dir=None):
    folder = config_dir or os.environ.get('XYCUT_HUABU_CONFIG_DIR') or Path.home() / '.xycut-huabu'
    return outside_repository(folder) / 'settings.json'


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('Refusing to replace a linked settings or manifest file')
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def merge(base, supplied):
    result = copy.deepcopy(base)
    for key, value in supplied.items():
        if key not in result:
            raise ValueError('Unknown settings field: ' + key)
        if isinstance(result[key], dict):
            if not isinstance(value, dict):
                raise ValueError('Expected object for settings: ' + key)
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def validate(settings):
    if type(settings['schema_version']) is not int or settings['schema_version'] != 1:
        raise ValueError('Unsupported settings schema_version')
    settings['projects_root'] = str(outside_repository(settings['projects_root']))
    tts, asr = settings['speech']['tts'], settings['speech']['asr']
    if asr['provider'] not in ('local', 'cloud') or asr['mode'] not in ('seedasr_standard', 'standard', 'flash'):
        raise ValueError('Invalid ASR provider or mode')
    for field in ('api_key', 'appid', 'voice_id', 'resource_id'):
        if not isinstance(tts[field], str):
            raise ValueError('TTS field must be a string: ' + field)
    for field in ('api_key', 'resource_id', 'fallback_resource_id', 'flash_resource_id'):
        if not isinstance(asr[field], str):
            raise ValueError('ASR field must be a string: ' + field)
    if not tts['voice_id'].strip() or not tts['resource_id'].strip():
        raise ValueError('Voice ID and TTS resource ID cannot be empty')
    if not isinstance(settings['tools']['ffmpeg_path'], str):
        raise ValueError('FFmpeg path must be a string')
    for field, lower, upper in [('speech_rate', .5, 2.0), ('volume', .1, 3.0)]:
        if type(tts[field]) not in (int, float) or not lower <= tts[field] <= upper:
            raise ValueError(f'{field} must be between {lower} and {upper}')
    return settings


def load_settings(config_dir=None):
    path = settings_file(config_dir)
    supplied = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    if not isinstance(supplied, dict):
        raise ValueError('Settings must be a JSON object; existing file was not replaced')
    return validate(merge(DEFAULTS, supplied))


def effective_settings(config_dir=None):
    settings = load_settings(config_dir)
    for kind in ('tts', 'asr'):
        section = settings['speech'][kind]
        specific = 'XYCUT_HUABU_TTS_API_KEY' if kind == 'tts' else 'XYCUT_HUABU_ASR_API_KEY'
        section['api_key'] = (os.environ.get(specific) or section['api_key'] or os.environ.get('VOLCENGINE_API_KEY', '')).strip()
    return settings


def scrub(value, secrets=()):
    if isinstance(value, dict):
        return {key: ('[redacted]' if key.lower() in SECRET_FIELDS else scrub(item, secrets)) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, '[redacted]')
    return value


def public_settings(settings, config_dir=None):
    result = scrub(settings)
    for kind in ('tts', 'asr'):
        result['speech'][kind]['api_key_configured'] = bool(settings['speech'][kind]['api_key'])
    return {'config_file': str(settings_file(config_dir)), 'settings': result, 'credentials_verified': False}


def configure(config_dir=None, *, api_key=None, asr_api_key=None, voice_id=None, speech_rate=None, volume=None,
              asr_provider=None, projects_root=None, ffmpeg=None, tts_resource_id=None, asr_resource_id=None):
    settings = load_settings(config_dir)
    for name, value in [('api_key', api_key), ('voice_id', voice_id), ('speech_rate', speech_rate), ('volume', volume), ('resource_id', tts_resource_id)]:
        if value is not None:
            settings['speech']['tts'][name] = value
    for name, value in [('api_key', asr_api_key), ('provider', asr_provider), ('resource_id', asr_resource_id)]:
        if value is not None:
            settings['speech']['asr'][name] = value
    if projects_root is not None:
        settings['projects_root'] = str(projects_root)
    if ffmpeg is not None:
        settings['tools']['ffmpeg_path'] = str(ffmpeg)
    validate(settings)
    atomic_json(settings_file(config_dir), settings)
    return public_settings(settings, config_dir)


def env_key(name):
    if not name:
        return None
    value = os.environ.get(name, '').strip()
    if not value:
        raise ValueError('The requested API key environment variable is empty')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-dir', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('show')
    edit = commands.add_parser('configure')
    edit.add_argument('--api-key-env')
    edit.add_argument('--asr-api-key-env')
    edit.add_argument('--voice-id')
    edit.add_argument('--speech-rate', type=float)
    edit.add_argument('--volume', type=float)
    edit.add_argument('--asr-provider', choices=['local', 'cloud'])
    edit.add_argument('--tts-resource-id')
    edit.add_argument('--asr-resource-id')
    edit.add_argument('--projects-root', type=Path)
    edit.add_argument('--ffmpeg', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'show':
            result = public_settings(effective_settings(args.config_dir), args.config_dir)
        else:
            result = configure(args.config_dir, api_key=env_key(args.api_key_env), asr_api_key=env_key(args.asr_api_key_env),
                               voice_id=args.voice_id, speech_rate=args.speech_rate, volume=args.volume,
                               asr_provider=args.asr_provider, projects_root=args.projects_root, ffmpeg=args.ffmpeg,
                               tts_resource_id=args.tts_resource_id, asr_resource_id=args.asr_resource_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, TypeError) as error:
        parser.exit(1, 'Settings error: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
