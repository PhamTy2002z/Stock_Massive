"""Tests for the CafeF article body reader.

Offline and deterministic: `httpx.get` is patched, so nothing here reaches
cafef.vn. The markup fixtures reproduce the shapes measured on real articles —
prose and figures as direct children of `div.detail-content`, with the "TIN MỚI"
widget, the ticker strip and the ad slots nested inside the same container.
"""

from unittest.mock import Mock, patch

import httpx
import pytest

from src.stocks.news.router import get_news_article as get_news_article_route
from src.stocks.news.service import NewsFeedService
from src.stocks.providers.cafef_article import (
    MIN_ARTICLE_CHARS,
    extract_blocks,
    fetch_article,
    is_cafef_article_url,
)
from src.stocks.providers.cafef_rss import FETCH_TIMEOUT_SECONDS, CafeFUnavailable
from src.stocks.shared import StockServiceError

_URL = "https://cafef.vn/mot-bai-viet-188260818221328453.chn"

# Long enough to clear `MIN_ARTICLE_CHARS` on its own, so a fixture that means
# to test something other than the length floor is not tripped by it.
_LONG = (
    "Thị trường chứng khoán Việt Nam ghi nhận thanh khoản cải thiện trong phiên "
    "giao dịch cuối tuần, với dòng tiền tập trung vào nhóm cổ phiếu ngân hàng và "
    "chứng khoán, trong khi khối ngoại tiếp tục bán ròng trên sàn HOSE."
)


@pytest.fixture
def service():
    return NewsFeedService()


def _page(body: str) -> str:
    """A CafeF article page: the content container inside the usual furniture."""
    return f"""<!DOCTYPE html><html><head><title>x</title>
    <script>var related = "<p>not prose</p>";</script></head>
    <body><div class="left-detail">
      <h2 class="sapo">Sapo nam ngoai container</h2>
      <div class="detail-content afcbc-body">{body}</div>
      <div class="list-news"><h3>CÙNG CHUYÊN MỤC</h3><p>{_LONG}</p></div>
    </div></body></html>"""


def _response(body: str, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        text=body,
        request=httpx.Request("GET", _URL),
    )


def _fetch(body: str, url: str = _URL):
    """Run `fetch_article` against a canned article page."""
    with patch(
        "src.stocks.providers.cafef_article.httpx.get", return_value=_response(body)
    ):
        return fetch_article(url)


