"use client";

/** PROTOTYPE — throwaway. Mảnh dùng chung nhỏ nhất; layout thì không. */

import { useState } from "react";
import type { Evidence, Card } from "./mock-data";

/* Từ chuyên môn giải thích tại chỗ. Không ai phải đoán "bps" nghĩa là gì. */
const GLOSSARY: Record<string, string> = {
  CASA: "Tiền gửi không kỳ hạn / tổng tiền gửi. Càng cao thì chi phí huy động càng rẻ và càng ít chịu ảnh hưởng khi lãi suất tăng.",
  bps: "Điểm cơ bản. 100 bps = 1%.",
  NIM: "Biên lãi ròng — chênh lệch giữa lãi cho vay và chi phí huy động.",
  "huy động bán buôn": "Vốn vay từ các tổ chức tín dụng khác, thay vì tiền gửi dân cư. Đắt hơn và biến động theo thị trường liên ngân hàng.",
  Brier: "Điểm đo độ chính xác của dự báo xác suất. Càng thấp càng tốt; 0 là hoàn hảo.",
  "nợ nhóm 2": "Nợ cần chú ý — quá hạn 10–90 ngày. Chỉ báo sớm của nợ xấu.",
};

export function Term({ children }: { children: string }) {
  const note = GLOSSARY[children];
  if (!note) return <>{children}</>;
  return (
    <abbr
      title={note}
      className="cursor-help border-b border-dotted border-ink-5/50 no-underline decoration-transparent"
    >
      {children}
    </abbr>
  );
}

/* Con số click được — mọi số đều có đường về nguồn. */
export function Fig({
  children, evidence, onOpen,
}: { children: React.ReactNode; evidence?: Evidence; onOpen: (e: Evidence) => void }) {
  if (!evidence) return <span className="text-ink-5">chưa có số</span>;
  return (
    <button
      onClick={() => onOpen(evidence)}
      className="rounded-sm font-mono tabular-nums text-ink-1 underline decoration-ink-5/40 decoration-dotted underline-offset-4 transition-colors hover:decoration-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
    >
      {children}
    </button>
  );
}

export function EvidenceDrawer({ ev, onClose }: { ev: Evidence | null; onClose: () => void }) {
  if (!ev) return null;
  const tierLabel: Record<string, string> = {
    registered_field: "Tính bằng code, đã đăng ký",
    extracted_filing: "Trích từ báo cáo tài chính",
    derived: "Suy ra, chưa hiệu chuẩn",
    unknown: "Không rõ",
  };
  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-[2px]" />
      <aside
        onClick={(e) => e.stopPropagation()}
        className="relative flex h-full w-[440px] flex-col overflow-y-auto border-l border-white/10 bg-surface-panel"
      >
        <header className="flex items-start justify-between gap-4 border-b border-white/8 px-7 py-6">
          <div>
            <h2 className="text-lg leading-tight text-ink-1">{ev.label}</h2>
            <p className="mt-1.5 text-meta text-ink-5">{tierLabel[ev.tier]}</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Đóng"
            className="-mr-2 -mt-1 rounded-md p-2 text-ink-5 transition-colors hover:bg-white/5 hover:text-ink-1"
          >
            ✕
          </button>
        </header>

        <div className="px-7 py-6">
          <div className="font-mono text-[2.75rem] leading-none tabular-nums text-ink-1">{ev.value}</div>
        </div>

        {ev.formula && (
          <div className="mx-7 mb-7 rounded-card bg-surface-sunken px-5 py-4">
            <p className="text-row text-ink-3">{ev.formula}</p>
            {ev.numerator && (
              <div className="mt-3 space-y-1 font-mono text-meta tabular-nums text-ink-4">
                <div>{ev.numerator}</div>
                <div className="border-t border-white/10 pt-1">{ev.denominator}</div>
              </div>
            )}
          </div>
        )}

        <dl className="mx-7 mb-7 space-y-3.5 text-row">
          {[
            ["Tài liệu", ev.doc],
            ["Vị trí", ev.page],
            ["Kỳ báo cáo", ev.period],
            ["Doanh nghiệp công bố", ev.published],
            ["Hệ thống đọc được", ev.observed],
            ["Người review", ev.reviewed ?? "chưa có"],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between gap-6">
              <dt className="shrink-0 text-ink-5">{k}</dt>
              <dd className="text-right text-ink-2">{v}</dd>
            </div>
          ))}
        </dl>

        {ev.revisedFrom && (
          <div className="mx-7 mb-7 rounded-card border border-caution/25 bg-caution/[0.07] px-5 py-4">
            <p className="text-row text-caution">Con số này đã được đính chính</p>
            <p className="mt-2 font-mono text-meta tabular-nums text-ink-3">
              {ev.revisedFrom.value} → {ev.value}
            </p>
            <p className="mt-2.5 text-meta leading-relaxed text-ink-5">
              Hệ thống giữ cả bản cũ. Khi chấm điểm một luận điểm viết ngày {ev.revisedFrom.observed},
              nó dùng {ev.revisedFrom.value} — con số biết được lúc đó — chứ không dùng con số hôm nay.
            </p>
          </div>
        )}

        <div className="mt-auto border-t border-white/8 px-7 py-5">
          <button className="w-full rounded-md border border-white/12 py-2.5 text-control text-ink-2 transition-colors hover:border-white/25 hover:bg-white/[0.03]">
            Mở báo cáo tại {ev.page}
          </button>
        </div>
      </aside>
    </div>
  );
}

