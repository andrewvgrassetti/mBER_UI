/**API client for communicating with the mBER backend. */

const API_BASE = "/api";

export interface JobListItem {
  id: string;
  target_name: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  created_at: string;
  error_message: string | null;
  progress: {
    accepted_count: number;
    total_trajectories: number;
    target_accepted: number;
    max_trajectories: number;
  };
}

export interface JobDetail extends JobListItem {
  updated_at: string;
  error_message: string | null;
  settings_path: string | null;
  output_dir: string | null;
}

export interface DesignResult {
  index: number;
  sequence: string;
  iptm: number;
  plddt: number;
  pdb_filename: string | null;
  additional_metrics: Record<string, string>;
}

export interface SystemStatus {
  ready: boolean;
  gpus: Array<{
    index: number;
    name: string;
    memory_total_mb: number;
    memory_used_mb: number;
    memory_free_mb: number;
    utilization_percent: number;
  }>;
  weights: {
    path: string;
    exists: boolean;
    size_gb: number;
    ready: boolean;
  };
  cli: {
    cli_path: string;
    available: boolean;
    repo_path: string;
    repo_exists: boolean;
  };
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Request failed");
  }
  return response.json();
}

export async function submitJob(formData: FormData): Promise<{ job_id: string }> {
  const response = await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Submission failed" }));
    throw new Error(error.detail);
  }
  return response.json();
}

export async function listJobs(): Promise<JobListItem[]> {
  return request<JobListItem[]>("/jobs");
}

export async function getJob(jobId: string): Promise<JobDetail> {
  return request<JobDetail>(`/jobs/${jobId}`);
}

export async function getResults(jobId: string): Promise<DesignResult[]> {
  return request<DesignResult[]>(`/jobs/${jobId}/results`);
}

export async function getJobLog(jobId: string): Promise<{ log: string }> {
  return request<{ log: string }>(`/jobs/${jobId}/log`);
}

export async function cancelJob(jobId: string): Promise<void> {
  await request(`/jobs/${jobId}`, { method: "DELETE" });
}

export async function retryJob(jobId: string): Promise<{ job_id: string; status: string }> {
  return request<{ job_id: string; status: string }>(`/jobs/${jobId}/retry`, { method: "POST" });
}

export async function getSystemStatus(): Promise<SystemStatus> {
  return request<SystemStatus>("/system/status");
}

export function getFileUrl(jobId: string, filename: string): string {
  return `${API_BASE}/jobs/${jobId}/files/${filename}`;
}

export function createJobStream(jobId: string): WebSocket {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return new WebSocket(`${protocol}//${window.location.host}/ws/jobs/${jobId}/stream`);
}
