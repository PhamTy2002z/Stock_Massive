import Link from "next/link"

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center">
      <h2 className="text-2xl font-bold">Page Not Found</h2>
      <p className="mt-2 text-muted-foreground">Could not find requested resource</p>
      <Link href="/" className="mt-4 text-primary hover:underline">
        Return Home
      </Link>
    </div>
  )
}
