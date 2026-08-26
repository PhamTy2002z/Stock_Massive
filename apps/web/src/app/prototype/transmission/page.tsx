/**
 * PROTOTYPE — throwaway, xoá sau khi chốt.
 *
 * Ba variant của Transmission Lab, đổi bằng `?variant=A|B|C`.
 * Không gọi API, không auth, không persist — mọi số là mock.
 *
 *   pnpm dev:web  →  http://localhost:3000/prototype/transmission?variant=A
 */

import { Suspense } from "react";
import { VariantSwitcher } from "./switcher";
import VariantA from "./variant-a";
import VariantB from "./variant-b";
import VariantC from "./variant-c";

export const metadata = { title: "PROTOTYPE — Transmission Lab" };

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ variant?: string }>;
}) {
  const { variant } = await searchParams;
  const v = (variant ?? "A").toUpperCase();

  return (
    <Suspense>
      {v === "B" ? <VariantB /> : v === "C" ? <VariantC /> : <VariantA />}
      <VariantSwitcher current={v} />
    </Suspense>
  );
}
