import { useQuery, useMutation, useQueryClient, UseQueryOptions } from '@tanstack/react-query'
import { jobsApi, JobListParams } from '@/lib/api'
import type { Job, JobCreate, JobUpdate, JobStatus, JobListResponse, JobStatusCount } from '@/types/job'

// ---------------------------------------------------------------------------
// Query Keys
// ---------------------------------------------------------------------------

export const jobKeys = {
  all: ['jobs'] as const,
  lists: () => [...jobKeys.all, 'list'] as const,
  list: (params?: JobListParams) => [...jobKeys.lists(), params] as const,
  details: () => [...jobKeys.all, 'detail'] as const,
  detail: (id: string) => [...jobKeys.details(), id] as const,
  timeline: (id: string) => [...jobKeys.detail(id), 'timeline'] as const,
  documents: (id: string) => [...jobKeys.detail(id), 'documents'] as const,
  statusCounts: () => [...jobKeys.all, 'status-counts'] as const,
}

// ---------------------------------------------------------------------------
// useJobs — paginated list with filtering
// ---------------------------------------------------------------------------

export function useJobs(
  params?: JobListParams,
  options?: Omit<UseQueryOptions<JobListResponse>, 'queryKey' | 'queryFn'>
) {
  return useQuery<JobListResponse>({
    queryKey: jobKeys.list(params),
    queryFn: () => jobsApi.list(params) as unknown as Promise<JobListResponse>,
    staleTime: 30_000,
    ...options,
  })
}

// ---------------------------------------------------------------------------
// useJob — single job by ID
// ---------------------------------------------------------------------------

export function useJob(
  id: string | null | undefined,
  options?: Omit<UseQueryOptions<Job>, 'queryKey' | 'queryFn'>
) {
  return useQuery<Job>({
    queryKey: jobKeys.detail(id ?? ''),
    queryFn: () => jobsApi.get(id!) as unknown as Promise<Job>,
    enabled: !!id,
    staleTime: 30_000,
    ...options,
  })
}

// ---------------------------------------------------------------------------
// useJobTimeline
// ---------------------------------------------------------------------------

export function useJobTimeline(
  id: string | null | undefined,
  options?: Omit<UseQueryOptions<Job['timeline']>, 'queryKey' | 'queryFn'>
) {
  return useQuery<Job['timeline']>({
    queryKey: jobKeys.timeline(id ?? ''),
    queryFn: () => jobsApi.getTimeline(id!) as unknown as Promise<Job['timeline']>,
    enabled: !!id,
    staleTime: 15_000,
    ...options,
  })
}

// ---------------------------------------------------------------------------
// useJobStatusCounts
// ---------------------------------------------------------------------------

export function useJobStatusCounts(
  options?: Omit<UseQueryOptions<Record<JobStatus, number>>, 'queryKey' | 'queryFn'>
) {
  return useQuery<Record<JobStatus, number>>({
    queryKey: jobKeys.statusCounts(),
    queryFn: () => jobsApi.getStatusCounts() as Promise<Record<JobStatus, number>>,
    staleTime: 60_000,
    refetchInterval: 60_000,
    ...options,
  })
}

// ---------------------------------------------------------------------------
// useCreateJob
// ---------------------------------------------------------------------------

export function useCreateJob() {
  const queryClient = useQueryClient()

  return useMutation<Job, Error, JobCreate>({
    mutationFn: (data: JobCreate) => jobsApi.create(data as unknown as Record<string, unknown>) as unknown as Promise<Job>,

    onSuccess: (newJob) => {
      // Invalidate all job lists so they refetch
      queryClient.invalidateQueries({ queryKey: jobKeys.lists() })
      queryClient.invalidateQueries({ queryKey: jobKeys.statusCounts() })

      // Pre-populate the detail cache
      queryClient.setQueryData<Job>(jobKeys.detail(newJob.id), newJob)
    },
  })
}

// ---------------------------------------------------------------------------
// useUpdateJob
// ---------------------------------------------------------------------------

export function useUpdateJob() {
  const queryClient = useQueryClient()

  return useMutation<Job, Error, { id: string; data: JobUpdate }>({
    mutationFn: ({ id, data }) =>
      jobsApi.update(id, data as unknown as Record<string, unknown>) as unknown as Promise<Job>,

    onSuccess: (updatedJob) => {
      // Update the detail cache immediately
      queryClient.setQueryData<Job>(jobKeys.detail(updatedJob.id), updatedJob)

      // Invalidate lists so they pick up changes
      queryClient.invalidateQueries({ queryKey: jobKeys.lists() })
      queryClient.invalidateQueries({ queryKey: jobKeys.statusCounts() })
    },

    // Optimistic update
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: jobKeys.detail(id) })

      const previous = queryClient.getQueryData<Job>(jobKeys.detail(id))

      if (previous) {
        queryClient.setQueryData<Job>(jobKeys.detail(id), {
          ...previous,
          ...(data as Partial<Job>),
          updated_at: new Date().toISOString(),
        })
      }

      return { previous }
    },

    onError: (_err, { id }, context) => {
      // Roll back optimistic update on error
      const ctx = context as { previous?: Job } | undefined
      if (ctx?.previous) {
        queryClient.setQueryData<Job>(jobKeys.detail(id), ctx.previous)
      }
    },
  })
}

