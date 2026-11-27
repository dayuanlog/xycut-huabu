"""Export a self-contained project as a client-importable canvas template ZIP."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.pytest_cache', '.cache'}
SKIP_SUFFIXES = {'.log', '.tmp', '.bak', '.pyc'}


def files(project):
    for parent, dirs, names in os.walk(project, followlinks=False):
        parent = Path(parent)
        for name in dirs + names:
            p = parent / name
            if p.is_symlink() or getattr(p, 'is_junction', lambda: False)():
                raise ValueError(f'Linked resource is not supported: {p}')
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for name in names:
            p = parent / name
            if name != '.DS_Store' and p.suffix.lower() not in SKIP_SUFFIXES:
                yield p


def check_references(project):
    for p in project.rglob('*'):
        if p.suffix.lower() not in {'.html', '.css', '.js', '.mjs'}:
            continue
        text = p.read_text(encoding='utf-8-sig')
        if re.search(r'file:///|(?<![A-Za-z0-9])[A-Za-z]:[\\/]', text):
            raise ValueError(f'Remove machine-specific absolute paths: {p}')
        if p.suffix.lower() == '.html':
            tags = re.findall(r'<(?:script|link|img|video|audio|source)\b[^>]*>', text, re.I)
            refs = [ref for tag in tags for ref in re.findall(r'\b(?:src|href|poster)=["\']([^"\']+)', tag, re.I)]
        elif p.suffix.lower() == '.css':
            refs = re.findall(r'url\(\s*["\']?([^\s)"\']+)', text)
        else:
            refs = []
        for ref in refs:
            if ref.startswith(('data:', '#')) or '${' in ref:
                continue
            if re.match(r'^(?:[a-z]+:|/)', ref, re.I):
                raise ValueError(f'Bundle external resource locally: {p}: {ref}')
            target = (p.parent / ref.split('#')[0].split('?')[0]).resolve()
            if not target.is_relative_to(project.resolve()) or not target.is_file():
                raise ValueError(f'Missing or escaping dependency: {p}: {ref}')


def package(project, destination, template_id, name, theme, cover, preview,
            narrative_mode='canvas-led', presenter=False):
    project, destination = project.resolve(strict=True), destination.resolve()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,99}', template_id):
        raise ValueError('Use a lowercase alphanumeric template ID with hyphens or underscores')
    if not name.strip() or theme not in ('dark', 'light'):
        raise ValueError('A name and dark/light theme are required')
    if destination.suffix.lower() != '.zip' or destination.exists() or destination.is_relative_to(project):
        raise ValueError('Choose a new ZIP path outside the source project')
    if cover.suffix.lower() != '.png' or preview.suffix.lower() != '.mp4':
        raise ValueError('Provide a PNG cover and MP4 preview')
    if not cover.is_file() or not preview.is_file():
        raise ValueError('Cover or preview does not exist')
    plan = json.loads((project / 'canvas-plan.json').read_text(encoding='utf-8-sig'))
    output = plan['output']
    for key in ('width', 'height', 'fps'):
        value = output.get(key)
        if type(value) is not int or not 0 < value <= (120 if key == 'fps' else 8192):
            raise ValueError('Invalid output dimensions or frame rate')
    if not isinstance(plan.get('boards'), list) or not isinstance(plan.get('components'), list):
        raise ValueError('Plan must contain boards and components')
    if narrative_mode not in ('canvas-led', 'presenter-led') or narrative_mode == 'presenter-led' and not presenter:
        raise ValueError('Presenter-led templates require presenter media')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='canvas-export-') as temp:
        stage = Path(temp)
        for source in files(project):
            target = stage / 'project' / source.relative_to(project)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        if not (stage / 'project/index.html').is_file():
            raise ValueError('Project must contain index.html')
        check_references(stage / 'project')
        shutil.copy2(cover, stage / 'cover.png')
        shutil.copy2(preview, stage / 'preview.mp4')
        manifest = dict(schema_version='1.0', kind='canvas-video-template', id=template_id,
                        name=name, theme=theme, narrative_mode=narrative_mode, presenter=presenter,
                        output=output, min_skill_version='0.7.0', entry='project/index.html',
                        canvas_plan='project/canvas-plan.json', cover='cover.png', preview='preview.mp4',
                        duration=plan.get('duration', 0),
                        reference_policy='Style and component reference; replan for new script and final ASR.')
        license_file = stage / 'project/assets/ui-kit/ANT_DESIGN_LICENSE.txt'
        if license_file.exists():
            manifest['notices'] = license_file.relative_to(stage).as_posix()
        (stage / 'canvas-template.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        members = [p for p in stage.rglob('*') if p.is_file()]
        if len(members) > 10000 or sum(p.stat().st_size for p in members) > 1024**3:
            raise ValueError('Template exceeds client package limits; compact preview/media first')
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.zip', delete=False) as handle:
            archive_path = Path(handle.name)
        try:
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
                for p in sorted(members):
                    archive.write(p, p.relative_to(stage).as_posix())
            if archive_path.stat().st_size > 512 * 1024**2:
                raise ValueError('ZIP exceeds client 512 MB limit')
            # Exclusive creation avoids replacing a user file if another export finishes first.
            with destination.open('xb') as out, archive_path.open('rb') as src:
                shutil.copyfileobj(src, out)
        finally:
            archive_path.unlink(missing_ok=True)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--id', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--theme', choices=['dark', 'light'], required=True)
    p.add_argument('--cover', type=Path, required=True)
    p.add_argument('--preview', type=Path, required=True)
    p.add_argument('--narrative-mode', choices=['canvas-led', 'presenter-led'], default='canvas-led')
    p.add_argument('--presenter', action='store_true')
    a = p.parse_args()
    result = package(a.project, a.output, a.id, a.name, a.theme, a.cover, a.preview, a.narrative_mode, a.presenter)
    print(json.dumps(dict(zip=str(a.output.resolve()), template_id=result['id']), ensure_ascii=False))


if __name__ == '__main__':
    main()
