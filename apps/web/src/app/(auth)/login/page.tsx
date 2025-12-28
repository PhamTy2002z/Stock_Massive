import { Metadata } from "next"
import { Suspense } from "react"
import LoginForm from "./login-form"

export const metadata: Metadata = {
  title: "Login - Stock Massive",
  description: "Sign in to your Stock Massive account",
}

// Loading fallback for Suspense boundary
function LoginFormFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-[450px] space-y-6">
        <div className="flex flex-col items-center space-y-2 text-center">
          <div className="h-8 w-48 animate-pulse rounded bg-muted" />
          <div className="h-4 w-64 animate-pulse rounded bg-muted" />
        </div>
        <div className="h-12 w-full animate-pulse rounded bg-muted" />
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFormFallback />}>
      <LoginForm />
    </Suspense>
  )
}
