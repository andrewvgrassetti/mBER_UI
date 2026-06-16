import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight } from "lucide-react";
import { listJobs, cancelJob, retryJob, type JobListItem } from "../lib/api";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-800",
};

type FilterTab = "all" | "active" | "completed" | "failed";

const FILTER_TABS: { key: FilterTab; label: string }[] = [
  { key: "all", label: "All" },
  { key: "active", label: "Active" },
  { key: "completed", label: "Completed" },
  { key: "failed", label: "Failed" },
];

function filterJobs(jobs: JobListItem[], filter: FilterTab): JobListItem[] {
  switch (filter) {
    case "active":
      return jobs.filter((j) => j.status === "running" || j.status === "pending");
    case "completed":
      return jobs.filter((j) => j.status === "completed");
    case "failed":
      return jobs.filter((j) => j.status === "failed" || j.status === "cancelled");
    case "all":
    default:
      return jobs;
  }
}

function countByFilter(jobs: JobListItem[], filter: FilterTab): number {
  return filterJobs(jobs, filter).length;
}

function CollapsibleError({ message }: { message: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center space-x-1 text-xs font-medium text-red-700 dark:text-red-300 hover:underline"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <span>Error details</span>
      </button>
      {open && (
        <div className="mt-1 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <pre className="font-mono text-xs text-red-800 dark:text-red-200 whitespace-pre-wrap">
            {message}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<FilterTab>("active");

  async function fetchJobs() {
    try {
      const data = await listJobs();
      setJobs(data);
    } catch (err) {
      console.error("Failed to fetch jobs:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, []);

  async function handleCancel(jobId: string) {
    if (confirm("Cancel this job?")) {
      await cancelJob(jobId);
      fetchJobs();
    }
  }

  async function handleRetry(jobId: string) {
    try {
      await retryJob(jobId);
      fetchJobs();
    } catch (err) {
      console.error("Failed to retry job:", err);
    }
  }

  if (loading) {
    return <div className="text-center py-12 text-muted-foreground">Loading jobs...</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Job Dashboard</h1>
        <Link
          to="/"
          className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
        >
          + New Job
        </Link>
      </div>

      {jobs.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p>No jobs yet.</p>
          <Link to="/" className="text-primary hover:underline">
            Submit your first design job
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex space-x-2 mb-4">
            {FILTER_TABS.map((tab) => {
              const count = countByFilter(jobs, tab.key);
              const isActive = activeFilter === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveFilter(tab.key)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "border hover:bg-accent"
                  }`}
                >
                  {tab.label}{" "}
                  <span
                    className={`inline-flex items-center justify-center rounded-full px-1.5 py-0.5 text-xs ${
                      isActive
                        ? "bg-primary-foreground/20 text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
          {filterJobs(jobs, activeFilter).map((job) => (
            <div
              key={job.id}
              className="rounded-lg border p-4 flex items-center justify-between"
            >
              <div className="flex-1">
                <div className="flex items-center space-x-3">
                  <span className="font-medium">{job.target_name}</span>
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      STATUS_COLORS[job.status] || ""
                    }`}
                  >
                    {job.status}
                  </span>
                </div>
                <div className="text-sm text-muted-foreground mt-1">
                  ID: {job.id} • Created:{" "}
                  {new Date(job.created_at).toLocaleString()}
                </div>
                {/* Progress bar */}
                {(job.status === "running" || job.status === "completed") && (
                  <div className="mt-2">
                    <div className="flex justify-between text-xs text-muted-foreground mb-1">
                      <span>
                        {job.progress.accepted_count} /{" "}
                        {job.progress.target_accepted} accepted
                      </span>
                      <span>
                        {job.progress.total_trajectories} trajectories
                      </span>
                    </div>
                    <div className="w-full bg-secondary rounded-full h-2">
                      <div
                        className="bg-primary h-2 rounded-full transition-all"
                        style={{
                          width: `${Math.min(
                            100,
                            (job.progress.accepted_count /
                              job.progress.target_accepted) *
                              100
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
                {/* Error message for failed jobs */}
                {job.status === "failed" && job.error_message && (
                  <CollapsibleError message={job.error_message} />
                )}
              </div>

              <div className="flex items-center space-x-2 ml-4">
                {job.status === "completed" && (
                  <Link
                    to={`/jobs/${job.id}/results`}
                    className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent"
                  >
                    View Results
                  </Link>
                )}
                {job.status === "running" && (
                  <>
                    <Link
                      to={`/jobs/${job.id}/results`}
                      className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent"
                    >
                      Monitor
                    </Link>
                    <button
                      onClick={() => handleCancel(job.id)}
                      className="rounded-md border border-destructive/30 px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10"
                    >
                      Cancel
                    </button>
                  </>
                )}
                {(job.status === "failed" || job.status === "cancelled") && (
                  <button
                    onClick={() => handleRetry(job.id)}
                    className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent"
                  >
                    Retry
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
