/**
 * Taking a desk view out of the browser as a file.
 *
 * **The numbers leave raw.** Every other reader in this directory formats for a
 * person — `formatNumber` abbreviates a million to "1 tr" and groups with a
 * Vietnamese separator — and a file that did the same would be a picture of a
 * spreadsheet rather than one. What leaves here is what the Study computed, so
 * the column the reader sorts on in Excel is the column the answer was written
 * from. The *headers* are still the reader's, through `labelOf`: the server
 * chose those words because it chose what the column means.
 *
 * **One frame, named after the deskView.** A desk view is several blocks over a
 * handful of frames, and a zip of them is a different feature. The primary
 * frame — the one the first block draws, which is the picture the answer is
 * about — is what a reader asking for "the data behind this" means.
 *
 * No library. `Blob` and an anchor are what a download is, and a dependency for
 * it would be three kilobytes to avoid ten lines.
 */

import { isBoardSpec } from "@/lib/alpha-desk/types"
import type { ArtifactPayload, Frame } from "@/lib/alpha-desk/types"

import { labelOf } from "./frame"

/**
 * The frame a reader means by "this desk view", or null.
 *
 * The first block's, because the spec puts the headline picture first and the
 * blocks after it read it. Falls back to whichever frame exists when the spec
 * names one that does not — a spec and a frame map that disagree is a backend
 * fault, and refusing the export over it helps nobody.
 */
export function primaryFrame(artifact: ArtifactPayload): Frame | null {
  const named = firstDrawnFrame(artifact)
  if (named !== null && artifact.frames[named] !== undefined) {
    return artifact.frames[named]
  }
  const first = Object.values(artifact.frames ?? {})[0]
  return first ?? null
}

/**
 * Which frame the first picture on the board draws, in either spelling.
 *
 * A v2 board's first block may be a caption — a sentence assembled from cells of
 * several frames — and exporting "the data behind this" as the frame a sentence
 * happened to quote would be the wrong file. So the search is for the first
 * *visual*, and a board of nothing but captions falls through to the fallback.
 */
function firstDrawnFrame(artifact: ArtifactPayload): string | null {
  const spec = artifact.signal_desk_spec
  if (isBoardSpec(spec)) {
    for (const section of spec.sections ?? []) {
      for (const block of section.blocks ?? []) {
        if (block.kind === "visual") return block.frame
      }
    }
    return spec.appendix?.frame ?? null
  }
  const named = spec?.blocks?.[0]?.frame
  return typeof named === "string" ? named : null
}

/**
 * One frame as CSV text.
 *
 * CRLF and the RFC 4180 quoting rules, because the reader opening this is
 * opening it in Excel: a cell holding a comma, a quote or a newline is wrapped
 * and its quotes doubled, and everything else goes out bare. A cell that is
 * neither a number nor a string — a null the Study could not fill — is empty
 * rather than "null", which is the same distinction the widgets draw: no value
 * is not zero.
 */
export function frameToCsv(frame: Frame): string {
  const header = frame.columns.map((column) => csvCell(labelOf(frame, column)))
  const rows = frame.rows.map((row) =>
    frame.columns.map((_, index) => csvCell(cellText(row[index]))).join(","),
  )
  return [header.join(","), ...rows].join("\r\n")
}

function cellText(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return String(value)
  if (typeof value === "string") return value
  if (typeof value === "boolean") return String(value)
  return ""
}

function csvCell(text: string): string {
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

/**
 * What the file is called.
 *
 * The desk view's own title and the `as_of` it was frozen at, because a folder of
 * downloads is where a reader loses track of which fortnight they were looking
 * at. Diacritics are folded and everything outside `[a-z0-9]` becomes a hyphen:
 * the name has to survive a Windows filesystem, and it is a filename rather
 * than a sentence.
 */
export function csvFilename(title: string, asOf: string): string {
  const slug = title
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
  const stamp = asOf.slice(0, 10)
  const stem = [slug || "signal-desk", stamp].filter((part) => part !== "").join("-")
  return `${stem}.csv`
}

/**
 * Hand the file to the browser.
 *
 * A BOM in front of the text, deliberately: Excel on Windows reads a CSV as the
 * system codepage without it, and a column of Vietnamese labels arrives as
 * mojibake — which makes the export useless to exactly the reader it is for.
 *
 * Guarded rather than assumed. `createObjectURL` is absent under a test DOM and
 * in a sandboxed frame, and a download that cannot happen must not take the
 * pane down with it.
 */
export function downloadCsv(filename: string, csv: string): boolean {
  if (typeof window === "undefined" || typeof URL.createObjectURL !== "function") {
    return false
  }
  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" })
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = href
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  // Freed on the next tick rather than immediately: revoking while the click is
  // still being handled cancels the download in Safari.
  window.setTimeout(() => URL.revokeObjectURL(href), 0)
  return true
}

/** The whole of the export, from the row the pane already has. */
export function exportArtifact(artifact: ArtifactPayload): boolean {
  const frame = primaryFrame(artifact)
  if (frame === null) return false
  return downloadCsv(
    csvFilename(artifact.signal_desk_spec?.title ?? "", artifact.provenance?.asOf ?? ""),
    frameToCsv(frame),
  )
}
