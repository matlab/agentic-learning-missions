"""Portable entry point for the author evaluation infrastructure."""

import sys

# These scripts ship with authoring assets; keep runtime bytecode out of bundles.
sys.dont_write_bytecode = True

from mission_evals.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
