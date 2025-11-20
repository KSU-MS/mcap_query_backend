# Frontend Integration Guide - Job Status & Queue Info

This guide shows how to implement job status and queue monitoring in your frontend.

## API Endpoints

### 1. Get All Job Statuses
- **URL:** `GET /api/mcap-logs/job-statuses/`
- **Query Params:** `?status=pending|processing|completed|error`
- **Returns:** List of all jobs with their statuses

### 2. Get Single Job Status
- **URL:** `GET /api/mcap-logs/{id}/job-status/`
- **Returns:** Detailed status for a specific job

## Status Values

- `pending` - Job queued, waiting to start
- `processing` - Job currently running
- `completed` - Job finished successfully
- `error: <message>` - Job failed with error message

## Implementation Examples

### React/TypeScript Implementation

#### 1. API Service Layer

```typescript
// services/api.ts
const API_BASE_URL = 'http://localhost:8000/api';

export interface JobStatus {
  log_id: number;
  file_name: string;
  parse_status: 'pending' | 'processing' | 'completed' | string;
  parse_task_id: string | null;
  created_at: string;
  task_state: string | null;
  task_ready?: boolean;
}

export interface JobStatusResponse {
  count: number;
  results: JobStatus[];
}

export interface SingleJobStatus extends JobStatus {
  task_info?: {
    ready: boolean;
    successful: boolean | null;
    failed: boolean | null;
    result?: string;
    error?: string;
  };
}

// Get all job statuses
export async function getAllJobStatuses(
  statusFilter?: 'pending' | 'processing' | 'completed' | 'error'
): Promise<JobStatusResponse> {
  const url = statusFilter
    ? `${API_BASE_URL}/mcap-logs/job-statuses/?status=${statusFilter}`
    : `${API_BASE_URL}/mcap-logs/job-statuses/`;
  
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch job statuses: ${response.statusText}`);
  }
  return response.json();
}

// Get single job status
export async function getJobStatus(logId: number): Promise<SingleJobStatus> {
  const response = await fetch(`${API_BASE_URL}/mcap-logs/${logId}/job-status/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch job status: ${response.statusText}`);
  }
  return response.json();
}
```

#### 2. React Hook for Polling Job Statuses

```typescript
// hooks/useJobStatuses.ts
import { useState, useEffect, useCallback, useRef } from 'react';
import { getAllJobStatuses, JobStatus } from '../services/api';

interface UseJobStatusesOptions {
  pollInterval?: number; // milliseconds
  statusFilter?: 'pending' | 'processing' | 'completed' | 'error';
  autoPoll?: boolean;
  showAll?: boolean; // Show all jobs including completed ones
}

export function useJobStatuses(options: UseJobStatusesOptions = {}) {
  const {
    pollInterval = 1000, // Poll every 1 second for faster updates
    statusFilter,
    autoPoll = true,
    showAll = true, // Show all jobs by default
  } = options;

  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      setError(null);
      // Don't filter by status if showAll is true - get everything
      const filter = showAll ? undefined : statusFilter;
      const data = await getAllJobStatuses(filter);
      setJobs(data.results);
      setLoading(false);
    } catch (err) {
      setError(err as Error);
      setLoading(false);
    }
  }, [statusFilter, showAll]);

  useEffect(() => {
    fetchJobs();

    if (!autoPoll) return;

    // Clear any existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    // Start polling
    intervalRef.current = setInterval(() => {
      fetchJobs();
    }, pollInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchJobs, pollInterval, autoPoll]);

  // Check if there are any active jobs (pending or processing)
  const hasActiveJobs = jobs.some(
    (job) => job.parse_status === 'pending' || job.parse_status === 'processing'
  );

  // Group jobs by status for easier display
  const jobsByStatus = {
    pending: jobs.filter(j => j.parse_status === 'pending'),
    processing: jobs.filter(j => j.parse_status === 'processing'),
    completed: jobs.filter(j => j.parse_status === 'completed'),
    error: jobs.filter(j => j.parse_status?.startsWith('error')),
  };

  return {
    jobs,
    loading,
    error,
    refetch: fetchJobs,
    hasActiveJobs,
    jobsByStatus,
    stats: {
      total: jobs.length,
      pending: jobsByStatus.pending.length,
      processing: jobsByStatus.processing.length,
      completed: jobsByStatus.completed.length,
      error: jobsByStatus.error.length,
    },
  };
}
```

#### 3. React Hook for Single Job Status

```typescript
// hooks/useJobStatus.ts
import { useState, useEffect, useCallback } from 'react';
import { getJobStatus, SingleJobStatus } from '../services/api';

