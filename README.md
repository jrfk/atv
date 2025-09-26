# TaskScope 🌱

<img width="2850" height="1480" alt="image" src="https://github.com/user-attachments/assets/9b8916b7-4ca0-4715-b63b-280f2c1bf8fd" />


TaskScope is a CLI for exploring Python `asyncio` processes with a Textual UI. It starts by listing Python processes running locally, and we plan to integrate execution of `asyncio ps` / `pstree` and call-graph visualization.

## Setup

```bash
cd TaskScope
uv sync
```

`uv sync` installs the specified dependencies (`textual`, `psutil`) into your local environment.

## Usage

```bash
uv run taskscope
```

Shortcuts:

- `R` – Refresh the process list (the table shows PID / Process / File / Command Line)
- `Q` – Exit
- `Enter` / `P` – Run `python -m asyncio ps` for the selected PID and display the result in the right pane

### Using uvx

Once released, you'll be able to launch it with a one-liner.

```bash
uvx taskscope
```

If you want to test uvx behavior during local development, run the following in the project root.

```bash
uvx --from . taskscope
```

## Roadmap

- View that periodically runs `python -m asyncio ps` for the selected process
- Visualization for `asyncio pstree` / `format_call_graph`
- Snapshot capture and diff comparison
- Integration with the FastAPI demo (retrieve task information via the API)

## License

This project is licensed under the MIT License. See `LICENSE` for details.
