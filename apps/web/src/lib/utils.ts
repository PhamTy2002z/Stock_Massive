import { clsx, type ClassValue } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

/**
 * The type ramp's own names, as `tailwind.config.js` declares them.
 *
 * They have to be repeated here, and the reason is worth stating because
 * getting it wrong is silent. `tailwind-merge` decides which utilities conflict
 * from a model of Tailwind's *default* scale, and `text-*` is ambiguous — it is
 * both the font-size utility and the text-colour one. A size it does not
 * recognise is classified as a colour, so `text-eyebrow text-ink-6` reads as
 * two colours, the earlier one is dropped as redundant, and the element falls
 * back to whatever size it inherits.
 *
 * Nothing warns. The class is in the source, absent from the DOM, and every
 * label built that way renders at the body's 15px instead of its own step —
 * which is exactly how a design system with a correct ramp still ships type
 * that is uniformly too large.
 */
const RAMP = ["eyebrow", "micro", "meta", "control", "row"] as const

const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: [...RAMP] }],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
