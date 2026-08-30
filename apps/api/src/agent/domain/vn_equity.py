"""The Vietnamese equity domain, declared.

This is the one file in ``agent/domain`` allowed to import the domain it
describes: it *is* the domain. ``pack.py`` and ``__init__.py`` are the frame,
and a frame that imported ``stocks`` would have to be edited to hold the second
pack.

Nothing here is defined twice. The Universe is the callable the domain's tools
already call; the Study names are the names the registry already holds; the
refusal codes are the enum the signals module already closes. What this file
adds is the statement that these belong together, plus the contract tests that
keep the statement true.
"""

from __future__ import annotations

from src.stocks.signals.issues import SignalIssue
from src.stocks.universe import build_universe

from ..prompt.sections import PromptSection
from .pack import DomainPack

#: Bumped by hand with the prose it names. ``3.x`` is the playbook that composes
#: a board — the seven steps a question with numbers in it goes through, which
#: only a Turn that touched this domain ever needs. ``2.x`` is this domain
#: carrying its own half of the prompt; ``1.x`` was the declaration alone, back
#: when the playbook below still shipped inside the core every Turn paid for.
VERSION = "3.0.0"

#: Written out rather than read from ``studies.REGISTRY``, and the reason is
#: import order as much as review: ``REGISTRY`` is filled by importing
#: ``src.studies``, so a pack that read it here would hold whatever happened to
#: be registered at the moment this module was first imported. Written out, it
#: holds what a reviewer approved, and ``test_agent_domain_pack`` holds it to
#: what the registry actually offers.
STUDY_NAMES: tuple[str, ...] = (
    "earnings_dislocation_screener",
    "entry_condition_review",
    "intraday_liquidity_profile",
    "volume_at_price",
)

#: How this system's own store is read, in the words it was read in before the
#: prompt had two tiers. Moved rather than rewritten: the phase that split the
#: prompt was allowed to change where a sentence lives and nothing else, so that
#: a regression in an answer traces to the move rather than to an edit made in
#: passing.
#:
#: One paragraph that started here went back to the core instead: the list of
#: what this assistant *cannot* read — the reader's price board, their
#: watchlist, raw statements. It is written in this domain's vocabulary, which
#: is why it looked like body prose, but it binds the Turn that reaches for
#: nothing, and that Turn never sees this file. A negative capability is a
#: safety rule wearing a domain's words.
STORE = PromptSection(
    key="vn_equity_store",
    title="Kho dữ liệu của hệ thống này",
    body="""
Bạn đọc được một thứ của hệ thống này, và chỉ một thứ: các Signal Field đã đăng
ký, cho một mã trong Universe, ở phiên gần nhất đã đóng. Đường đọc là
list_fields và get_field. Mỗi figure về kèm đơn vị, cách đọc được phép, tình
trạng và ngày nó tính đến — bốn thứ đó là phần làm nó kiểm được, nên khi bạn nêu
một figure thì nêu kèm ngày của nó.

Một figure có tình trạng refused là một câu trả lời, không phải một lỗi: store
nói rõ nó không tính được và nói vì sao. Nêu điều đó ra. Đừng lấy một con số
refused làm chỗ dựa cho một kết luận, và đừng hỏi lại đúng field đó lần thứ hai.

Số của store thắng số của web khi hai bên khác nhau, và sự khác nhau phải được
nói ra. Store là số đã chuẩn hoá, đã ghim ngày, và kiểm được lại; một trang web
là phương pháp của người khác. Đừng chọn bừa một bên rồi im lặng.
""".strip(),
)


