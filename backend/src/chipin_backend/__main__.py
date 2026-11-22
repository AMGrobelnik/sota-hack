"""``python -m chipin_backend``: the same command line as ``chipin-backend``."""

import sys

from chipin_backend.cli import main

if __name__ == "__main__":
    sys.exit(main())
