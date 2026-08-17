"""Tests for company news mapping and the market-wide news feed.

All vnstock access is mocked — these tests are offline and deterministic.
"""
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from src.core.vnstock_client import VnstockUnavailable, VnstockUnsupported
from src.stocks.company.router import get_company_news as get_company_news_route
from src.stocks.company.service import CompanyService
from src.stocks.news.router import get_news_feed as get_news_feed_route
from src.stocks.news.service import FEED_SYMBOL_LIMIT, NewsFeedService
from src.stocks.providers.normalize import VN_TZ
from src.stocks.schemas.company import NewsItem, NewsResponse
from src.stocks.shared import StockServiceError


@pytest.fixture
def service():
    return CompanyService(source="VCI")


@pytest.fixture
def feed_service():
    return NewsFeedService(source="VCI")


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


def _news_response(symbol: str, *stamps: str) -> NewsResponse:
    """A per-symbol news response carrying one item per published_at stamp."""
    items = [
        NewsItem(id=index, title=f"{symbol} headline {index}", published_at=stamp)
        for index, stamp in enumerate(stamps)
    ]
    return NewsResponse(symbol=symbol, items=items, total_count=len(items))


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
        assert item.id == 4231
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

        assert [item.id for item in result.items] == [0, 1]


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
        assert item.id == 77
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


class TestNewsFeedSymbols:
    def test_symbol_set_is_capped(self, feed_service):
        listing = MagicMock()
        listing.return_value.symbols_by_group.return_value = [
            f"S{i:02d}" for i in range(30)
        ]

        with patch("src.stocks.news.service.Listing", listing):
            symbols = feed_service._feed_symbols()

        listing.return_value.symbols_by_group.assert_called_once_with("VN30")
        assert len(symbols) == FEED_SYMBOL_LIMIT
        assert symbols[0] == "S00"

    def test_empty_group_becomes_service_error(self, feed_service):
        listing = MagicMock()
        listing.return_value.symbols_by_group.return_value = []

        with patch("src.stocks.news.service.Listing", listing):
            with pytest.raises(StockServiceError, match="Failed to list news feed symbols"):
                feed_service._feed_symbols()

    def test_quota_exhaustion_is_not_flattened(self, feed_service):
        listing = MagicMock()
        listing.return_value.symbols_by_group.side_effect = VnstockUnavailable("quota")

        with patch("src.stocks.news.service.Listing", listing):
            with pytest.raises(VnstockUnavailable):
                feed_service._feed_symbols()


class TestNewsFeed:
    def test_merges_symbols_and_sorts_newest_first(self, feed_service):
        company = Mock()
        company.get_company_news.side_effect = lambda symbol: {
            "VCB": _news_response("VCB", "2026-02-14 09:30", "2026-02-10 08:00"),
            "ACB": _news_response("ACB", "2026-02-15 17:45"),
        }[symbol]

        with (
            patch.object(feed_service, "_feed_symbols", return_value=["VCB", "ACB"]),
            patch("src.stocks.news.service.get_company_service", return_value=company),
        ):
            result = feed_service.get_feed()

        assert [item.published_at for item in result.items] == [
            "2026-02-15 17:45",
            "2026-02-14 09:30",
            "2026-02-10 08:00",
        ]
        assert [item.symbol for item in result.items] == ["ACB", "VCB", "VCB"]
        assert result.symbols == ["VCB", "ACB"]
        assert result.total_count == 3
        assert result.generated_at

    def test_undated_items_sort_last_rather_than_being_dropped(self, feed_service):
        company = Mock()
        company.get_company_news.return_value = _news_response(
            "VCB", "", "2026-02-14 09:30"
        )

        with (
            patch.object(feed_service, "_feed_symbols", return_value=["VCB"]),
            patch("src.stocks.news.service.get_company_service", return_value=company),
        ):
            result = feed_service.get_feed()

        assert [item.published_at for item in result.items] == ["2026-02-14 09:30", ""]

    def test_failing_symbol_is_skipped_and_absent_from_symbols(self, feed_service):
        company = Mock()

        def news(symbol):
            if symbol == "BID":
                raise StockServiceError("Failed to fetch company news for BID")
            return _news_response(symbol, "2026-02-14 09:30")

        company.get_company_news.side_effect = news

        with (
            patch.object(feed_service, "_feed_symbols", return_value=["VCB", "BID", "ACB"]),
            patch("src.stocks.news.service.get_company_service", return_value=company),
        ):
            result = feed_service.get_feed()

        assert result.symbols == ["VCB", "ACB"]
        assert result.total_count == 2
        assert "BID" not in {item.symbol for item in result.items}

    def test_unsupported_symbol_is_skipped(self, feed_service):
        company = Mock()

        def news(symbol):
            if symbol == "BID":
                raise VnstockUnsupported("not implemented")
            return _news_response(symbol, "2026-02-14 09:30")

        company.get_company_news.side_effect = news

        with (
            patch.object(feed_service, "_feed_symbols", return_value=["BID", "ACB"]),
            patch("src.stocks.news.service.get_company_service", return_value=company),
        ):
            result = feed_service.get_feed()

        assert result.symbols == ["ACB"]

    def test_symbol_with_no_items_does_not_claim_to_have_contributed(self, feed_service):
        company = Mock()
        company.get_company_news.side_effect = lambda symbol: {
            "VCB": _news_response("VCB"),
            "ACB": _news_response("ACB", "2026-02-14 09:30"),
        }[symbol]

        with (
            patch.object(feed_service, "_feed_symbols", return_value=["VCB", "ACB"]),
            patch("src.stocks.news.service.get_company_service", return_value=company),
        ):
            result = feed_service.get_feed()

        assert result.symbols == ["ACB"]