export function PortfolioSheet({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [raw, setRaw] = useState("MBB 25\nVCB 20\nTCB 15\nVPB 15\nACB 10");
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/65 p-6" onClick={onCancel}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[440px] rounded-card border border-white/10 bg-surface-raised p-7"
      >
        <h2 className="text-xl leading-tight text-ink-1">Danh mục của bạn</h2>
        <p className="mt-2.5 text-row leading-relaxed text-ink-4">
          Mỗi dòng một mã, kèm tỷ trọng. Không cần giá vốn, không cần kết nối tài khoản chứng khoán.
        </p>
        <textarea
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          rows={6}
          spellCheck={false}
          className="mt-5 w-full resize-none rounded-md border border-white/12 bg-surface-sunken px-4 py-3 font-mono text-row leading-relaxed text-ink-1 outline-none transition-colors focus:border-primary/50"
        />
        <div className="mt-6 flex items-center justify-end gap-3">
          <button onClick={onCancel} className="rounded-md px-4 py-2.5 text-control text-ink-4 transition-colors hover:text-ink-1">
            Huỷ
          </button>
          <button
            onClick={onDone}
            className="rounded-md bg-primary px-5 py-2.5 text-control font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            Lưu danh mục
          </button>
        </div>
      </div>
    </div>
  );
}

export function BriefSheet({ card, onClose }: { card: Card; onClose: () => void }) {
  const top = card.exposures[0];
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/65 p-6" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[540px] overflow-hidden rounded-card border border-white/10 bg-surface-raised"
      >
        <header className="flex items-center justify-between border-b border-white/8 px-7 py-5">
          <h2 className="text-lg text-ink-1">Bản tin gửi khách</h2>
          <button onClick={onClose} aria-label="Đóng" className="rounded-md p-1.5 text-ink-5 hover:bg-white/5 hover:text-ink-1">✕</button>
        </header>

        <div className="space-y-4 px-7 py-6 text-row leading-relaxed text-ink-2">
          <p className="text-ink-1">Cập nhật danh mục — 26/08/2026</p>
          <p>{card.plainSummary}</p>
          <p>
            Trong danh mục của anh/chị, <strong className="font-medium text-ink-1">{top.ticker}</strong>{" "}
            ({top.weight}%) là vị thế chịu ảnh hưởng rõ nhất
            {top.wholesale !== null && <>, do phụ thuộc huy động bán buôn {top.wholesale}% và CASA chỉ {top.casa}%</>}.
          </p>
          <p><span className="text-positive">Ủng hộ luận điểm:</span> {card.trigger.text}.</p>
          <p><span className="text-caution">Phản chiều:</span> {card.counterforces[0]}.</p>
          <p>Anh/chị muốn giữ tỷ trọng {top.ticker} hiện tại, hay giảm về mức trung tính ngành?</p>
          <p className="border-t border-white/8 pt-4 text-meta italic text-ink-5">
            Bản tin là phân tích dữ liệu, không phải khuyến nghị đầu tư. Mọi số liệu dẫn nguồn báo cáo đã công bố.
          </p>
        </div>

        <footer className="flex items-center justify-between border-t border-white/8 px-7 py-4">
          <span className="text-meta text-ink-5">Bạn duyệt và tự gửi. Hệ thống không gửi thay.</span>
          <div className="flex gap-2.5">
            <button className="rounded-md border border-white/12 px-4 py-2 text-control text-ink-2 hover:border-white/25">Sửa</button>
            <button className="rounded-md bg-primary px-4 py-2 text-control font-medium text-primary-foreground">Sao chép</button>
          </div>
        </footer>
      </div>
    </div>
  );
}
