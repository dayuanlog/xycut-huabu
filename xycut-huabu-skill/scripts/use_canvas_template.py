"""Resolve an installed canvas resource and optionally copy its project to a new task."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile
from contextlib import nullcontext


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def version_numbers(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Invalid canvas Skill version')
    return tuple(int(part) for part in value.split('.'))


def require_skill_version(minimum):
    skill_file = Path(__file__).resolve().parents[1] / 'SKILL.md'
    document = skill_file.read_text(encoding='utf-8-sig')
    frontmatter = re.match(r'\A---[ \t]*\n(.*?)\n---(?:\s|$)', document, re.DOTALL)
    metadata = re.search(r'^metadata:[ \t]*\n((?:[ \t]+[^\n]*(?:\n|$))*)', frontmatter[1], re.MULTILINE) if frontmatter else None
    version = re.search(r'^[ \t]+version:[ \t]*("[^"\n]*"|\x27[^\x27\n]*\x27|[^\s#]+)[ \t]*(?:#.*)?$', metadata[1], re.MULTILINE) if metadata else None
    if not version:
        raise ValueError('Missing metadata.version in canvas SKILL.md')
    current = version_numbers(version[1].strip('"\x27'))
    if version_numbers(minimum) > current:
        raise ValueError('Update canvas Skill before using this template')


def member(root, value):
    if not isinstance(value, str) or '\\' in value or ':' in value:
        raise ValueError('Invalid package member')
    rel = PurePosixPath(value)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise ValueError('Package member escapes package')
    path = root.joinpath(*rel.parts).resolve(strict=True)
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Package member escapes package')
    return path


def resolve(context_path, template_id, source='online'):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,99}', template_id):
        raise ValueError('Invalid template ID')
    context = read(context_path)
    if source not in ('online', 'local'):
        raise ValueError('Invalid template source')
    prefix = 'local_' if source == 'local' else ''
    if not all(context.get('paths', {}).get(prefix + key) for key in ('canvas_templates_dir', 'canvas_template_index_file')):
        raise ValueError('Template paths are missing; regenerate Agent Context in the current XYCut client')
    library = Path(context['paths'][prefix + 'canvas_templates_dir']).resolve(strict=True)
    index = read(Path(context['paths'][prefix + 'canvas_template_index_file']))
    candidates = index.get('templates', [])
    selected = [t for t in candidates if t.get('source', source) == source and template_id in (t.get('id'), t.get('slug'), t.get('template_id'))]
    if len(selected) != 1:
        raise ValueError('Select one installed template in XYCut first')
    item = selected[0]
    manifest_file = Path(item.get('manifest_file') or item.get('manifest_path') or Path(item['cache_path']) / 'canvas-template.json').resolve(strict=True)
    if not manifest_file.is_relative_to(library) or manifest_file.parent != library / template_id:
        raise ValueError('Manifest is outside client resource library')
    manifest = read(manifest_file)
    if manifest.get('kind') != 'canvas-video-template' or manifest.get('schema_version') != '1.0' or manifest.get('id') != template_id:
        raise ValueError('Invalid canvas template manifest')
    require_skill_version(manifest.get('min_skill_version', '0.7.0'))
    root = manifest_file.parent
    files = {key: str(member(root, manifest[key])) for key in ('entry', 'canvas_plan', 'cover', 'preview')}
    return manifest_file, manifest, files


def unpack(archive, destination):
    with zipfile.ZipFile(archive) as package:
        members = package.infolist()
        if len(members) > 10000 or sum(p.file_size for p in members) > 1024**3:
            raise ValueError('Template archive exceeds limits')
        seen = set()
        for item in members:
            name = item.filename
            rel = PurePosixPath(name)
            if '\\' in name or ':' in name or rel.is_absolute() or '..' in rel.parts or not rel.parts:
                raise ValueError('Invalid ZIP member')
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('ZIP links are not supported')
            if rel.as_posix().casefold() in seen:
                raise ValueError('Duplicate ZIP member')
            seen.add(rel.as_posix().casefold())
        package.extractall(destination)


def resolve_package(root):
    manifests = list(root.rglob('canvas-template.json'))
    if len(manifests) != 1:
        raise ValueError('Select a package with one canvas-template.json')
    manifest_file = manifests[0]
    manifest = read(manifest_file)
    if manifest.get('kind') != 'canvas-video-template' or manifest.get('schema_version') != '1.0':
        raise ValueError('Invalid canvas template manifest')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,99}', str(manifest.get('id', ''))):
        raise ValueError('Invalid template ID')
    require_skill_version(manifest.get('min_skill_version', '0.7.0'))
    files = {key: str(member(manifest_file.parent, manifest[key])) for key in ('entry', 'canvas_plan', 'cover', 'preview')}
    return manifest_file, manifest, files


def main():
    parser = argparse.ArgumentParser()
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--agent-context', type=Path)
    choice.add_argument('--package', type=Path, help='Standalone template directory or ZIP')
    parser.add_argument('--template-id')
    parser.add_argument('--source', choices=['online', 'local'], default='online')
    parser.add_argument('--task-dir', type=Path)
    args = parser.parse_args()
    if args.agent_context and not args.template_id:
        parser.error('--template-id is required with --agent-context')
    zipped = args.package and args.package.is_file() and args.package.suffix.lower() == '.zip'
    if zipped and not args.task_dir:
        parser.error('ZIP input requires --task-dir so extracted project paths remain usable')
    with tempfile.TemporaryDirectory(prefix='canvas-template-') if zipped else nullcontext(None) as temporary:
        if zipped:
            unpack(args.package, Path(temporary))
        manifest_file, manifest, files = resolve_package(Path(temporary) if zipped else args.package.resolve(strict=True)) if args.package else resolve(args.agent_context, args.template_id, args.source)
        result = dict(template_id=manifest['id'], template_source='package' if args.package else args.source,
                      manifest_file=str(args.package.resolve() if zipped else manifest_file),
                      manifest_sha256=hashlib.sha256(manifest_file.read_bytes()).hexdigest(), example_timing_only=True, files=files)
        if args.task_dir:
            source = manifest_file.parent / 'project'
            if not source.is_dir() or any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in source.rglob('*')):
                raise ValueError('Invalid self-contained project')
            from package_canvas_template import check_references
            check_references(source)
            if args.task_dir.exists():
                if not (args.task_dir / 'task_manifest.json').is_file() or (args.task_dir / 'output/canvas-project').exists() or (args.task_dir / 'planning/template-reference.json').exists():
                    raise FileExistsError('Use a new task workspace with no existing canvas project')
            else:
                args.task_dir.mkdir(parents=True, exist_ok=False)
                (args.task_dir / 'planning').mkdir()
                (args.task_dir / 'input').mkdir()
            shutil.copytree(source, args.task_dir / 'output/canvas-project')
            if zipped:
                result['files'] = {key: str((args.task_dir / 'output/canvas-project' / Path(files[key]).relative_to(source.resolve())).resolve()) for key in ('entry', 'canvas_plan')}
            (args.task_dir / 'planning/template-reference.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            result['project'] = str((args.task_dir / 'output/canvas-project').resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
