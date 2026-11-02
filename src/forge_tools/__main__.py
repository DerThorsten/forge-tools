"""Allow running the CLI via ``python -m forge_tools``."""

import sys

from forge_tools.cli import main

sys.exit(main())
