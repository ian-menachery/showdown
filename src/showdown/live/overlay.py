"""The suggestion overlay: a small window kept on top of the table (DECISIONS 42).

It is an ordinary window, visible to screen sharing (DECISIONS 29). It only shows text;
it never clicks.
"""

from __future__ import annotations

from showdown.live.tracker import Event


def event_lines(event: Event) -> tuple[str, list[str], str]:
    """(the headline, the detail lines, the state line) for one event."""
    d, s = event.decision, event.suggestion
    state = ""
    if d is not None:
        villain = "BB" if d.seat == "sb" else "SB"
        state = (
            f"{d.street}  pot {d.pot_bb:g}  to call {d.to_call_bb:g}  "
            f"you {d.stacks_bb[d.seat]:g}  {villain} {d.stacks_bb[villain.lower()]:g} (bb)"
        )
    if s is None:
        return event.text or event.kind, [], state
    if s.action is None:
        return "NO SUGGESTION", [s.source], state
    head = s.action.upper() + (f" {s.size_bb:g} bb" if s.size_bb else "")
    lines = []
    if s.evs:
        lines.append("EV " + ", ".join(f"{k} {v:+.2f}" for k, v in s.evs.items()))
    if s.mix:
        lines.append("mix " + ", ".join(f"{k} {v:.0%}" for k, v in s.mix.items() if v >= 0.005))
    lines += [f"! {note}" for note in s.notes]
    if s.equity is not None:
        need = f" (need {s.threshold:.1%})" if s.threshold is not None else ""
        lines.append(f"equity {s.equity:.1%}{need}")
    lines.append(s.source)
    return head, lines, state


class Overlay:
    def __init__(self) -> None:
        import tkinter as tk

        self.root = tk.Tk()
        self.root.title("showdown advice")
        self.root.attributes("-topmost", True)
        self.head = tk.Label(self.root, font=("Segoe UI", 20, "bold"), anchor="w")
        self.detail = tk.Label(self.root, font=("Segoe UI", 10), anchor="w", justify="left")
        self.state = tk.Label(self.root, font=("Segoe UI", 9), anchor="w", fg="#555555")
        for label in (self.head, self.detail, self.state):
            label.pack(fill="x", padx=10, pady=2)
        self.root.update()

    def show(self, event: Event) -> None:
        head, lines, state = event_lines(event)
        self.head.config(text=head)
        self.detail.config(text="\n".join(lines))
        self.state.config(text=state)
        self.root.update()

    def texts(self) -> tuple[str, str, str]:
        return self.head.cget("text"), self.detail.cget("text"), self.state.cget("text")

    def wait(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        self.root.destroy()
