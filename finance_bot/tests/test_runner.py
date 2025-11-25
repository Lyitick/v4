"""Helper to run tests programmatically."""
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Run pytest suite and return exit code."""

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", str(root / "tests")], check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
