"use client"

import Link from "next/link"
import { unstable_rethrow, useSearchParams } from "next/navigation"
import { useEffect, useState } from "react"
import { Eye, EyeOff, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { VisgniteMark, VisgniteWordmark } from "@/components/shared/visgnite-logo"
import { clearDeskSession } from "@/lib/alpha-desk/desk-session"

import type { AuthActionResult } from "./actions"

interface AuthFormProps {
  mode: "login" | "register"
  action: (formData: FormData, next?: string) => Promise<AuthActionResult>
}

const COPY = {
  login: {
    title: "Welcome back",
    description: "Sign in to pick up your research where you left off.",
    submit: "Sign in",
    pending: "Signing in…",
    footerText: "Don't have an account?",
    footerHref: "/register",
    footerLink: "Sign up",
  },
  register: {
    title: "Open an account",
    description: "One screen to ask questions, read the tape, and track your tickers.",
    submit: "Create account",
    pending: "Creating account…",
    footerText: "Already have an account?",
    footerHref: "/login",
    footerLink: "Sign in",
  },
} as const

/**
 * The way in, drawn on the same ground as the product.
 *
 * One column rather than the split-screen the old design used: the app behind
 * this form is a single surface, and a marketing panel beside the fields would
 * be the only place in the product that looked like a website. The greeting is
 * the same serif line that opens a conversation, for the same reason — it is
 * the system addressing someone, not a heading.
 */
export default function AuthForm({ mode, action }: AuthFormProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const searchParams = useSearchParams()
  const next = searchParams.get("next") || searchParams.get("callbackUrl") || undefined

  const copy = COPY[mode]
  const isRegister = mode === "register"

  // Whatever this tab was reading before, it is not what the person signing in
  // asked for. Done on mount rather than after the action, because the action
  // redirects and never hands control back to this component.
  useEffect(() => {
    clearDeskSession()
  }, [])

  async function onSubmit(formData: FormData) {
    setIsLoading(true)
    try {
      const result = await action(formData, next)
      if (result?.error) {
        toast.error(result.error)
        setIsLoading(false)
      } else if (result === undefined) {
        // A sign-in that worked never arrives here: it ends in `redirect()`,
        // which rejects this promise and is rethrown below. Reaching this line
        // means the action came back having neither redirected nor named a
        // reason — and the spinner was left running forever on a form the
        // reader could no longer submit. Releasing the control is the part
        // that matters; the sentence is what stops it reading as success.
        toast.error("No response from the server. Please try again.")
        setIsLoading(false)
      }
    } catch (error) {
      // A successful sign-in ends in `redirect()`, which Next reports by
      // rejecting the action promise — swallowing it here would show a failure
      // toast on success and leave the router with nothing to act on.
      unstable_rethrow(error)
      toast.error("Something went wrong. Please try again.")
      setIsLoading(false)
    }
  }

  return (
    <main className="flex min-h-dvh flex-col bg-background px-6 py-8 text-foreground sm:px-10">
      <Link href="/" className="w-fit rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <VisgniteWordmark />
      </Link>

      <div className="my-auto flex justify-center py-12">
        <div className="w-full max-w-[392px] animate-vg-message-in">
          <header className="mb-7 flex flex-col items-start gap-3">
            <VisgniteMark className="h-[26px] w-[29px]" />
            <h1 className="font-serif text-[clamp(1.8rem,4vw,2.3rem)] font-normal leading-[1.1] tracking-[-0.01em] text-ink-display">
              {copy.title}
            </h1>
            <p className="text-row leading-relaxed text-ink-4">{copy.description}</p>
          </header>

          <form action={onSubmit} className="space-y-3.5">
            {isRegister && (
              <Field id="full_name" label="Full name">
                <input
                  id="full_name"
                  name="full_name"
                  type="text"
                  autoComplete="name"
                  placeholder="Jane Doe"
                  className={FIELD_CLASS}
                />
              </Field>
            )}

            <Field id="email" label="Email">
              <input
                id="email"
                name="email"
                type="email"
                required
                autoComplete="email"
                placeholder="you@example.com"
                className={FIELD_CLASS}
              />
            </Field>

            <Field id="password" label="Password">
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={isRegister ? 8 : undefined}
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  placeholder={isRegister ? "At least 8 characters" : "Enter your password"}
                  className={`${FIELD_CLASS} pr-12`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute inset-y-0 right-1 flex w-11 items-center justify-center rounded-lg text-ink-5 transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {showPassword ? <EyeOff className="size-[18px]" /> : <Eye className="size-[18px]" />}
                </button>
              </div>
            </Field>

            <button
              type="submit"
              disabled={isLoading}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-[11px] bg-primary text-[0.9rem] font-medium text-primary-foreground transition-[filter] hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-60"
            >
              {isLoading && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              {isLoading ? copy.pending : copy.submit}
            </button>
          </form>

          <p className="mt-6 text-center text-row text-ink-4">
            {copy.footerText}{" "}
            <Link
              href={copy.footerHref}
              className="font-medium text-primary underline-offset-4 transition-colors hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {copy.footerLink}
            </Link>
          </p>
        </div>
      </div>

      <footer className="flex items-center justify-between text-meta text-ink-6">
        <span>© {new Date().getFullYear()} VisgniteAI</span>
        <span>HOSE · HNX · UPCOM</span>
      </footer>
    </main>
  )
}

/** One field's shell. The label is always rendered — a placeholder is not one. */
function Field({
  id,
  label,
  children,
}: {
  id: string
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-control font-medium text-ink-2">
        {label}
      </label>
      {children}
    </div>
  )
}

const FIELD_CLASS =
  "h-12 w-full rounded-[11px] border border-border bg-surface-sunken px-3.5 text-[0.9rem] text-foreground outline-none transition-colors placeholder:text-ink-6 focus-visible:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring/40"
