import { Metadata } from "next"
import { Suspense } from "react"

import AuthFormFallback from "../auth-form-fallback"
import RegisterForm from "./register-form"

export const metadata: Metadata = {
  title: "Create account · VisgniteAI",
  description: "Create a VisgniteAI account",
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<AuthFormFallback />}>
      <RegisterForm />
    </Suspense>
  )
}
