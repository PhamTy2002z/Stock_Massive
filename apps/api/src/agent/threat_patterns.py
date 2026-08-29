"""The patterns that say a piece of outside content is trying to give orders.

**This is the second of two layers, and only the first one is hard.** Every
result from a tool that reads outside content is wrapped in a delimiter that
tells the model it is reading evidence rather than instruction
(``untrusted.py``), and that wrapper always runs. This module is the warning
light beside it: it reads the same text, matches a small list of phrases, and
records what it found so a **person** can see it.

Hermes states the split in one sentence, and it is the sentence that governs
this file: *"lớp 2 (regex scan) chỉ để cảnh báo con người, chấp nhận
false-negative"* (``docs/hermes/hermes-web-security-260820-2352.md:109``). A
regex list cannot enumerate every sentence an attacker might write, and a
defence built on the claim that it can is worse than one that does not claim it
— because the second one is still backed by the wrapper.

**Two scopes, not three.** Hermes has ``all``, ``context`` and ``strict``. The
first two are here. ``strict`` — SSH keys, ``authorized_keys``, edits to
``AGENTS.md`` — protects an agent that can *write to a filesystem*, and this
lane has no tool that writes anywhere outside its own database. Copying it in
would leave a scope that can never fire, and a rule that can never fire is a
rule nobody maintains.

**Every pattern says what it catches, in a comment beside it.** A pattern
nobody can explain is a pattern nobody can tune, and the whole failure mode of a
list like this is that it grows past the point where anyone reads it. If this
file ever runs past one screen, that is the signal that the problem is being
solved in the wrong place rather than the signal to add a screen.

**Normalisation before matching, because the attack is written to defeat the
match.** Full-width characters read as ordinary ones to a model and as different
code points to a regex, and a zero-width space between two letters splits a word
for the pattern and for nobody else. So the text is folded to NFKC and stripped
of invisible and bidirectional marks first.
"""

from __future__ import annotations

import re
import unicodedata

#: Unicode code points that occupy no width, or that reorder what follows them.
#:
#: Seventeen of them, the set Hermes carries
#: (``hermes-web-security-260820-2352.md:245``). Every one is a character a
#: reader cannot see and a regex can: ``ig​nore previous instructions``
#: reads as the attack to a model and as two unrelated words to a pattern.
#: Stripped rather than replaced with a space, because the attack is built out of
#: them being invisible — putting a space back would split the word the reader
#: sees joined.
INVISIBLE_CHARS = (
    "­"  # soft hyphen
    "᠎"  # mongolian vowel separator
    "​"  # zero width space
    "‌"  # zero width non-joiner
    "‍"  # zero width joiner
    "‎"  # left-to-right mark
    "‏"  # right-to-left mark
    "‪"  # left-to-right embedding
    "‫"  # right-to-left embedding
    "‬"  # pop directional formatting
    "‭"  # left-to-right override
    "‮"  # right-to-left override
    "⁠"  # word joiner
    "⁦"  # left-to-right isolate
    "⁧"  # right-to-left isolate
    "⁨"  # first strong isolate
    "⁩"  # pop directional isolate
)

_INVISIBLE = re.compile(f"[{INVISIBLE_CHARS}]")

#: Scope names. ``ALL`` applies to every result read from outside; ``CONTEXT``
#: adds the phrases that only make sense against something holding a system
#: prompt, and applies to the same results plus a reader's own uploads.
SCOPE_ALL = "all"
SCOPE_CONTEXT = "context"

