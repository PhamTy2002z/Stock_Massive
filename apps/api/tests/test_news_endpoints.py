"""Tests for company news mapping and the CafeF-backed market news feed.

Offline and deterministic: vnstock is mocked and `httpx.get` is patched, so no
test here reaches VCI or cafef.vn.
"""
import hashlib
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import httpx
import pandas as pd
import pytest

from src.core.vnstock_client import VnstockUnavailable
from src.stocks.company.router import get_company_news as get_company_news_route
from src.stocks.company.service import CompanyService
from src.stocks.news.router import get_news_categories as get_news_categories_route
from src.stocks.news.router import get_news_feed as get_news_feed_route
from src.stocks.news.service import MAX_FEED_ITEMS, NewsFeedService
from src.stocks.providers.cafef_rss import (
    CAFEF_CATEGORIES,
    FETCH_TIMEOUT_SECONDS,
    CafeFUnavailable,
    fetch_category,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.shared import StockServiceError


@pytest.fixture
def service():
    return CompanyService(source="VCI")


@pytest.fixture
def feed_service():
    return NewsFeedService()


def _mock_company(**frames):
    """Build a Vnstock() mock whose stock().company exposes the given frames."""
    company = MagicMock()
    for name, value in frames.items():
        getattr(company, name).return_value = value
    stock = MagicMock()
    stock.company = company
    vnstock = MagicMock()
    vnstock.stock.return_value = stock
    return vnstock


def _epoch_millis(*args) -> int:
    """The millisecond stamp VCI puts in `public_date` for a VN wall-clock time."""
    return int(datetime(*args, tzinfo=VN_TZ).timestamp() * 1000)


# --- CafeF RSS fixtures ---
#
# Shapes copied from a live `https://cafef.vn/home.rss` response: CDATA
# description opening with a thumbnail anchor, a two-digit-year pubDate, and the
# article id as the digit run the slug ends with.

_LINK = "https://cafef.vn/hoan-thien-thuoc-do-rui-ro-188260817190901375.chn"
_ARTICLE_ID = "188260817190901375"
_IMAGE = (
    "https://cafefcdn.com/zoom/600_315/203337114487263232/2026/8/17/"
    "avatar1786968495715-17869684995715.jpg"
)
_DESCRIPTION = (
    f'<a href="{_LINK}"><img src="{_IMAGE}"></a> '
    "Xếp hạng tín nhiệm đã có khung pháp lý &amp; doanh nghiệp cung cấp"
    "&nbsp;dịch vụ,   nhưng mức độ sử dụng còn thấp."
)
_SUMMARY = (
    "Xếp hạng tín nhiệm đã có khung pháp lý & doanh nghiệp cung cấp dịch vụ, "
    "nhưng mức độ sử dụng còn thấp."
)


def _item(
    title: str | None = "Hoàn thiện thước đo rủi ro thị trường trái phiếu",
    link: str | None = _LINK,
    description: str = _DESCRIPTION,
    pub_date: str | None = "Mon, 17 Aug 26 19:59:00 +0700",
    guid: str | None = None,
) -> str:
    """One `<item>`; a None field is omitted from the XML entirely."""
    parts = []
    if title is not None:
        parts.append(f"<title><![CDATA[{title}]]></title>")
    if link is not None:
        parts.append(f"<link>{link}</link>")
    parts.append(f"<description><![CDATA[{description}]]></description>")
    if pub_date is not None:
        parts.append(f"<pubDate>{pub_date}</pubDate>")
    if guid is not None:
        parts.append(f"<guid>{guid}</guid>")
    return f"<item>{''.join(parts)}</item>"


def _rss(*items: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<rss version="2.0"><channel><title>CafeF RSS</title>'
        f"{''.join(items)}"
        "</channel></rss>"
    ).encode("utf-8")


def _response(body: bytes, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=body,
        request=httpx.Request("GET", "https://cafef.vn/home.rss"),
    )


def _fetch(body: bytes, slug: str = "moi-nhat"):
    """Run `fetch_category` against a canned RSS body."""
    with patch(
        "src.stocks.providers.cafef_rss.httpx.get", return_value=_response(body)
    ):
        return fetch_category(slug)


def _feed_row(**overrides):
    """A provider row as `fetch_category` returns it."""
    row = {
        "id": _ARTICLE_ID,
        "title": "Headline",
        "url": _LINK,
        "summary": _SUMMARY,
        "image_url": _IMAGE,
        "published_at": "2026-08-17T19:59:00+07:00",
        "source": "CafeF",
        "category": "moi-nhat",
    }
    row.update(overrides)
    return row


class TestVciNewsFrame:
    """The service runs on source="VCI", whose column names are its own."""

    def test_maps_vci_column_names(self, service):
        df = pd.DataFrame([{
            "id": 4231,
            "news_title": "VCB công bố kết quả kinh doanh quý 4",
            "news_source": "CafeF",
            "public_date": _epoch_millis(2026, 2, 14, 9, 30),
            "news_short_content": "<p>Lợi nhuận&nbsp;tăng   18%</p>",
            "news_full_content": "<div>Chi tiết <b>báo cáo</b></div>",
            "news_source_link": "https://cafef.vn/vcb-q4",
            "news_image_url": "https://cafef.vn/vcb.png",
            "close_price": 59_700.0,
            "price_change_ratio": 0.012,
        }])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(news=df)):
            result = service.get_company_news("VCB")

        assert result.total_count == 1
        item = result.items[0]
        assert item.id == "4231"
        assert item.title == "VCB công bố kết quả kinh doanh quý 4"
        assert item.source == "CafeF"
        assert item.published_at == "2026-02-14 09:30"
        # HTML tags and entities are stripped; whitespace collapses to one space.
        assert item.summary == "Lợi nhuận tăng 18%"
        assert item.content == "Chi tiết báo cáo"
        assert item.url == "https://cafef.vn/vcb-q4"
        assert item.image_url == "https://cafef.vn/vcb.png"
        assert item.price == 59_700.0
        assert item.price_change_pct == pytest.approx(0.012)

    def test_hex_id_is_served_rather_than_dropped(self, service):
        """VCI's `id` is a hex digest, which `int()` could never accept."""
        df = pd.DataFrame([{
            "news_title": "T",
            "id": "6a71318b35a7497fa78fb4c3",
        }])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(news=df)):
            result = service.get_company_news("VCB")

        assert result.items[0].id == "6a71318b35a7497fa78fb4c3"

    def test_news_id_wins_over_the_hex_id(self, service):
        df = pd.DataFrame([{
            "news_title": "T",
            "news_id": 918_273,
            "id": "6a71318b35a7497fa78fb4c3",
        }])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(news=df)):
            result = service.get_company_news("VCB")

        assert result.items[0].id == "918273"

    def test_seconds_epoch_is_not_read_as_millis(self, service):
        seconds = int(datetime(2026, 2, 14, 9, 30, tzinfo=VN_TZ).timestamp())
        df = pd.DataFrame([{"news_title": "T", "public_date": seconds}])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(news=df)):
            result = service.get_company_news("VCB")

        assert result.items[0].published_at == "2026-02-14 09:30"

    def test_relative_link_is_dropped_rather_than_served(self, service):
        df = pd.DataFrame([{
            "news_title": "T",
            "news_source_link": "/vcb-q4",
            "news_image_url": "  ",
        }])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(news=df)):
            result = service.get_company_news("VCB")

        assert result.items[0].url is None
        assert result.items[0].image_url is None

    def test_missing_source_falls_back_to_the_configured_provider(self, service):
        df = pd.DataFrame([{"news_title": "T"}])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(news=df)):
            result = service.get_company_news("VCB")

        assert result.items[0].source == "VCI"
        assert result.items[0].published_at == ""

    def test_missing_id_falls_back_to_row_position(self, service):
        df = pd.DataFrame([{"news_title": "First"}, {"news_title": "Second"}])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(news=df)):
            result = service.get_company_news("VCB")

        assert [item.id for item in result.items] == ["row-0", "row-1"]