interface UseJobStatusOptions {
  logId: number;
  pollInterval?: number;
  autoPoll?: boolean;
}

export function useJobStatus(options: UseJobStatusOptions) {
  const { logId, pollInterval = 2000, autoPoll = true } = options;

  const [job, setJob] = useState<SingleJobStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchJob = useCallback(async () => {
    try {
      setError(null);
      const data = await getJobStatus(logId);
      setJob(data);
      setLoading(false);
    } catch (err) {
      setError(err as Error);
      setLoading(false);
    }
  }, [logId]);

  useEffect(() => {
    if (!logId) return;
    
    fetchJob();

    if (!autoPoll) return;

    const interval = setInterval(() => {
      fetchJob();
    }, pollInterval);

    // Stop polling when job is completed or failed
    const shouldStopPolling = 
      job?.parse_status === 'completed' || 
      job?.parse_status?.startsWith('error');

    if (shouldStopPolling) {
      clearInterval(interval);
    }

    return () => clearInterval(interval);
  }, [fetchJob, pollInterval, autoPoll, job?.parse_status]);

  return {
    job,
    loading,
    error,
    refetch: fetchJob,
    isComplete: job?.parse_status === 'completed',
    isError: job?.parse_status?.startsWith('error'),
    isProcessing: job?.parse_status === 'processing' || job?.parse_status === 'pending',
  };
}
```

#### 4. Job Queue Component (Improved)

```tsx
// components/JobQueue.tsx
import React, { useState } from 'react';
import { useJobStatuses } from '../hooks/useJobStatuses';

