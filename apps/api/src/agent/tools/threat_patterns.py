"""The single source of truth for prompt-injection markers in untrusted prose.

Four defences already stand between a hostile page and the model: the tool
result labels external prose ``external_claim``, the news lane accepts cleared
publishers only, ``_html.py`` keeps visible text and caps it, and the System
Prompt Contract states that retrieved text is data and never an instruction.
This module is the fifth, and it is deliberately the weakest of them: it reads
text and returns *names for what it recognised*. It never decides anything.

Two properties make that safe to call from a tool path.

**It is pure.** No I/O, no session, no settings, no application import — only
the standard library. A pattern library that reached for a database would be a
new failure mode on the retrieval path, and the retrieval path is the one place
this product cannot afford one.

**It fails open, without exception.** :func:`scan_untrusted_text` wraps
everything it does and returns an empty tuple on *any* error. A scan that
raised would turn a page the reader asked for into a Turn that died, which is
strictly worse than a page nobody labelled: the content was already going to be
treated as data. So a broken pattern, a surprising type, a pathological string
— all of them mean "no labels", never "no answer" and never "no content".

The corollary is that false positives are cheap and are accepted. A label
attached to an ordinary market wire costs one key in a JSON payload and one
line in a log; a false negative costs nothing extra either, because the four
defences above do not depend on this one. Tighten the patterns when the ops
count says a label is firing on ordinary traffic — that count is the reason
``ops.py`` tallies them.
"""

from __future__ import annotations

import re
import unicodedata

#: Zero-width, bidi-override, word-joiner and tag characters — text that is in
#: the payload but not on the screen, which is how an instruction hides from the
#: person who approved the page and not from the model that reads it.
INVISIBLE_CHARACTERS = "invisible_characters"

#: Attempts to replace the standing instructions: *ignore previous
#: instructions*, *you are now*, and their Vietnamese equivalents.
INSTRUCTION_OVERRIDE = "instruction_override"

#: Attempts to make the model emit a secret or its own prompt.
CREDENTIAL_PROBE = "credential_probe"

#: Text shaped like a chat-template role marker, trying to be read as a turn
#: boundary rather than as page content.
IMPERSONATED_SYSTEM = "impersonated_system"

# Explicit ranges rather than a bare ``Cf`` category test, because the tag block
# is mostly unassigned and unassigned code points answer ``Cn``. The category
# test below catches the rest, including format characters added after this
# Python build.
_INVISIBLE = re.compile(
    "["
    "\u200b-\u200f"  # zero-width space through the right-to-left mark
    "\u202a-\u202e"  # bidirectional embedding and override
    "\u2060-\u2064"  # word joiner and the invisible operators
    "\ufeff"  # zero-width no-break space, also the byte-order mark
    "\U000e0000-\U000e007f"  # tag characters
    "]"
)

# Separator between the words of a phrase. Punctuation, whitespace and
# underscores are what an evasion inserts and what ordinary typography inserts
# too, so a phrase is matched across them: this is what makes one entry cover
# ``api key``, ``api_key`` and ``api - key`` without three entries.
_GAP = r"[\W_]{0,8}"

# The determiners a real sentence stacks in front of the noun — *ignore all the
# previous instructions* is the same attempt as *ignore previous instructions*,
# and enumerating each stacking as its own phrase is how a pattern list rots.
# Bounded at three so the slot cannot swallow a clause.
_DETERMINERS = r"(?:(?:all|any|every|the|these|those|of)[\W_]{1,8}){0,3}"

