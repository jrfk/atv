# atv 🌱

[![PyPI][pypi-badge]][pypi-link]
[![Python versions][versions-badge]][pypi-link]
[![GitHub Actions][github-ci-badge]][github-ci-link]
[![License][license-badge]][license-link]

<img width="800" height="403" alt="image" src="https://github.com/user-attachments/assets/1a8000b2-2eee-42f9-a9ac-b6ecb79c9e60" />


atv(async task viewer) is a CLI for exploring Python `asyncio` processes with a Textual UI. It starts by listing Python processes running locally, and we plan to integrate execution of `asyncio ps` / `pstree` and call-graph visualization.

## Setup

```bash
cd atv
uv sync
```

`uv sync` installs the specified dependencies (`textual`, `psutil`) into your local environment.

## Usage

```bash
uv run atv
```

Shortcuts:

- `R` – Refresh the process list (the table shows PID / Process / File / Command Line)
- `Q` – Exit
- `Enter` / `P` – Run `python -m asyncio ps` for the selected PID and display the result in the right pane

### Using uvx

Once released, you'll be able to launch it with a one-liner.

```bash
uvx atv
```

If you want to test uvx behavior during local development, run the following in the project root.

```bash
uvx --from . atv
```

## Roadmap

- View that periodically runs `python -m asyncio ps` for the selected process
- Visualization for `asyncio pstree` / `format_call_graph`
- Snapshot capture and diff comparison
- Integration with the FastAPI demo (retrieve task information via the API)

## License

This project is licensed under the MIT License. See `LICENSE` for details.

[pypi-badge]: https://img.shields.io/pypi/v/atv.svg
[pypi-link]: https://pypi.org/project/atv/
[versions-badge]: https://img.shields.io/pypi/pyversions/atv.svg
[github-ci-badge]: https://github.com/jrfk/atv/actions/workflows/workflow.yml/badge.svg
[github-ci-link]: https://github.com/jrfk/atv/actions/workflows/workflow.yml
[license-badge]: https://img.shields.io/github/license/jrfk/atv
[license-link]: https://github.com/jrfk/atv/blob/main/LICENSE
