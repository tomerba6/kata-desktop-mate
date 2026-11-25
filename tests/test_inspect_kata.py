"""tools/inspect_kata.py: the pure helpers behind the run-kata report, checked without a desktop.

The style bits are written out here from the Win32 documentation rather than taken from the tool,
so a wrong constant in the tool can't agree with itself.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image

from kata.sheet import read_sheet_info

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "inspect_kata.py"

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_BORDER = 0x00800000
WS_DLGFRAME = 0x00400000
WS_CAPTION = 0x00C00000  # WS_BORDER | WS_DLGFRAME
WS_THICKFRAME = 0x00040000
WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_LAYERED = 0x00080000


def load_tool() -> ModuleType:
    """Import tools/inspect_kata.py by its path: the tools folder is not a package.

    The module goes into sys.modules before it runs, because @dataclass looks its module up there.
    """
    spec = importlib.util.spec_from_file_location("inspect_kata", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = load_tool()


def test_kata_s_styles_decode_to_a_bare_topmost_tool_window() -> None:
    traits = tool.decode_styles(WS_POPUP | WS_VISIBLE, WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_LAYERED)
    assert traits == tool.Traits(
        caption=False, border=False, tool_window=True, topmost=True, layered=True, app_window=False
    )


def test_an_ordinary_window_has_a_caption_and_a_border() -> None:
    traits = tool.decode_styles(WS_OVERLAPPEDWINDOW | WS_VISIBLE, 0)
    assert traits == tool.Traits(
        caption=True, border=True, tool_window=False, topmost=False, layered=False, app_window=False
    )


@pytest.mark.parametrize(
    ("style", "ex_style", "trait"),
    [
        (WS_BORDER, 0, "border"),
        (WS_DLGFRAME, 0, "border"),
        (WS_THICKFRAME, 0, "border"),
        (0, WS_EX_TOPMOST, "topmost"),
        (0, WS_EX_TOOLWINDOW, "tool_window"),
        (0, WS_EX_LAYERED, "layered"),
        (0, WS_EX_APPWINDOW, "app_window"),
    ],
)
def test_each_style_bit_sets_its_own_trait_and_no_other(style: int, ex_style: int, trait: str) -> None:
    traits = tool.decode_styles(style, ex_style)
    on = {name for name, value in vars(traits).items() if value}
    assert on == {trait}


def test_a_caption_needs_both_of_its_bits() -> None:
    # WS_CAPTION is two bits; WS_BORDER alone is a thin border with no title bar.
    assert not tool.decode_styles(WS_BORDER, 0).caption
    assert tool.decode_styles(WS_CAPTION, 0).caption


def test_a_negative_style_from_a_signed_long_still_decodes() -> None:
    # GetWindowLongW returns a signed LONG, so WS_POPUP's top bit arrives as a negative number.
    traits = tool.decode_styles(WS_POPUP - 2**32, WS_EX_TOOLWINDOW)
    assert traits.tool_window and not traits.caption


OUTLINE = (38, 25, 44)


def image(size: tuple[int, int], outlined: list[tuple[int, int]]) -> Image.Image:
    im = Image.new("RGB", size, (10, 10, 10))
    for xy in outlined:
        im.putpixel(xy, OUTLINE)
    return im


def test_the_pixels_of_a_colour_are_found_row_by_row() -> None:
    found = tool.pixels_of_colour(image((4, 5), [(3, 3), (1, 0), (0, 2)]), OUTLINE)
    assert found == [(1, 0), (0, 2), (3, 3)]


def test_a_colour_one_step_off_in_one_channel_is_not_a_match() -> None:
    im = image((3, 3), [])
    im.putpixel((2, 1), (38, 25, 45))
    assert tool.pixels_of_colour(im, OUTLINE) == []


def test_the_lowest_row_of_some_points() -> None:
    assert tool.lowest_row([(1, 0), (3, 3), (0, 2)]) == 3
    assert tool.lowest_row([]) is None


def test_the_point_nearest_another_is_found() -> None:
    assert tool.nearest([(0, 0), (6, 5), (9, 9)], (5, 5)) == (6, 5)
    assert tool.nearest([], (1, 1)) is None


def test_the_box_around_some_points_ends_one_past_the_last() -> None:
    assert tool.bounding_box([(2, 7), (5, 1), (3, 3)]) == (2, 1, 6, 8)
    assert tool.bounding_box([]) is None


def test_the_outline_colour_is_what_kata_png_draws_its_edges_in() -> None:
    # The tool finds Kata on screen by its outline. make_sprites.py outlines every sprite, so the
    # first drawn pixel of the first frame, scanning from the top, is an outline pixel.
    info = read_sheet_info()
    with Image.open(ROOT / "src" / "kata" / "assets" / info.image) as sheet:
        rgba = sheet.convert("RGBA").crop((0, 0, info.frame_w, info.frame_h)).tobytes()
    first_drawn = next(rgba[i : i + 3] for i in range(0, len(rgba), 4) if rgba[i + 3])
    assert bytes(tool.outline_colour()) == first_drawn


def test_a_filetime_is_100_ns_units_split_into_two_32_bit_halves() -> None:
    # GetProcessTimes reports CPU time as a FILETIME: (high << 32 | low) counts of 100 ns.
    assert tool.filetime_seconds(10_000_000, 0) == 1.0
    assert tool.filetime_seconds(0, 1) == 2**32 / 10_000_000  # 429.4967296 s
    assert tool.filetime_seconds(5_000_000, 1) == (2**32 + 5_000_000) / 10_000_000


def test_cpu_use_as_a_share_of_one_core_and_of_all_cores() -> None:
    # 0.5 s of CPU over 10 s: 5% of one core; on 8 cores, Task Manager would show 0.625%.
    assert tool.cpu_percent(0.5, 10.0, 8) == (5.0, 0.625)


def test_cpu_use_needs_some_wall_time() -> None:
    with pytest.raises(ValueError):
        tool.cpu_percent(0.5, 0.0, 8)


def test_a_capture_path_inside_the_repo_is_refused() -> None:
    # Captures show the user's desktop; they must never be committed by accident.
    assert tool.inside_repo(ROOT / "docs" / "kata.png")
    assert not tool.inside_repo(ROOT.parent / "elsewhere" / "kata.png")
