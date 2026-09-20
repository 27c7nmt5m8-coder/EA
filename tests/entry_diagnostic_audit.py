"""Reverse only the exact reviewed instrumentation, retaining all baseline gates.

Each new and old hunk is explicit and occurs once. No pattern-based deletion of
arbitrary diagnostic code and no historical hash replacement is permitted.
"""
import json
from pathlib import Path

EDITS = json.loads((Path(__file__).with_name('entry_diagnostic_projection.json')).read_text())

def project(name, text):
    for edit in reversed(EDITS):
        if edit['file'] != 'src/' + name:
            continue
        assert text.count(edit['new']) == 1, 'Changed/missing reviewed diagnostic hunk: ' + name
        text = text.replace(edit['new'], edit['old'], 1)
    return text
