"use client";

/**
 * VARIANT B — "Theo vị thế".
 *
 * Danh mục là trục chính: MỘT hàng cho mỗi mã, không phải một hàng cho mỗi
 * cặp mã × cơ chế. Hàng nói mức ảnh hưởng nặng nhất và có mấy cơ chế đang
 * chạm tới. Chi tiết mở ra bên cạnh trên màn rộng, mở xuống dưới trên điện thoại.
 */

import { useState } from "react";
import { CARDS, PORTFOLIO, type Card, type Evidence } from "./mock-data";
import { EvidenceDrawer, PortfolioSheet, BriefSheet, Fig, Term } from "./shared";
import { sensTone } from "./variant-a";

const RANK: Record<string, number> = {
  "nhạy nhất": 0, "trung tính": 1, "không rõ": 2, "được che": 3, "ít ảnh hưởng": 4,
};

type Hit = { card: Card; sensitivity: string; casa: number | null; wholesale: number | null; impactBps: [number, number] | null };
type Position = { ticker: string; weight: number; hits: Hit[]; worst: string };

function buildPositions(): Position[] {
  const out: Position[] = [];
  for (const p of PORTFOLIO) {
    if (p.ticker === "Khác") continue;
    const hits: Hit[] = [];
    for (const card of CARDS) {
      const e = card.exposures.find((x) => x.ticker === p.ticker);
      if (e) hits.push({ card, sensitivity: e.sensitivity, casa: e.casa, wholesale: e.wholesale, impactBps: e.impactBps });
    }
    if (!hits.length) continue;
    hits.sort((a, b) => (RANK[a.sensitivity] ?? 9) - (RANK[b.sensitivity] ?? 9));
    out.push({ ticker: p.ticker, weight: p.weight, hits, worst: hits[0].sensitivity });
  }
  return out.sort((a, b) => (RANK[a.worst] ?? 9) - (RANK[b.worst] ?? 9) || b.weight - a.weight);
}

