"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchVolumeSpikes, type VolumeSpikeParams } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useVolumeSpikes(params: VolumeSpikeParams = {}) {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.volumeSpikes(params),
    queryFn: () => fetchVolumeSpikes(params),
    staleTime: 2 * 60 * 1000,
    refetchInterval: 3 * 60 * 1000,
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
