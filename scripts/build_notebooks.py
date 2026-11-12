"""Build the twelve PitchVision notebooks as real .ipynb files, and optionally execute them.

    python scripts/build_notebooks.py            # write notebooks/*.ipynb (without outputs)
    python scripts/build_notebooks.py --execute  # also run every cell and save the outputs
    python scripts/build_notebooks.py --execute 03 07   # only notebooks whose name starts with 03 or 07

The notebook content lives in nb_part_*.py as plain lists of ("md" | "code", text) cells, which keeps it
reviewable in version control. The .ipynb files are the deliverable; edit them freely in Jupyter.
"""
import importlib
import re
import sys
import time
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "notebooks"
sys.path.insert(0, str(HERE))


def collect() -> dict:
    books = {}
    for part in ("nb_part_a", "nb_part_b", "nb_part_c"):
        try:
            books.update(importlib.import_module(part).NOTEBOOKS)
        except ModuleNotFoundError:
            pass
    return dict(sorted(books.items()))


def build(name: str, cells: list) -> Path:
    nb = new_notebook()
    # Markdown is kept plain: bold used only for emphasis is removed so the prose reads as prose.
    plain = lambda t: re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    nb.cells = [new_markdown_cell(plain(t)) if kind == "md" else new_code_cell(t) for kind, t in cells]
    nb.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"}}
    nbformat.validate(nb)
    path = OUT / name
    nbformat.write(nb, path)
    return path


def execute(path: Path) -> float:
    from nbconvert.preprocessors import ExecutePreprocessor
    nb = nbformat.read(path, as_version=4)
    start = time.time()
    ExecutePreprocessor(timeout=900, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(OUT)}})
    nbformat.validate(nb)
    nbformat.write(nb, path)
    return time.time() - start


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run = "--execute" in sys.argv
    failed = []
    for name, cells in collect().items():
        if args and not any(name.startswith(a) for a in args):
            continue
        path = build(name, cells)
        msg = f"wrote {name} ({len(cells)} cells)"
        if run:
            try:
                msg += f", executed in {execute(path):.1f}s"
            except Exception as e:           # report and carry on so every notebook is attempted
                failed.append(name)
                msg += f", EXECUTION FAILED: {str(e)[-900:]}"
        print(msg)
    if failed:
        sys.exit(f"{len(failed)} notebook(s) failed: {', '.join(failed)}")