class TestLegacyNewsFrame:
    """The TCBS-era column names still resolve through the fallback keys."""

    def test_maps_legacy_column_names(self, service):
        df = pd.DataFrame([{
            "id": 77,
            "title": "ACB chốt quyền trả cổ tức",
            "source": "VnExpress",
            "publish_date": pd.Timestamp("2026-01-15 14:05"),
            "price": 24_500.0,
            "price_change_ratio": -0.008,
        }])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(news=df)):
            result = service.get_company_news("ACB")

        item = result.items[0]
        assert item.id == "77"
        assert item.title == "ACB chốt quyền trả cổ tức"
        assert item.source == "VnExpress"
        assert item.published_at == "2026-01-15 14:05"
        assert item.price == 24_500.0
        assert item.price_change_pct == pytest.approx(-0.008)
        assert item.summary is None
        assert item.content is None

    def test_unparsable_date_string_is_served_raw(self, service):
        df = pd.DataFrame([{"title": "T", "publish_date": "15/01/2026"}])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(news=df)):
            result = service.get_company_news("ACB")

        assert result.items[0].published_at == "15/01/2026"


class TestNewsRowSkipping:
    def test_row_without_a_title_is_skipped(self, service):
        df = pd.DataFrame([
            {"news_title": None, "news_source": "CafeF"},
            {"news_title": "   ", "news_source": "CafeF"},
            {"news_title": "<p></p>", "news_source": "CafeF"},
            {"news_title": "Real headline", "news_source": "CafeF"},
        ])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(news=df)):
            result = service.get_company_news("VCB")

        assert result.total_count == 1
        assert result.items[0].title == "Real headline"

    def test_empty_frame_returns_empty_response(self, service):
        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(news=pd.DataFrame())):
            result = service.get_company_news("VCB")

        assert result.items == []
        assert result.total_count == 0

    def test_upstream_failure_becomes_service_error(self, service):
        vnstock = _mock_company()
        vnstock.stock.side_effect = RuntimeError("upstream down")

        with patch("src.stocks.company.service.Vnstock", return_value=vnstock):
            with pytest.raises(StockServiceError, match="Failed to fetch company news"):
                service.get_company_news("VCB")

    def test_quota_exhaustion_is_not_flattened(self, service):
        vnstock = _mock_company()
        vnstock.stock.side_effect = VnstockUnavailable("quota")

        with patch("src.stocks.company.service.Vnstock", return_value=vnstock):
            with pytest.raises(VnstockUnavailable):
                service.get_company_news("VCB")