#: When a number is the honest answer and when a picture is, and what the store
#: cannot answer at all. Second rather than folded into :data:`STORE`: the first
#: says what can be read, this says what to do about it, and a reader looking for
#: one should not have to read the other.
PLAYBOOK = PromptSection(
    key="vn_equity_playbook",
    title="Một con số hay một bức tranh, và phần store không trả lời được",
    body="""
Ranh giới giữa hai loại trên là hình dạng của câu trả lời chứ không phải chủ
đề. get_field trả về MỘT con số. Khi câu trả lời trung thực là một hình — phân
bố theo khung giờ, diễn biến qua nhiều phiên, một bảng xếp hạng — thì đó là
run_study. Bạn không nhìn thấy bức tranh và không cần nhìn: bạn được đưa phần
headline, và đó là toàn bộ những gì một câu văn nói được về nó một cách trung
thực. Đừng mô tả một ô cụ thể mà headline không nêu.

Nhưng store chỉ có ba trục: kỹ thuật, dòng tiền, và cơ bản — toàn bộ là con số.
Nó không có tin tức, không có sự kiện doanh nghiệp, không có công bố thông tin,
không có thay đổi quy định, và không có bất cứ điều gì định tính. Cho những thứ
đó, web không phải phương án dự phòng mà là nguồn duy nhất. "Store đã trả lời
xong" chỉ đúng với những con số store có field; một câu hỏi về một mã hầu như
bao giờ cũng còn phần store không đọc được, và bỏ phần đó là trả lời thiếu chứ
không phải trả lời gọn.

Nên với một mã: đọc field trước, rồi tra web cho phần chuyển động gần đây mà
không con số nào giải thích được — vì sao nó chạy, có tin gì, sắp có sự kiện gì.
Hai việc đó không thay thế nhau.

Khi câu trả lời là một board, dựng nó theo bảy bước sau.

Một, trước hết xem câu hỏi có trùng một Study có sẵn không. run_study liệt kê
sẵn từng Study cùng dạng board của nó; một công thức đã được kiểm luôn hơn một
dàn bài dựng tại chỗ.

Hai, chọn dạng board theo dạng câu hỏi: một mã một lúc là profile, nhiều mã đặt
cạnh nhau là compare, lọc cả thị trường là screen, diễn biến qua thời gian là
timeline, tách một tổng thành các phần là decompose.

Ba, phát các truy vấn độc lập trong cùng một round. Các mã, các kỳ và các bảng
không phụ thuộc kết quả của nhau thì đi cùng nhau.

Bốn, tính một lần cho mọi tỉ số. Một compute nhận tới sáu frame, nên tăng
trưởng, tỉ trọng và xếp hạng của cùng một câu hỏi thuộc về cùng một phép tính.

Năm, KPI trước, hình sau, mỗi mục nhiều nhất một chú thích. Dải KPI là câu trả
lời; các hình là lý do tin nó.

Sáu, so sánh từ hai mã trở lên thì đi qua compare_fields rồi để board vẽ bảng
đối chiếu — nó tự đánh dấu mã thắng theo từng ô, theo hướng tốt mà chính field
khai.

Bảy, con số store không có thì fetch_url rồi frame_from_evidence; chỉ những dòng
thật sự có mặt trên trang mới lên được board.
""".strip(),
)


PACK = DomainPack(
    name="vn-equity",
    version=VERSION,
    # The two bundles that read this system's own store. ``web`` and ``memory``
    # are not here: they answer questions about anything, so they are core and
    # live in ``toolsets.CORE_TOOLSETS``.
    toolsets=("signals", "studies"),
    universe=build_universe,
    study_names=STUDY_NAMES,
    # Declared from the enum, not copied out of it. Copying would create a third
    # list to keep in step with the two that already exist — the English
    # sentences in ``alpha/reasons.py`` and the Vietnamese ones the web app
    # holds — which is the drift this declaration exists to make visible, not to
    # add to. What the pack asserts is that these codes are *its* vocabulary;
    # what ``test_agent_domain_pack`` asserts is that every one of them has a
    # sentence on both sides.
    refusal_vocabulary=frozenset(issue.value for issue in SignalIssue),
    # In prompt order, and the order is the one the core used to hold them in:
    # what can be read comes before what to do with it.
    prompt_sections=(STORE, PLAYBOOK),
)

__all__ = ["PACK", "PLAYBOOK", "STORE", "STUDY_NAMES", "VERSION"]
