"use client"

import AuthForm from "../auth-form"
import { loginAction } from "../actions"

export default function LoginForm() {
  return <AuthForm mode="login" action={loginAction} />
}
