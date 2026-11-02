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

1. Create a module in `src/forge_tools/commands/` that defines
   `register(subparsers)` (returns the sub-parser) and `run(args)` (returns an exit code).
2. Add the module to `COMMANDS` in `src/forge_tools/commands/__init__.py`.
3. Add tests in `tests/`.
