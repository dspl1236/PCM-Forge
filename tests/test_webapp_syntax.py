"""The web app is one file served straight to users from main, so a single
syntax error in its inline JavaScript takes the whole site down. Check every
inline <script> block with `node --check`. Skipped when Node is not installed.
"""
import os
import re
import shutil
import subprocess

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP = os.path.join(REPO_ROOT, 'docs', 'index.html')
NODE = shutil.which('node')


def inline_scripts():
    html = open(WEBAPP, encoding='utf-8').read()
    # inline blocks only: <script src=...> (the coffee button) has no body to check
    return re.findall(r'<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>', html)


def test_webapp_has_inline_script():
    assert inline_scripts(), 'no inline <script> found in docs/index.html'


@pytest.mark.skipif(NODE is None, reason='node not installed')
@pytest.mark.parametrize('index', range(len(inline_scripts())))
def test_inline_script_parses(index, tmp_path):
    src = tmp_path / ('block%d.js' % index)
    src.write_text(inline_scripts()[index], encoding='utf-8')
    r = subprocess.run([NODE, '--check', str(src)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
