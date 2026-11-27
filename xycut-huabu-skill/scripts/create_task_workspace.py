"""Create one exclusive canvas task without requiring XYCut or another Skill."""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import unicodedata


def create_task_workspace(tasks_root, label='', mode='standalone', now=None):
    tasks_root = Path(tasks_root).expanduser().resolve()
    tasks_root.mkdir(parents=True, exist_ok=True)
    label = re.sub(r'[^\w-]+', '_', unicodedata.normalize('NFKC', label)).strip('_-')[:32]
    now = now or datetime.now().astimezone()
    for i in range(10000):
        stamp = now + timedelta(milliseconds=i)
        name = stamp.strftime('%Y%m%d_%H%M%S_') + f'{stamp.microsecond // 1000:03d}'
        target = tasks_root / (name + ('_' + label if label else ''))
        try:
            target.mkdir()
        except FileExistsError:
            continue
        for subdir in ('input', 'speech', 'planning', 'output'):
            (target / subdir).mkdir()
        manifest = dict(schema_version=1, kind='canvas-video-task', task_id=target.name,
                        created_at=stamp.isoformat(), runtime_mode=mode, label=label)
        (target / 'task_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return target
    raise FileExistsError('No free task directory after 10000 attempts')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks-root', type=Path, required=True)
    parser.add_argument('--label', default='')
    parser.add_argument('--mode', choices=['xycut', 'standalone'], default='standalone')
    args = parser.parse_args()
    task = create_task_workspace(args.tasks_root, args.label, args.mode)
    print(json.dumps(dict(task_id=task.name, task_dir=str(task), manifest_file=str(task / 'task_manifest.json')), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
