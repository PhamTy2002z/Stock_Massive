"use client"

/**
 * PROTOTYPE — issue #22.
 * Three Alpha Desk harness layouts, switchable via `?variant=`, with the same
 * six states switchable via `?state=` so structure and behavior are separable.
 */

import { PrototypeSegments, PrototypeSwitcher } from "@/components/shared/prototype-switcher"
import { STATES, type HarnessState } from "./fixtures"
import { VARIANT_A_NAME, VariantA } from "./variant-a"
import { VARIANT_B_NAME, VariantB } from "./variant-b"
import { VARIANT_C_NAME, VariantC } from "./variant-c"

const VARIANTS = ["A", "B", "C"] as const
const NAMES: Record<string, string> = {
  A: VARIANT_A_NAME,
  B: VARIANT_B_NAME,
  C: VARIANT_C_NAME,
}

export function AlphaDeskPrototype({ variant, state }: { variant: string; state: string }) {
  const key = (VARIANTS as readonly string[]).includes(variant) ? variant : "A"
  const scenario: HarnessState = (STATES as readonly string[]).includes(state)
    ? (state as HarnessState)
    : "ready"

  return (
    <div className="h-full min-h-0">
      {key === "A" && <VariantA key={`${key}-${scenario}`} state={scenario} />}
      {key === "B" && <VariantB key={`${key}-${scenario}`} state={scenario} />}
      {key === "C" && <VariantC key={`${key}-${scenario}`} state={scenario} />}

      <PrototypeSwitcher variants={VARIANTS} names={NAMES} current={key}>
        <PrototypeSegments param="state" options={STATES} current={scenario} />
      </PrototypeSwitcher>
    </div>
  )
}
