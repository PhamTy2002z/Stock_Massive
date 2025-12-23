"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchVolumeSpikes, type VolumeSpikeParams } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useVolumeSpikes(params: VolumeSpikeParams = {}) {
  const query = useQuery({
    queryKey: queryKeys.volumeSpikes(params),
    queryFn: () => fetchVolumeSpikes(params),
    staleTime: 2 * 60 * 1000,
    refetchInterval: 3 * 60 * 1000,
    placeholderData: keepPreviousData,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
  }
}
