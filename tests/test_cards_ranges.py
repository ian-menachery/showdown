"""Card encoding, hand classes and range parsing."""

import pytest

from showdown.equity.cards import (
    ALL_COMBOS,
    CLASS_COMBOS,
    CLASS_NAMES,
    card_str,
    class_index,
    class_name,
    class_of,
    combo_str,
    make_combo,
    parse_card,
    parse_cards,
)
from showdown.equity.ranges import parse_range


def test_card_round_trip() -> None:
    assert [card_str(c) for c in range(4)] == ["2c", "2d", "2h", "2s"]
    assert all(parse_card(card_str(c)) == c for c in range(52))
    assert parse_card("aS") == parse_card("As") == 51
    assert parse_cards("As Kd,7c") == (51, 45, 20)


@pytest.mark.parametrize("bad", ["1s", "Ax", "A", "Ass"])
def test_bad_cards(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_card(bad)


def test_bad_card_lists() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        parse_cards("AsAs")
    with pytest.raises(ValueError):
        parse_cards("AsK")
    with pytest.raises(ValueError):
        make_combo(3, 3)


def test_class_grid() -> None:
    assert len(CLASS_NAMES) == 169 and len(set(CLASS_NAMES)) == 169
    assert class_name(0) == "AA" and class_name(1) == "AKs" and class_name(13) == "AKo"
    assert class_name(168) == "22"
    assert class_index("t9S") == class_index("T9s")
    with pytest.raises(ValueError):
        class_index("AAs")


def test_every_combo_in_exactly_one_class() -> None:
    assert len(ALL_COMBOS) == len(set(ALL_COMBOS)) == 1326
    sizes = {len(CLASS_COMBOS[i]) for i in range(169)}
    assert sizes == {4, 6, 12}
    for i, name in enumerate(CLASS_NAMES):
        expected = 6 if len(name) == 2 else (4 if name.endswith("s") else 12)
        assert len(CLASS_COMBOS[i]) == expected
        assert all(class_of(c) == i for c in CLASS_COMBOS[i])
    assert combo_str(make_combo(parse_card("Ks"), parse_card("As"))) == "AsKs"


@pytest.mark.parametrize(
    ("text", "count"),
    [
        ("AA", 6),
        ("AKs", 4),
        ("AKo", 12),
        ("AK", 16),
        ("TT+", 30),
        ("A2s+", 48),
        ("KTo+", 36),
        ("AT+", 64),
        ("22-55", 24),
        ("55-22", 24),
        ("A2s-A5s", 16),
        ("kto-kqo", 36),
        ("AsKs", 1),
        ("random", 1326),
        ("AA, KK ,AA", 12),
        ("JTs,AsKs,AKs", 8),
    ],
)
def test_range_sizes(text: str, count: int) -> None:
    assert len(parse_range(text)) == count


@pytest.mark.parametrize("bad", ["", "AAs", "AK-QJ", "A2s-A5o", "XX", "AKx"])
def test_bad_ranges(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_range(bad)
