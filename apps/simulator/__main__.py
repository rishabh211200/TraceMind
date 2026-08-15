"""Executable entrypoint for python -m apps.simulator."""

import sys

from apps.simulator.cli import run_cli

if __name__ == "__main__":
    sys.exit(run_cli())