class TestCafeFParsing:
    def test_reads_the_verified_item_shape(self):
        rows = _fetch(_rss(_item(guid=_LINK)))

        assert len(rows) == 1
        row = rows[0]
        assert row["title"] == "Hoàn thiện thước đo rủi ro thị trường trái phiếu"
        assert row["url"] == _LINK
        assert row["image_url"] == _IMAGE
        assert row["source"] == "CafeF"
        assert row["category"] == "moi-nhat"
        # Markup gone, `&amp;`/`&nbsp;` resolved, runs of whitespace collapsed.
        assert row["summary"] == _SUMMARY
        assert "<img" not in row["summary"]

    def test_two_digit_year_pubdate_lands_on_the_right_vn_instant(self):
        rows = _fetch(_rss(_item()))

        assert rows[0]["published_at"] == "2026-08-17T19:59:00+07:00"

    def test_utc_pubdate_is_converted_into_vn_time(self):
        rows = _fetch(_rss(_item(pub_date="Mon, 17 Aug 26 12:59:00 +0000")))

        assert rows[0]["published_at"] == "2026-08-17T19:59:00+07:00"

    def test_unreadable_pubdate_leaves_the_item_undated(self):
        rows = _fetch(_rss(_item(pub_date="hôm nay")))

        assert rows[0]["published_at"] == ""

    def test_missing_pubdate_leaves_the_item_undated(self):
        rows = _fetch(_rss(_item(pub_date=None)))

        assert rows[0]["published_at"] == ""

    def test_description_without_an_image_yields_no_image_url(self):
        rows = _fetch(_rss(_item(description="Chỉ có chữ, không có ảnh.")))

        assert rows[0]["image_url"] is None
        assert rows[0]["summary"] == "Chỉ có chữ, không có ảnh."

    def test_data_uri_image_is_not_served_as_a_link(self):
        rows = _fetch(_rss(_item(description='<img src="data:image/gif;base64,AA"> Chữ')))

        assert rows[0]["image_url"] is None

    def test_empty_description_yields_no_summary(self):
        rows = _fetch(_rss(_item(description=f'<a href="{_LINK}"><img src="{_IMAGE}"></a>')))

        assert rows[0]["summary"] is None
        assert rows[0]["image_url"] == _IMAGE

    def test_summary_is_capped(self):
        rows = _fetch(_rss(_item(description="a" * 900)))

        assert len(rows[0]["summary"]) == 600

    def test_empty_channel_yields_no_rows(self):
        assert _fetch(_rss()) == ()


