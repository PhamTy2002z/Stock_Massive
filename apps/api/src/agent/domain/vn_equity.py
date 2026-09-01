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

PACK = DomainPack(
    name="vn-equity",
    version=VERSION,
    prompt_sections=(WEB_FIRST_RESEARCH,),
)

__all__ = ["PACK", "VERSION", "WEB_FIRST_RESEARCH"]
