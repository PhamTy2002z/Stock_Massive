export default function AuthFormFallback() {
  return (
    <div className="grid min-h-dvh bg-white lg:grid-cols-2">
      <div className="flex min-h-dvh items-center justify-center px-6 sm:px-14">
        <div className="w-full max-w-[392px] space-y-5">
          <div className="h-11 w-56 animate-pulse rounded-lg bg-[#eef0f3]" />
          <div className="h-5 w-80 max-w-full animate-pulse rounded bg-[#eef0f3]" />
          <div className="h-12 w-full animate-pulse rounded-xl bg-[#eef0f3]" />
          <div className="h-12 w-full animate-pulse rounded-xl bg-[#eef0f3]" />
          <div className="h-12 w-full animate-pulse rounded-full bg-[#ff6500]/40" />
        </div>
      </div>
      <div className="hidden min-h-dvh bg-auth-background lg:block" />
    </div>
  )
}
