"""Vietnamese-equity guidance for the web-first agent harness."""

from __future__ import annotations

from ..prompt.sections import PromptSection
from .pack import DomainPack

VERSION = "4.0.0"

WEB_FIRST_RESEARCH = PromptSection(
    key="vn_equity_web_first",
    title="Nghiên cứu chứng khoán Việt Nam bằng nguồn web",
    body="""
Với câu hỏi về chứng khoán, hãy dùng web_search để tìm nguồn hiện hành rồi dùng
fetch_url để đọc nguồn trước khi đưa ra dữ kiện. Ưu tiên công bố của doanh
nghiệp, sở giao dịch, cơ quan quản lý và nguồn dữ liệu có phương pháp rõ ràng.
Nêu ngày hoặc kỳ báo cáo bên cạnh số liệu, phân biệt dữ kiện với suy luận, và
chỉ kết luận trong giới hạn bằng chứng đã đọc.

Hệ thống không có kho chỉ báo, bộ tính toán kỹ thuật hay Study cục bộ. Không
được nói rằng đã đọc dữ liệu nội bộ, đã chạy chỉ báo, đã dựng board hoặc đã tính
một đại lượng nếu tool không thực sự cung cấp bằng chứng cho việc đó. Khi nguồn
không đủ hoặc mâu thuẫn, nói rõ khoảng trống và điều cần kiểm chứng thêm.
""".strip(),
)

#: How a Vietnamese listing is written: three to eight shouted characters,
#: starting with a letter, bounded by something that is not one.
#:
#: Covers the ticker (``VNM``), the index and its futures (``VN30``,
#: ``VN30F1M``), the listed funds (``E1VFVN30``) and the venues (``HOSE``,
#: ``UPCOM``) with one shape rather than a table, because a table of listings is
#: a market-data dependency and this module has none.
#:
#: It over-matches — ``USD``, ``CEO`` and ``PDF`` have the same shape — and that
#: is the direction to be wrong in. A false positive costs the body's few
#: hundred tokens; a false negative answers a market question with the domain's
#: rules left out.
SYMBOL_SHAPE = r"(?<![0-9A-Za-z])[A-Z][A-Z0-9]{2,7}(?![0-9A-Za-z])"

#: What a reader says when the question is about this market, ticker or not.
#:
#: Wider than equities on purpose: rates, the currency and the bond market are
#: what an equity question is answered against, and a reader asking about one of
#: them is asking a question this pack's rules apply to. Both languages, because
#: readers mix them in one sentence.
TOPIC_MARKERS: tuple[str, ...] = (
    "cổ phiếu",
    "chứng khoán",
    "thị trường",
    "cổ tức",
    "vốn hóa",
    "định giá",
    "doanh thu",
    "lợi nhuận",
    "báo cáo tài chính",
    "khối ngoại",
    "thanh khoản",
    "trái phiếu",
    "lãi suất",
    "tỷ giá",
    "đầu tư",
    "giá",
    "vn-index",
    "vnindex",
    "p/e",
    "stock",
    "share",
    "market",
    "ticker",
    "equity",
    "earnings",
    "revenue",
    "dividend",
    "valuation",
)

#: What a reader says when the question is about the assistant instead.
#:
#: Short, and it stays short. This is the only evidence that withholds the
#: playbook, so a word admitted here on a hunch is a market question answered
#: without the domain's rules. Everything not on this list — including every
#: question nobody anticipated — keeps the body.
OFF_TOPIC_MARKERS: tuple[str, ...] = (
    "bạn là ai",
    "bạn là gì",
    "bạn tên gì",
    "bạn có thể làm gì",
    "bạn làm được gì",
    "bạn hoạt động",
    "who are you",
    "what are you",
    "what can you do",
    "how do you work",
    "xin chào",
    "chào bạn",
    "hello",
    "cảm ơn",
    "thank you",
)

PACK = DomainPack(
    name="vn-equity",
    version=VERSION,
    prompt_sections=(WEB_FIRST_RESEARCH,),
    symbol_shape=SYMBOL_SHAPE,
    topic_markers=TOPIC_MARKERS,
    off_topic_markers=OFF_TOPIC_MARKERS,
)

__all__ = [
    "OFF_TOPIC_MARKERS",
    "PACK",
    "SYMBOL_SHAPE",
    "TOPIC_MARKERS",
    "VERSION",
    "WEB_FIRST_RESEARCH",
]
