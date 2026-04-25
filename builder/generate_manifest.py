"""
Generate docs/app/manifest.json from the local modules/ directory tree.

This manifest is consumed by docs/index.html so the in-browser USB
builder can fetch all module files at runtime from raw.githubusercontent.com.

Re-run whenever modules are added, removed, or files change:
    python builder/generate_manifest.py

Output: docs/app/manifest.json
"""
import json
import os
import sys
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
MODULES_DIR = os.path.join(REPO_ROOT, 'modules')
CORE_DIR = os.path.join(REPO_ROOT, 'core')
OUT_DIR = os.path.join(REPO_ROOT, 'docs', 'app')
OUT_FILE = os.path.join(OUT_DIR, 'manifest.json')

RAW_BASE = 'https://raw.githubusercontent.com/dspl1236/PCM-Forge/main/'
CORE_FILES = {
    'copie_scr_sh': 'core/copie_scr.sh',
    'showScreen': 'core/bin/showScreen',
    'lib_running_png': 'core/lib/running.png',
    'lib_done_png': 'core/lib/done.png',
    'lib_activating_png': 'core/lib/activating.png',
    'lib_activating_done_png': 'core/lib/activating-done.png',
}


def walk_module(mod_dir):
    """Return a list of {path, size} for every file in a module directory."""
    files = []
    for root, _, fnames in os.walk(mod_dir):
        for fname in sorted(fnames):
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, mod_dir)
            files.append({'path': rel, 'size': os.path.getsize(fpath)})
    return files


def build_manifest():
    manifest = {
        'generated': str(date.today()),
        'branch': 'main',
        'raw_url_base': RAW_BASE,
        'core_files': {},
        'modules': {},
    }

    # Core files
    for key, rel_path in CORE_FILES.items():
        full_path = os.path.join(REPO_ROOT, rel_path)
        if os.path.exists(full_path):
            manifest['core_files'][key] = rel_path

    # Modules
    if not os.path.isdir(MODULES_DIR):
        print(f'  No modules/ directory found at {MODULES_DIR}')
        return manifest

    total_files = 0
    total_bytes = 0

    for mod_name in sorted(os.listdir(MODULES_DIR)):
        mod_dir = os.path.join(MODULES_DIR, mod_name)
        if not os.path.isdir(mod_dir):
            continue

        mod_json_path = os.path.join(mod_dir, 'module.json')
        if not os.path.exists(mod_json_path):
            continue

        with open(mod_json_path) as f:
            mod_meta = json.load(f)

        files = walk_module(mod_dir)
        total_files += len(files)
        total_bytes += sum(f['size'] for f in files)

        manifest['modules'][mod_name] = {
            'status': mod_meta.get('status', 'alpha'),
            'description': mod_meta.get('description', ''),
            'standalone': mod_meta.get('standalone', True),
            'run_script': mod_meta.get('run_script'),
            'script_dir': mod_meta.get('script_dir'),
            'installs_to_flash': mod_meta.get('installs_to_flash', False),
            'compatible': mod_meta.get('compatible', []),
            'options': mod_meta.get('options', {}),
            'files': files,
        }

    print(f'  {len(manifest["modules"])} modules, {total_files} files, {total_bytes:,} bytes total')
    return manifest


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = build_manifest()
    with open(OUT_FILE, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f'  Written to {OUT_FILE}')
