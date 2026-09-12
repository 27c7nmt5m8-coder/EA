"""Run the shipped offline validation gates. No connection to MT5 or a broker."""
from pathlib import Path
import subprocess
import sys

directory = Path(__file__).resolve().parent
for name in ['verify_v244.py', 'verify_json_regression.py', 'verify_stats.py', 'audit_source.py']:
    print(name, flush=True)
    subprocess.run([sys.executable, str(directory / name)], check=True)
