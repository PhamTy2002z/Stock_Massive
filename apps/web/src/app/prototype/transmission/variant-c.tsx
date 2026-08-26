"use client";

/**
 * VARIANT C — "Sổ thành tích".
 *
 * Mở đầu bằng thành tích, không bằng tin tức: hệ thống đã đoán bao nhiêu lần,
 * đúng mấy lần, và lần sai thì sai vì sao. Luận điểm đang mở nằm sau đó.
 */

import { useState } from "react";
import { CARDS, RESOLVED, CALENDAR, type Card, type Evidence } from "./mock-data";
import { EvidenceDrawer, BriefSheet, Fig, Term } from "./shared";
import { sensTone } from "./variant-a";

export default function VariantC() {
  const [sel, setSel] = useState<Card | null>(null);
  const [ev, setEv] = useState<Evidence | null>(null);
  const [brief, setBrief] = useState<Card | null>(null);

  return (
    <div className="min-h-screen bg-surface-ground text-ink-2 antialiased">
      <div className="mx-auto max-w-[820px] px-5 pb-28 pt-12 sm:px-8 sm:pb-32 sm:pt-16">

        <header className="max-w-[60ch]">
          <p className="text-meta text-ink-5">Cập nhật 26 tháng 8, 2026</p>
          <h1 className="mt-3 text-[1.75rem] font-medium leading-[1.15] tracking-tight text-ink-1 sm:text-[2rem]">
            Hệ thống này đã đúng 6 trên 9 lần
          </h1>
          <p className="mt-5 text-[1.0625rem] leading-relaxed text-ink-3">
            Mỗi luận điểm đều kèm điều kiện bác bỏ, viết trước ngày số liệu ra và không sửa được nữa.
            Dưới đây là toàn bộ, kể cả những lần sai.
          </p>
        </header>

        {/* ── Đã chấm ─────────────────────────────────────────────── */}
        <section className="mt-14">
          <h2 className="text-lg text-ink-1">Đã chấm</h2>
          <div className="mt-6 space-y-2.5">
            {RESOLVED.map((r) => {
              const verdict =
                r.outcome === "confirmed" ? ["Đúng", "text-positive"] :
                r.outcome === "invalidated" ? ["Sai", "text-negative"] :
                ["Đã đóng", "text-ink-5"];
              return (
                <div key={r.id} className="rounded-card bg-surface-raised px-5 py-5 sm:px-7 sm:py-6">
                  <div className="flex items-baseline justify-between gap-6">
                    <h3 className="text-[1.0625rem] leading-snug text-ink-1">{r.title}</h3>
                    <span className={`shrink-0 text-row ${verdict[1]}`}>{verdict[0]}</span>
                  </div>
                  <p className="mt-3.5 max-w-[58ch] text-row leading-relaxed text-ink-3">{r.reason}</p>
                  <p className="mt-4 text-meta text-ink-5">
                    Viết {r.writtenAt}, {r.outcome === "closed" ? "đóng" : "chấm"} {r.resolvedAt}. Độ tin của cơ chế{" "}
                    <span className="font-mono tabular-nums text-ink-4">{r.edgeBefore}%</span>
                    {" → "}
                    <span className={`font-mono tabular-nums ${r.edgeAfter >= r.edgeBefore ? "text-positive" : "text-negative"}`}>
                      {r.edgeAfter === 0 ? "đã đóng" : `${r.edgeAfter}%`}
                    </span>
                  </p>
                </div>
              );
            })}
          </div>

          <p className="mt-6 max-w-[62ch] text-row leading-relaxed text-ink-5">
            Luận điểm thứ ba đã đóng hẳn: không ngân hàng nào công bố hạn mức tín dụng được cấp,
            nên không có cách nào chấm nó đúng hay sai. Một cơ chế không thể sai thì không có giá trị.
          </p>
        </section>

        {/* ── Đang mở ─────────────────────────────────────────────── */}
        <section className="mt-16 border-t border-white/8 pt-10">
          <h2 className="text-lg text-ink-1">Đang chờ chấm</h2>
          <div className="mt-6 space-y-2.5">
            {CARDS.map((c) => {
              const active = sel?.id === c.id;
              return (
                <div key={c.id} className={`overflow-hidden rounded-card ${active ? "bg-surface-bubble" : "bg-surface-raised"}`}>
                  <button
                    onClick={() => setSel(active ? null : c)}
                    className="block w-full px-5 py-5 text-left sm:px-7 sm:py-6 transition-colors hover:bg-white/[0.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/50"
                  >
                    <div className="flex items-baseline justify-between gap-8">
                      <h3 className="text-[1.0625rem] leading-snug text-ink-1">{c.title}</h3>
                      <span className="shrink-0 font-mono text-[1.25rem] tabular-nums text-ink-1">{c.confidence}%</span>
                    </div>
                    <p className="mt-3.5 max-w-[58ch] text-row leading-relaxed text-ink-3">{c.plainSummary}</p>
                    <p className="mt-4 text-meta text-ink-5">
                      Sẽ chấm {c.verification.expectedAt} theo {c.verification.source} ·{" "}
                      cơ chế đã kiểm {c.edge.checked} lần, đúng {c.edge.right}
                    </p>
                  </button>

                  {active && (
                    <div className="border-t border-white/8 px-5 pb-6 pt-6 sm:px-7 sm:pb-7 sm:pt-7">
                      <h4 className="mb-4 text-control font-medium text-ink-1">Điều kiện đã khoá</h4>
                      <dl className="space-y-2.5 text-row">
                        <div className="flex gap-4">
                          <dt className="w-[4.5rem] shrink-0 text-positive">Đúng nếu</dt>
                          <dd className="text-ink-3">{c.verification.confirmIf}</dd>
                        </div>
                        <div className="flex gap-4">
                          <dt className="w-[4.5rem] shrink-0 text-negative">Sai nếu</dt>
                          <dd className="text-ink-3">{c.verification.refuteIf}</dd>
                        </div>
                      </dl>
                      <p className="mt-3.5 text-meta text-ink-5">Viết ngày {c.verification.writtenAt}.</p>

                      <h4 className="mb-4 mt-8 text-control font-medium text-ink-1">Vị thế liên quan</h4>
                      <div className="space-y-3">
                        {c.exposures.map((e) => (
                          <div key={e.ticker} className="flex items-baseline gap-5 text-row">
                            <span className="w-12 shrink-0 font-mono text-ink-1">{e.ticker}</span>
                            <span className="text-ink-4">
                              {e.casa !== null ? (
                                <><Term>CASA</Term>{" "}
                                  <Fig evidence={c.evidence[`${e.ticker}.casa`]} onOpen={setEv}>{e.casa}%</Fig>
                                </>
                              ) : <span className="text-ink-5">chưa có số quý này</span>}
                            </span>
                            <span className={`ml-auto ${sensTone(e.sensitivity)}`}>{e.sensitivity}</span>
                          </div>
                        ))}
                      </div>

                      <button
                        onClick={() => setBrief(c)}
                        className="mt-8 rounded-md bg-primary px-5 py-2.5 text-control font-medium text-primary-foreground transition-opacity hover:opacity-90"
                      >
                        Soạn bản tin gửi khách
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* ── Lịch ────────────────────────────────────────────────── */}
        <section className="mt-16 border-t border-white/8 pt-10">
          <h2 className="text-lg text-ink-1">Lịch chấm điểm</h2>
          <ul className="mt-6 space-y-4">
            {CALENDAR.map((c) => (
              <li key={c.date} className="flex items-baseline gap-5">
                <span className="w-[86px] shrink-0 font-mono text-meta tabular-nums text-ink-5">{c.date}</span>
                <span className="text-row text-ink-3">{c.label}</span>
                {c.cards && <span className="ml-auto shrink-0 text-meta text-primary">chấm {c.cards} luận điểm</span>}
              </li>
            ))}
          </ul>
        </section>
      </div>

      <EvidenceDrawer ev={ev} onClose={() => setEv(null)} />
      {brief && <BriefSheet card={brief} onClose={() => setBrief(null)} />}
    </div>
  );
}
