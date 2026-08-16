/**
 * What fills the frame while the shell's own bundle arrives.
 *
 * Deliberately almost nothing: the surface is one dark ground with three
 * regions drawn on it, and a skeleton of cards would promise a layout this app
 * does not have. The mark is enough to say the page is loading rather than
 * broken.
 */
import { VisgniteMark } from "@/components/shared/visgnite-logo"

export default function Loading() {
  return (
    <div className="flex h-dvh items-center justify-center bg-background">
      <VisgniteMark className="h-8 w-[21px] animate-vg-fade-in" />
      <span className="sr-only">Đang tải VisgniteAI</span>
    </div>
  )
}