#: A finding is named by what it caught, not by the pattern that caught it. The
#: name is what a person reads in a trace, so it says the behaviour rather than
#: the regex.
_ALL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        # The classic: tell the reader's own instructions to stand down. Written
        # with bounded gaps rather than ``.*`` so a page cannot make one match
        # span half a document, and so the pattern cannot backtrack on a long one.
        "instruction_override",
        re.compile(
            r"\b(ignore|disregard|forget|bỏ qua|phớt lờ)\b[^\n]{0,40}?"
            r"\b(previous|prior|above|earlier|all|trước|trên)\b[^\n]{0,40}?"
            r"\b(instruction|instructions|prompt|rules?|hướng dẫn|chỉ dẫn|quy tắc)\b",
            re.IGNORECASE,
        ),
    ),
    (
        # A page asserting authority over the harness's own prompt.
        "system_prompt_override",
        re.compile(
            r"\b(system\s+prompt\s+(override|update|change)|"
            r"new\s+system\s+(prompt|instruction)s?|"
            r"override\s+your\s+(instruction|rule)s?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        # Content positioned so a reader cannot see it but a model can. Hidden
        # text is not evidence: nobody publishes a fact they intend nobody to
        # read, so the only reason to hide a sentence is who it is aimed at.
        "hidden_directive",
        re.compile(
            r"<[^>\n]{0,80}style\s*=\s*[\"'][^\"'\n]{0,120}"
            r"(display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0)",
            re.IGNORECASE,
        ),
    ),
    (
        # An instruction to keep the reader out of it. Whatever follows is aimed
        # at the model over the head of the person it answers to.
        "conceal_from_user",
        re.compile(
            r"\b(do\s+not|don'?t|never)\s+(tell|show|mention|reveal)\b[^\n]{0,20}"
            r"\b(the\s+)?(user|human|reader|người dùng)\b",
            re.IGNORECASE,
        ),
    ),
)

_CONTEXT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        # Role-play hijack: reassign who the model is, and the rules that came
        # with the old identity are meant to leave with it.
        "role_reassignment",
        re.compile(
            r"\b(you\s+are\s+now|from\s+now\s+on\s+you\s+are|"
            r"act\s+as\s+(?:a|an|the)|bạn\s+bây\s+giờ\s+là)\b",
            re.IGNORECASE,
        ),
    ),
    (
        # Asking for the prompt itself. There is no honest reason for a page to
        # ask the thing reading it to recite its own instructions.
        "prompt_disclosure",
        re.compile(
            r"\b(output|print|reveal|repeat|show)\b[^\n]{0,30}"
            r"\b(your\s+)?(system\s+prompt|initial\s+instructions|"
            r"system\s+message)\b",
            re.IGNORECASE,
        ),
    ),
    (
        # A page telling the reader to go and call a tool. Evidence describes the
        # world; it does not ask for an action to be taken on the reader's behalf.
        "tool_invocation_request",
        re.compile(
            r"\b(call|invoke|use|run)\s+(the\s+)?"
            r"(tool|function|fetch_url|web_search|get_field)\b[^\n]{0,30}"
            r"\b(with|on|to)\b",
            re.IGNORECASE,
        ),
    ),
)

PATTERNS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    SCOPE_ALL: _ALL_PATTERNS,
    SCOPE_CONTEXT: _ALL_PATTERNS + _CONTEXT_PATTERNS,
}


def normalise(text: str) -> str:
    """Fold the two ways a payload hides from a pattern but not from a model.

    NFKC first, so ``ｉｇｎｏｒｅ`` is ``ignore``; then the invisible marks come
    out, so ``ig​nore`` is too. Both are cheap, both are done once, and
    together they are the difference between a list of patterns and a list of
    patterns that can be walked around with a text editor.
    """
    return _INVISIBLE.sub("", unicodedata.normalize("NFKC", text))


def findings_in(text: str, *, scope: str = SCOPE_ALL) -> list[str]:
    """Every pattern name this text matches, in a stable order.

    Names rather than matched spans: a span is a piece of the attacker's own
    text, and putting it in a trace and then on a screen would be handing the
    page a second channel to write on.
    """
    folded = normalise(text)
    return [
        name for name, pattern in PATTERNS.get(scope, ()) if pattern.search(folded)
    ]


__all__ = [
    "INVISIBLE_CHARS",
    "PATTERNS",
    "SCOPE_ALL",
    "SCOPE_CONTEXT",
    "findings_in",
    "normalise",
]
