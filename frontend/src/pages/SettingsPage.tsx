import { useState, useEffect } from "react";
import { getSystemStatus, type SystemStatus } from "../lib/api";

export default function SettingsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStatus() {
      try {
        const data = await getSystemStatus();
        setStatus(data);
      } catch (err) {
        console.error("Failed to fetch system status:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchStatus();
  }, []);

  if (loading) {
    return <div className="text-center py-12 text-muted-foreground">Loading system status...</div>;
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">System Configuration</h1>

      {/* System Readiness */}
      <div className="rounded-lg border p-4 mb-6">
        <div className="flex items-center space-x-3 mb-4">
          <div
            className={`w-3 h-3 rounded-full ${
              status?.ready ? "bg-green-500" : "bg-red-500"
            }`}
          />
          <h2 className="font-semibold">
            System {status?.ready ? "Ready" : "Not Ready"}
          </h2>
        </div>

        {!status?.ready && (
          <p className="text-sm text-muted-foreground mb-4">
            Resolve the issues below before submitting jobs.
          </p>
        )}
      </div>

      {/* GPU Status */}
      <div className="rounded-lg border p-4 mb-6">
        <h2 className="font-semibold mb-3">GPU Status</h2>
        {status?.gpus && status.gpus.length > 0 ? (
          <div className="space-y-3">
            {status.gpus.map((gpu) => (
              <div key={gpu.index} className="bg-muted rounded p-3">
                <div className="flex justify-between items-center">
                  <span className="font-medium text-sm">
                    GPU {gpu.index}: {gpu.name}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {gpu.utilization_percent}% utilized
                  </span>
                </div>
                <div className="mt-2">
                  <div className="flex justify-between text-xs text-muted-foreground mb-1">
                    <span>
                      Memory: {gpu.memory_used_mb}MB / {gpu.memory_total_mb}MB
                    </span>
                    <span>{gpu.memory_free_mb}MB free</span>
                  </div>
                  <div className="w-full bg-background rounded-full h-2">
                    <div
                      className="bg-primary h-2 rounded-full"
                      style={{
                        width: `${(gpu.memory_used_mb / gpu.memory_total_mb) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-destructive">
            No GPUs detected. mBER requires an NVIDIA GPU with 32GB+ VRAM.
          </p>
        )}
      </div>

      {/* Model Weights */}
      <div className="rounded-lg border p-4 mb-6">
        <h2 className="font-semibold mb-3">Model Weights</h2>
        {status?.weights ? (
          <div className="space-y-2 text-sm">
            <div className="flex items-center space-x-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  status.weights.ready ? "bg-green-500" : "bg-red-500"
                }`}
              />
              <span>
                {status.weights.ready
                  ? `Weights loaded (${status.weights.size_gb} GB)`
                  : "Weights not found or incomplete"}
              </span>
            </div>
            <p className="text-muted-foreground">Path: {status.weights.path}</p>
          </div>
        ) : null}
      </div>

      {/* CLI Status */}
      <div className="rounded-lg border p-4 mb-6">
        <h2 className="font-semibold mb-3">mBER CLI</h2>
        {status?.cli ? (
          <div className="space-y-2 text-sm">
            <div className="flex items-center space-x-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  status.cli.available ? "bg-green-500" : "bg-red-500"
                }`}
              />
              <span>
                {status.cli.available
                  ? "mber-vhh CLI available"
                  : "mber-vhh CLI not found"}
              </span>
            </div>
            <p className="text-muted-foreground">
              Repo: {status.cli.repo_path}{" "}
              {status.cli.repo_exists ? "✓" : "✗ not found"}
            </p>
          </div>
        ) : null}
      </div>

      {/* Configuration Note */}
      <div className="rounded-lg border p-4 bg-muted/50">
        <h2 className="font-semibold mb-2">Configuration</h2>
        <p className="text-sm text-muted-foreground">
          Server configuration is managed via environment variables or the{" "}
          <code className="bg-background px-1 rounded">.env</code> file in the
          backend directory. See{" "}
          <code className="bg-background px-1 rounded">.env.example</code> for
          available options.
        </p>
      </div>
    </div>
  );
}
