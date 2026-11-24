"""The committed sprite sheet is exactly what tools/make_sprites.py draws.

If the drawing code changes and nobody reruns the tool, kata.json and kata.png quietly describe art
the code no longer makes. These tests draw the sheet afresh into a temporary folder and compare it
with the committed files: the JSON as parsed data, the PNGs pixel by pixel. File bytes are not
compared, because PNG encoding can differ between Pillow versions, and on Windows the tool writes
the JSON with CRLF line endings while git stores it with LF.
"""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "make_sprites.py"
RERUN = "rerun `python tools/make_sprites.py` and commit what it writes"


def load_tool() -> ModuleType:
    """Import tools/make_sprites.py by its path: the tools folder is not a package."""
    spec = importlib.util.spec_from_file_location("make_sprites", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def drawn(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("drawn")
    load_tool().build(out)
    return out


def pixels(path: Path) -> tuple[tuple[int, int], bytes]:
    with Image.open(path) as image:
        return image.size, image.convert("RGBA").tobytes()


def test_kata_json_is_what_the_tool_writes(drawn: Path) -> None:
    rel = "src/kata/assets/kata.json"
    fresh = json.loads((drawn / rel).read_text(encoding="utf-8"))
    committed = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    assert fresh == committed, f"{rel} is out of date: {RERUN}"


@pytest.mark.parametrize("rel", ["src/kata/assets/kata.png", "docs/sprites-preview.png"])
def test_image_is_what_the_tool_draws(drawn: Path, rel: str) -> None:
    same = pixels(drawn / rel) == pixels(ROOT / rel)
    assert same, f"{rel} is out of date: {RERUN}"
