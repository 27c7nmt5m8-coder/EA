import hashlib
from pathlib import Path
import tempfile
import unittest
from xml.sax.saxutils import escape
from native_preflight import inspect_events


class Events(unittest.TestCase):
    def test_only_enforced_matching_binary_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'fixture.exe'
            binary.write_bytes(b'synthetic bytes, not an executable')
            sha = hashlib.sha256(binary.read_bytes()).hexdigest()
            path = escape('\\Device\\TestVolume' + str(binary.resolve())[2:].replace('/', '\\'))
            def event(event_id, digest):
                return f'''<Events><Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
                <System><EventID>{event_id}</EventID><TimeCreated SystemTime="2026-01-01T00:00:00Z"/></System>
                <EventData><Data Name="File Name">{path}</Data><Data Name="SHA256 Flat Hash">{digest}</Data>
                <Data Name="PolicyName">fixture-policy</Data></EventData></Event></Events>'''
            self.assertEqual(inspect_events(event(3077, sha), [binary])['status'], 'BLOCKED')
            self.assertEqual(inspect_events(event(3077, '0'*64), [binary])['status'], 'UNKNOWN')
            self.assertEqual(inspect_events(event(3033, sha), [binary])['status'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
