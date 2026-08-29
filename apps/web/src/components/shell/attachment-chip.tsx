"use client"

import { useEffect, useState } from "react"
import { AlertCircle, FileText, X } from "lucide-react"

import { ATTACHMENT_COPY } from "@/lib/alpha-desk/copy"
import { cn } from "@/lib/utils"

/** How a file's size reads to a person. */
export function readableSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export interface AttachmentChipProps {
  filename: string
  byteSize: number
  /** Whether to draw a thumbnail rather than a document icon. */
  image: boolean
  /**
   * Where the picture is. A local `blob:` URL before the upload lands, the
   * proxy's own path afterwards, and `undefined` for anything not an image.
   */
  previewUrl?: string
  status?: "uploading" | "ready" | "error"
  /** Why it failed, in the product's own words. Drawn instead of the size. */
  error?: string
  /** Absent on a chip drawn in the transcript: a sent question cannot change. */
  onRemove?: () => void
}

/**
 * One attached file, before it is sent or after.
 *
 * The same component both times, because the reader is looking at the same
 * thing: what this question carries. Only `onRemove` differs — a question
 * already asked cannot have a file taken out of it, and drawing a button that
 * would have to refuse is worse than drawing none.
 *
 * The thumbnail is the reason this shows a picture rather than a filename. A
 * screenshot is chosen from a grid of near-identical thumbnails and named
 * something like `Screenshot 2026-08-29 at 01.14.22.png`; the filename does not
 * tell the reader whether they picked the right one, and the image does.
 */
export function AttachmentChip({
  filename,
  byteSize,
  image,
  previewUrl,
  status = "ready",
  error,
  onRemove,
}: AttachmentChipProps) {
  const failed = status === "error"
  return (
    <span
      className={cn(
        "inline-flex max-w-[220px] items-center gap-2 rounded-lg border py-1 pl-1 pr-1",
        // Neutral, like the analysis-context pill beside it. The accent on this
        // card belongs to the mode control, and two oranges in one card compete.
        failed ? "border-destructive/40 bg-destructive/5" : "border-border bg-surface-bubble",
      )}
    >
      <span className="grid size-7 shrink-0 place-items-center overflow-hidden rounded-md bg-foreground/[0.06]">
        {failed ? (
          <AlertCircle className="size-3.5 text-destructive" strokeWidth={1.8} />
        ) : image && previewUrl ? (
          // Not `next/image`: the source is a `blob:` URL for a file the reader
          // just chose, and the optimizer cannot fetch one.
          <img src={previewUrl} alt="" className="size-full object-cover" />
        ) : (
          <FileText className="size-3.5 text-ink-4" strokeWidth={1.7} />
        )}
      </span>
      <span className="flex min-w-0 flex-col leading-tight">
        <span className="truncate text-meta text-ink-2">{filename}</span>
        <span className={cn("truncate text-micro", failed ? "text-destructive" : "text-ink-6")}>
          {status === "uploading"
            ? ATTACHMENT_COPY.uploading
            : failed
              ? (error ?? ATTACHMENT_COPY.failed)
              : readableSize(byteSize)}
        </span>
      </span>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={ATTACHMENT_COPY.remove(filename)}
          className="grid size-[18px] shrink-0 place-items-center rounded-[5px] text-ink-4 transition-colors hover:bg-foreground/10 hover:text-foreground"
        >
          <X className="size-2.5" strokeWidth={2.4} />
        </button>
      )}
    </span>
  )
}

/**
 * A `blob:` URL for a local file, revoked when it stops being needed.
 *
 * The revoke is the whole reason this is a hook rather than a call at the point
 * of use. `createObjectURL` pins the file in memory until something releases
 * it, so a reader who attaches and removes twenty screenshots while writing one
 * question would hold all twenty for the life of the tab.
 */
export function useObjectUrl(file: File | null): string | undefined {
  const [url, setUrl] = useState<string | undefined>(undefined)
  useEffect(() => {
    if (file === null) {
      setUrl(undefined)
      return
    }
    const created = URL.createObjectURL(file)
    setUrl(created)
    return () => URL.revokeObjectURL(created)
  }, [file])
  return url
}