# Phrases as word tuples. A tuple entry is a regex fragment for one word, and an
# entry ending in ``?`` is an optional filler word. Written this way so the
# separator rule lives in one place and the phrase list stays readable as
# phrases.
_PHRASES: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = (
    (
        INSTRUCTION_OVERRIDE,
        (
            (
                r"(?:ignore|disregard|forget|override)",
                _DETERMINERS,
                # Repeatable, because *your prior rules* stacks two of them.
                r"(?:(?:previous|prior|earlier|preceding|above|your)[\W_]{0,8}){1,2}",
                r"(?:instructions?|prompts?|rules?|directives?)",
            ),
            (r"(?:ignore|disregard|forget)", r"the", r"above"),
            (r"you", r"are", r"now"),
            (r"new", r"instructions"),
            (r"system", r"prompt"),
            (
                r"bỏ",
                r"qua",
                r"(?:mọi|các|những|tất\s+cả|toàn\s+bộ)?",
                r"(?:hướng\s+dẫn|chỉ\s+thị|chỉ\s+dẫn|quy\s+tắc)",
                r"(?:trước|trên|cũ)?",
            ),
            (
                r"quên",
                r"(?:mọi|hết|các|những|tất\s+cả)?",
                r"(?:hướng\s+dẫn|chỉ\s+thị|chỉ\s+dẫn)",
            ),
            (r"từ", r"nay", r"(?:bạn|mày|ngươi)", r"là"),
        ),
    ),
    (
        CREDENTIAL_PROBE,
        (
            (r"api", r"key"),
            (r"secret", r"key"),
            (r"access", r"token"),
            (
                r"(?:reveal|show|print|output|repeat|display)",
                r"(?:me)?",
                r"(?:your|the)",
                r"(?:system\s+prompt|initial\s+prompt|instructions|prompt)",
            ),
            (r"(?:khoá|khóa)", r"api"),
            (r"mật", r"khẩu"),
            (r"(?:lộ|tiết\s+lộ|để\s+lộ)", r"prompt"),
        ),
    ),
)

# Role markers are not phrases — they are punctuation-shaped, so they are
# written as regexes directly. The role-and-colon form is anchored to a sentence
# or line start: ``visible_text`` has already collapsed the page's newlines, so
# an unanchored ``system:`` would fire on any prose that happens to contain the
# word before a colon.
_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        IMPERSONATED_SYSTEM,
        (
            r"<\|[a-z_]{2,20}\|>",
            r"\[\s*(?:system|assistant)\s*\]",
            r"#{2,6}\s*(?:system|assistant)\b",
            r"</?\s*(?:system|assistant)\s*>",
            r"(?:^|[\n\r]|[.!?…]\s)\s*(?:system|assistant|user)\s*:",
            r"\bbegin\s+system\b",
        ),
    ),
)


def _compile_phrase(words: tuple[str, ...]) -> re.Pattern[str]:
    """One phrase, tolerant of what an evasion puts between its words."""
    return re.compile(
        r"(?<!\w)" + _GAP.join(words) + r"(?!\w)",
        re.IGNORECASE,
    )


_COMPILED: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = tuple(
    (label, tuple(_compile_phrase(words) for words in phrases))
    for label, phrases in _PHRASES
) + tuple(
    (label, tuple(re.compile(marker, re.IGNORECASE) for marker in markers))
    for label, markers in _MARKERS
)


def _normalize(value: str) -> str:
    """Fold the text into the one form the phrase patterns are written against.

    NFKC first, so full-width and compatibility spellings collapse onto the
    ASCII the patterns use; invisible characters removed second, so a phrase
    broken by a zero-width space reads as the phrase again. Without the second
    step the whole phrase layer is bypassed by one character nobody can see.
    """
    return _INVISIBLE.sub(
        "",
        "".join(
            character
            for character in unicodedata.normalize("NFKC", value)
            if unicodedata.category(character) != "Cf"
        ),
    )


def _has_invisible(value: str) -> bool:
    return bool(_INVISIBLE.search(value)) or any(
        unicodedata.category(character) == "Cf" for character in value
    )


def scan_untrusted_text(*values: str | None) -> tuple[str, ...]:
    """Name what the given untrusted text looks like. Never raise, never block.

    Returns the labels that matched, sorted so two readings of the same page
    produce the same tuple and a stored payload diffs cleanly. An empty tuple
    means *nothing recognised* **or** *the scan failed*; the caller cannot tell
    the two apart and must not need to, because in both cases the content
    passes through untouched.

    Values that are not strings are skipped rather than coerced: a ``None``
    title and a provider handing back a number are both "no text here", and
    ``str()`` on them would invent a haystack that was never on the page.
    """
    try:
        labels: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not value:
                continue
            if _has_invisible(value):
                labels.add(INVISIBLE_CHARACTERS)
            haystack = _normalize(value)
            for label, patterns in _COMPILED:
                if label in labels:
                    continue
                if any(pattern.search(haystack) for pattern in patterns):
                    labels.add(label)
        return tuple(sorted(labels))
    except Exception:  # noqa: BLE001 - the whole point of this module
        return ()


__all__ = [
    "CREDENTIAL_PROBE",
    "IMPERSONATED_SYSTEM",
    "INSTRUCTION_OVERRIDE",
    "INVISIBLE_CHARACTERS",
    "scan_untrusted_text",
]
