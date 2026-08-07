"use client"

import Image from "next/image"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useState } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

import type { AuthActionResult } from "./actions"

interface AuthFormProps {
  mode: "login" | "register"
  action: (formData: FormData, next?: string) => Promise<AuthActionResult>
}

const COPY = {
  login: {
    title: "Sign in to Stock Massive",
    submit: "Sign in",
    pending: "Signing in...",
    footerText: "Don't have an account?",
    footerHref: "/register",
    footerLink: "Create one",
  },
  register: {
    title: "Create your account",
    submit: "Create account",
    pending: "Creating account...",
    footerText: "Already have an account?",
    footerHref: "/login",
    footerLink: "Sign in",
  },
} as const

/**
 * Shared email/password form for both login and register.
 *
 * On success the server action redirects, so loading state is deliberately left
 * on — clearing it would flash an idle button during navigation.
 */
export default function AuthForm({ mode, action }: AuthFormProps) {
  const [isLoading, setIsLoading] = useState(false)
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
    } catch {
      toast.error("Something went wrong. Please try again.")
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-[450px] space-y-6">
        <div className="flex flex-col items-center space-y-4 text-center">
          <Image
            src="/logo.png"
            alt="Stock Massive Logo"
            width={64}
            height={64}
            className="rounded-xl"
            priority
          />
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              {copy.title}
            </h1>
            <p className="text-base text-muted-foreground">
              Navigate the volatility. Seize the opportunity.
            </p>
          </div>
        </div>

        <form action={onSubmit} className="space-y-4">
          {isRegister && (
            <div className="space-y-2">
              <Label htmlFor="full_name">Name</Label>
              <Input
                id="full_name"
                name="full_name"
                type="text"
                autoComplete="name"
                placeholder="Your name"
                className="h-12"
              />
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="email"
              placeholder="you@example.com"
              className="h-12"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              name="password"
              type="password"
              required
              minLength={isRegister ? 8 : undefined}
              autoComplete={isRegister ? "new-password" : "current-password"}
              placeholder={isRegister ? "At least 8 characters" : "Your password"}
              className="h-12"
            />
          </div>

          <Button type="submit" disabled={isLoading} className="w-full h-12 text-base">
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {copy.pending}
              </>
            ) : (
              copy.submit
            )}
          </Button>
        </form>

        <div className="text-center">
          <p className="text-sm text-muted-foreground">
            {copy.footerText}{" "}
            <Link
              href={copy.footerHref}
              className="text-foreground underline underline-offset-2 hover:text-primary transition-colors"
            >
              {copy.footerLink}
            </Link>
          </p>
        </div>

        <div className="text-center">
          <p className="text-sm text-muted-foreground">
            By continuing, you agree to our{" "}
            <Link
              href="/terms"
              className="text-muted-foreground underline underline-offset-2 hover:text-foreground transition-colors"
            >
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link
              href="/privacy"
              className="text-muted-foreground underline underline-offset-2 hover:text-foreground transition-colors"
            >
              Privacy Policy
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  )
}
