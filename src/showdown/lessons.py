"""Lesson cards for the trainer and the leak finder (DECISIONS 62): our own text in
docs/lessons/, one card per spot pattern. External links only once Ian approves each."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LESSONS_DIR = ROOT / "docs" / "lessons"
IDS = (
    "isolate-limpers",
    "dont-fold-behind-limpers",
    "blinds-vs-limpers",
    "steal-tight-blinds",
    "open-tighter",
    "loose-openers",
    "tight-openers",
    "pushfold-vs-types",
)


def lesson_for(family: str, seat: str, limpers: int, answer: str, best: str) -> str:
    """The card for a spot, from the family, the hero's seat, the limpers, and the kinds of
    the answer and the best action."""
    if family == "pushfold":
        return "pushfold-vs-types"
    if family == "open":
        if best == "fold" or (best == "call" and answer == "raise"):
            return "tight-openers"
        return "loose-openers"
    if limpers:
        if seat in ("SB", "BB"):
            return "blinds-vs-limpers"
        if answer == "fold" and best != "fold":
            return "dont-fold-behind-limpers"
        return "isolate-limpers"
    return "steal-tight-blinds" if best == "raise" else "open-tighter"


def card(lesson_id: str) -> dict[str, str]:
    """{"id", "title", "summary", "path", "text"} from the card's Markdown."""
    if lesson_id not in IDS:
        raise ValueError(f"no lesson {lesson_id!r}")
    path = LESSONS_DIR / f"{lesson_id}.md"
    text = path.read_text(encoding="utf-8")
    title, _, rest = text.partition("\n")
    summary = rest.strip().split("\n\n")[0].replace("\n", " ")
    return {
        "id": lesson_id,
        "title": title.lstrip("# ").strip(),
        "summary": summary,
        "path": f"docs/lessons/{lesson_id}.md",
        "text": text,
    }
