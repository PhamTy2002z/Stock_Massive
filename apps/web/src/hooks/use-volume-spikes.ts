"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchVolumeSpikes, type VolumeSpikeParams } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

/**
 * The Volume Spike signal for one Signal Scope.
 *
 * Polled rather than pushed, and deliberately unhurried: the signal is computed
 * from end-of-day sessions, so nothing it reports changes during a session. The
 * interval exists to pick up the evening's collection cycle, not to chase a
 * moving number.
 */
export function useVolumeSpikes(params: VolumeSpikeParams = {}) {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.volumeSpikes(params),
    queryFn: () => fetchVolumeSpikes(params),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  // data is ALWAYS defined with useSuspenseQuery
  return {
    data,
    isFetching,
    refetch,
  }
}
