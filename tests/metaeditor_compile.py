"""Compile copies in .validation; never launch MT5 or deploy EX5."""
import hashlib
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def compile_sources(editor, include, out, sha):
    result = {'status': 'NOT_RUN', 'commit': sha, 'builds': []}
    if not include or not (Path(include) / 'Include/Trade/Trade.mqh').is_file():
        result['reason'] = 'MQL5 standard Include directory unavailable'
        return result
    target = out / 'metaeditor'
    target.mkdir(exist_ok=True)
    result['source_sha256'] = {}
    for source in sorted((ROOT / 'src').iterdir()):
        if source.is_file():
            shutil.copyfile(source, target / source.name)
            result['source_sha256'][source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    for name in ['MTFAutoTrader_3Mode_AI_v2_44.mq5', 'MTFAutoTrader_AI_Worker.mq5']:
        log = target / (name + '.log')
        ex5 = target / Path(name).with_suffix('.ex5')
        log.unlink(missing_ok=True)
        ex5.unlink(missing_ok=True)
        try:
            subprocess.run([editor, '/compile:' + str(target / name), '/inc:' + str(include), '/log:' + str(log)],
                           timeout=180, capture_output=True)
        except (OSError, subprocess.TimeoutExpired):
            result['status'] = 'BLOCKED'
            return result
        text = log.read_text(encoding='utf-16', errors='replace') if log.exists() else ''
        match = re.search(r'Result: (\d+) errors?, (\d+) warnings?', text)
        passed = match is not None and match.groups() == ('0', '0') and ex5.is_file()
        result['builds'].append({'source': name, 'status': 'PASS' if passed else 'FAIL',
                                 'errors': int(match[1]) if match else None,
                                 'warnings': int(match[2]) if match else None})
    result['status'] = 'PASS' if all(b['status'] == 'PASS' for b in result['builds']) else 'FAIL'
    return result
