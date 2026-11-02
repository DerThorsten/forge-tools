# Emscripten-forge
Emscripten-forge is a GitHub organization/repository containing conda recipes for the emscripten-wasm32 / emscripten-wasm64 platforms.
Conda-forge does not support these platforms. 


# this repository

This repository provides cli tooling needed around emscripten-forge.
These tools are things like:

- helper to mirror a prefix.dev channel to another prefix.dev channel
- various helpers coding agents can use when building/maintaining emscripten-forge recipes



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


## Adding dependencies

Dependencies should be added to `environment-dev.yaml` (all deps including development dependencies) and 
`pyproject.toml` contains the python package dependencies.
