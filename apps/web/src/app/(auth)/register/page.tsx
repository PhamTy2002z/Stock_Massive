import { Metadata } from "next"
import { Suspense } from "react"

import AuthFormFallback from "../auth-form-fallback"
import RegisterForm from "./register-form"

export const metadata: Metadata = {
  title: "Tạo tài khoản - Stock Massive",
  description: "Tạo tài khoản Stock Massive",
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<AuthFormFallback />}>
      <RegisterForm />
    </Suspense>
  )
}
