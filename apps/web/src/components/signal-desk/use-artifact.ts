"use client"

/**
 * One Study run, fetched once and cached forever.
 *
 * Two surfaces need the same row and must not disagree about it: the pane draws
 * the blocks, and the chrome above them names the tab and hands the numbers to
 * the export. Written here rather than twice because the *options* are the
 * contract, not the call — `staleTime: Infinity` is not a performance choice, it
 * is the freeze. The row is immutable by design: it is written once, and
 * re-opening a Thread renders what was frozen rather than asking the store for a
 * fresher slice. Two copies of these options are two places a future change
 * could quietly start recomputing yesterday's picture.
 *
 * Both callers share one query key, so the chrome costs no second request.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query"

import { fetchArtifact } from "@/lib/alpha-desk/api"
import type { ArtifactPayload } from "@/lib/alpha-desk/types"
import { queryKeys } from "@/lib/query-keys"

export function useArtifact(artifactId: string | null): UseQueryResult<ArtifactPayload> {
  return useQuery({
    queryKey: queryKeys.artifact(artifactId ?? ""),
    queryFn: () => fetchArtifact(artifactId as string),
    enabled: artifactId !== null,
    staleTime: Infinity,
    gcTime: Infinity,
    // Nothing about an immutable row changes because a tab regained focus.
    refetchOnWindowFocus: false,
    // No retry. The failure this route actually has is a 404 — an artifact
    // belonging to another Thread — and retrying it asks the same question
    // twice before telling the reader the one true answer.
    retry: false,
  })
}
