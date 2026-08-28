/**
 * The address that leads nowhere.
 *
 * The page this used to draw by hand is now the `page` density of
 * `FailureState`, so a 404 route and a 500 route are recognisably the same
 * screen with different words — which is the whole reason the density exists.
 * The copy stays specific to this one: the product really is a single screen,
 * and saying so is what stops the reader hunting for the page they think they
 * lost.
 */

import { FailureState } from "@/components/ui/failure-state"

export default function NotFound() {
  return (
    <FailureState
      density="page"
      failure={{
        kind: "not_found",
        title: "Không có gì ở địa chỉ này",
        detail:
          "Đường dẫn bạn mở không còn tồn tại. Toàn bộ VisgniteAI nằm trên một màn hình duy nhất.",
        recovery: "home",
        action: "Về màn hình chính",
        status: 404,
      }}
    />
  )
}
