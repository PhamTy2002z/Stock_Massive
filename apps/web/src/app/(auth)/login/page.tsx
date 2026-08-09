import { Metadata } from "next"
import { Suspense } from "react"

import AuthFormFallback from "../auth-form-fallback"
import LoginForm from "./login-form"

export const metadata: Metadata = {
  title: "Đăng nhập - Stock Massive",
  description: "Đăng nhập vào tài khoản Stock Massive",
}

export default function LoginPage() {
  return (
    <Suspense fallback={<AuthFormFallback />}>
      <LoginForm />
    </Suspense>
  )
}
