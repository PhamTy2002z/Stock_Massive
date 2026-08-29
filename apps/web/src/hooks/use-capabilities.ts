"use client"

import { useQuery } from "@tanstack/react-query"

import { fetchCapabilities } from "@/lib/alpha-desk/api"
import { queryKeys } from "@/lib/query-keys"

/**
 * What the configured route can do.
 *
 * A deployment fact, not an account one: identical for every reader and
 * unchanged until a deploy. So it is fetched once and never refetched — no
 * interval, no refetch on focus. `staleTime: Infinity` is the honest setting
 * for a value that only a restart can change.
 */
export function useCapabilities() {
  const query = useQuery({
    queryKey: queryKeys.capabilities,
    queryFn: fetchCapabilities,
    staleTime: Infinity,
    gcTime: Infinity,
  })
  return {
    // True until the answer arrives. The alternative flashes "the model cannot
    // read pictures" on every load of a deployment where it can, which is a
    // worse wrong answer than being briefly optimistic.
    vision: query.data?.vision ?? true,
    loaded: query.isSuccess,
  }
}
