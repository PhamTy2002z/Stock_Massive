"""The golden measurement harness. Deliberately outside ``src/``.

Nothing under ``src/`` may import this package, and the directory layout is what
enforces it rather than a promise: production code that tried would have to
reach outside its own tree. The reverse direction is fine and is the point — the
harness reads the public seams of ``src.agent`` and scores what it finds.

The name is not ``eval``. That one has been deleted twice (2026-08-22 and again
at the harness-first pivot on 2026-08-25) and it carries an expectation of a
much larger machine than the one that belongs here: a corpus file, a runner and
a pure grading function.
"""
