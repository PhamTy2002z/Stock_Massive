"use client"

import * as React from "react"
import { Check, Copy } from "lucide-react"
import { toast } from "sonner"

import { changePasswordAction, logoutAllAction } from "@/app/(auth)/account-actions"
import { useAuth } from "@/hooks/use-auth"
import { cn } from "@/lib/utils"

import { ConfirmAction, FIELD, PillAction, SettingsRow, SettingsSection } from "./settings-primitives"

/**
 * How this login is secured: the address it signs in with, its password, and
 * every session it has open.
 *
 * Signing *this* session out alone is not offered here. It already lives one
 * click away in the account menu, and a second copy inside a settings dialog is
 * a second place to keep correct for no gain.
 */
function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = React.useState(false)

  // The timer is cleared on unmount so a copy immediately before closing the
  // dialog does not set state on a gone component.
  React.useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), 2000)
    return () => clearTimeout(timer)
  }, [copied])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
    } catch {
      // Clipboard access is refused outside a secure context, and a button that
      // silently does nothing is worse than one that says so.
      toast.error("Your browser won't allow copying")
    }
  }

  return (
    <PillAction onClick={handleCopy}>
      <span className="flex items-center gap-1.5">
        {copied ? (
          <Check className="size-[14px] text-positive" strokeWidth={1.9} />
        ) : (
          <Copy className="size-[14px]" strokeWidth={1.7} />
        )}
        {copied ? "Copied" : `Copy ${label}`}
      </span>
    </PillAction>
  )
}

type PasswordField = "current" | "next" | "confirm"

const PASSWORD_FIELDS: { key: PasswordField; label: string; autoComplete: string }[] = [
  { key: "current", label: "Current password", autoComplete: "current-password" },
  { key: "next", label: "New password", autoComplete: "new-password" },
  { key: "confirm", label: "Confirm new password", autoComplete: "new-password" },
]

/** The client's own checks, in the order a reader fixes them. */
function validate(values: Record<PasswordField, string>): Partial<Record<PasswordField, string>> {
  const errors: Partial<Record<PasswordField, string>> = {}
  if (values.current === "") errors.current = "Enter your current password."
  if (values.next.length < 8) errors.next = "The new password needs at least 8 characters."
  else if (values.next === values.current) errors.next = "The new password must differ from the current one."
  if (values.confirm !== values.next) errors.confirm = "The passwords don't match."
  return errors
}

/**
 * Change the password without leaving the row.
 *
 * The API answers a change with a fresh token pair, and the server action
 * stores it as this browser's session — so the reader stays signed in here
 * on the new credentials.
 */
function PasswordForm({ onDone }: { onDone: () => void }) {
  const [values, setValues] = React.useState<Record<PasswordField, string>>({
    current: "",
    next: "",
    confirm: "",
  })
  const [errors, setErrors] = React.useState<Partial<Record<PasswordField, string>>>({})
  const [pending, setPending] = React.useState(false)
  const firstField = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => firstField.current?.focus(), [])

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    const found = validate(values)
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setPending(true)
    try {
      const result = await changePasswordAction({
        current_password: values.current,
        new_password: values.next,
      })
      if (result.ok) {
        toast.success("Password changed")
        onDone()
        return
      }
      if (result.status === 400) setErrors({ current: "That current password is incorrect" })
      else if (result.status === 422) setErrors({ next: "The new password isn't valid." })
      else toast.error("Couldn't change the password. Please try again.")
    } catch {
      toast.error("Couldn't change the password. Please try again.")
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate className="flex w-full flex-col gap-3 md:max-w-sm">
      {PASSWORD_FIELDS.map((field, index) => {
        const error = errors[field.key]
        const id = `password-${field.key}`
        return (
          <div key={field.key}>
            <label htmlFor={id} className="text-control text-ink-4">
              {field.label}
            </label>
            <input
              ref={index === 0 ? firstField : undefined}
              id={id}
              type="password"
              autoComplete={field.autoComplete}
              value={values[field.key]}
              disabled={pending}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `${id}-error` : undefined}
              onChange={(event) =>
                setValues((previous) => ({ ...previous, [field.key]: event.target.value }))
              }
              className={cn(FIELD, "mt-1 h-8", error && "border-negative/60")}
            />
            {error ? (
              <p id={`${id}-error`} className="mt-1 text-meta text-negative">
                {error}
              </p>
            ) : null}
          </div>
        )
      })}
      <div className="flex gap-2">
        <PillAction disabled={pending} onClick={onDone}>
          Cancel
        </PillAction>
        <PillAction type="submit" disabled={pending}>
          {pending ? "Changing…" : "Change password"}
        </PillAction>
      </div>
    </form>
  )
}

export function SecuritySection() {
  const { user, isPending, signOut } = useAuth()
  const email = user?.email ?? ""
  const [changing, setChanging] = React.useState(false)

  const logoutEverywhere = async () => {
    const result = await logoutAllAction()
    if (!result.ok) {
      toast.error("Couldn't sign out other devices. Please try again.")
      return
    }
    // The same way out the account menu takes: drop every cached query and
    // land on the sign-in page.
    signOut()
  }

  return (
    <SettingsSection title="Security">
      <SettingsRow
        label="Sign-in email"
        description={isPending ? "Loading…" : email || "Not signed in"}
      >
        {email ? <CopyButton value={email} label="email" /> : null}
      </SettingsRow>

      <SettingsRow
        label="Password"
        description="Change your sign-in password. This session stays signed in."
        className={changing ? "md:flex-col md:items-stretch" : undefined}
      >
        {changing ? (
          <PasswordForm onDone={() => setChanging(false)} />
        ) : (
          <PillAction disabled={!user} onClick={() => setChanging(true)}>
            Change password
          </PillAction>
        )}
      </SettingsRow>

      <SettingsRow
        label="Sign out of every device"
        description="Ends every signed-in session on this account, including this one."
      >
        <ConfirmAction
          confirmLabel="Confirm sign out"
          pendingLabel="Signing out…"
          disabled={!user}
          onConfirm={logoutEverywhere}
        >
          Sign out
        </ConfirmAction>
      </SettingsRow>
    </SettingsSection>
  )
}
