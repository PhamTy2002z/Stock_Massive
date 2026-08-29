"""Real document formats produce bounded excerpts with exact provenance."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

import pytest
from openpyxl import Workbook
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from src.agent.evidence import EvidenceKind
from src.agent.evidence.documents import (
    DOCX_MEDIA_TYPE,
    PDF_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
    DocumentParseError,
    DocumentQuotas,
    parse_document,
)


OBSERVED_AT = datetime(2026, 8, 29, 9, 0, tzinfo=UTC)


def _pdf_bytes(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(
        f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    )
    page.replace_contents(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _xlsx_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "KQKD"
    sheet.append(["Năm", "Doanh thu", "Tăng trưởng"])
    sheet.append([2026, 1250, "12.5%"])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _docx_bytes() -> bytes:
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Kết quả</w:t></w:r></w:p>
    <w:p><w:r><w:t>Doanh thu tăng 12,5%.</w:t></w:r></w:p>
    <w:tbl><w:tr>
      <w:tc><w:p><w:r><w:t>FPT</w:t></w:r></w:p></w:tc>
      <w:tc><w:p><w:r><w:t>125.000</w:t></w:r></w:p></w:tc>
    </w:tr></w:tbl>
    <w:sectPr/>
  </w:body>
</w:document>"""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)
    return output.getvalue()


def test_pdf_extracts_page_provenance_and_sanitizes_the_filename():
    parsed = parse_document(
        content=_pdf_bytes("Revenue 2026: 12.5 percent"),
        media_type=PDF_MEDIA_TYPE,
        filename="../../quarterly-report.pdf",
        observed_at=OBSERVED_AT,
    )

    assert parsed.filename == "quarterly-report.pdf"
    assert parsed.truncated is False
    assert len(parsed.evidence) == 1
    page = parsed.evidence[0]
    assert page.kind is EvidenceKind.DOCUMENT_PAGE
    assert page.location is not None and page.location.page == 1
    assert page.excerpt == "Revenue 2026: 12.5 percent"
    assert page.observed_at == OBSERVED_AT

    windows_path = parse_document(
        content=_pdf_bytes("Revenue 2026"),
        media_type=PDF_MEDIA_TYPE,
        filename=r"C:\\uploads\\quarterly-report.pdf",
        observed_at=OBSERVED_AT,
    )
    assert windows_path.filename == "quarterly-report.pdf"


def test_xlsx_extracts_each_populated_row_with_sheet_and_cell_range():
    parsed = parse_document(
        content=_xlsx_bytes(),
        media_type=XLSX_MEDIA_TYPE,
        filename="financials.xlsx",
        observed_at=OBSERVED_AT,
    )

    assert [item.location.cell_range for item in parsed.evidence if item.location] == [
        "A1:C1",
        "A2:C2",
    ]
    assert all(
        item.location is not None and item.location.sheet == "KQKD"
        for item in parsed.evidence
    )
    assert parsed.evidence[1].excerpt == "A2=2026 | B2=1250 | C2=12.5%"


def test_docx_uses_heading_sections_and_table_row_coordinates():
    parsed = parse_document(
        content=_docx_bytes(),
        media_type=DOCX_MEDIA_TYPE,
        filename="analysis.docx",
        observed_at=OBSERVED_AT,
    )

    paragraph, table_row = parsed.evidence
    assert paragraph.kind is EvidenceKind.DOCUMENT_SECTION
    assert paragraph.location is not None
    assert paragraph.location.section == "Kết quả"
    assert paragraph.location.block == 1
    assert table_row.kind is EvidenceKind.DOCUMENT_CELL_RANGE
    assert table_row.location is not None
    assert table_row.location.sheet == "Table 1"
    assert table_row.location.cell_range == "R1C1:R1C2"
    assert table_row.excerpt == "C1=FPT | C2=125.000"


def test_parser_marks_quota_truncation_instead_of_reading_unbounded_rows():
    parsed = parse_document(
        content=_xlsx_bytes(),
        media_type=XLSX_MEDIA_TYPE,
        filename="financials.xlsx",
        quotas=DocumentQuotas(max_rows_per_sheet=1),
        observed_at=OBSERVED_AT,
    )

    assert parsed.truncated is True
    assert len(parsed.evidence) == 1
    assert "row quota" in parsed.warnings[0]


def test_parser_rejects_unsupported_empty_and_oversized_inputs():
    with pytest.raises(DocumentParseError) as unsupported:
        parse_document(
            content=b"text",
            media_type="text/plain",
            filename="note.txt",
        )
    assert unsupported.value.code == "unsupported_media_type"

    with pytest.raises(DocumentParseError) as empty:
        parse_document(content=b"", media_type=PDF_MEDIA_TYPE, filename="empty.pdf")
    assert empty.value.code == "empty_document"

    with pytest.raises(DocumentParseError) as oversized:
        parse_document(
            content=b"12",
            media_type=PDF_MEDIA_TYPE,
            filename="large.pdf",
            quotas=DocumentQuotas(max_input_bytes=1),
        )
    assert oversized.value.code == "input_too_large"


def test_docx_zip_bomb_guard_runs_before_xml_parsing():
    content = _docx_bytes()
    with pytest.raises(DocumentParseError) as too_large:
        parse_document(
            content=content,
            media_type=DOCX_MEDIA_TYPE,
            filename="analysis.docx",
            quotas=DocumentQuotas(max_zip_uncompressed_bytes=10),
        )
    assert too_large.value.code == "archive_too_large"
