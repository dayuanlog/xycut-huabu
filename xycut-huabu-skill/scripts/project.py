"""Create, inspect and continue standalone projects without client state."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path

from create_task_workspace import create_task_workspace
from local_settings import atomic_json, effective_settings, outside_repository, SECRET_FIELDS

STATUSES = ('created', 'speech_ready', 'planning', 'preview_ready', 'awaiting_confirmation', 'preview_confirmed', 'completed', 'speech_failed')


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def read_project(task):
    task = Path(task).expanduser().resolve(strict=True)
    manifest_path = task / 'task_manifest.json'
    if manifest_path.is_symlink():
        raise ValueError('Linked project manifests are not supported')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    if manifest.get('schema_version', 1) != 1:
        raise ValueError('Unsupported project schema_version')
    if manifest.get('task_id') != task.name or manifest.get('kind', 'canvas-video-task') != 'canvas-video-task':
        raise ValueError('Project identity does not match its directory')
    if manifest.get('runtime_mode', 'standalone') != 'standalone':
        raise ValueError('This command manages standalone projects only')
    for key, default in [('status', 'created'), ('revision', 0), ('input', {}), ('speech', {}), ('selection', {}), ('artifacts', {}), ('history', [])]:
        manifest.setdefault(key, default)
    return task, manifest


@contextmanager
def project_lock(task, name='.project.lock'):
    task = Path(task).resolve(strict=True)
    path = task / name
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RuntimeError('Project operation already running; inspect the lock before retrying: ' + str(path)) from error
    try:
        with os.fdopen(descriptor, 'w', encoding='ascii') as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)


def assert_no_credentials(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in SECRET_FIELDS:
                raise ValueError('Credentials belong in private settings, not project records')
            assert_no_credentials(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_credentials(item)


def update_project(task, changes, event):
    assert_no_credentials(changes)
    task = Path(task).resolve(strict=True)
    with project_lock(task):
        _, manifest = read_project(task)
        if changes.get('status', manifest['status']) not in STATUSES:
            raise ValueError('Unknown project status')
        for key, value in changes.items():
            if key in ('input', 'speech', 'selection', 'artifacts'):
                manifest[key].update(value)
            elif key == 'status':
                manifest[key] = value
            else:
                raise ValueError('Unsupported project field: ' + key)
        manifest['revision'] += 1
        manifest['updated_at'] = now()
        manifest['history'] = (manifest['history'] + [{'at': now(), 'event': event}])[-200:]
        atomic_json(task / 'planning/records' / f'{manifest["revision"]:06d}.json', manifest)
        atomic_json(task / 'task_manifest.json', manifest)
    return manifest


def artifact(task, path):
    task = Path(task).resolve(strict=True)
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_relative_to(task) or not path.is_file():
        raise ValueError('Project artifacts must be files inside the task directory')
    return {'path': path.relative_to(task).as_posix(), 'sha256': file_hash(path), 'size_bytes': path.stat().st_size}


def create_project(config_dir=None, projects_root=None, label=''):
    settings = effective_settings(config_dir)
    root = outside_repository(projects_root or settings['projects_root'])
    task = create_task_workspace(root, label, mode='standalone')
    update_project(task, {}, 'project_created')
    return {'task_dir': str(task), 'manifest_file': str(task / 'task_manifest.json'), 'status': 'created'}


def resume_project(task):
    task, manifest = read_project(task)
    issues = []
    for section in ('input', 'artifacts'):
        for name, record in manifest[section].items():
            if not isinstance(record, dict) or 'path' not in record:
                continue
            if record.get('stale'):
                issues.append(name + ': needs updating after speech changed')
            path = (task / record['path']).resolve()
            if not path.is_relative_to(task) or not path.is_file():
                issues.append(name + ': missing or outside project')
            elif record.get('sha256') and file_hash(path) != record['sha256']:
                issues.append(name + ': changed since recording')
    return {'task_dir': str(task), 'manifest': manifest, 'artifacts_valid': not issues, 'issues': issues,
            'instruction': 'Continue this same project. Reuse verified speech; do not treat recorded preview status as new user approval.'}


def list_projects(config_dir=None, projects_root=None, limit=20):
    root = outside_repository(projects_root or effective_settings(config_dir)['projects_root'])
    items = []
    if root.is_dir():
        for file in sorted(root.glob('*/task_manifest.json'), reverse=True):
            try:
                task, manifest = read_project(file.parent)
            except (ValueError, OSError, TypeError):
                continue
            items.append({'task_dir': str(task), 'task_id': manifest['task_id'], 'label': manifest.get('label'), 'status': manifest['status'], 'updated_at': manifest.get('updated_at', manifest.get('created_at'))})
            if len(items) >= limit:
                break
    return {'projects_root': str(root), 'projects': items}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-dir', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    create.add_argument('--projects-root', type=Path)
    create.add_argument('--label', default='')
    listing = commands.add_parser('list')
    listing.add_argument('--projects-root', type=Path)
    listing.add_argument('--limit', type=int, default=20)
    for name in ('resume', 'record'):
        command = commands.add_parser(name)
        command.add_argument('--task-dir', type=Path, required=True)
        if name == 'record':
            command.add_argument('--template-id')
            command.add_argument('--orientation', choices=['landscape', 'portrait'])
            command.add_argument('--title')
            command.add_argument('--status', choices=STATUSES)
            command.add_argument('--preview-file', type=Path)
            command.add_argument('--video-file', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'create':
            result = create_project(args.config_dir, args.projects_root, args.label)
        elif args.command == 'list':
            if args.limit < 1:
                raise ValueError('limit must be positive')
            result = list_projects(args.config_dir, args.projects_root, args.limit)
        elif args.command == 'resume':
            result = resume_project(args.task_dir)
        else:
            changes = {'selection': {key: value for key, value in {'template_id': args.template_id, 'orientation': args.orientation, 'title': args.title}.items() if value is not None}, 'artifacts': {}}
            if args.status:
                changes['status'] = args.status
            for name, path in [('preview', args.preview_file), ('video', args.video_file)]:
                if path:
                    changes['artifacts'][name] = artifact(args.task_dir, path)
            result = update_project(args.task_dir, changes, 'project_updated')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, TypeError, RuntimeError) as error:
        parser.exit(1, 'Project error: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
