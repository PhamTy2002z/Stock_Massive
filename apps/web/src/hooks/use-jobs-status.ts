import { useQuery } from "@tanstack/react-query"
import { fetchJobsStatus, JobStatus } from "@/lib/api"

export function useJobsStatus() {
  return useQuery({
    queryKey: ["jobs-status"],
    queryFn: fetchJobsStatus,
    refetchInterval: (query) => {
      // Poll every 10s if any job is running, 60s otherwise
      const hasRunning = query.state.data?.some((j) => j.status === "running")
      return hasRunning ? 10000 : 60000
    },
    refetchIntervalInBackground: true,
    staleTime: 4000,
    // Error handling - silently fail, don't break UI
    retry: 2,
    retryDelay: 1000,
    throwOnError: false,
  })
}

// Helper: get only running jobs
export function useRunningJobs(): JobStatus[] {
  const { data } = useJobsStatus()
  return data?.filter((j) => j.status === "running") ?? []
}

// Helper: get completed/failed jobs (for notification history)
export function useCompletedJobsToday(): JobStatus[] {
  const { data } = useJobsStatus()
  return data?.filter((j) => j.status === "completed" || j.status === "failed") ?? []
}
