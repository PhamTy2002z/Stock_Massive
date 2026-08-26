"use client";

/**
 * VARIANT A — "Bản tin sáng".
 *
 * Một cột đọc, câu chuyện dẫn trước, số liệu theo sau. Thẻ đóng chỉ trả lời
 * hai câu: chuyện gì, và nó dính tới ai trong danh mục. Cơ chế, bảng phơi
 * nhiễm và điều kiện bác bỏ chỉ hiện khi bấm mở.
 */

import { useState } from "react";
import { CARDS, PORTFOLIO, CALENDAR, type Card, type Evidence } from "./mock-data";
import { EvidenceDrawer, PortfolioSheet, BriefSheet, Fig, Term } from "./shared";

export default function VariantA() {
  const [hasPortfolio, setHasPortfolio] = useState(false);
  const [editing, setEditing] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [ev, setEv] = useState<Evidence | null>(null);
  const [brief, setBrief] = useState<Card | null>(null);

  return (
    <div className="min-h-screen bg-surface-ground text-ink-2 antialiased">
      <div className="mx-auto max-w-[760px] px-5 pb-28 pt-12 sm:px-8 sm:pb-32 sm:pt-16">

        {/* ── Mở đầu: một câu, đọc là hiểu ─────────────────────────── */}
        <header>
          <p className="text-meta text-ink-5">Thứ tư, 26 tháng 8</p>
          <h1 className="mt-3 text-[1.75rem] font-medium leading-[1.15] tracking-tight text-ink-1 sm:text-[2rem]">
            Thanh khoản thắt lại,<br />chi phí vốn ngân hàng đang lên
          </h1>
          <p className="mt-5 max-w-[58ch] text-[1.0625rem] leading-relaxed text-ink-3">
            Hai thay đổi đáng chú ý kể từ lần bạn xem.{" "}
            {hasPortfolio
              ? "Cả hai đều chạm tới danh mục của bạn."
              : "Thêm danh mục để biết vị thế nào của bạn bị ảnh hưởng."}
          </p>

          {!hasPortfolio && (
            <button
              onClick={() => setEditing(true)}
              className="mt-7 rounded-md bg-primary px-5 py-3 text-control font-medium text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-ground"
            >
              Thêm danh mục của bạn
            </button>
          )}
        </header>

        {hasPortfolio && <PortfolioStrip onEdit={() => setEditing(true)} />}

        {/* ── Thẻ ──────────────────────────────────────────────────── */}
        <section className="mt-14 space-y-5">
          {CARDS.map((c) => (
            <CardBlock
              key={c.id}
              card={c}
              hasPortfolio={hasPortfolio}
              expanded={open === c.id}
              onToggle={() => setOpen(open === c.id ? null : c.id)}
              onEvidence={setEv}
              onBrief={() => setBrief(c)}
            />
          ))}
        </section>

        {/* ── Sắp tới ──────────────────────────────────────────────── */}
        <section className="mt-16 border-t border-white/8 pt-10">
          <h2 className="text-lg text-ink-1">Sắp tới</h2>
          <p className="mt-2 text-row text-ink-5">
            Những mốc này sẽ chấm điểm các luận điểm ở trên.
          </p>
          <ul className="mt-6 space-y-4">
            {CALENDAR.map((c) => (
              <li key={c.date} className="flex items-baseline gap-5">
                <span className="w-[86px] shrink-0 font-mono text-meta tabular-nums text-ink-5">{c.date}</span>
                <span className="text-row text-ink-3">{c.label}</span>
                {c.cards && (
                  <span className="ml-auto shrink-0 text-meta text-primary">
                    chấm {c.cards} luận điểm
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>

        {/* ── Hỏi thêm: cuối trang, sau khi đã đọc ─────────────────── */}
        <section className="mt-16 border-t border-white/8 pt-10">
          <h2 className="text-lg text-ink-1">Còn thắc mắc gì?</h2>
          <div className="mt-5 flex flex-wrap gap-2.5">
            {["Giải thích cơ chế này kỹ hơn", "So sánh CASA của MBB và TCB", "Nếu CASA tăng thì sao?"].map((s) => (
              <button
                key={s}
                className="rounded-pill border border-white/12 px-4 py-2 text-control text-ink-3 transition-colors hover:border-white/25 hover:text-ink-1"
              >
                {s}
              </button>
            ))}
          </div>
        </section>
      </div>

      {editing && (
        <PortfolioSheet
          onDone={() => { setHasPortfolio(true); setEditing(false); }}
          onCancel={() => setEditing(false)}
        />
      )}
      <EvidenceDrawer ev={ev} onClose={() => setEv(null)} />
      {brief && <BriefSheet card={brief} onClose={() => setBrief(null)} />}
    </div>
  );
}

function PortfolioStrip({ onEdit }: { onEdit: () => void }) {
  return (
    <div className="mt-9 flex items-center gap-5 rounded-card bg-surface-raised px-6 py-4">
      <div className="flex flex-1 items-center gap-5">
        {PORTFOLIO.filter((p) => p.ticker !== "Khác").map((p) => (
          <div key={p.ticker}>
            <div className="font-mono text-row text-ink-2">{p.ticker}</div>
            <div className="mt-1 font-mono text-meta tabular-nums text-ink-5">{p.weight}%</div>
          </div>
        ))}
      </div>
      <button onClick={onEdit} className="text-meta text-ink-5 transition-colors hover:text-ink-2">
        Sửa
      </button>
    </div>
  );
}

function CardBlock({
  card, hasPortfolio, expanded, onToggle, onEvidence, onBrief,
}: {
  card: Card; hasPortfolio: boolean; expanded: boolean;
  onToggle: () => void; onEvidence: (e: Evidence) => void; onBrief: () => void;
}) {
  const delta = card.confidence - card.confidencePrev;

  return (
    <article className="overflow-hidden rounded-card bg-surface-raised">
      {/* Đóng: chỉ hai câu và một con số */}
      <button
        onClick={onToggle}
        aria-expanded={expanded}
        className="block w-full px-5 py-6 text-left sm:px-7 sm:py-7 transition-colors hover:bg-white/[0.015] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/50"
      >
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between sm:gap-8">
          <div className="min-w-0">
            <h2 className="text-[1.375rem] font-medium leading-snug tracking-tight text-ink-1">
              {card.title}
            </h2>
            <p className="mt-3.5 max-w-[54ch] text-row leading-relaxed text-ink-3">
              {card.plainSummary}
            </p>
            {hasPortfolio && (
              <p className="mt-4 max-w-[54ch] text-row leading-relaxed text-ink-2">
                {card.plainWho}
              </p>
            )}
          </div>

          <div className="shrink-0 sm:text-right">
            <div className="font-mono text-[2rem] leading-none tabular-nums text-ink-1">
              {card.confidence}%
            </div>
            <div className="mt-2 text-meta text-ink-5">khả năng đúng</div>
            <div className={`mt-1 text-meta tabular-nums ${delta > 0 ? "text-positive" : "text-caution"}`}>
              {delta > 0 ? "+" : ""}{delta} điểm tuần này
            </div>
          </div>
        </div>

        <div className="mt-7 flex items-center gap-3 text-meta text-ink-5">
          <span>Kiểm chứng {card.verification.expectedAt} · {card.verification.source}</span>
          <span className="ml-auto text-ink-4">{expanded ? "Thu gọn ↑" : "Xem cơ chế và bằng chứng ↓"}</span>
        </div>
      </button>

      {/* Mở: cơ chế, bảng, điều kiện bác bỏ */}
      {expanded && (
        <div className="border-t border-white/8 px-5 pb-6 pt-7 sm:px-7 sm:pb-7 sm:pt-8">

          <Block title="Chuỗi tác động">
            <ol className="space-y-2.5">
              {card.mechanism.chain.map((n, i) => (
                <li key={n} className="flex items-baseline gap-4 text-row text-ink-2">
                  <span className="w-4 shrink-0 font-mono text-meta tabular-nums text-ink-6">{i + 1}</span>
                  <span>{n}</span>
                </li>
              ))}
            </ol>
            <p className="mt-5 max-w-[56ch] text-row leading-relaxed text-ink-5">
              Chuỗi này chỉ chạy khi ngân hàng phụ thuộc <Term>huy động bán buôn</Term> trên 15%
              và <Term>CASA</Term> không đủ bù.
            </p>
          </Block>

          <Block title="Ai chịu ảnh hưởng">
            <div className="space-y-px overflow-hidden rounded-md">
              {card.exposures.map((e) => (
                <div
                  key={e.ticker}
                  className="flex items-center gap-5 bg-surface-sunken px-5 py-3.5 text-row"
                >
                  <span className="w-12 shrink-0 font-mono text-ink-1">{e.ticker}</span>
                  <span className="w-[10.5rem] shrink-0 text-ink-4">
                    {e.wholesale !== null ? <>bán buôn {e.wholesale}%</> : "—"}
                  </span>
                  <span className="text-ink-4">
                    {e.casa !== null ? (
                      <>CASA <Fig evidence={card.evidence[`${e.ticker}.casa`]} onOpen={onEvidence}>{e.casa}%</Fig></>
                    ) : (
                      <span className="text-ink-5">chưa có số quý này</span>
                    )}
                  </span>
                  <span className={`ml-auto shrink-0 ${sensTone(e.sensitivity)}`}>{e.sensitivity}</span>
                </div>
              ))}
            </div>
            {card.exposures.some((e) => e.casa === null) && (
              <p className="mt-4 max-w-[56ch] text-row leading-relaxed text-ink-5">
                ACB chưa công bố số liệu cần thiết cho quý này. Hệ thống để trống thay vì ước lượng.
              </p>
            )}
          </Block>

          <Block title="Điều gì có thể làm luận điểm này sai">
            <ol className="max-w-[56ch] space-y-2.5">
              {card.counterforces.map((c, i) => (
                <li key={c} className="flex gap-4 text-row leading-relaxed text-ink-3">
                  <span className="w-3 shrink-0 font-mono text-meta tabular-nums text-ink-6">{i + 1}</span>
                  <span>{c}</span>
                </li>
              ))}
            </ol>
          </Block>

          <div className="mt-9 rounded-card bg-surface-sunken px-6 py-5">
            <p className="text-row text-ink-1">
              Ngày {card.verification.expectedAt}, {card.verification.source} sẽ quyết định luận điểm này đúng hay sai.
            </p>
            <dl className="mt-4 space-y-2.5 text-row">
              <div className="flex gap-4">
                <dt className="w-[5.5rem] shrink-0 text-positive">Đúng nếu</dt>
                <dd className="text-ink-3">{card.verification.confirmIf}</dd>
              </div>
              <div className="flex gap-4">
                <dt className="w-[5.5rem] shrink-0 text-negative">Sai nếu</dt>
                <dd className="text-ink-3">{card.verification.refuteIf}</dd>
              </div>
            </dl>
            <p className="mt-4 text-meta text-ink-5">
              Hai điều kiện này viết ngày {card.verification.writtenAt} và không sửa được nữa.
            </p>
          </div>

          <div className="mt-8 flex items-center gap-5 border-t border-white/8 pt-6">
            <p className="text-meta text-ink-5">
              Cơ chế này đã được kiểm {card.edge.checked} lần, đúng {card.edge.right}.
            </p>
            <button
              onClick={onBrief}
              className="ml-auto rounded-md bg-primary px-5 py-2.5 text-control font-medium text-primary-foreground transition-opacity hover:opacity-90"
            >
              Soạn bản tin gửi khách
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-9 last:mb-0">
      <h3 className="mb-4 text-control font-medium text-ink-1">{title}</h3>
      {children}
    </div>
  );
}

export function sensTone(s: string) {
  if (s === "nhạy nhất") return "text-negative";
  if (s === "trung tính") return "text-caution";
  if (s === "được che") return "text-positive";
  return "text-ink-5";
}
