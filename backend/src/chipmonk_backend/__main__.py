"""``python -m chipmonk_backend``: the same command line as ``chipmonk-backend``."""

import sys

from chipmonk_backend.cli import main

if __name__ == "__main__":
    sys.exit(main())
