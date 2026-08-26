"use client";

/** PROTOTYPE — throwaway. Thanh đổi variant, không thuộc thiết kế đang đánh giá. */

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export const VARIANTS = [
  { key: "A", name: "Bản tin sáng" },
  { key: "B", name: "Theo vị thế" },
  { key: "C", name: "Sổ thành tích" },
] as const;

export function VariantSwitcher({ current }: { current: string }) {
  const router = useRouter();
  const params = useSearchParams();

  const go = (delta: number) => {
    const i = VARIANTS.findIndex((v) => v.key === current);
    const next = VARIANTS[(i + delta + VARIANTS.length) % VARIANTS.length];
    const p = new URLSearchParams(params.toString());
    p.set("variant", next.key);
    router.replace(`?${p.toString()}`);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = document.activeElement;
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return;
      if (el instanceof HTMLElement && el.isContentEditable) return;
      if (e.key === "ArrowLeft") go(-1);
      if (e.key === "ArrowRight") go(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (process.env.NODE_ENV === "production") return null;

  const cur = VARIANTS.find((v) => v.key === current) ?? VARIANTS[0];

  return (
    <div className="fixed bottom-5 left-1/2 z-[100] -translate-x-1/2">
      <div className="flex items-center gap-1 rounded-full border border-white/15 bg-black/85 px-2 py-1.5 shadow-2xl backdrop-blur">
        <button onClick={() => go(-1)} className="h-7 w-7 rounded-full text-white/70 hover:bg-white/10 hover:text-white">←</button>
        <span className="whitespace-nowrap px-3 font-mono text-xs tracking-wide text-white">
          {cur.key} — {cur.name}
        </span>
        <button onClick={() => go(1)} className="h-7 w-7 rounded-full text-white/70 hover:bg-white/10 hover:text-white">→</button>
        <span className="ml-1 hidden border-l border-white/15 pl-2 pr-1 text-[10px] uppercase tracking-widest text-white/40 sm:block">
          prototype
        </span>
      </div>
    </div>
  );
}
