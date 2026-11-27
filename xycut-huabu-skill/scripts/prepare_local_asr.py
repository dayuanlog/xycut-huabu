"""Download a pinned SenseVoice model to user cache, or resolve an explicit local model."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request

REVISION = '2365baeacb507f821a0c8120fcee3d484dba7a07'
BASE = 'https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/' + REVISION + '/'
FILES = {
    'model.int8.onnx': 'c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51',
    'tokens.txt': 'f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc',
    'LICENSE': '221c6df10b0931a5629adad671ea48fb7747e034c414b6d2bfa275bc3dd4ea17',
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def default_cache():
    root = os.environ.get('XYCUT_CANVAS_CACHE')
    if root:
        return Path(root).expanduser()
    if os.name == 'nt':
        root = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local')))
    else:
        root = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache')))
    return root / 'xycut-canvas-video'


def download(url, target, expected):
    target = Path(target)
    if target.exists():
        if digest(target) == expected:
            return
        raise ValueError(f'Cached file checksum mismatch: {target}; remove it explicitly and retry')
    partial = target.with_name(target.name + '.part')
    if partial.exists() and digest(partial) == expected:
        os.replace(partial, target)
        return
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {'User-Agent': 'xycut-canvas-video-skill'}
    if offset:
        headers['Range'] = f'bytes={offset}-'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
        resumed = response.status == 206 and response.headers.get('Content-Range', '').startswith(f'bytes {offset}-')
        if response.status == 206 and not resumed:
            raise ValueError('Invalid download resume response')
        size = int(response.headers.get('Content-Length', '0')) + (offset if resumed else 0)
        count = offset if resumed else 0
        with partial.open('ab' if resumed else 'wb') as handle:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                handle.write(block)
                count += len(block)
                if count // (20 * 1024 * 1024) != (count - len(block)) // (20 * 1024 * 1024):
                    print(f'{target.name}: {count}/{size or "unknown"} bytes', file=sys.stderr)
    if digest(partial) != expected:
        partial.unlink()
        raise ValueError(f'Download checksum mismatch: {target.name}')
    os.replace(partial, target)


def resolve_local(model_dir):
    root = Path(model_dir).expanduser().resolve(strict=True)
    model = next((root / n for n in ('model.int8.onnx', 'model_q8.onnx', 'model.onnx') if (root / n).is_file()), None)
    tokens = root / 'tokens.txt'
    if model is None or not tokens.is_file():
        raise ValueError('Local model directory needs a SenseVoice ONNX model and matching tokens.txt')
    return dict(model=str(model), tokens=str(tokens), model_sha256=digest(model),
                tokens_sha256=digest(tokens), source='user-local', integrity='recorded; compatibility checked when loaded')


def prepare(cache_dir=None, model_dir=None):
    if model_dir:
        return resolve_local(model_dir)
    folder = (Path(cache_dir) if cache_dir else default_cache()) / ('models/sensevoice-' + REVISION[:12])
    folder.mkdir(parents=True, exist_ok=True)
    if all((folder / name).is_file() and digest(folder / name) == sha for name, sha in FILES.items()):
        result = resolve_local(folder)
        result.update(source=BASE, revision=REVISION, integrity='sha256-verified')
        return result
    lock = folder / '.download.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError(f'Model download already active, or interrupted lock remains: {lock}')
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(str(os.getpid()))
        for name, sha in FILES.items():
            download(BASE + name, folder / name, sha)
    finally:
        lock.unlink(missing_ok=True)
    result = resolve_local(folder)
    result.update(source=BASE, revision=REVISION, integrity='sha256-verified')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--model-dir', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.cache_dir, args.model_dir), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'Model preparation failed: {exc}\n')


if __name__ == '__main__':
    main()
