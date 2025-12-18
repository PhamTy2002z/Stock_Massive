"use client"

import { AlertCircle } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

interface StockDetailErrorProps {
  error: Error
  onRetry?: () => void
}

export function StockDetailError({ error, onRetry }: StockDetailErrorProps) {
  return (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Error Loading Stock Data</AlertTitle>
      <AlertDescription className="mt-2">
        {error.message || "Failed to fetch stock details. Please try again."}
      </AlertDescription>
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="mt-3"
        >
          Retry
        </Button>
      )}
    </Alert>
  )
}
