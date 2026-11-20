"""`showdown capture`: F9 saves only a Poker Now window (DECISIONS 30, spike S1)."""

from datetime import datetime

from showdown.cli import main
from showdown.live import capture

WHEN = datetime(2026, 11, 20, 21, 5, 3, 120000)


def test_only_poker_now_titles() -> None:
    assert capture.is_poker_now("Poker Now - Poker with Friends - Google Chrome")
    assert capture.is_poker_now("pokernow.club/games/abc")
    assert not capture.is_poker_now("Inbox - Gmail - Google Chrome")
    assert not capture.is_poker_now("")


def test_saves_the_window_and_names_sort_by_time(tmp_path) -> None:
    grabbed = []

    def grab(rect):
        grabbed.append(rect)
        return b"png"

    path = capture.save_shot("Poker Now", (10, 20, 800, 600), grab, tmp_path / "s", WHEN)
    assert grabbed == [(10, 20, 800, 600)] and path.read_bytes() == b"png"
    later = capture.shot_path(tmp_path, WHEN.replace(second=4, microsecond=0))
    assert path.suffix == ".png" and path.name < later.name


def test_other_windows_and_minimised_ones_are_never_grabbed(tmp_path) -> None:
    def grab(rect):
        raise AssertionError("grabbed")

    assert capture.save_shot("Inbox", (0, 0, 800, 600), grab, tmp_path, WHEN) is None
    assert capture.save_shot("Poker Now", (0, 0, 0, 0), grab, tmp_path, WHEN) is None
    assert not any(tmp_path.iterdir())


def test_capture_command(tmp_path, capsys, monkeypatch) -> None:
    def fake_run(folder, report):
        assert folder == tmp_path
        report(folder / "a.png")
        report(None)
        raise KeyboardInterrupt

    monkeypatch.setattr(capture, "run", fake_run)
    assert main(["capture", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "(1)" in out and "nothing saved" in out and "stopped: 1 saved" in out
