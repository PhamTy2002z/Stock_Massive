/**
 * What an `insufficient_data` answer looks like.
 *
 * An explanatory state rather than an empty table: a table with no rows reads
 * as "nothing spiked today", which is a finding. Too little data to compute a
 * finding is a different thing, and the two must not look alike.
 */
export function InsufficientDataNotice({ className }: { className?: string }) {
  return (
    <div
      className={
        className ??
        "rounded-lg border border-border bg-card p-8 text-center space-y-2"
      }
    >
      <p className="font-medium">Chưa đủ dữ liệu để kết luận</p>
      <p className="text-sm text-muted-foreground">
        Tín hiệu chỉ được tính khi phần lớn phạm vi có đủ 21 phiên liên tiếp
        trong kho dữ liệu. Dải phía trên cho biết hiện còn thiếu ở đâu.
      </p>
    </div>
  )
}
