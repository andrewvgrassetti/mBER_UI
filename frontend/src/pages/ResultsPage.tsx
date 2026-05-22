import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { getJob, getResults, getFileUrl, type JobDetail, type DesignResult } from "../lib/api";
import { useJobStream } from "../hooks/useJobStream";

type SortField = "iptm" | "plddt" | "index";

export default function ResultsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [results, setResults] = useState<DesignResult[]>([]);
  const [sortField, setSortField] = useState<SortField>("iptm");
  const [sortAsc, setSortAsc] = useState(false);
  const [loading, setLoading] = useState(true);

  const { data: streamData } = useJobStream(
    job?.status === "running" ? jobId! : null
  );

  useEffect(() => {
    if (!jobId) return;

    async function fetchData() {
      try {
        const [jobData, resultsData] = await Promise.all([
          getJob(jobId!),
          getResults(jobId!),
        ]);
        setJob(jobData);
        setResults(resultsData);
      } catch (err) {
        console.error("Failed to fetch results:", err);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
    // Refresh results periodically if job is running
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [jobId]);

  const sortedResults = [...results].sort((a, b) => {
    const mult = sortAsc ? 1 : -1;
    return mult * (a[sortField] - b[sortField]);
  });

  function handleSort(field: SortField) {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  }

  if (loading) {
    return <div className="text-center py-12 text-muted-foreground">Loading results...</div>;
  }

  if (!job) {
    return <div className="text-center py-12 text-destructive">Job not found</div>;
  }

  return (
    <div>
      {/* Job Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{job.target_name} — Results</h1>
        <p className="text-sm text-muted-foreground">
          Job ID: {job.id} • Status: {job.status}
          {job.status === "running" && streamData && (
            <span className="ml-2">
              • {streamData.accepted_count} accepted / {streamData.total_trajectories} trajectories
            </span>
          )}
        </p>
      </div>

      {/* Live Log (if running) */}
      {job.status === "running" && streamData.log && (
        <div className="mb-6 rounded-lg border p-4 bg-card">
          <h2 className="font-semibold mb-2">Live Log</h2>
          <pre className="text-xs font-mono max-h-48 overflow-y-auto whitespace-pre-wrap bg-muted p-3 rounded">
            {streamData.log.slice(-5000)}
          </pre>
        </div>
      )}

      {/* Results Table */}
      {results.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          {job.status === "running"
            ? "Waiting for accepted designs..."
            : "No results available."}
        </div>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  <th
                    className="px-4 py-3 text-left cursor-pointer hover:bg-accent"
                    onClick={() => handleSort("index")}
                  >
                    # {sortField === "index" && (sortAsc ? "↑" : "↓")}
                  </th>
                  <th className="px-4 py-3 text-left">Sequence</th>
                  <th
                    className="px-4 py-3 text-left cursor-pointer hover:bg-accent"
                    onClick={() => handleSort("iptm")}
                  >
                    iPTM {sortField === "iptm" && (sortAsc ? "↑" : "↓")}
                  </th>
                  <th
                    className="px-4 py-3 text-left cursor-pointer hover:bg-accent"
                    onClick={() => handleSort("plddt")}
                  >
                    pLDDT {sortField === "plddt" && (sortAsc ? "↑" : "↓")}
                  </th>
                  <th className="px-4 py-3 text-left">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {sortedResults.map((result) => (
                  <tr key={result.index} className="hover:bg-muted/50">
                    <td className="px-4 py-3">{result.index + 1}</td>
                    <td className="px-4 py-3 font-mono text-xs max-w-xs truncate">
                      {result.sequence}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={
                          result.iptm >= 0.8
                            ? "text-green-600 font-medium"
                            : ""
                        }
                      >
                        {result.iptm.toFixed(3)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={
                          result.plddt >= 0.8
                            ? "text-green-600 font-medium"
                            : ""
                        }
                      >
                        {result.plddt.toFixed(3)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {result.pdb_filename && (
                        <a
                          href={getFileUrl(jobId!, result.pdb_filename)}
                          download
                          className="text-primary hover:underline text-xs"
                        >
                          Download PDB
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Summary */}
      {results.length > 0 && (
        <div className="mt-4 text-sm text-muted-foreground">
          {results.length} designs • Avg iPTM:{" "}
          {(results.reduce((s, r) => s + r.iptm, 0) / results.length).toFixed(3)}{" "}
          • Avg pLDDT:{" "}
          {(results.reduce((s, r) => s + r.plddt, 0) / results.length).toFixed(3)}
        </div>
      )}
    </div>
  );
}
