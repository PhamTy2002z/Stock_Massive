"use client"

/**
 * PROTOTYPE — throwaway. Issue #21.
 *
 * Four variants of the nightly Analysis artifact, switchable via `?variant=`,
 * each rendered inside the same fake thread. `?symbol=` swaps the fixture so the
 * per-industry emphasis question can be judged in every variant:
 *   VCB = bank (fundamental leads) · VHM = real estate (money flow leads)
 *   MWG = retail (technical leads, and one field refused by #41's seam)
 */

import { PrototypeSegments, PrototypeSwitcher } from "@/components/shared/prototype-switcher"
import { ARTIFACTS, SYMBOLS } from "./fixtures"
import { ThreadShell } from "./thread-shell"
import { VARIANT_A_NAME, VariantA } from "./variant-a"
import { VARIANT_B_NAME, VariantB } from "./variant-b"
import { VARIANT_C_NAME, VariantC } from "./variant-c"
import { VARIANT_D_NAME, VariantD } from "./variant-d"

const VARIANTS = ["A", "B", "C", "D"] as const
const NAMES: Record<string, string> = {
  A: VARIANT_A_NAME,
  B: VARIANT_B_NAME,
  C: VARIANT_C_NAME,
  D: VARIANT_D_NAME,
}

export function AnalysisArtifactPrototype({
  variant,
  symbol,
}: {
  variant: string
  symbol: string
}) {
  const key = (VARIANTS as readonly string[]).includes(variant) ? variant : "A"
  const sym = symbol in ARTIFACTS ? symbol : "VCB"
  const artifact = ARTIFACTS[sym]

  return (
    <ThreadShell artifact={artifact}>
      {key === "A" && <VariantA artifact={artifact} />}
      {key === "B" && <VariantB artifact={artifact} />}
      {key === "C" && <VariantC artifact={artifact} />}
      {key === "D" && <VariantD artifact={artifact} />}

      <PrototypeSwitcher variants={VARIANTS} names={NAMES} current={key}>
        <PrototypeSegments param="symbol" options={SYMBOLS} current={sym} />
      </PrototypeSwitcher>
    </ThreadShell>
  )
}