class TestCafeFArticleId:
    def test_id_is_the_article_id_the_slug_ends_with(self):
        rows = _fetch(_rss(_item()))

        assert rows[0]["id"] == _ARTICLE_ID

    def test_id_falls_back_to_a_hash_when_the_slug_carries_no_id(self):
        link = "https://cafef.vn/thi-truong-chung-khoan"
        rows = _fetch(_rss(_item(link=link)))

        assert rows[0]["id"] == hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]

    def test_id_does_not_change_when_the_item_moves_in_the_feed(self):
        """The regression this id exists for: a positional id renames articles."""
        other = "https://cafef.vn/tin-khac-188260817190901999.chn"
        first = _item()
        second = _item(title="Tin khác", link=other)

        head_first = _fetch(_rss(first, second))
        head_second = _fetch(_rss(second, first))

        assert {row["title"]: row["id"] for row in head_first} == {
            row["title"]: row["id"] for row in head_second
        }
        assert head_second[1]["id"] == _ARTICLE_ID

    def test_guid_is_preferred_over_the_link(self):
        rows = _fetch(_rss(_item(link="https://cafef.vn/redirect", guid=_LINK)))

        assert rows[0]["id"] == _ARTICLE_ID


class TestCafeFItemSkipping:
    def test_item_without_a_title_is_skipped(self):
        rows = _fetch(_rss(_item(title=None), _item(title="   "), _item()))

        assert [row["title"] for row in rows] == [
            "Hoàn thiện thước đo rủi ro thị trường trái phiếu"
        ]

    def test_item_without_a_link_is_skipped(self):
        rows = _fetch(_rss(_item(link=None), _item()))

        assert len(rows) == 1

    def test_item_with_a_relative_link_is_skipped(self):
        rows = _fetch(_rss(_item(link="/hoan-thien-thuoc-do.chn")))

        assert rows == ()


class TestCafeFTransport:
    def test_browser_user_agent_and_timeout_are_sent(self):
        """Without a browser UA the WAF answers 503 to every CafeF URL."""
        with patch(
            "src.stocks.providers.cafef_rss.httpx.get",
            return_value=_response(_rss(_item())),
        ) as get:
            fetch_category("chung-khoan")

        assert get.call_args.args[0] == "https://cafef.vn/thi-truong-chung-khoan.rss"
        user_agent = get.call_args.kwargs["headers"]["User-Agent"]
        assert user_agent.startswith("Mozilla/5.0")
        assert "Chrome/" in user_agent
        assert get.call_args.kwargs["timeout"] == FETCH_TIMEOUT_SECONDS

    def test_our_slug_is_mapped_to_the_cafef_path(self):
        with patch(
            "src.stocks.providers.cafef_rss.httpx.get",
            return_value=_response(_rss()),
        ) as get:
            fetch_category("kinh-te")

        assert get.call_args.args[0] == "https://cafef.vn/vi-mo-dau-tu.rss"

    def test_non_200_becomes_cafef_unavailable(self):
        with patch(
            "src.stocks.providers.cafef_rss.httpx.get",
            return_value=_response(b"blocked", status_code=503),
        ):
            with pytest.raises(CafeFUnavailable, match="request failed"):
                fetch_category("moi-nhat")

    def test_transport_failure_becomes_cafef_unavailable(self):
        with patch(
            "src.stocks.providers.cafef_rss.httpx.get",
            side_effect=httpx.ConnectTimeout("timed out"),
        ):
            with pytest.raises(CafeFUnavailable, match="request failed"):
                fetch_category("moi-nhat")

    def test_malformed_xml_becomes_cafef_unavailable(self):
        with patch(
            "src.stocks.providers.cafef_rss.httpx.get",
            return_value=_response(b"<rss><channel><item>"),
        ):
            with pytest.raises(CafeFUnavailable, match="not parseable XML"):
                fetch_category("moi-nhat")

    def test_unknown_slug_is_the_callers_error_not_an_outage(self):
        with patch("src.stocks.providers.cafef_rss.httpx.get") as get:
            with pytest.raises(ValueError, match="Unknown CafeF news category"):
                fetch_category("khong-co")

        get.assert_not_called()