export default function VariantB() {
  const [editing, setEditing] = useState(false);
  const [sel, setSel] = useState<string | null>(null);
  const [ev, setEv] = useState<Evidence | null>(null);
  const [brief, setBrief] = useState<Card | null>(null);

  const positions = buildPositions();
  const hot = positions.filter((p) => p.worst === "nhạy nhất");
  const selected = positions.find((p) => p.ticker === sel) ?? null;

  return (
    <div className="min-h-screen bg-surface-ground text-ink-2 antialiased">
      <div className="lg:flex">
        <main className="min-w-0 flex-1 px-5 pb-28 pt-12 sm:px-8 lg:px-10 lg:pt-14">
          <header className="max-w-[58ch]">
            <p className="text-meta text-ink-5">Thứ tư, 26 tháng 8</p>
            <h1 className="mt-3 text-[1.75rem] font-medium leading-[1.15] tracking-tight text-ink-1 sm:text-[2rem]">
              Danh mục của bạn đang chịu gì
            </h1>
            <p className="mt-5 text-[1.0625rem] leading-relaxed text-ink-3">
              {hot.length === 0
                ? "Không vị thế nào chịu ảnh hưởng rõ lúc này."
                : `${hot.length} trên ${positions.length} vị thế chịu ảnh hưởng rõ từ những thay đổi vĩ mô đang diễn ra.`}{" "}
              Bấm một mã để xem cơ chế và bằng chứng.
            </p>
            <button
              onClick={() => setEditing(true)}
              className="mt-6 rounded-sm text-control text-ink-4 underline decoration-ink-6 decoration-dotted underline-offset-4 transition-colors hover:text-ink-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
            >
              Sửa danh mục
            </button>
          </header>

          <div className="mt-11 overflow-hidden rounded-card">
            {positions.map((p, i) => {
              const active = sel === p.ticker;
              return (
                <div key={p.ticker}>
                  <button
                    onClick={() => setSel(active ? null : p.ticker)}
                    aria-expanded={active}
                    className={`block w-full px-5 py-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/50 sm:px-6 sm:py-5 ${
                      active ? "bg-surface-bubble" : "bg-surface-raised hover:bg-white/[0.035]"
                    } ${i > 0 ? "border-t border-white/[0.06]" : ""}`}
                  >
                    <div className="flex items-baseline gap-4 sm:gap-6">
                      <span className="w-[3.25rem] shrink-0 font-mono text-[1.1875rem] text-ink-1">{p.ticker}</span>
                      <span className="w-11 shrink-0 font-mono text-meta tabular-nums text-ink-5">{p.weight}%</span>
                      <span className={`w-[6.5rem] shrink-0 text-row ${sensTone(p.worst)}`}>{p.worst}</span>
                      <span className="min-w-0 flex-1 truncate text-row text-ink-4">
                        {p.hits.length === 1
                          ? p.hits[0].card.title
                          : `${p.hits.length} cơ chế đang chạm tới`}
                      </span>
                      <span className="hidden shrink-0 text-meta text-ink-5 sm:block">{active ? "↑" : "↓"}</span>
                    </div>
                  </button>

                  {/* Trên điện thoại chi tiết mở ngay dưới hàng */}
                  {active && selected && (
                    <div className="bg-surface-bubble px-5 pb-7 sm:px-6 lg:hidden">
                      <Detail position={selected} onEvidence={setEv} onBrief={setBrief} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <p className="mt-8 max-w-[58ch] text-row leading-relaxed text-ink-5">
            Xếp theo mức ảnh hưởng nặng nhất, rồi tới tỷ trọng. Mã nào không xuất hiện nghĩa là
            chưa cơ chế nào chạm tới nó theo điều kiện kích hoạt hiện tại.
          </p>
        </main>

        {/* Trên màn rộng chi tiết nằm cạnh */}
        <aside className="sticky top-0 hidden h-screen w-[400px] shrink-0 overflow-y-auto border-l border-white/8 bg-surface-panel lg:block xl:w-[440px]">
          {selected ? (
            <>
              <header className="flex items-start justify-between gap-4 px-8 pb-6 pt-9">
                <div>
                  <div className="font-mono text-[1.75rem] leading-none text-ink-1">{selected.ticker}</div>
                  <p className="mt-2.5 text-row text-ink-5">{selected.weight}% danh mục</p>
                </div>
                <button onClick={() => setSel(null)} aria-label="Đóng" className="-mr-2 rounded-md p-2 text-ink-5 hover:bg-white/5 hover:text-ink-1">✕</button>
              </header>
              <div className="px-8 pb-10">
                <Detail position={selected} onEvidence={setEv} onBrief={setBrief} />
              </div>
            </>
          ) : (
            <div className="flex h-full items-center px-8">
              <p className="text-row leading-relaxed text-ink-5">
                Chọn một mã để xem vì sao nó được xếp vào mức đó, và dữ kiện nào
                sắp tới sẽ xác nhận hay bác bỏ.
              </p>
            </div>
          )}
        </aside>
      </div>

      {editing && <PortfolioSheet onDone={() => setEditing(false)} onCancel={() => setEditing(false)} />}
      <EvidenceDrawer ev={ev} onClose={() => setEv(null)} />
      {brief && <BriefSheet card={brief} onClose={() => setBrief(null)} />}
    </div>
  );
}

function Detail({
  position, onEvidence, onBrief,
}: { position: Position; onEvidence: (e: Evidence) => void; onBrief: (c: Card) => void }) {
  return (
    <div className="space-y-8">
      {position.hits.map((h) => (
        <section key={h.card.id}>
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="text-[1.0625rem] leading-snug text-ink-1">{h.card.title}</h3>
            <span className={`shrink-0 text-row ${sensTone(h.sensitivity)}`}>{h.sensitivity}</span>
          </div>

          <p className="mt-3 text-row leading-relaxed text-ink-3">{h.card.plainSummary}</p>

          <dl className="mt-5 space-y-2.5 text-row">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-5">Huy động bán buôn</dt>
              <dd className="font-mono tabular-nums text-ink-2">{h.wholesale !== null ? `${h.wholesale}%` : "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-5"><Term>CASA</Term></dt>
              <dd>
                {h.casa !== null
                  ? <Fig evidence={h.card.evidence[`${position.ticker}.casa`]} onOpen={onEvidence}>{h.casa}%</Fig>
                  : <span className="text-ink-5">chưa có số quý này</span>}
              </dd>
            </div>
            {h.impactBps && (
              <div className="flex justify-between gap-4">
                <dt className="text-ink-5">Ước tính tác động</dt>
                <dd className="font-mono tabular-nums text-ink-2">{h.impactBps[0]}…{h.impactBps[1]} <Term>bps</Term></dd>
              </div>
            )}
          </dl>

          <div className="mt-5 rounded-card bg-surface-sunken px-5 py-4">
            <p className="text-row text-ink-1">{h.card.verification.source}, {h.card.verification.expectedAt}</p>
            <dl className="mt-3.5 space-y-2.5 text-row">
              <div className="flex gap-4">
                <dt className="w-[4.5rem] shrink-0 text-positive">Đúng nếu</dt>
                <dd className="text-ink-3">{h.card.verification.confirmIf}</dd>
              </div>
              <div className="flex gap-4">
                <dt className="w-[4.5rem] shrink-0 text-negative">Sai nếu</dt>
                <dd className="text-ink-3">{h.card.verification.refuteIf}</dd>
              </div>
            </dl>
            <p className="mt-3.5 text-meta text-ink-5">Viết ngày {h.card.verification.writtenAt}, đã khoá.</p>
          </div>

          <button
            onClick={() => onBrief(h.card)}
            className="mt-5 w-full rounded-md bg-primary py-2.5 text-control font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            Soạn bản tin gửi khách
          </button>
        </section>
      ))}
    </div>
  );
}
