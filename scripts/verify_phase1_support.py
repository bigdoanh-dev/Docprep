"""Shared subprocess helper: fixed local Compose project, no shell or secret output."""
from pathlib import Path
import subprocess


def compose(args):
    result=subprocess.run(['docker','compose','--env-file','.env.phase1','-f','deploy/compose.phase1.yml']+args,
        cwd=Path(__file__).resolve().parents[1],text=True,encoding='utf-8',capture_output=True)
    if result.returncode: raise RuntimeError('Local Phase 1 operation failed: '+' '.join(args[:3]))
    return result.stdout.strip()
