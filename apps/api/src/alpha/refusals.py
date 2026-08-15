"""One shape for every Alpha Desk refusal.

A refusal carries two things that must not be folded together: a stable code the
interface may branch on, and a sentence a person reads. One string forces every
caller to parse the reason out of prose, and the prose is exactly the part that
is allowed to change.

Subclassed per area so a handler can catch the base and a caller can catch the
one it cares about.
"""


class AlphaRefusal(Exception):
    """A request Alpha Desk refuses, for a reason it names."""

    def __init__(self, reason: str, message: str, status_code: int) -> None:
        super().__init__(f"{reason}: {message}")
        self.reason = reason
        self.message = message
        self.status_code = status_code
