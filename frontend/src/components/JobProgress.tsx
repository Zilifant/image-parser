import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { api } from '../api/client'

export default function JobProgress({
  jobId,
  label,
  onDone,
}: {
  jobId: string
  label: string
  onDone: () => void
}) {
  const { data: job } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.getJob(jobId),
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 500 : false),
  })

  const status = job?.status
  useEffect(() => {
    if (status === 'done') onDone()
  }, [status, onDone])

  if (!job) return null
  if (job.status === 'error') return <span className="error-text">{label} failed: {job.error}</span>

  const percent = job.total > 0 ? Math.round((100 * job.done) / job.total) : 0
  return (
    <span className="row">
      <span className="hint">
        {label} {job.status === 'done' ? 'done' : `${job.done}/${job.total}`}
      </span>
      <span className="progress">
        <div style={{ width: `${job.status === 'done' ? 100 : percent}%` }} />
      </span>
    </span>
  )
}
