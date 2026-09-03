"""Deterministic source, publication-time, and evidence-retention policy.

Search relevance answers "does this result match the query?".  This module
answers the separate questions that matter to the evidence contract: who
published it, whether it may support a material claim, when it existed, and
how long a fetched public copy may be retained.

The mappings are deliberately conservative.  An unfamiliar domain remains
``unknown``; a convincing hostname or a high search score never promotes it to
a primary source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from .contracts import (
    PublicationConfidence,
    PublicationMethod,
    SourceClass,
    TimePrecision,
    TosRisk,
)

POLICY_VERSION = "2026-09-02.1"
ICT = ZoneInfo("Asia/Ho_Chi_Minh")


class SourceTier(str, Enum):
    PRIMARY = "primary"
    PROFESSIONAL_MEDIA = "professional_media"
    AGGREGATOR = "aggregator"
    SNIPPET = "snippet"
    UNKNOWN = "unknown"


class EvidenceCacheKind(str, Enum):
    DYNAMIC_MARKET = "dynamic_market"
    MEDIA_ARTICLE = "media_article"
    PRIMARY_FILING = "primary_filing"
    AGGREGATOR_PAGE = "aggregator_page"
    SEARCH_SNIPPET = "search_snippet"
    PRIVATE_TRAJECTORY = "private_trajectory"
    CLAIM_LEDGER = "claim_ledger"


@dataclass(frozen=True)
class SourcePolicy:
    source_class: SourceClass
    tier: SourceTier
    tos_risk: TosRisk
    material_min_publishers: int | None
    durable_evidence: bool

    @property
    def primary(self) -> bool:
        return self.tier is SourceTier.PRIMARY


@dataclass(frozen=True)
class PublicationStamp:
    published_at: datetime | None
    method: PublicationMethod
    confidence: PublicationConfidence
    precision: TimePrecision
    raw_value: str | None = None

    def to_payload(self) -> dict[str, str | None]:
        return {
            "publishedAt": self.published_at.isoformat() if self.published_at else None,
            "publicationMethod": self.method.value,
            "publicationConfidence": self.confidence.value,
            "publicationPrecision": self.precision.value,
        }


@dataclass(frozen=True)
class RetentionPolicy:
    kind: EvidenceCacheKind
    freshness: timedelta | None
    retention: timedelta | None
    durable_evidence: bool
    owner_scoped: bool


_TRACKING_PARAMS = frozenset(
    {
        "fbclid",
        "gclid",
        "dclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "ref_src",
    }
)

_REGULATOR_DOMAINS = frozenset(
    {
        "ssc.gov.vn",
        "ubcknn.gov.vn",
        "sbv.gov.vn",
        "mof.gov.vn",
        "gso.gov.vn",
    }
)
_EXCHANGE_DOMAINS = frozenset(
    {
        "hsx.vn",
        "hose.vn",
        "staticfile.hsx.vn",
        "hnx.vn",
    }
)
_DEPOSITORY_DOMAINS = frozenset({"vsd.vn", "vsdc.vn"})
_ISSUER_DOMAINS = frozenset(
    {
        "vietcombank.com.vn",
        "vcb.com.vn",
        "hpggroup.vn",
        "hoaphat.com.vn",
        "fpt.com.vn",
        "vnm.com.vn",
        "vinamilk.com.vn",
    }
)
_MEDIA_DOMAINS = frozenset(
    {
        "reuters.com",
        "bloomberg.com",
        "vnexpress.net",
        "baodautu.vn",
        "tuoitre.vn",
        "thanhnien.vn",
        "cafef.vn",
        "vietstock.vn",
    }
)
_AGGREGATOR_DOMAINS = frozenset(
    {
        "finance.yahoo.com",
        "investing.com",
        "tradingview.com",
        "simplize.vn",
        "stockbiz.vn",
    }
)

_PRIMARY = SourcePolicy(SourceClass.PRIMARY_DOCUMENT, SourceTier.PRIMARY, TosRisk.LOW, 1, True)
_MEDIA = SourcePolicy(SourceClass.MEDIA, SourceTier.PROFESSIONAL_MEDIA, TosRisk.MEDIUM, 2, True)
_AGGREGATOR = SourcePolicy(SourceClass.AGGREGATOR, SourceTier.AGGREGATOR, TosRisk.HIGH, 2, True)
_SNIPPET = SourcePolicy(SourceClass.UNKNOWN, SourceTier.SNIPPET, TosRisk.UNKNOWN, None, False)
_UNKNOWN = SourcePolicy(SourceClass.UNKNOWN, SourceTier.UNKNOWN, TosRisk.UNKNOWN, 2, True)

RETENTION_POLICIES: Mapping[EvidenceCacheKind, RetentionPolicy] = {
    EvidenceCacheKind.DYNAMIC_MARKET: RetentionPolicy(
        EvidenceCacheKind.DYNAMIC_MARKET, timedelta(days=1), timedelta(days=7), True, False
    ),
    EvidenceCacheKind.MEDIA_ARTICLE: RetentionPolicy(
        EvidenceCacheKind.MEDIA_ARTICLE, None, timedelta(days=30), True, False
    ),
    EvidenceCacheKind.PRIMARY_FILING: RetentionPolicy(
        EvidenceCacheKind.PRIMARY_FILING, None, timedelta(days=730), True, False
    ),
    EvidenceCacheKind.AGGREGATOR_PAGE: RetentionPolicy(
        EvidenceCacheKind.AGGREGATOR_PAGE, timedelta(hours=6), timedelta(days=7), True, False
    ),
    EvidenceCacheKind.SEARCH_SNIPPET: RetentionPolicy(
        EvidenceCacheKind.SEARCH_SNIPPET, timedelta(minutes=30), None, False, False
    ),
    EvidenceCacheKind.PRIVATE_TRAJECTORY: RetentionPolicy(
        EvidenceCacheKind.PRIVATE_TRAJECTORY, None, timedelta(days=30), False, True
    ),
    EvidenceCacheKind.CLAIM_LEDGER: RetentionPolicy(
        EvidenceCacheKind.CLAIM_LEDGER, None, None, True, True
    ),
}


def _domain_matches(host: str, domains: Iterable[str]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def canonical_url(url: str) -> str:
    """Return a stable public-document identity without changing page semantics."""

    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("canonical evidence URL must use http or https and name a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("canonical evidence URL must not contain credentials")
    scheme = parsed.scheme.lower()
    host = parsed.hostname.rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("canonical evidence URL has an invalid host") from exc
    port = parsed.port
    netloc = host
    if port is not None and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_PARAMS
        ),
        doseq=True,
    )
    return urlunsplit((scheme, netloc, parsed.path or "/", query, ""))


def classify_source(url: str, *, snippet: bool = False) -> SourcePolicy:
    """Classify only known publisher domains; unknown never means primary."""

    if snippet:
        return _SNIPPET
    try:
        host = (urlsplit(canonical_url(url)).hostname or "").lower()
    except ValueError:
        return _UNKNOWN
    if _domain_matches(host, _REGULATOR_DOMAINS):
        return SourcePolicy(SourceClass.REGULATOR, SourceTier.PRIMARY, TosRisk.LOW, 1, True)
    if _domain_matches(host, _EXCHANGE_DOMAINS):
        return SourcePolicy(SourceClass.EXCHANGE, SourceTier.PRIMARY, TosRisk.LOW, 1, True)
    if _domain_matches(host, _DEPOSITORY_DOMAINS):
        return _PRIMARY
    if _domain_matches(host, _ISSUER_DOMAINS):
        return SourcePolicy(SourceClass.ISSUER, SourceTier.PRIMARY, TosRisk.LOW, 1, True)
    if _domain_matches(host, _MEDIA_DOMAINS):
        return _MEDIA
    if _domain_matches(host, _AGGREGATOR_DOMAINS):
        return _AGGREGATOR
    return _UNKNOWN


def cache_kind_for(policy: SourcePolicy, *, dynamic_market: bool = False) -> EvidenceCacheKind:
    if policy.tier is SourceTier.SNIPPET:
        return EvidenceCacheKind.SEARCH_SNIPPET
    if dynamic_market:
        return EvidenceCacheKind.DYNAMIC_MARKET
    if policy.tier is SourceTier.PRIMARY:
        return EvidenceCacheKind.PRIMARY_FILING
    if policy.tier is SourceTier.AGGREGATOR:
        return EvidenceCacheKind.AGGREGATOR_PAGE
    return EvidenceCacheKind.MEDIA_ARTICLE


_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
)


def _parse_datetime(value: Any) -> tuple[datetime, TimePrecision] | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = None
    if parsed is not None:
        precision = TimePrecision.INSTANT if re.search(r"[T ]\d{1,2}:\d{2}", normalized) else TimePrecision.DATE
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ICT)
        return parsed, precision
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ICT)
        return parsed, TimePrecision.INSTANT
    for format_string in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(raw, format_string)
        except ValueError:
            continue
        precision = TimePrecision.INSTANT if "%H" in format_string else TimePrecision.DATE
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ICT)
        return parsed, precision
    vietnamese = re.fullmatch(
        r"(?:ngày\s+)?(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
        raw,
        flags=re.IGNORECASE,
    )
    if vietnamese:
        return (
            datetime(
                int(vietnamese.group(3)),
                int(vietnamese.group(2)),
                int(vietnamese.group(1)),
                tzinfo=ICT,
            ),
            TimePrecision.DATE,
        )
    return None


_META_KEYS = (
    "article:published_time",
    "datepublished",
    "date_published",
    "publishdate",
    "pubdate",
    "date",
)
_VISIBLE_DATE_RE = re.compile(
    r"(?:Published|Publication date|Ngày đăng|Ngày xuất bản|Công bố)\s*[:\-]?\s*"
    r"((?:\d{4}[-/]\d{1,2}[-/]\d{1,2})|(?:\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})|"
    r"(?:ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}))",
    flags=re.IGNORECASE,
)
_URL_DATE_RE = re.compile(r"/(20\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])(?:/|$)")


def _stamp(
    raw: Any,
    method: PublicationMethod,
    confidence: PublicationConfidence,
) -> PublicationStamp | None:
    parsed = _parse_datetime(raw)
    if parsed is None:
        return None
    instant, precision = parsed
    return PublicationStamp(instant, method, confidence, precision, str(raw).strip())


def extract_publication_stamp(
    *,
    provider_values: Sequence[Any] = (),
    html_metadata: Mapping[str, Any] | None = None,
    json_ld_values: Sequence[Any] = (),
    visible_text: str = "",
    url: str = "",
) -> PublicationStamp:
    """Extract publication time in provenance order; never use retrieval time."""

    for value in provider_values:
        found = _stamp(value, PublicationMethod.PROVIDER, PublicationConfidence.HIGH)
        if found:
            return found
    lowered = {str(key).lower(): value for key, value in (html_metadata or {}).items()}
    for key in _META_KEYS:
        values = lowered.get(key)
        for value in values if isinstance(values, (list, tuple)) else (values,):
            found = _stamp(value, PublicationMethod.HTML_META, PublicationConfidence.HIGH)
            if found:
                return found
    for value in json_ld_values:
        found = _stamp(value, PublicationMethod.JSON_LD, PublicationConfidence.HIGH)
        if found:
            return found
    visible = _VISIBLE_DATE_RE.search(visible_text[:8_000])
    if visible:
        found = _stamp(visible.group(1), PublicationMethod.VISIBLE_TEXT, PublicationConfidence.MEDIUM)
        if found:
            return found
    matched = _URL_DATE_RE.search(urlsplit(url).path if url else "")
    if matched:
        try:
            value = date(int(matched.group(1)), int(matched.group(2)), int(matched.group(3)))
        except ValueError:
            pass
        else:
            return PublicationStamp(
                datetime.combine(value, time.min, tzinfo=ICT),
                PublicationMethod.URL_PATTERN,
                PublicationConfidence.LOW,
                TimePrecision.DATE,
                matched.group(0).strip("/"),
            )
    return PublicationStamp(
        None,
        PublicationMethod.UNKNOWN,
        PublicationConfidence.UNKNOWN,
        TimePrecision.UNKNOWN,
        None,
    )


def is_temporally_admissible(stamp: PublicationStamp, as_of: datetime) -> bool:
    """Whether this publication was knowable by ``as_of``.

    Unknown publication time fails closed.  A date-only source is compared by
    local calendar date because the publisher did not expose a time of day.
    """

    if as_of.utcoffset() is None:
        raise ValueError("as_of must include a timezone")
    if stamp.published_at is None:
        return False
    if stamp.precision is TimePrecision.DATE:
        return stamp.published_at.astimezone(ICT).date() <= as_of.astimezone(ICT).date()
    return stamp.published_at <= as_of


def as_of_bucket(
    *,
    kind: EvidenceCacheKind,
    as_of: datetime,
) -> str:
    """Stable cache window without implying that retrieval time is publication."""

    if as_of.utcoffset() is None:
        raise ValueError("as_of must include a timezone")
    local = as_of.astimezone(ICT)
    if kind is EvidenceCacheKind.AGGREGATOR_PAGE:
        hour = local.hour - (local.hour % 6)
        return local.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()
    if kind is EvidenceCacheKind.SEARCH_SNIPPET:
        minute = local.minute - (local.minute % 30)
        return local.replace(minute=minute, second=0, microsecond=0).isoformat()
    return local.date().isoformat()


__all__ = [
    "EvidenceCacheKind",
    "ICT",
    "POLICY_VERSION",
    "PublicationConfidence",
    "PublicationMethod",
    "PublicationStamp",
    "RETENTION_POLICIES",
    "RetentionPolicy",
    "SourcePolicy",
    "SourceTier",
    "TimePrecision",
    "TosRisk",
    "as_of_bucket",
    "cache_kind_for",
    "canonical_url",
    "classify_source",
    "extract_publication_stamp",
    "is_temporally_admissible",
]