class TestNewsFeedService:
    def test_maps_provider_rows_onto_feed_items(self, feed_service):
        with patch(
            "src.stocks.news.service.fetch_category", return_value=(_feed_row(),)
        ) as fetch:
            result = feed_service.get_feed("chung-khoan")

        fetch.assert_called_once_with("chung-khoan")
        assert result.category == "chung-khoan"
        assert result.total_count == 1
        assert result.symbols == []
        assert result.generated_at
        item = result.items[0]
        assert item.id == _ARTICLE_ID
        assert item.url == _LINK
        assert item.image_url == _IMAGE
        assert item.source == "CafeF"
        # A press article has no ticker to be attributed to.
        assert item.symbol is None

    def test_defaults_to_the_newest_category(self, feed_service):
        with patch(
            "src.stocks.news.service.fetch_category", return_value=()
        ) as fetch:
            result = feed_service.get_feed()

        fetch.assert_called_once_with("moi-nhat")
        assert result.category == "moi-nhat"

    def test_response_carries_the_whole_registry_for_the_pill_row(self, feed_service):
        with patch("src.stocks.news.service.fetch_category", return_value=()):
            result = feed_service.get_feed()

        assert [category.slug for category in result.categories] == [
            "moi-nhat",
            "chung-khoan",
            "kinh-te",
            "tai-chinh",
            "bat-dong-san",
            "doanh-nghiep",
            "cong-nghe",
            "the-gioi",
        ]
        assert result.categories[0].label == "Mới nhất"

    def test_sorts_newest_first_with_undated_items_last(self, feed_service):
        rows = (
            _feed_row(title="older", published_at="2026-08-16T08:00:00+07:00"),
            _feed_row(title="undated", published_at=""),
            _feed_row(title="newest", published_at="2026-08-17T19:59:00+07:00"),
        )

        with patch("src.stocks.news.service.fetch_category", return_value=rows):
            result = feed_service.get_feed()

        assert [item.title for item in result.items] == ["newest", "older", "undated"]

    def test_feed_is_capped(self, feed_service):
        rows = tuple(
            _feed_row(
                id=str(index),
                title=f"Headline {index}",
                published_at=f"2026-08-17T{index % 24:02d}:00:00+07:00",
            )
            for index in range(MAX_FEED_ITEMS + 40)
        )

        with patch("src.stocks.news.service.fetch_category", return_value=rows):
            result = feed_service.get_feed()

        assert len(result.items) == MAX_FEED_ITEMS
        assert result.total_count == MAX_FEED_ITEMS

    def test_unknown_category_is_rejected_before_a_request_is_spent(self, feed_service):
        with patch("src.stocks.news.service.fetch_category") as fetch:
            with pytest.raises(StockServiceError, match="Unknown news category"):
                feed_service.get_feed("khong-co")

        fetch.assert_not_called()

    def test_cafef_outage_propagates(self, feed_service):
        with patch(
            "src.stocks.news.service.fetch_category",
            side_effect=CafeFUnavailable("503 from the WAF"),
        ):
            with pytest.raises(CafeFUnavailable):
                feed_service.get_feed()

    def test_categories_match_the_provider_registry(self, feed_service):
        categories = feed_service.get_categories()

        assert [(item.slug, item.label) for item in categories] == [
            (category.slug, category.label) for category in CAFEF_CATEGORIES
        ]


