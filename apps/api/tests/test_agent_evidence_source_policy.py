"""Phase 6 source identity, publication-time, and retention contract."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from src.agent.evidence.contracts import SourceClass
from src.agent.evidence.source_policy import (
    EvidenceCacheKind,
    PublicationConfidence,
    PublicationMethod,
    RETENTION_POLICIES,
    SourceTier,
    TosRisk,
    as_of_bucket,
    canonical_url,
    classify_source,
    extract_publication_stamp,
    ICT,
    as_of_from_text,
    is_temporally_admissible,
)


def test_canonical_url_removes_only_identity_noise_and_sorts_query():
    assert canonical_url(
        "HTTPS://Example.COM:443/a?utm_source=x&b=2&a=1&fbclid=tracking#fragment"
    ) == "https://example.com/a?a=1&b=2"


def test_canonical_url_keeps_non_default_port_and_material_blank_query():
    assert canonical_url("http://Example.com:8080?a=&z=2") == (
        "http://example.com:8080/?a=&z=2"
    )


@pytest.mark.parametrize("value", ["file:///tmp/a", "https://user:pw@example.com/a", "not a url"])
def test_canonical_url_rejects_non_public_identity_shapes(value: str):
    with pytest.raises(ValueError):
        canonical_url(value)


@pytest.mark.parametrize(
    ("url", "source_class"),
    [
        ("https://ssc.gov.vn/document", SourceClass.REGULATOR),
        ("https://staticfile.hsx.vn/report.pdf", SourceClass.EXCHANGE),
        ("https://vsdc.vn/news", SourceClass.PRIMARY_DOCUMENT),
        ("https://www.vietcombank.com.vn/ir", SourceClass.ISSUER),
        ("https://www.reuters.com/markets/x", SourceClass.MEDIA),
        ("https://finance.yahoo.com/quote/VCB.VN", SourceClass.AGGREGATOR),
        ("https://research-looking.example/official", SourceClass.UNKNOWN),
    ],
)
def test_source_class_is_from_known_final_domain_not_search_relevance(url: str, source_class: SourceClass):
    assert classify_source(url).source_class is source_class


def test_primary_media_aggregator_and_snippet_have_distinct_material_rules():
    primary = classify_source("https://hnx.vn/report")
    media = classify_source("https://vnexpress.net/article")
    aggregator = classify_source("https://www.investing.com/equities/x")
    snippet = classify_source("https://hnx.vn/report", snippet=True)

    assert (primary.tier, primary.material_min_publishers, primary.tos_risk) == (
        SourceTier.PRIMARY,
        1,
        TosRisk.LOW,
    )
    assert media.material_min_publishers == 2
    assert (aggregator.material_min_publishers, aggregator.tos_risk) == (2, TosRisk.HIGH)
    assert snippet.durable_evidence is False
    assert snippet.material_min_publishers is None


def test_publication_priority_is_provider_then_metadata_then_json_ld():
    stamp = extract_publication_stamp(
        provider_values=("2026-08-20T09:30:00+07:00",),
        html_metadata={"article:published_time": "2026-08-19T10:00:00+07:00"},
        json_ld_values=("2026-08-18",),
    )

    assert stamp.published_at == datetime.fromisoformat("2026-08-20T09:30:00+07:00")
    assert stamp.method is PublicationMethod.PROVIDER
    assert stamp.confidence is PublicationConfidence.HIGH


def test_publication_falls_back_to_visible_vietnamese_date_then_url_pattern():
    visible = extract_publication_stamp(visible_text="Ngày đăng: ngày 19 tháng 8 năm 2026")
    url = extract_publication_stamp(url="https://example.com/2026/08/18/story")

    assert visible.published_at is not None and visible.published_at.date().isoformat() == "2026-08-19"
    assert visible.method is PublicationMethod.VISIBLE_TEXT
    assert url.published_at is not None and url.published_at.date().isoformat() == "2026-08-18"
    assert url.method is PublicationMethod.URL_PATTERN
    assert url.confidence is PublicationConfidence.LOW


def test_unknown_publication_is_not_retrieval_time_and_fails_historical_admission():
    stamp = extract_publication_stamp(visible_text="retrieved at 2026-08-20")

    assert stamp.published_at is None
    assert stamp.method is PublicationMethod.UNKNOWN
    assert is_temporally_admissible(stamp, datetime(2026, 8, 20, tzinfo=timezone.utc)) is False


def test_publication_after_as_of_cannot_support_the_claim():
    stamp = extract_publication_stamp(provider_values=("2026-08-21T00:00:01+00:00",))

    assert is_temporally_admissible(
        stamp, datetime(2026, 8, 21, 0, 0, 0, tzinfo=timezone.utc)
    ) is False


def test_date_precision_uses_the_finance_local_calendar():
    stamp = extract_publication_stamp(provider_values=("2026-08-21",))

    assert is_temporally_admissible(
        stamp, datetime(2026, 8, 20, 17, 30, tzinfo=timezone.utc)
    ) is True


def test_retention_and_bucket_values_are_locked_by_policy():
    assert RETENTION_POLICIES[EvidenceCacheKind.DYNAMIC_MARKET].retention == timedelta(days=7)
    assert RETENTION_POLICIES[EvidenceCacheKind.MEDIA_ARTICLE].retention == timedelta(days=30)
    assert RETENTION_POLICIES[EvidenceCacheKind.PRIMARY_FILING].retention == timedelta(days=730)
    assert RETENTION_POLICIES[EvidenceCacheKind.AGGREGATOR_PAGE].freshness == timedelta(hours=6)
    assert RETENTION_POLICIES[EvidenceCacheKind.SEARCH_SNIPPET].retention is None
    assert RETENTION_POLICIES[EvidenceCacheKind.PRIVATE_TRAJECTORY].owner_scoped is True
    assert RETENTION_POLICIES[EvidenceCacheKind.CLAIM_LEDGER].retention is None

    as_of = datetime.fromisoformat("2026-08-21T13:47:00+07:00")
    assert as_of_bucket(kind=EvidenceCacheKind.DYNAMIC_MARKET, as_of=as_of) == "2026-08-21"
    assert as_of_bucket(kind=EvidenceCacheKind.AGGREGATOR_PAGE, as_of=as_of) == (
        "2026-08-21T12:00:00+07:00"
    )


def test_the_boundary_is_read_out_of_the_question_and_only_when_it_is_a_date():
    """A stated date bounds the Turn; a ratio that looks like one does not.

    "tính đến ngày 20/8/2026" is a boundary the reader wrote down, and §2 says
    a page published on the 21st cannot answer it. "P/E 30/8" is not a date at
    all, and reading it as one would bound the Turn to August and quietly starve
    it of everything since — which is why a year-less pair needs a date word in
    front of it.
    """
    now = datetime(2026, 9, 4, 23, 0, tzinfo=ICT)

    bounded = as_of_from_text("Tính đến ngày 20/8/2026, thanh khoản HOSE ra sao?", now=now)
    assert bounded is not None and bounded.astimezone(ICT).date() == date(2026, 8, 20)

    # The end of a range, not its start.
    ranged = as_of_from_text("Từ 01/08/2026 đến 20/08/2026 thị trường thế nào?", now=now)
    assert ranged is not None and ranged.astimezone(ICT).date() == date(2026, 8, 20)

    assert as_of_from_text("phiên 12/8 vừa rồi thế nào?", now=now) is not None
    assert as_of_from_text("P/E 30/8 của VCB là bao nhiêu?", now=now) is None
    assert as_of_from_text("Vốn điều lệ hiện tại của VCB?", now=now) is None
    # A forecast horizon is not a limit on what may be read.
    assert as_of_from_text("Dự báo tới 31/12/2027 ra sao?", now=now) is None


def test_a_compact_news_id_dates_the_page_a_snippet_left_undated():
    """CafeF and Tuổi Trẻ write the date into the article id, not the path.

    A search snippet from either arrives with no publication field at all, and
    an undated source is admitted everywhere a dated one is refused — so a page
    published after the reader's stated boundary walks in on the strength of its
    publisher's URL scheme. Read the id and it does not.
    """
    cafef = extract_publication_stamp(
        url="https://cafef.vn/sau-dip-le-quoc-khanh-188260829154209089.chn"
    )
    assert cafef.published_at is not None
    assert cafef.published_at.astimezone(ICT).date() == date(2026, 8, 29)
    assert cafef.method is PublicationMethod.URL_PATTERN

    tuoitre = extract_publication_stamp(
        url="https://tuoitre.vn/chung-khoan-14-8-100260814074820245.htm"
    )
    assert tuoitre.published_at is not None
    assert tuoitre.published_at.astimezone(ICT).date() == date(2026, 8, 14)

    # An id with no date in it stays unknown rather than inventing one.
    plain = extract_publication_stamp(
        url="https://vnexpress.net/chung-khoan-giam-them-37-diem-5109204.html"
    )
    assert plain.published_at is None
