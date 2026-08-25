"""Realtime module — post-rip-out.

The DNSE ingress, coordinator/spine, projections and monitor router were all
removed with the market surfaces. Only three read-side pieces survive because
the surviving signal fields still need them: ``contracts`` for the wire types,
``storage.deserialize_event`` for one Signal Field's own read of the trade log,
``health`` and ``policy`` because ``storage`` still imports them.

Do not re-export anything here. Callers reach for a specific submodule by name,
and expanding this namespace would drag ingest-side code back through import.
"""
