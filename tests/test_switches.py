"""kata.switches reads developer switches from an environment it is given, and formats log lines."""

import pytest

from kata.switches import is_on, log_line


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "True"])
def test_a_switch_is_on_for_1_and_true_in_any_case(value: str) -> None:
    assert is_on("KATA_LOG", {"KATA_LOG": value})


@pytest.mark.parametrize("value", ["", "0", "no", "yes", "false", "2"])
def test_a_switch_is_off_for_anything_else(value: str) -> None:
    assert not is_on("KATA_LOG", {"KATA_LOG": value})


def test_an_unset_switch_is_off() -> None:
    assert not is_on("KATA_LOG", {"OTHER": "1"})


def test_a_log_line_names_the_time_the_event_and_its_fields() -> None:
    assert log_line(1.234, "placed", feet=(640, 720)) == "kata 1.234 placed feet=640,720"


def test_a_log_line_keeps_the_fields_in_order_and_the_time_to_the_millisecond() -> None:
    line = log_line(0.5, "placed", screen="DISPLAY1", dpr=1.5, feet=(640, 720))
    assert line == "kata 0.500 placed screen=DISPLAY1 dpr=1.5 feet=640,720"


def test_a_log_line_needs_no_fields() -> None:
    assert log_line(0, "started") == "kata 0.000 started"
