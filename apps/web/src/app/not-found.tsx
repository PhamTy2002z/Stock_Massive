import Link from "next/link"

import { VisgniteMark } from "@/components/shared/visgnite-logo"
import { Button } from "@/components/ui/button"

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
      <Button asChild size="action" className="mt-2 px-4">
        <Link href="/">Về màn hình chính</Link>
      </Button>
    </div>
  )
}
