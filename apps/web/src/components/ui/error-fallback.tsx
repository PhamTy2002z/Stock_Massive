"use client"

import { AlertCircle, RefreshCw, WifiOff } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface ErrorFallbackProps {
  error: Error
  resetErrorBoundary: () => void
  compact?: boolean
  className?: string
}

export function ErrorFallback({
  error,
  resetErrorBoundary,
  compact,
  className,
}: ErrorFallbackProps) {
  const isNetworkError =
    error.message.toLowerCase().includes("network") ||
    error.message.toLowerCase().includes("fetch") ||
    error.message.toLowerCase().includes("failed to load")

  if (compact) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 p-3 rounded-lg border border-destructive/50 bg-destructive/10",
          className
        )}
      >
        {isNetworkError ? (
          <WifiOff className="h-4 w-4 text-destructive shrink-0" />
        ) : (
          <AlertCircle className="h-4 w-4 text-destructive shrink-0" />
        )}
        <span className="text-sm text-destructive truncate">
          {isNetworkError ? "Lỗi kết nối mạng" : error.message}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={resetErrorBoundary}
          className="shrink-0 h-7 px-2"
        >
          <RefreshCw className="h-3 w-3" />
        </Button>
      </div>
    )
  }

  return (
    <Card className={cn("border-destructive/50 bg-destructive/5", className)}>
      <CardContent className="flex flex-col items-center gap-4 p-8">
        {isNetworkError ? (
          <WifiOff className="h-12 w-12 text-destructive" />
        ) : (
          <AlertCircle className="h-12 w-12 text-destructive" />
        )}
        <div className="text-center space-y-1">
          <h3 className="font-semibold">Đã xảy ra lỗi</h3>
          <p className="text-sm text-muted-foreground">
            {isNetworkError
              ? "Không thể kết nối. Vui lòng kiểm tra mạng của bạn."
              : error.message}
          </p>
        </div>
        <Button onClick={resetErrorBoundary} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Thử lại
        </Button>
      </CardContent>
    </Card>
  )
}