class TestArticleUrlAllowlist:
    """The endpoint takes the URL from the client, so this is the security edge."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://cafef.vn/bai-viet-188260818221328453.chn",
            "https://www.cafef.vn/bai-viet-188260818221328453.chn",
            "https://cafef.vn/BAI-VIET-1882608.CHN",
        ],
    )
    def test_cafef_article_urls_are_readable(self, url):
        assert is_cafef_article_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            # Another host entirely — the open-proxy case.
            "https://example.com/bai-viet-188260818221328453.chn",
            # The allowed host as a prefix of an attacker's domain.
            "https://cafef.vn.evil.com/bai-viet-1882608.chn",
            # The allowed host in userinfo rather than as the host.
            "https://cafef.vn@evil.com/bai-viet-1882608.chn",
            # Loopback and link-local, the SSRF targets that matter on a host
            # that can reach a metadata service.
            "http://127.0.0.1:8000/bai-viet-1882608.chn",
            "http://169.254.169.254/latest/meta-data.chn",
            # Not https.
            "http://cafef.vn/bai-viet-1882608.chn",
            # Not an article.
            "https://cafef.vn/thi-truong-chung-khoan.rss",
            "https://cafef.vn/",
            # Not a URL at all.
            "javascript:alert(1)",
            "",
        ],
    )
    def test_everything_else_is_refused(self, url):
        assert is_cafef_article_url(url) is False

    def test_a_refused_url_is_never_fetched(self):
        with patch("src.stocks.providers.cafef_article.httpx.get") as get:
            with pytest.raises(ValueError, match="Not a fetchable CafeF article URL"):
                fetch_article("https://example.com/x.chn")

        get.assert_not_called()


class TestBlockExtraction:
    def test_prose_becomes_paragraphs_in_reading_order(self):
        blocks = extract_blocks(
            _page(f"<p>{_LONG} Mot.</p><p>{_LONG} Hai.</p><p>{_LONG} Ba.</p>")
        )

        assert [block["kind"] for block in blocks] == ["paragraph"] * 3
        assert [block["text"].split()[-1] for block in blocks] == ["Mot.", "Hai.", "Ba."]

    def test_headings_keep_their_own_kind(self):
        blocks = extract_blocks(_page(f"<h3>Khi nao von ngoai quay lai?</h3><p>{_LONG}</p>"))

        assert blocks[0] == {"kind": "heading", "text": "Khi nao von ngoai quay lai?"}
        assert blocks[1]["kind"] == "paragraph"

    def test_a_figure_becomes_an_image_with_its_caption(self):
        blocks = extract_blocks(
            _page(
                '<figure class="VCSortableInPreviewMode">'
                '<img src="https://cafefcdn.com/anh.png">'
                "<figcaption>Mai Van Chi cung tang vat.</figcaption>"
                f"</figure><p>{_LONG}</p>"
            )
        )

        assert blocks[0] == {
            "kind": "image",
            "image_url": "https://cafefcdn.com/anh.png",
            "caption": "Mai Van Chi cung tang vat.",
        }

    def test_a_lazy_loaded_image_uses_the_real_url_not_the_placeholder(self):
        """`src` holds a data: placeholder until the lazy loader swaps it."""
        blocks = extract_blocks(
            _page(
                "<figure>"
                '<img src="data:image/gif;base64,R0lGOD" '
                'data-src="https://cafefcdn.com/that.png">'
                f"</figure><p>{_LONG}</p>"
            )
        )

        assert blocks[0]["image_url"] == "https://cafefcdn.com/that.png"

    def test_a_figure_with_no_resolvable_image_is_dropped(self):
        blocks = extract_blocks(
            _page(f'<figure><img src="data:image/gif;base64,R0lGOD"></figure><p>{_LONG}</p>')
        )

        assert [block["kind"] for block in blocks] == ["paragraph"]

    def test_a_list_keeps_its_items(self):
        blocks = extract_blocks(
            _page(f"<ul><li>Mot dieu</li><li>Hai dieu</li></ul><p>{_LONG}</p>")
        )

        assert blocks[0] == {"kind": "list", "items": ["Mot dieu", "Hai dieu"]}

    def test_inline_markup_is_flattened_into_the_paragraph(self):
        blocks = extract_blocks(_page(f"<p><b>VN-Index</b> tang <i>2%</i>. {_LONG}</p>"))

        assert blocks[0]["text"].startswith("VN-Index tang 2%.")

    def test_entities_are_decoded_and_whitespace_collapsed(self):
        blocks = extract_blocks(_page(f"<p>M&amp;C\n\n  lon   hon. {_LONG}</p>"))

        assert blocks[0]["text"].startswith("M&C lon hon.")

    def test_the_zero_width_padding_cafef_writes_is_removed(self):
        """A ZWNBSP inside a sentence splits words for anything that searches it."""
        blocks = extract_blocks(_page(f"<p>Codupha﻿ co tien than. {_LONG}</p>"))

        assert "﻿" not in blocks[0]["text"]
        assert blocks[0]["text"].startswith("Codupha co tien than.")


class TestFurnitureIsExcluded:
    """The widgets share the container with the prose; only nesting separates them."""

    def test_the_tin_moi_widget_is_not_body(self):
        blocks = extract_blocks(
            _page(
                '<div class="tindnd clearfix">TIN MỚI'
                f"<ul><li><p>{_LONG} Link cu.</p></li></ul></div>"
                f"<p>{_LONG} That su la bai viet.</p>"
            )
        )

        assert [block["kind"] for block in blocks] == ["paragraph"]
        assert blocks[0]["text"].endswith("That su la bai viet.")

    def test_the_ticker_strip_and_ad_slots_are_not_body(self):
        blocks = extract_blocks(
            _page(
                '<div class="chisochungkhoan">CDP: Giá hiện tại</div>'
                '<div class="h-show-pc"></div><div class="h-show-mobile"></div>'
                f"<p>{_LONG}</p>"
                '<div class="rennab" id="sdaWeb_SdaArticleAfterBodyText"></div>'
            )
        )

        assert [block["kind"] for block in blocks] == ["paragraph"]

    def test_the_related_section_outside_the_container_is_not_body(self):
        """`_page` puts a `CÙNG CHUYÊN MỤC` block after the container every time."""
        blocks = extract_blocks(_page(f"<p>{_LONG}</p>"))

        assert len(blocks) == 1
        assert "CHUYÊN MỤC" not in blocks[0]["text"]

    def test_script_text_inside_the_container_is_not_body(self):
        blocks = extract_blocks(
            _page(f'<script>var x = "{_LONG} tu script";</script><p>{_LONG} that.</p>')
        )

        assert len(blocks) == 1
        assert "script" not in blocks[0]["text"]

    def test_an_empty_figcaption_placeholder_is_dropped(self):
        blocks = extract_blocks(_page(f"<figcaption></figcaption><p>{_LONG}</p>"))

        assert [block["kind"] for block in blocks] == ["paragraph"]

    def test_a_stray_short_paragraph_is_below_the_prose_floor(self):
        blocks = extract_blocks(_page(f"<p>Chia sẻ</p><p>{_LONG}</p>"))

        assert [block["kind"] for block in blocks] == ["paragraph"]
        assert blocks[0]["text"] == _LONG

    def test_a_stray_close_tag_inside_a_block_does_not_silence_the_rest(self):
        """An unmatched inner tag must not shift the depth counter permanently.

        The container's own `</div>` is still what ends extraction, which is the
        one nesting signal a non-validating parser has. What this guards is the
        cheaper failure: a `</span>` with no opener inside a paragraph, which
        would otherwise unwind the stack and drop every block after it.
        """
        blocks = extract_blocks(
            _page(f"<p>{_LONG} Truoc.</span></p><p>{_LONG} Sau.</p>")
        )

        assert [block["text"].split()[-1] for block in blocks] == ["Truoc.", "Sau."]

    def test_a_page_without_the_container_yields_nothing(self):
        blocks = extract_blocks(f"<html><body><p>{_LONG}</p></body></html>")

        assert blocks == []


class TestFlattenedContent:
    def test_content_is_the_blocks_as_newline_separated_text(self):
        article = _fetch(
            _page(
                f"<p>{_LONG} Mot.</p><h3>Tieu de phu</h3>"
                f"<ul><li>Mot dieu</li></ul><p>{_LONG} Hai.</p>"
            )
        )

        lines = article["content"].split("\n")
        assert lines[0].endswith("Mot.")
        assert lines[1] == "Tieu de phu"
        assert lines[2] == "Mot dieu"
        assert lines[3].endswith("Hai.")

    def test_an_image_contributes_only_its_caption(self):
        article = _fetch(
            _page(
                f"<p>{_LONG}</p><figure><img src=\"https://cafefcdn.com/a.png\">"
                "<figcaption>Anh minh hoa.</figcaption></figure>"
            )
        )

        assert "cafefcdn.com" not in article["content"]
        assert article["content"].endswith("Anh minh hoa.")


class TestArticleTransport:
    def test_browser_user_agent_and_timeout_are_sent(self):
        """Without a browser UA the WAF answers 503, exactly as on the feed."""
        with patch(
            "src.stocks.providers.cafef_article.httpx.get",
            return_value=_response(_page(f"<p>{_LONG}</p>")),
        ) as get:
            fetch_article(_URL)

        assert get.call_args.args[0] == _URL
        user_agent = get.call_args.kwargs["headers"]["User-Agent"]
        assert user_agent.startswith("Mozilla/5.0")
        assert "Chrome/" in user_agent
        assert get.call_args.kwargs["timeout"] == FETCH_TIMEOUT_SECONDS

    def test_the_article_carries_its_url_and_source(self):
        article = _fetch(_page(f"<p>{_LONG}</p>"))

        assert article["url"] == _URL
        assert article["source"] == "CafeF"

    def test_non_200_becomes_cafef_unavailable(self):
        with patch(
            "src.stocks.providers.cafef_article.httpx.get",
            return_value=_response("blocked", status_code=503),
        ):
            with pytest.raises(CafeFUnavailable, match="request failed"):
                fetch_article(_URL)

    def test_transport_failure_becomes_cafef_unavailable(self):
        with patch(
            "src.stocks.providers.cafef_article.httpx.get",
            side_effect=httpx.ConnectTimeout("timed out"),
        ):
            with pytest.raises(CafeFUnavailable, match="request failed"):
                fetch_article(_URL)

    def test_a_renamed_container_is_an_outage_not_an_empty_article(self):
        """Serving two sentences as the body would hide the breakage."""
        with patch(
            "src.stocks.providers.cafef_article.httpx.get",
            return_value=_response(
                '<html><body><div class="new-name-for-content">'
                f"<p>{_LONG}</p></div></body></html>"
            ),
        ):
            with pytest.raises(CafeFUnavailable, match="characters of body"):
                fetch_article(_URL)

    def test_the_length_floor_is_what_rejects_a_stub_page(self):
        short = "Bai viet nay chi co mot cau ngan."
        assert len(short) < MIN_ARTICLE_CHARS

        with patch(
            "src.stocks.providers.cafef_article.httpx.get",
            return_value=_response(_page(f"<p>{short}</p>")),
        ):
            with pytest.raises(CafeFUnavailable, match="characters of body"):
                fetch_article(_URL)


class TestArticleService:
    def test_the_service_returns_a_validated_response(self, service):
        with patch(
            "src.stocks.news.service.fetch_article",
            return_value={
                "url": _URL,
                "source": "CafeF",
                "blocks": [{"kind": "paragraph", "text": _LONG}],
                "content": _LONG,
            },
        ) as fetch:
            article = service.get_article(_URL)

        fetch.assert_called_once_with(_URL)
        assert article.blocks[0].kind == "paragraph"
        assert article.blocks[0].image_url is None
        assert article.content == _LONG

    def test_a_foreign_url_is_the_callers_error_and_is_never_fetched(self, service):
        with patch("src.stocks.news.service.fetch_article") as fetch:
            with pytest.raises(StockServiceError, match="Not a readable article URL"):
                service.get_article("https://example.com/x.chn")

        fetch.assert_not_called()


class TestArticleRoute:
    def test_cache_hit_does_not_reach_the_service(self):
        cached = {
            "url": _URL,
            "source": "CafeF",
            "blocks": [{"kind": "paragraph", "text": "Cached body"}],
            "content": "Cached body",
        }
        service = Mock()

        with (
            patch("src.stocks.news.router.get_news_feed_service", return_value=service),
            patch(
                "src.stocks.news.router.news_article_cache.get_or_load",
                return_value=cached,
            ) as get_or_load,
        ):
            result = get_news_article_route(url=_URL)

        assert result.content == "Cached body"
        get_or_load.assert_called_once()
        assert get_or_load.call_args.args[0] == _URL
        service.get_article.assert_not_called()

    def test_a_foreign_url_is_a_400_and_never_takes_a_cache_key(self, client):
        with patch("src.stocks.news.router.news_article_cache.get_or_load") as get_or_load:
            response = client.get(
                "/api/v1/stocks/news/article?url=https://example.com/x.chn"
            )

        assert response.status_code == 400
        assert "CafeF" in response.json()["detail"]
        get_or_load.assert_not_called()

    def test_the_article_path_is_not_captured_as_a_symbol(self, client):
        """`/stocks/{symbol}` sits beside this route and must not swallow it."""
        with patch(
            "src.stocks.news.router.news_article_cache.get_or_load",
            side_effect=CafeFUnavailable("down"),
        ):
            response = client.get(f"/api/v1/stocks/news/article?url={_URL}")

        assert response.status_code != 404
