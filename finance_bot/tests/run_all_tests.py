"""Run all pytest suites."""
import pytest


if __name__ == "__main__":
    raise SystemExit(pytest.main(["-q", "tests"]))
