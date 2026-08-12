"use client"

import Image from "next/image"
import Link from "next/link"
import { unstable_rethrow, useSearchParams } from "next/navigation"
import { useState } from "react"
import { Eye, EyeOff, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

import type { AuthActionResult } from "./actions"
import MarketShowcase from "./market-showcase"

interface AuthFormProps {
  mode: "login" | "register"
  action: (formData: FormData, next?: string) => Promise<AuthActionResult>
}

const COPY = {
  login: {
    title: "Đăng nhập",
    description: "Truy cập bảng phân tích chứng khoán Việt Nam của bạn.",
    submit: "Đăng nhập",
    pending: "Đang đăng nhập...",
    footerText: "Chưa có tài khoản?",
    footerHref: "/register",
    footerLink: "Đăng ký",
  },
  register: {
    title: "Tạo tài khoản",
    description: "Bắt đầu theo dõi và phân tích thị trường chứng khoán Việt Nam.",
    submit: "Tạo tài khoản",
    pending: "Đang tạo tài khoản...",
    footerText: "Đã có tài khoản?",
    footerHref: "/login",
    footerLink: "Đăng nhập",
  },
} as const

export default function AuthForm({ mode, action }: AuthFormProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const searchParams = useSearchParams()
  const next = searchParams.get("next") || searchParams.get("callbackUrl") || undefined

  const copy = COPY[mode]
  const isRegister = mode === "register"

  async function onSubmit(formData: FormData) {
    setIsLoading(true)
    try {
      const result = await action(formData, next)
      if (result?.error) {
        toast.error(result.error)
        setIsLoading(false)
      }
    } catch (error) {
      // A successful sign-in ends in `redirect()`, which Next reports by
      // rejecting the action promise — swallowing it here would show a failure
      // toast on success and leave the router with nothing to act on.
      unstable_rethrow(error)
      toast.error("Đã có lỗi xảy ra. Vui lòng thử lại.")
      setIsLoading(false)
    }
  }

  return (
    <main className="grid min-h-dvh bg-white lg:grid-cols-2">
      <section className="relative flex min-h-dvh flex-col bg-white px-6 py-8 text-auth-ink sm:px-14 sm:py-10 lg:px-14">
        <Link
          href="/"
          className="flex w-fit items-center gap-3 rounded-md font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-auth-orange focus-visible:ring-offset-4"
        >
          <Image src="/logo.png" alt="" width={30} height={26} className="h-7 w-8 object-contain" priority />
          <span>Stock Massive</span>
        </Link>

        <div className="my-auto flex justify-center py-12">
          <div className="w-full max-w-[392px] animate-auth-up">
            <header className="mb-6">
              <h1 className="text-[40px] font-bold leading-[1.12] tracking-[-0.04em] text-auth-ink">
                {copy.title}
              </h1>
              <p className="mt-2 max-w-[370px] text-base leading-6 text-auth-muted">
                {copy.description}
              </p>
            </header>

            <form action={onSubmit} className="space-y-4">
              {isRegister && (
                <div className="space-y-2">
                  <Label htmlFor="full_name" className="text-sm font-semibold text-auth-ink">
                    Họ và tên
                  </Label>
                  <Input
                    id="full_name"
                    name="full_name"
                    type="text"
                    autoComplete="name"
                    placeholder="Nguyễn Văn A"
                    className="h-12 rounded-xl border-auth-border bg-white px-4 text-base text-auth-ink shadow-none placeholder:text-[#a5abb5] focus-visible:ring-auth-orange md:text-base"
                  />
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm font-semibold text-auth-ink">
                  Email
                </Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  placeholder="you@example.com"
                  className="h-12 rounded-xl border-auth-border bg-white px-4 text-base text-auth-ink shadow-none placeholder:text-[#a5abb5] focus-visible:ring-auth-orange md:text-base"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-semibold text-auth-ink">
                  Mật khẩu
                </Label>
                <div className="relative">
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    required
                    minLength={isRegister ? 8 : undefined}
                    autoComplete={isRegister ? "new-password" : "current-password"}
                    placeholder={isRegister ? "Tối thiểu 8 ký tự" : "Nhập mật khẩu"}
                    className="h-12 rounded-xl border-auth-border bg-white px-4 pr-12 text-base text-auth-ink shadow-none placeholder:text-[#a5abb5] focus-visible:ring-auth-orange md:text-base"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((visible) => !visible)}
                    aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                    className="absolute inset-y-0 right-1 flex w-11 items-center justify-center rounded-lg text-[#858d98] transition-colors hover:text-auth-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-auth-orange"
                  >
                    {showPassword ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                disabled={isLoading}
                className="h-12 w-full rounded-full bg-auth-orange text-base font-semibold text-white shadow-none transition-colors hover:bg-[#e95d00] focus-visible:ring-2 focus-visible:ring-auth-orange focus-visible:ring-offset-2 active:bg-[#d95500]"
              >
                {isLoading && <Loader2 className="animate-spin" aria-hidden="true" />}
                {isLoading ? copy.pending : copy.submit}
              </Button>
            </form>

            <p className="mt-6 text-center text-base text-auth-muted">
              {copy.footerText}{" "}
              <Link
                href={copy.footerHref}
                className="font-semibold text-auth-orange transition-colors hover:text-[#d95500] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-auth-orange focus-visible:ring-offset-2"
              >
                {copy.footerLink}
              </Link>
            </p>
          </div>
        </div>

        <footer className="flex items-center justify-between text-sm text-[#767e8a]">
          <span>© 2026 Stock Massive</span>
          <nav aria-label="Liên kết pháp lý" className="flex gap-6">
            <Link href="/terms" className="hover:text-auth-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-auth-orange">
              Điều khoản
            </Link>
            <Link href="/privacy" className="hover:text-auth-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-auth-orange">
              Bảo mật
            </Link>
          </nav>
        </footer>
      </section>

      <MarketShowcase />
    </main>
  )
}
