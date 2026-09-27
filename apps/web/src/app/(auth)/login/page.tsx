import { Metadata } from "next"
import { Suspense } from "react"

import AuthFormFallback from "../auth-form-fallback"
import LoginForm from "./login-form"

export const metadata: Metadata = {
  title: "Sign in · VisgniteAI",
  description: "Sign in to your VisgniteAI account",
}

export default function LoginPage() {
  return (
    <Suspense fallback={<AuthFormFallback />}>
      <LoginForm />
    </Suspense>
  )
}
