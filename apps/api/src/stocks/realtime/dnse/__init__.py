"""DNSE wire adapter isolated behind the source-neutral realtime contracts."""

from .auth import DnseCredentials, RestSigner, WebSocketSigner
from .deduplication import EventOrderTracker, SnapshotDeduplicator
from .metrics import AdapterMetrics, MetricsSnapshot
from .parsing import DnseEventParser, ParseResult, raw_payload_hash
from .rate_budget import EndpointFamily, RateBudget
from .reconciliation import ReconciliationBatch, ReconnectReconciler
from .rest import DnseRestClient, RestPage, RestResult
from .validation import EventWindow, OhlcRequest
from .websocket import DnseWebSocketClient, Subscription

__all__ = [
    "AdapterMetrics",
    "DnseCredentials",
    "DnseEventParser",
    "DnseRestClient",
    "DnseWebSocketClient",
    "EndpointFamily",
    "EventOrderTracker",
    "EventWindow",
    "MetricsSnapshot",
    "OhlcRequest",
    "ParseResult",
    "RateBudget",
    "ReconciliationBatch",
    "ReconnectReconciler",
    "RestPage",
    "RestResult",
    "RestSigner",
    "SnapshotDeduplicator",
    "Subscription",
    "WebSocketSigner",
    "raw_payload_hash",
]