class TestNewsFeedQuotaExhaustion:
    def test_nothing_gathered_re_raises_unavailable(self, feed_service):
        company = Mock()
        company.get_company_news.side_effect = VnstockUnavailable("quota")

        with (
            patch.object(feed_service, "_feed_symbols", return_value=["VCB", "ACB"]),
            patch("src.stocks.news.service.get_company_service", return_value=company),
        ):
            with pytest.raises(VnstockUnavailable):
                feed_service.get_feed()

        # The first refusal ends the walk; the rest would only burn the window.
        assert company.get_company_news.call_count == 1

    def test_partial_feed_survives_a_later_refusal(self, feed_service):
        company = Mock()

        def news(symbol):
            if symbol == "VCB":
                return _news_response("VCB", "2026-02-14 09:30")
            raise VnstockUnavailable("quota")

        company.get_company_news.side_effect = news

        with (
            patch.object(feed_service, "_feed_symbols", return_value=["VCB", "ACB", "BID"]),
            patch("src.stocks.news.service.get_company_service", return_value=company),
        ):
            result = feed_service.get_feed()

        assert result.symbols == ["VCB"]
        assert result.total_count == 1
        # Broke out at ACB rather than walking on to BID.
        assert company.get_company_news.call_count == 2


class TestNewsRouteCaching:
    """A cache hit must not reach the provider service at all."""

    def test_company_news_cache_hit_does_not_call_provider_service(self):
        service = Mock()
        cached = {
            "symbol": "VCB",
            "items": [
                {
                    "id": 1,
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
        cached = {
            "items": [
                {
                    "id": 1,
                    "symbol": "VCB",
                    "title": "Cached headline",
                    "published_at": "2026-02-14 09:30",
                }
            ],
            "symbols": ["VCB"],
            "generated_at": "2026-02-14T09:31:00+07:00",
            "total_count": 1,
        }

        with (
            patch("src.stocks.news.router.get_news_feed_service", return_value=service),
            patch(
                "src.stocks.news.router.news_feed_cache.get_or_load",
                return_value=cached,
            ) as get_or_load,
        ):
            result = get_news_feed_route()

        assert result.symbols == ["VCB"]
        assert result.items[0].symbol == "VCB"
        get_or_load.assert_called_once()
        service.get_feed.assert_not_called()


class TestNewsFeedRouteRegistration:
    def test_feed_path_is_not_captured_as_a_symbol(self, client):
        """`/news/feed` must reach the feed route, never /{symbol}/... routes."""
        with patch(
            "src.stocks.news.router.news_feed_cache.get_or_load",
            return_value={
                "items": [],
                "symbols": [],
                "generated_at": "2026-02-14T09:31:00+07:00",
                "total_count": 0,
            },
        ) as get_or_load:
            response = client.get("/api/v1/stocks/news/feed")

        assert response.status_code == 200
        assert response.json()["symbols"] == []
        get_or_load.assert_called_once()
