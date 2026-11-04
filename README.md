# atv 🌱

[![PyPI][pypi-badge]][pypi-link]
[![Python versions][versions-badge]][pypi-link]
[![GitHub Actions][github-ci-badge]][github-ci-link]
[![License][license-badge]][license-link]

<img width="800" height="403" alt="image" src="https://github.com/user-attachments/assets/1a8000b2-2eee-42f9-a9ac-b6ecb79c9e60" />


atv (async task viewer) is a Textual UI for discovering Python processes, inspecting asyncio tasks and await trees, comparing snapshots, and capturing Tachyon flame graphs.

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

### Inspect and profile

Select a process in the left pane, then use:

| Key | Action |
| --- | --- |
| `R` | Refresh processes, keeping the selected PID when possible |
| `Enter` / `P` | Capture `asyncio ps` |
| `T` | Capture `asyncio pstree` |
| `S` | Save the last successful task/tree snapshot as text |
| `D` | Compare the last two captures of the same PID and view |
| `F` | Capture a Tachyon flame graph of running asyncio tasks |
| `G` | Capture a Tachyon flame graph including waiting tasks |
| `O` | Open the last successful flame graph in a browser |
| `X` | Cancel the current observation |
| `Q` | Exit |

Task snapshots show the state at capture time. Flame graphs aggregate samples
across a time window. Snapshot diffs are textual: task IDs, stack lines and
ordering changes may appear in the diff; this is not a task lifecycle tracker.
Capture twice with P or T before using D. Saved snapshots and profiles get unique
filenames under `~/.atv/captures`; captures are never overwritten automatically.

Profiling requires an observer with `profiling.sampling` (Python 3.15+).
Task inspection remains available with Python 3.14. Choose an observer matching
the target Python minor version and standard/free-threaded build; pre-release
versions may require an exact version match.

```bash
uv run atv --python "$(uv python find 3.15)" --duration 10
uv run atv --output-dir ./captures
```

`--duration` accepts 1–300 seconds. F and G attach only to the selected process;
X cancels the observer, not the target. atv does not invoke sudo automatically.
On macOS, process observation may require elevated privileges. Use the
[Python permission guide](https://docs.python.org/3/howto/remote_debugging.html#permission-requirements)
to configure your environment. Errors remain visible in the output pane.
When running atv under sudo, set `--output-dir` explicitly if desired; generated
files belong to that user and the browser may need to be opened manually.

### Development checks

```bash
uv run python -m unittest discover -s tests -v
```

The suite checks subprocess errors, cancellation/timeout cleanup, and headless
UI interactions with mocked external inspection. It does not require attaching
to other processes or elevated privileges.

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

- Structured task navigation and lifecycle-aware snapshot comparison
- Periodic task inspection with an explicit refresh interval
- Integration with application-provided task information

## License

This project is licensed under the MIT License. See `LICENSE` for details.

[pypi-badge]: https://img.shields.io/pypi/v/atv.svg
[pypi-link]: https://pypi.org/project/atv/
[versions-badge]: https://img.shields.io/pypi/pyversions/atv.svg
[github-ci-badge]: https://github.com/jrfk/atv/actions/workflows/workflow.yml/badge.svg
[github-ci-link]: https://github.com/jrfk/atv/actions/workflows/workflow.yml
[license-badge]: https://img.shields.io/github/license/jrfk/atv
[license-link]: https://github.com/jrfk/atv/blob/main/LICENSE
