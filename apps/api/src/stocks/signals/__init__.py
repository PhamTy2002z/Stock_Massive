"""Signal Field pack.

Everything reachable from this package is deliberately imported through its
submodule (``registry``, ``fields``, ``bars``, ``price_band``, ``serving``,
``sessions``, ``issues``). The top-level re-exports that used to expand this
namespace were dropped when the market-data plane was ripped out; leaving the
re-exports in place would drag ``volume_spike``, ``corporate_actions`` and
``position_sizing`` back through this import.
"""
