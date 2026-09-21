"""Reverse only exact reviewed v2.45 hunks before the immutable historical audits.

This is an allowlist, not a function-name mask. Any byte changed in an approved
hunk or outside it fails. Review the manifest as production code when updating it.
"""
from pathlib import Path
import hashlib
import json

MANIFEST = json.loads((Path(__file__).with_name('v245_reviewed_scope.json')).read_text(encoding='utf-8'))


def project_v245(name, code):
    record = MANIFEST['files'].get(name)
    if record is None:
        return code
    for patch in record['patches']:
        assert code.count(patch['after']) == 1, 'Changed/missing reviewed v2.45 hunk: ' + name
        code = code.replace(patch['after'], patch['before'], 1)
    assert hashlib.sha256(code.encode()).hexdigest() == record['main_sha256'], 'Unreviewed v2.45 change: ' + name
    return code
