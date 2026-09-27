"""Read existing enforced Code Integrity events; never launch a probe binary."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

NS = {'e': 'http://schemas.microsoft.com/win/2004/08/events/event'}


def inspect_events(xml, candidates):
    for event in ET.fromstring(xml).findall('e:Event', NS):
        if event.findtext('e:System/e:EventID', namespaces=NS) != '3077':
            continue
        data = {d.get('Name'): d.text or '' for d in event.findall('e:EventData/e:Data', NS)}
        for path in candidates:
            if not path.is_file():
                continue
            suffix = str(path.resolve())[2:].replace('/', '\\').lower()
            if not data.get('File Name', '').lower().endswith(suffix):
                continue
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            if sha != data.get('SHA256 Flat Hash', '').lower():
                continue
            return {'status': 'BLOCKED', 'reason': 'Application Control / Code Integrity',
                    'binary': path.name, 'sha256': sha, 'event_id': 3077,
                    'utc': event.find('e:System/e:TimeCreated', NS).get('SystemTime'),
                    'policy': data.get('PolicyName'), 'block_status': data.get('Status'),
                    'evidence': 'historical enforced block, current binary hash matched; no launch attempted'}
    return {'status': 'UNKNOWN', 'reason': 'No current-binary hash match; absence is not PASS'}


def preflight():
    if os.name != 'nt':
        return {'status': 'UNKNOWN', 'reason': 'Windows event log not available'}
    root = Path(__file__).resolve().parents[1]
    candidates = [root / 'verification' / name for name in ('integration.exe', 'json_test.exe')]
    compiler = shutil.which('g++')
    if compiler:
        candidates.append(Path(compiler))
        candidates.extend((Path(compiler).parent.parent / 'lib/gcc').glob('**/cc1plus.exe'))
    try:
        p = subprocess.run(['wevtutil.exe', 'qe', 'Microsoft-Windows-CodeIntegrity/Operational',
                            '/q:*[System[(EventID=3077)]]', '/c:256', '/rd:true', '/f:xml', '/e:Events'],
                           capture_output=True, timeout=30, check=True)
        return inspect_events(p.stdout, candidates)
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError):
        return {'status': 'UNKNOWN', 'reason': 'Code Integrity event log unavailable'}
