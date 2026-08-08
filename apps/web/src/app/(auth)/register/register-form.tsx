"use client"

import AuthForm from "../auth-form"
import { registerAction } from "../actions"

export default function RegisterForm() {
  return <AuthForm mode="register" action={registerAction} />
}