export function JobQueue() {
  const [showCompleted, setShowCompleted] = useState(true);
  
  const { 
    jobs, 
    loading, 
    error, 
    hasActiveJobs, 
    jobsByStatus,
    stats 
  } = useJobStatuses({
    pollInterval: 1000, // Poll every 1 second for faster updates
    autoPoll: true,
    showAll: true, // Show all jobs including completed
  });

  // Helper functions (define outside component or in utils)
  const getStatusColor = (status: string) => {
    if (status === 'completed') return 'text-green-600';
    if (status === 'processing') return 'text-blue-600';
    if (status === 'pending') return 'text-yellow-600';
    if (status.startsWith('error')) return 'text-red-600';
    return 'text-gray-600';
  };

  const getStatusBadge = (status: string) => {
    if (status === 'completed') return '✅ Completed';
    if (status === 'processing') return '⏳ Processing';
    if (status === 'pending') return '⏸️ Pending';
    if (status.startsWith('error')) return '❌ Error';
    return status;
  };

  if (loading) {
    return <div>Loading job queue...</div>;
  }

  if (error) {
    return <div className="text-red-600">Error: {error.message}</div>;
  }

  // Filter jobs to show based on toggle
  const jobsToShow = showCompleted 
    ? jobs 
    : jobs.filter(j => j.parse_status !== 'completed');

  return (
    <div className="job-queue">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold">Job Queue</h2>
        <div className="flex items-center gap-4">
          {/* Status Summary */}
          <div className="flex gap-2 text-sm">
            {stats.pending > 0 && (
              <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded">
                {stats.pending} Pending
              </span>
            )}
            {stats.processing > 0 && (
              <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded">
                {stats.processing} Processing
              </span>
            )}
            {stats.completed > 0 && (
              <span className="px-2 py-1 bg-green-100 text-green-800 rounded">
                {stats.completed} Completed
              </span>
            )}
            {stats.error > 0 && (
              <span className="px-2 py-1 bg-red-100 text-red-800 rounded">
                {stats.error} Errors
              </span>
            )}
          </div>
          
          {/* Toggle to show/hide completed */}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={showCompleted}
              onChange={(e) => setShowCompleted(e.target.checked)}
              className="rounded"
            />
            Show completed
          </label>
        </div>
      </div>

      {/* Active Jobs Section */}
      {(stats.pending > 0 || stats.processing > 0) && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-2">Active Jobs</h3>
          <div className="space-y-2">
            {[...jobsByStatus.pending, ...jobsByStatus.processing].map((job) => (
              <JobItem key={job.log_id} job={job} />
            ))}
          </div>
        </div>
      )}

      {/* All Jobs Section */}
      <div>
        <h3 className="text-lg font-semibold mb-2">
          All Jobs {showCompleted ? `(${jobs.length})` : `(${jobsToShow.length})`}
        </h3>
        <div className="space-y-2">
          {jobsToShow.length === 0 ? (
            <div className="text-gray-500 text-center py-8">
              No jobs found
            </div>
          ) : (
            jobsToShow.map((job) => (
              <JobItem key={job.log_id} job={job} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

// Separate Job Item Component
function JobItem({ job }: { job: JobStatus }) {
  return (
    <div className="border rounded-lg p-4 hover:bg-gray-50 transition-colors">
      <div className="flex justify-between items-start">
        <div className="flex-1 min-w-0">
          <div className="font-medium truncate">{job.file_name}</div>
          <div className="text-sm text-gray-600 mt-1">
            ID: {job.log_id} • Created: {new Date(job.created_at).toLocaleString()}
          </div>
        </div>
        <div className="ml-4 text-right flex-shrink-0">
          <div className={`font-semibold ${getStatusColor(job.parse_status)}`}>
            {getStatusBadge(job.parse_status)}
          </div>
          {job.task_state && (
            <div className="text-xs text-gray-500 mt-1">
              {job.task_state}
            </div>
          )}
          {(job.parse_status === 'pending' || job.parse_status === 'processing') && (
            <div className="mt-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mx-auto"></div>
            </div>
          )}
        </div>
      </div>
      
      {job.parse_status?.startsWith('error') && (
        <div className="mt-2 text-sm text-red-600 bg-red-50 p-2 rounded">
          Error: {job.parse_status}
        </div>
      )}
    </div>
  );
}
```

#### 5. Single Job Status Component

```tsx
// components/JobStatusCard.tsx
import React from 'react';
import { useJobStatus } from '../hooks/useJobStatus';

interface JobStatusCardProps {
  logId: number;
}

export function JobStatusCard({ logId }: JobStatusCardProps) {
  const { job, loading, error, isComplete, isError, isProcessing } = useJobStatus({
    logId,
    pollInterval: 2000,
    autoPoll: isProcessing, // Only poll if still processing
  });

  if (loading) {
    return <div>Loading job status...</div>;
  }

  if (error || !job) {
    return <div className="text-red-600">Error loading job status</div>;
  }

  return (
    <div className="border rounded-lg p-4">
      <div className="flex justify-between items-center mb-2">
        <h3 className="font-semibold">{job.file_name}</h3>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
          isComplete ? 'bg-green-100 text-green-800' :
          isError ? 'bg-red-100 text-red-800' :
          isProcessing ? 'bg-blue-100 text-blue-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {job.parse_status}
        </span>
      </div>

      <div className="space-y-1 text-sm text-gray-600">
        <div>Job ID: {job.log_id}</div>
        {job.parse_task_id && (
          <div>Task ID: {job.parse_task_id.substring(0, 20)}...</div>
        )}
        {job.task_state && (
          <div>Task State: {job.task_state}</div>
        )}
        {job.task_info && (
          <div className="mt-2 p-2 bg-gray-50 rounded">
            <div>Ready: {job.task_info.ready ? 'Yes' : 'No'}</div>
            {job.task_info.error && (
              <div className="text-red-600 mt-1">Error: {job.task_info.error}</div>
            )}
          </div>
        )}
      </div>

      {isProcessing && (
        <div className="mt-3">
          <div className="flex items-center space-x-2">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
            <span className="text-sm text-blue-600">Processing...</span>
          </div>
        </div>
      )}
    </div>
  );
}
```

#### 6. Usage Example

```tsx
// pages/UploadPage.tsx
import React, { useState } from 'react';
import { JobQueue } from '../components/JobQueue';
import { JobStatusCard } from '../components/JobStatusCard';

export function UploadPage() {
  const [uploadedLogIds, setUploadedLogIds] = useState<number[]>([]);

  const handleBatchUpload = async (files: FileList) => {
    const formData = new FormData();
    Array.from(files).forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await fetch('http://localhost:8000/api/mcap-logs/batch-upload/', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      
      // Store the uploaded log IDs to show their status
      const ids = data.results
        .filter((r: any) => r.id)
        .map((r: any) => r.id);
      setUploadedLogIds(ids);
    } catch (error) {
      console.error('Upload failed:', error);
    }
  };

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">MCAP File Upload</h1>
      
      <input
        type="file"
        multiple
        accept=".mcap"
        onChange={(e) => {
          if (e.target.files) {
            handleBatchUpload(e.target.files);
          }
        }}
        className="mb-4"
      />

      {/* Show status of recently uploaded files */}
      {uploadedLogIds.length > 0 && (
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-2">Recently Uploaded</h2>
          <div className="space-y-2">
            {uploadedLogIds.map(id => (
              <JobStatusCard key={id} logId={id} />
            ))}
          </div>
        </div>
      )}

      {/* Show all jobs in queue */}
      <JobQueue />
    </div>
  );
}
```

## Best Practices

1. **Polling Intervals:**
   - **Active jobs (pending/processing): Poll every 1 second** - Jobs complete quickly, so frequent polling is needed
   - Completed jobs: Can reduce to every 5-10 seconds or stop polling
   - Use exponential backoff for errors
   - **Important:** With 20 files processing in parallel, jobs may complete in seconds, so 1-second polling is recommended

2. **Stop Polling When Done:**
   ```typescript
   // Stop polling when job is complete
   const shouldPoll = job?.parse_status === 'pending' || 
                      job?.parse_status === 'processing';
   
   // But keep showing completed jobs for a few minutes
   // so users can see what was processed
   ```
   
3. **Show All Statuses:**
   - Always show pending/processing jobs prominently
   - Group jobs by status (pending, processing, completed, error)
   - Allow users to toggle showing completed jobs
   - Display status counts/summary at the top

4. **Error Handling:**
   - Show user-friendly error messages
   - Retry failed requests with exponential backoff
   - Log errors for debugging

5. **Performance:**
   - Only poll jobs that are active (pending/processing)
   - Use React Query or SWR for better caching
   - Debounce rapid status updates

6. **User Experience:**
   - Show loading states immediately
   - Display progress indicators for active jobs
   - Group jobs by status for better visibility
   - Show status summary (X pending, Y processing, Z completed)
   - Allow filtering/toggling completed jobs
   - Notify when jobs complete (toast/notification)
   - Show timestamps for when jobs were created/completed
   - Show loading states
   - Display progress indicators
   - Notify when jobs complete
   - Allow manual refresh

## Alternative: Using React Query

```typescript
import { useQuery } from '@tanstack/react-query';

export function useJobStatusesQuery(statusFilter?: string) {
  return useQuery({
    queryKey: ['job-statuses', statusFilter],
    queryFn: () => getAllJobStatuses(statusFilter),
    refetchInterval: (query) => {
      // Only poll if there are active jobs
      const jobs = query.state.data?.results || [];
      const hasActive = jobs.some(
        j => j.parse_status === 'pending' || j.parse_status === 'processing'
      );
      return hasActive ? 2000 : false; // Poll every 2s if active, otherwise stop
    },
  });
}
```

This provides better caching, automatic refetching, and error handling out of the box.

