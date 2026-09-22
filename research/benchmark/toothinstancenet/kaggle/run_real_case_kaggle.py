# Kaggle single-cell launcher for the real-case artifact workflow.
from pathlib import Path
import subprocess
import sys

project = Path('/kaggle/working/AlignerStudio')
command = [sys.executable, str(project / 'research/benchmark/toothinstancenet/kaggle/run_real_case.py')]
subprocess.run(command, check=True)
print('/kaggle/working/toothinstancenet-real-case-artifact.zip')
