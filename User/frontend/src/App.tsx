import { useEffect, useMemo, useRef, useState } from "react";

type StepStatus = {
  name: string;
  status: "ready" | "pending" | "error";
  details?: string;
};

type CreateResponse = {
  id: string;
  namespace: string;
  accessPath: string;
  gatewayAuthToken: string;
};

type StatusResponse = {
  id: string;
  namespace: string;
  accessPath: string;
  steps: StepStatus[];
  podPhase: string;
  ready: boolean;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "";
const STORAGE_KEY = "openclaw.user.last";

export default function App() {
  const [userId, setUserId] = useState("");
  const [telegramBotToken, setTelegramBotToken] = useState("");
  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [created, setCreated] = useState<CreateResponse | null>(null);
  const [steps, setSteps] = useState<StepStatus[]>([]);
  const [podPhase, setPodPhase] = useState("Pending");
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [gatewayToken, setGatewayToken] = useState<string | null>(null);
  const [statusInfo, setStatusInfo] = useState<StatusResponse | null>(null);
  const pollRef = useRef<number | null>(null);

  const activeId = useMemo(() => created?.id ?? statusInfo?.id ?? "", [created, statusInfo]);

  useEffect(() => {
    const cached = localStorage.getItem(STORAGE_KEY);
    if (!cached) {
      return;
    }
    try {
      const parsed = JSON.parse(cached) as { id: string };
      if (parsed?.id) {
        setUserId(parsed.id);
        void refreshStatus(parsed.id);
        void fetchSecret(parsed.id);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (!activeId || !isPolling) {
      return;
    }
    const interval = window.setInterval(() => {
      void refreshStatus(activeId);
    }, 2500);
    pollRef.current = interval;
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
      }
    };
  }, [activeId, isPolling]);

  async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.error ?? "Request failed");
    }
    return data as T;
  }

  async function handleCreate() {
    setError(null);
    setIsCreating(true);
    setReady(false);
    setSteps([]);
    setPodPhase("Pending");
    setGatewayToken(null);
    try {
      const payload = {
        userId,
        telegramBotToken,
        openaiApiKey,
      };
      const response = await apiFetch<CreateResponse>("/api/pods", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setCreated(response);
      setGatewayToken(response.gatewayAuthToken);
      setIsPolling(true);
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ id: response.id }));
      await refreshStatus(response.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create pod");
    } finally {
      setIsCreating(false);
    }
  }

  async function refreshStatus(id: string) {
    try {
      const response = await apiFetch<StatusResponse>(`/api/pods/${id}/status`);
      setStatusInfo(response);
      setSteps(response.steps ?? []);
      setPodPhase(response.podPhase ?? "Pending");
      setReady(response.ready);
      if (response.ready) {
        setIsPolling(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch status");
    }
  }

  async function fetchSecret(id: string) {
    try {
      const response = await apiFetch<{ gatewayAuthToken: string }>(`/api/pods/${id}/secret`);
      setGatewayToken(response.gatewayAuthToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch gateway token");
    }
  }

  async function handleRetry() {
    if (!userId || !telegramBotToken || !openaiApiKey) {
      setError("Please fill user id, Telegram token, and OpenAI key before retrying.");
      return;
    }
    await handleCreate();
  }

  return (
    <div className="page">
      <header className="hero">
        <div className="hero__content">
          <p className="eyebrow">OpenClaw User Pods</p>
          <h1>Launch your personal OpenClaw pod</h1>
          <p className="lead">
            Create a fully isolated OpenClaw environment with MCP, skills, and tools. Each user gets
            a dedicated namespace, storage, and gateway token.
          </p>
        </div>
        <div className="hero__panel">
          <div className="panel__glow" />
          <div className="panel__inner">
            <h2>Creation details</h2>
            <div className="field">
              <label>User ID</label>
              <input
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
                placeholder="user-123"
              />
            </div>
            <div className="field">
              <label>Telegram Bot Token</label>
              <input
                value={telegramBotToken}
                onChange={(event) => setTelegramBotToken(event.target.value)}
                placeholder="123456:ABC..."
                type="password"
              />
            </div>
            <div className="field">
              <label>OpenAI API Key</label>
              <input
                value={openaiApiKey}
                onChange={(event) => setOpenaiApiKey(event.target.value)}
                placeholder="sk-..."
                type="password"
              />
            </div>
            <div className="actions">
              <button className="primary" onClick={handleCreate} disabled={isCreating}>
                {isCreating ? "Creating..." : "Create Pod"}
              </button>
              <button className="secondary" onClick={handleRetry}>
                Retry
              </button>
            </div>
            {error ? <p className="error">{error}</p> : null}
          </div>
        </div>
      </header>

      <section className="status">
        <div className="status__card">
          <div className="status__header">
            <h3>Status</h3>
            <span className={`badge ${ready ? "ready" : "pending"}`}>
              {ready ? "Ready" : "Provisioning"}
            </span>
          </div>
          <div className="status__meta">
            <div>
              <p className="meta-label">Pod phase</p>
              <p className="meta-value">{podPhase}</p>
            </div>
            <div>
              <p className="meta-label">Namespace</p>
              <p className="meta-value">{statusInfo?.namespace ?? created?.namespace ?? "-"}</p>
            </div>
            <div>
              <p className="meta-label">Access path</p>
              <p className="meta-value">{statusInfo?.accessPath ?? created?.accessPath ?? "-"}</p>
            </div>
          </div>
          <div className="steps">
            {steps.length === 0 ? (
              <p className="muted">No status yet. Create a pod to begin.</p>
            ) : (
              steps.map((step) => (
                <div key={step.name} className={`step ${step.status}`}>
                  <span>{step.name}</span>
                  <span className="step__status">{step.details ?? step.status}</span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="status__card">
          <div className="status__header">
            <h3>Gateway token</h3>
            <button
              className="ghost"
              onClick={() => activeId && fetchSecret(activeId)}
              disabled={!activeId}
            >
              Refresh
            </button>
          </div>
          <p className="muted">Use this token to access the gateway. It remains available here.</p>
          <div className="token">
            <code>{gatewayToken ?? "-"}</code>
          </div>
        </div>
      </section>
    </div>
  );
}
