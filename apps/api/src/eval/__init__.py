"""The Eval Fixture and the Eval Battery harness (``docs/adr/0016``).

Nothing in here is imported by the serving application. That separation is the
point of a package rather than a module beside the agent: the battery reads a
**dedicated eval database** and must never be able to reach the one the API
serves from, and an import edge from ``src.main`` into this package would be the
first step towards a code path that could.
"""
