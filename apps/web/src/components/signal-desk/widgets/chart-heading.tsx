/** A chart's subject and its one persistent unit label. */
export function ChartHeading({
  label,
  unit,
  secondary,
}: {
  label: string
  unit: string
  secondary?: string
}) {
  return (
    <div className="mb-1 flex items-baseline justify-between gap-3 text-meta">
      <span className="truncate font-medium text-ink-3">
        {label}
        {secondary !== undefined && (
          <span className="font-normal text-muted-foreground"> · {secondary}</span>
        )}
      </span>
      {unit !== "" && (
        <span className="shrink-0 whitespace-nowrap font-mono tabular-nums text-muted-foreground">
          {unit}
        </span>
      )}
    </div>
  )
}
