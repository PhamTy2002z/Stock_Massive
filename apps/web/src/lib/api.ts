/** Resolve the FastAPI origin for server-side probes and browser recovery. */
export const getApiBaseUrl = () => {
  if (typeof window === "undefined") {
    return process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"
}

/** A request the server answered and refused. */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = "ApiError"
  }
}
