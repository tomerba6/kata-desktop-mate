"""The no-Qt rule, checked rather than remembered.

Four things say which modules have no Qt in them: what each module really imports, the coverage
gate's `include` list in pyproject.toml, `module-path` in cosmic-ray.toml, and the "no Qt" marks in
CLAUDE.md's Layout. Nothing else holds them together, so a new pure module could sit outside the
gate or the mutation run, or a pure module could quietly pick up a Qt import, and the build would
stay green. These tests make all four agree.

Each module is imported in a fresh interpreter and counts as Qt if PySide6 ends up loaded, so an
indirect import counts too: a module that imports kata.sprites is a Qt module even though it
never names PySide6. Package __init__ files are left out.
"""

import re
import subprocess
import sys
import tomllib
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "kata"
GATED_PATTERN = re.compile(r"\*/kata/([\w/]+)\.py")
MUTATED_PATTERN = re.compile(r"src/kata/([\w/]+)\.py")


def module_names() -> list[str]:
    """Every module under src/kata, dotted, except package __init__ files."""
    names = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name != "__init__.py":
            names.append(".".join(path.relative_to(PACKAGE.parent).with_suffix("").parts))
    return names


@cache
def imports_qt(module: str) -> bool:
    code = f"import sys, {module}; print('PySide6' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return result.stdout.strip() == "True"


def no_qt_modules() -> set[str]:
    return {name for name in module_names() if not imports_qt(name)}


def gated_modules() -> set[str]:
    """The modules named in [tool.coverage.report] include, dotted."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = config.get("tool", {}).get("coverage", {}).get("report", {}).get("include", [])
    gated = set()
    for pattern in patterns:
        match = GATED_PATTERN.fullmatch(pattern)
        assert match, f"coverage include entry {pattern!r} is not of the form */kata/<module>.py"
        gated.add("kata." + match.group(1).replace("/", "."))
    return gated


def mutated_modules() -> set[str]:
    """The modules named in cosmic-ray.toml's module-path, dotted."""
    config = tomllib.loads((ROOT / "cosmic-ray.toml").read_text(encoding="utf-8"))
    paths = config["cosmic-ray"]["module-path"]
    mutated = set()
    for path in [paths] if isinstance(paths, str) else paths:
        match = MUTATED_PATTERN.fullmatch(path)
        assert match, f"cosmic-ray module-path entry {path!r} is not of the form src/kata/<module>.py"
        mutated.add("kata." + match.group(1).replace("/", "."))
    return mutated


def marked_in_claude_md() -> set[str]:
    """The modules CLAUDE.md's Layout marks "no Qt", dotted, whether or not they exist yet."""
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    block = text.split("## Layout", 1)[1].split("```text", 1)[1].split("```", 1)[0]
    marked = set()
    folders: list[tuple[int, str]] = []  # (indent, folder name) of the folders the line is in
    for line in block.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        entry = line.split()[0]
        while folders and folders[-1][0] >= indent:
            folders.pop()
        if entry.endswith("/"):
            folders.append((indent, entry.rstrip("/")))
        elif line.rstrip().endswith("no Qt"):
            path = "/".join([folder for _, folder in folders] + [entry.removesuffix(".py")])
            marked.add(path.removeprefix("src/").replace("/", "."))
    return marked


def test_the_scanner_tells_qt_modules_from_no_qt_ones() -> None:
    # A guard on the checks below: if the scan stops working, they would pass on nothing.
    assert "kata.sheet" in module_names()
    assert not imports_qt("kata.sheet")
    assert imports_qt("kata.sprites")
    assert "kata.sheet" in marked_in_claude_md()


def test_the_coverage_gate_measures_exactly_the_no_qt_modules() -> None:
    no_qt, gated = no_qt_modules(), gated_modules()
    assert not no_qt - gated, (
        f"these modules import no Qt, so they belong in [tool.coverage.report] include in "
        f"pyproject.toml: {sorted(no_qt - gated)}"
    )
    assert not gated - no_qt, (
        f"the coverage gate names modules that import Qt or no longer exist: {sorted(gated - no_qt)}"
    )


def test_mutation_testing_mutates_exactly_the_no_qt_modules() -> None:
    no_qt, mutated = no_qt_modules(), mutated_modules()
    assert not no_qt - mutated, (
        f"these modules import no Qt, so they belong in module-path in cosmic-ray.toml: "
        f"{sorted(no_qt - mutated)}"
    )
    assert not mutated - no_qt, (
        f"cosmic-ray.toml mutates modules that import Qt or no longer exist: {sorted(mutated - no_qt)}"
    )


def test_claude_md_marks_exactly_the_no_qt_modules_that_exist() -> None:
    existing, no_qt, marked = set(module_names()), no_qt_modules(), marked_in_claude_md()
    assert not no_qt - marked, f"mark these 'no Qt' in CLAUDE.md's Layout: {sorted(no_qt - marked)}"
    assert not (marked & existing) - no_qt, (
        f"CLAUDE.md marks these 'no Qt', but they import Qt: {sorted((marked & existing) - no_qt)}"
    )
