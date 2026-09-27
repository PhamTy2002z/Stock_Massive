/**
 * The FastAPI base URL, for the server-side routes that forward to it.
 *
 * The browser never calls the API directly: it goes through the same-origin
 * routes under `/api`, which is why only the server's view of the address is
 * resolved here.
 */
export const getApiBaseUrl = () =>
  process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"

/** A request the server answered and refused. */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = "ApiError"
  }
}
