import { Metadata } from "next"
import { Suspense } from "react"

import AuthFormFallback from "../auth-form-fallback"
import RegisterForm from "./register-form"

export const metadata: Metadata = {
  title: "Tạo tài khoản · VisgniteAI",
  description: "Tạo tài khoản VisgniteAI",
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<AuthFormFallback />}>
      <RegisterForm />
    </Suspense>
  )
}
