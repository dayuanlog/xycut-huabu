"""Download one indexed template, verify it, and optionally copy it to a task."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from use_canvas_template import require_skill_version, resolve_package, unpack, version_numbers


DEFAULT_INDEX = 'https://raw.githubusercontent.com/dayuanlog/xycut-huabu/main/templates/index.json'
MAX_INDEX_BYTES = 2 * 1024**2
MAX_PACKAGE_BYTES = 512 * 1024**2
IO_TIMEOUT = 30
TRANSFER_TIMEOUT = 300
CHUNK_BYTES = 256 * 1024
ID_PATTERN = re.compile(r'[a-z0-9][a-z0-9_-]{0,99}')
SHA_PATTERN = re.compile(r'[a-fA-F0-9]{64}')


def remote_url(value):
    parsed = urlparse(str(value))
    if parsed.scheme in ('http', 'https') and parsed.netloc:
        return str(value)
    return None


@contextmanager
def open_source(source):
    if remote_url(source):
        request = Request(str(source), headers={'User-Agent': 'xycut-huabu-template/1'})
        with urlopen(request, timeout=IO_TIMEOUT) as response:
            if not remote_url(response.geturl()):
                raise ValueError('Template download redirected to an unsupported URL')
            yield response
    else:
        with Path(source).open('rb') as stream:
            yield stream


def read_index(index):
    source = remote_url(index) or Path(index).expanduser().resolve(strict=True)
    with open_source(source) as stream:
        raw = stream.read(MAX_INDEX_BYTES + 1)
        if remote_url(source):
            source = stream.geturl()
    if len(raw) > MAX_INDEX_BYTES:
        raise ValueError('Template index exceeds size limit')
    data = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1 or not isinstance(data.get('templates'), list):
        raise ValueError('Invalid template index schema')
    seen = set()
    for item in data['templates']:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not ID_PATTERN.fullmatch(item['id']):
            raise ValueError('Invalid template ID in index')
        if item['id'] in seen:
            raise ValueError('Duplicate template ID in index')
        seen.add(item['id'])
        if not isinstance(item.get('name'), str) or not item['name'].strip():
            raise ValueError('Template name is required')
        if not isinstance(item.get('download_url'), str) or not item['download_url'].strip():
            raise ValueError('Template download URL is required')
        if not isinstance(item.get('sha256'), str) or not SHA_PATTERN.fullmatch(item['sha256']):
            raise ValueError('A valid template SHA256 is required')
        if 'min_skill_version' in item:
            version_numbers(item['min_skill_version'])
    return source, data['templates']


def download_source(index_source, value):
    if remote_url(index_source):
        resolved = urljoin(str(index_source), value)
        if not remote_url(resolved):
            raise ValueError('Template URL must use HTTP or HTTPS')
        return resolved
    if remote_url(value):
        return value
    if urlparse(value).scheme:
        raise ValueError('Unsupported template URL scheme')
    return (Path(index_source).parent / value).resolve(strict=True)


def file_sha256(path):
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(CHUNK_BYTES):
            size += len(chunk)
            if size > MAX_PACKAGE_BYTES:
                raise ValueError('Template package exceeds size limit')
            digest.update(chunk)
    return digest.hexdigest()


def validate_package(package, template_id):
    with tempfile.TemporaryDirectory(prefix='huabu-package-check-') as temporary:
        root = Path(temporary)
        unpack(package, root)
        _, manifest, _ = resolve_package(root)
        if manifest['id'] != template_id:
            raise ValueError('Template package ID does not match index')


def transfer(source, destination, expected_sha256):
    started = time.monotonic()
    created = False
    try:
        with destination.open('xb') as output:
            created = True
            with open_source(source) as stream:
                headers = getattr(stream, 'headers', {})
                length = headers.get('Content-Length')
                if length and int(length) > MAX_PACKAGE_BYTES:
                    raise ValueError('Template package exceeds size limit')
                size = 0
                digest = hashlib.sha256()
                while chunk := stream.read(CHUNK_BYTES):
                    size += len(chunk)
                    if size > MAX_PACKAGE_BYTES:
                        raise ValueError('Template package exceeds size limit')
                    if time.monotonic() - started > TRANSFER_TIMEOUT:
                        raise TimeoutError('Template package download timed out')
                    output.write(chunk)
                    digest.update(chunk)
                if digest.hexdigest() != expected_sha256:
                    raise ValueError('Template package SHA256 mismatch')
                output.flush()
                os.fsync(output.fileno())
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise


def download_template(template_id, index=DEFAULT_INDEX, cache_dir=None, task_dir=None):
    if not isinstance(template_id, str) or not ID_PATTERN.fullmatch(template_id):
        raise ValueError('Invalid template ID')
    index_source, entries = read_index(index)
    if not entries:
        raise ValueError('No templates are currently available in this index')
    selected = next((item for item in entries if item['id'] == template_id), None)
    if selected is None:
        raise ValueError(f'Template not found in index: {template_id}')
    if selected.get('min_skill_version'):
        require_skill_version(selected['min_skill_version'])
    expected = selected['sha256'].lower()
    cache_root = Path(cache_dir).expanduser() if cache_dir else Path.home() / '.cache' / 'xycut-huabu' / 'templates'
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root = cache_root.resolve(strict=True)
    package = cache_root / f'{template_id}-{expected}.zip'
    partial = package.with_suffix('.zip.part')
    if package.is_symlink() or partial.is_symlink():
        raise ValueError('Linked template cache files are not supported')
    cache_hit = package.exists()
    if cache_hit:
        if file_sha256(package) != expected:
            raise ValueError('Cached template SHA256 mismatch; remove the damaged cache file and retry')
        validate_package(package, template_id)
    else:
        source = download_source(index_source, selected['download_url'])
        downloaded = False
        try:
            transfer(source, partial, expected)
            downloaded = True
            validate_package(partial, template_id)
            partial.replace(package)
        except BaseException:
            if downloaded:
                partial.unlink(missing_ok=True)
            raise
    result = {'template_id': template_id, 'package_file': str(package), 'cache_hit': cache_hit, 'sha256': expected}
    if task_dir is not None:
        helper = Path(__file__).with_name('use_canvas_template.py')
        copied = subprocess.run([sys.executable, str(helper), '--package', str(package), '--task-dir', str(Path(task_dir).expanduser())],
                                capture_output=True, text=True, encoding='utf-8', timeout=TRANSFER_TIMEOUT,
                                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        if copied.returncode:
            raise ValueError(copied.stderr.strip() or 'Unable to copy template to task workspace')
        result['task'] = json.loads(copied.stdout)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template-id', required=True)
    parser.add_argument('--index', default=DEFAULT_INDEX, help='HTTP(S) index URL or local JSON path')
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--task-dir', type=Path)
    args = parser.parse_args()
    try:
        result = download_template(args.template_id, args.index, args.cache_dir, args.task_dir)
    except Exception as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