// ---------------------------------------------------------------------------
// useUpdateJobStatus
// ---------------------------------------------------------------------------

export function useUpdateJobStatus() {
  const queryClient = useQueryClient()

  return useMutation<Job, Error, { id: string; status: JobStatus; note?: string }>({
    mutationFn: ({ id, status, note }) =>
      jobsApi.updateStatus(id, status, note) as unknown as Promise<Job>,

    onSuccess: (updatedJob) => {
      queryClient.setQueryData<Job>(jobKeys.detail(updatedJob.id), updatedJob)
      queryClient.invalidateQueries({ queryKey: jobKeys.lists() })
      queryClient.invalidateQueries({ queryKey: jobKeys.statusCounts() })
      queryClient.invalidateQueries({ queryKey: jobKeys.timeline(updatedJob.id) })
    },

    // Optimistic status update
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: jobKeys.detail(id) })

      const previous = queryClient.getQueryData<Job>(jobKeys.detail(id))

      if (previous) {
        queryClient.setQueryData<Job>(jobKeys.detail(id), {
          ...previous,
          status,
          updated_at: new Date().toISOString(),
        })
      }

      return { previous }
    },

    onError: (_err, { id }, context) => {
      const ctx = context as { previous?: Job } | undefined
      if (ctx?.previous) {
        queryClient.setQueryData<Job>(jobKeys.detail(id), ctx.previous)
      }
    },
  })
}

// ---------------------------------------------------------------------------
// useDeleteJob
// ---------------------------------------------------------------------------

export function useDeleteJob() {
  const queryClient = useQueryClient()

  return useMutation<void, Error, string>({
    mutationFn: (id: string) => jobsApi.delete(id),

    onSuccess: (_data, id) => {
      // Remove from detail cache
      queryClient.removeQueries({ queryKey: jobKeys.detail(id) })

      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: jobKeys.lists() })
      queryClient.invalidateQueries({ queryKey: jobKeys.statusCounts() })
    },
  })
}

// ---------------------------------------------------------------------------
// useUploadJobDocument
// ---------------------------------------------------------------------------

export function useUploadJobDocument() {
  const queryClient = useQueryClient()

  return useMutation<Job['documents'][number], Error, { jobId: string; file: File; docType?: string }>({
    mutationFn: async ({ jobId, file, docType }) => {
      const formData = new FormData()
      formData.append('file', file)
      if (docType) formData.append('doc_type', docType)
      return jobsApi.uploadDocument(jobId, formData) as unknown as Promise<Job['documents'][number]>
    },

    onSuccess: (_data, { jobId }) => {
      queryClient.invalidateQueries({ queryKey: jobKeys.detail(jobId) })
      queryClient.invalidateQueries({ queryKey: jobKeys.documents(jobId) })
    },
  })
}

// ---------------------------------------------------------------------------
// useDeleteJobDocument
// ---------------------------------------------------------------------------

export function useDeleteJobDocument() {
  const queryClient = useQueryClient()

  return useMutation<void, Error, { jobId: string; docId: string }>({
    mutationFn: ({ jobId, docId }) => jobsApi.deleteDocument(jobId, docId),

    onSuccess: (_data, { jobId }) => {
      queryClient.invalidateQueries({ queryKey: jobKeys.detail(jobId) })
      queryClient.invalidateQueries({ queryKey: jobKeys.documents(jobId) })
    },
  })
}

// ---------------------------------------------------------------------------
// Helper — derive kanban columns from a job list
// ---------------------------------------------------------------------------

export const JOB_STATUS_COLUMNS: Array<{
  status: JobStatus
  label: string
  color: string
  bgColor: string
}> = [
  { status: 'draft',       label: 'Draft',       color: 'text-slate-400', bgColor: 'bg-slate-700' },
  { status: 'confirmed',   label: 'Confirmed',   color: 'text-brand-400',  bgColor: 'bg-brand-900/40' },
  { status: 'dispatched',  label: 'Dispatched',  color: 'text-violet-400',bgColor: 'bg-violet-900/40' },
  { status: 'in_progress', label: 'In Progress', color: 'text-amber-400', bgColor: 'bg-amber-900/40' },
  { status: 'completed',   label: 'Completed',   color: 'text-green-400', bgColor: 'bg-green-900/40' },
  { status: 'invoiced',    label: 'Invoiced',    color: 'text-purple-400',bgColor: 'bg-purple-900/40' },
]

export function groupJobsByStatus(jobs: Job[]): Record<JobStatus, Job[]> {
  const groups = {} as Record<JobStatus, Job[]>

  for (const col of JOB_STATUS_COLUMNS) {
    groups[col.status] = []
  }

  for (const job of jobs) {
    if (groups[job.status]) {
      groups[job.status].push(job)
    }
  }

  return groups
}

export function statusCountsFromList(jobs: Job[]): JobStatusCount[] {
  const counts = groupJobsByStatus(jobs)
  return JOB_STATUS_COLUMNS.map((col) => ({
    status: col.status,
    count: counts[col.status].length,
  }))
}
