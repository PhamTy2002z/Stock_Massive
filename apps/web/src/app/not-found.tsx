import Link from "next/link"

import { VisgniteMark } from "@/components/shared/visgnite-logo"

export default function NotFound() {
  return (
    <div className="flex h-dvh flex-col items-center justify-center gap-4 bg-background px-6 text-center">
      <VisgniteMark className="h-8 w-[21px]" />
      <h1 className="font-serif text-[1.8rem] font-normal leading-tight text-ink-display">
        Không có gì ở địa chỉ này
      </h1>
      <p className="max-w-sm text-row text-ink-4">
        Đường dẫn bạn mở không còn tồn tại. Toàn bộ VisgniteAI nằm trên một màn hình duy nhất.
      </p>
      <Link
        href="/"
        className="mt-2 rounded-[11px] bg-primary px-4 py-2.5 text-control font-medium text-primary-foreground transition-[filter] hover:brightness-110"
      >
        Về màn hình chính
      </Link>
    </div>
  )
}
