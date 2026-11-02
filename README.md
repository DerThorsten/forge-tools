# forge-tools

A collection of small command line tools, built on `argparse`.

## Development setup

```bash
micromamba create -f environment-dev.yaml
micromamba activate forge-tools-dev
python -m pip install --no-deps --no-build-isolation -e .
pytest
```

## Usage

```bash
forge-tools --help
```

## Adding a sub-command

1. Put the actual functionality in a library module `src/forge_tools/<name>.py`
   with a plain Python API (keyword arguments, return values, raise exceptions;
   no argparse, no exit codes, no `sys.exit`), so it can be used from Python:
   `from forge_tools.<name> import ...`.
2. Create a thin CLI module `src/forge_tools/cli/<name>.py` that defines
   `register(subparsers)` (returns the sub-parser) and `run(args)` (calls the
   library and turns its result / exceptions into an exit code).
3. Add the CLI module to `COMMANDS` in `src/forge_tools/cli/__init__.py`.
4. Add tests in `tests/`.
5. For diagnostics use `logger = logging.getLogger(__name__)`; don't configure
   logging in the command. `forge-tools --log-level LEVEL` (also accepted after
   the sub-command, or via `$FORGE_TOOLS_LOG_LEVEL`) sets the level centrally
   (`src/forge_tools/cli/log.py` for the option, `src/forge_tools/log.py` for
   `setup_logging()`). Logs go to stderr; print actual results to stdout.
