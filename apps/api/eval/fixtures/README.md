# Eval Fixtures

Frozen seeds, one file per `fixture_version`, produced by `make eval-fixture` and
**committed**. A fixture is the exam the Eval Battery is marked against, so it
has to be in the repository for a score to mean anything to a second reader.

Nothing here is hand-written or hand-edited. `fixture_version` is a digest of the
file's own contents, so an edited seed is refused on the next read.

A re-freeze lands *beside* its predecessor rather than replacing it: when
`fixture_version` changes the previous baseline is void (`docs/adr/0016`), and
the old exam has to stay nameable for that rule to be checkable.

The procedure, and why symbols are selected by property rather than named:
`docs/agents/eval-battery.md`.
