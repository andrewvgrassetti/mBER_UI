import { useState, useEffect, useCallback, useRef } from "react";
import { createJobStream } from "../lib/api";

interface StreamData {
  status: string;
  accepted_count: number;
  total_trajectories: number;
  log: string;
}

export function useJobStream(jobId: string | null) {
  const [data, setData] = useState<StreamData>({
    status: "pending",
    accepted_count: 0,
    total_trajectories: 0,
    log: "",
  });
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!jobId) return;

    const ws = createJobStream(jobId);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "progress") {
        setData((prev) => ({
          ...prev,
          status: msg.data.status,
          accepted_count: msg.data.accepted_count,
          total_trajectories: msg.data.total_trajectories,
        }));
      } else if (msg.type === "log") {
        setData((prev) => ({
          ...prev,
          log: prev.log + msg.data,
        }));
      } else if (msg.type === "done") {
        setData((prev) => ({ ...prev, status: msg.data.status }));
      }
    };

    return () => {
      ws.close();
    };
  }, [jobId]);

  useEffect(() => {
    const cleanup = connect();
    return cleanup;
  }, [connect]);

  return { data, connected };
}
