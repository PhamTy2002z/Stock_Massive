import Link from "next/link"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

interface SurfaceEmptyStateProps {
  /** The question this surface exists to answer. Not a feature name. */
  question: string
  /** How the surface answers it, in one plain sentence. */
  description: string
  action: {
    label: string
    href: string
  }
  /** What is not built yet. Stated plainly so the surface never oversells itself. */
  notYet?: string
}

/**
 * An empty state that teaches instead of a product tour. Every empty surface
 * states the question it answers plus exactly one action.
 */
export function SurfaceEmptyState({
  question,
  description,
  action,
  notYet,
}: SurfaceEmptyStateProps) {
  return (
    <Card className="mx-auto max-w-2xl border-dashed">
      <CardContent className="flex flex-col items-start gap-4 p-8">
        <h2 className="text-lg font-semibold text-foreground">{question}</h2>
        <p className="text-sm text-muted-foreground">{description}</p>
        <Button asChild>
          <Link href={action.href}>{action.label}</Link>
        </Button>
        {notYet ? (
          <p className="text-xs text-muted-foreground/80">{notYet}</p>
        ) : null}
      </CardContent>
    </Card>
  )
}