class TestNewsRouteCaching:
    """A cache hit must not reach the provider service at all."""

    _CACHED_FEED = {
        "items": [
            {
                "id": "188260817190901375",
                "title": "Cached headline",
                "published_at": "2026-08-17T19:59:00+07:00",
                "source": "CafeF",
                "category": "moi-nhat",
            }
        ],
        "category": "moi-nhat",
        "categories": [{"slug": "moi-nhat", "label": "Mới nhất"}],
        "symbols": [],
        "generated_at": "2026-08-17T20:00:00+07:00",
        "total_count": 1,
    }

    def test_company_news_cache_hit_does_not_call_provider_service(self):
        service = Mock()
        cached = {
            "symbol": "VCB",
            "items": [
                {
                    "id": "4231",
                    "title": "Cached headline",
                    "published_at": "2026-02-14 09:30",
                }
            ],
            "total_count": 1,
        }

        with (
            patch("src.stocks.company.router.get_company_service", return_value=service),
            patch(
                "src.stocks.company.router.company_news_cache.get_or_load",
                return_value=cached,
            ) as get_or_load,
        ):
            result = get_company_news_route("vcb")

        assert result.symbol == "VCB"
        assert result.items[0].title == "Cached headline"
        get_or_load.assert_called_once()
        service.get_company_news.assert_not_called()

    def test_news_feed_cache_hit_does_not_build_the_feed(self):
        service = Mock()

        with (
            patch("src.stocks.news.router.get_news_feed_service", return_value=service),
            patch(
                "src.stocks.news.router.news_feed_cache.get_or_load",
                return_value=self._CACHED_FEED,
            ) as get_or_load,
        ):
            result = get_news_feed_route(category="moi-nhat")

        assert result.category == "moi-nhat"
        assert result.symbols == []
        assert result.items[0].title == "Cached headline"
        assert result.items[0].symbol is None
        get_or_load.assert_called_once()
        service.get_feed.assert_not_called()

    def test_two_categories_do_not_share_a_cache_key(self):
        with (
            patch("src.stocks.news.router.get_news_feed_service", return_value=Mock()),
            patch(
                "src.stocks.news.router.news_feed_cache.get_or_load",
                return_value=self._CACHED_FEED,
            ) as get_or_load,
        ):
            get_news_feed_route(category="moi-nhat")
            get_news_feed_route(category="chung-khoan")

        assert [call.args[0] for call in get_or_load.call_args_list] == [
            "cafef:moi-nhat",
            "cafef:chung-khoan",
        ]

    def test_a_cafef_outage_is_allowed_to_serve_stale(self):
        with (
            patch("src.stocks.news.router.get_news_feed_service", return_value=Mock()),
            patch(
                "src.stocks.news.router.news_feed_cache.get_or_load",
                return_value=self._CACHED_FEED,
            ) as get_or_load,
        ):
            get_news_feed_route(category="moi-nhat")

        suppress = get_or_load.call_args.kwargs["suppress_failure"]
        assert suppress(CafeFUnavailable("503")) is True
        assert suppress(RuntimeError("something else")) is False


class TestNewsFeedRoutes:
    def test_feed_path_is_not_captured_as_a_symbol(self, client):
        """`/news/feed` must reach the feed route, never /{symbol}/... routes."""
        with patch(
            "src.stocks.news.router.news_feed_cache.get_or_load",
            return_value=TestNewsRouteCaching._CACHED_FEED,
        ) as get_or_load:
            response = client.get("/api/v1/stocks/news/feed")

        assert response.status_code == 200
        assert response.json()["category"] == "moi-nhat"
        get_or_load.assert_called_once()

    def test_unknown_category_is_a_400_not_a_cache_key(self, client):
        with patch(
            "src.stocks.news.router.news_feed_cache.get_or_load"
        ) as get_or_load:
            response = client.get("/api/v1/stocks/news/feed?category=khong-co")

        assert response.status_code == 400
        assert "khong-co" in response.json()["detail"]
        get_or_load.assert_not_called()

    def test_categories_route_lists_the_facets_in_order(self, client):
        response = client.get("/api/v1/stocks/news/categories")

        assert response.status_code == 200
        assert [item["slug"] for item in response.json()] == [
            "moi-nhat",
            "chung-khoan",
            "kinh-te",
            "tai-chinh",
            "bat-dong-san",
            "doanh-nghiep",
            "cong-nghe",
            "the-gioi",
        ]

    def test_categories_route_needs_no_network(self):
        with patch("src.stocks.providers.cafef_rss.httpx.get") as get:
            categories = get_news_categories_route()

        get.assert_not_called()
        assert [item.label for item in categories][:2] == ["Mới nhất", "Chứng khoán"]
