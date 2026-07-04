"use client";

import { useState, useEffect, useRef } from "react";

interface LogEntry {
  id: number;
  time: string;
  userId: string;
  endpoint: string;
  statusCode: number;
  statusLabel: string;
  payload?: unknown;
}

// ─── JSON Syntax Highlighter ──────────────────────────────────────────────────
function JsonToken({ value }: { value: unknown }) {
  const lines = JSON.stringify(value, null, 2).split("\n");

  return (
    <pre className="text-xs leading-5 font-mono whitespace-pre-wrap break-all">
      {lines.map((line, i) => {
        const formatted = line.replace(
          /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
          (match) => {
            if (/^"/.test(match)) {
              if (/:$/.test(match)) {
                return `<span class="text-sky-400">${match}</span>`;
              }
              return `<span class="text-emerald-400">${match}</span>`;
            }
            if (/true|false/.test(match)) return `<span class="text-amber-400">${match}</span>`;
            if (/null/.test(match)) return `<span class="text-rose-400">${match}</span>`;
            return `<span class="text-violet-400">${match}</span>`;
          }
        );
        return (
          <div key={i} className="flex">
            <span className="select-none w-8 shrink-0 text-right pr-3 text-zinc-600 text-[10px] leading-5">{i + 1}</span>
            <span dangerouslySetInnerHTML={{ __html: formatted }} />
          </div>
        );
      })}
    </pre>
  );
}

// ─── Memory Ring ──────────────────────────────────────────────────────────────
interface MemoryRingProps {
  usedMB: number;
  totalMB: number;
}

function MemoryRing({ usedMB, totalMB }: MemoryRingProps) {
  const pct = usedMB / totalMB;
  const r = 18;
  const circ = 2 * Math.PI * r;
  const dash = circ * (1 - pct);
  const color = pct > 0.85 ? "#f87171" : pct > 0.65 ? "#fbbf24" : "#34d399";

  return (
    <div className="flex items-center gap-3">
      <svg width="48" height="48" viewBox="0 0 48 48" className="-rotate-90">
        <circle cx="24" cy="24" r={r} fill="none" stroke="#27272a" strokeWidth="4" />
        <circle
          cx="24"
          cy="24"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeDasharray={circ}
          strokeDashoffset={dash}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.6s ease, stroke 0.4s ease" }}
        />
      </svg>
      <div className="leading-tight">
        <div className="text-xs text-zinc-400 uppercase tracking-widest">Memory</div>
        <div className="text-sm font-semibold text-zinc-100 font-mono">
          {usedMB}
          <span className="text-zinc-500 font-normal">/{totalMB} MB</span>
        </div>
        <div className="text-[10px] font-mono" style={{ color }}>
          {Math.round(pct * 100)}% used
        </div>
      </div>
    </div>
  );
}

// ─── Status Badge ─────────────────────────────────────────────────────────────
interface StatusBadgeProps {
  code: number;
  label: string;
}

function StatusBadge({ code, label }: StatusBadgeProps) {
  const colors =
    code === 200
      ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
      : code === 401 || code === 403
      ? "bg-rose-950 text-rose-400 border border-rose-800"
      : code === 429
      ? "bg-amber-950 text-amber-400 border border-amber-800"
      : "bg-red-950 text-red-400 border border-red-800";

  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold leading-none ${colors}`}>
      {code} {label}
    </span>
  );
}

// ─── Log Row ──────────────────────────────────────────────────────────────────
interface LogRowProps {
  entry: LogEntry;
  isSelected: boolean;
  onClick: () => void;
}

function LogRow({ entry, isSelected, onClick }: LogRowProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 border-b border-zinc-800 transition-colors duration-100 group
        ${isSelected ? "bg-zinc-800 border-l-2 border-l-sky-500" : "hover:bg-zinc-900 border-l-2 border-l-transparent"}`}
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className="text-[10px] font-mono text-zinc-500 shrink-0 pt-px">{entry.time.slice(11)}</span>
        <StatusBadge code={entry.statusCode} label={entry.statusLabel} />
      </div>
      <div className="text-[11px] font-mono text-sky-300 truncate">{entry.endpoint}</div>
      <div className="text-[10px] font-mono text-zinc-500 mt-0.5 flex items-center gap-1">
        <span className="text-zinc-600">uid</span>
        <span className="text-zinc-300">{entry.userId}</span>
      </div>
    </button>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function SecureMCPConsole() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [selected, setSelected] = useState<LogEntry | null>(null);
  const [memUsed, setMemUsed] = useState<number>(312);
  const [isLive, setIsLive] = useState<boolean>(true);
  const [filter, setFilter] = useState<string>("ALL");
  const [token, setToken] = useState<string | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Chat UI state
  const [messages, setMessages] = useState<{role: "user" | "model", content: string}[]>([]);
  const [inputMsg, setInputMsg] = useState("");
  const [isChatLoading, setIsChatLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputMsg.trim() || !token || isChatLoading) return;
    
    const userMsg = inputMsg.trim();
    setInputMsg("");
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setIsChatLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          message: userMsg,
          history: messages
        })
      });
      
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
      }
      
      const data = await res.json();
      setMessages(prev => [...prev, { role: "model", content: data.response || "No response received." }]);
    } catch (err: any) {
      console.error(err);
      setMessages(prev => [...prev, { role: "model", content: "Error: " + (err.message || String(err)) }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  // Fetch JWT token on mount
  useEffect(() => {
    const fetchToken = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/token");
        const data = await res.json();
        setToken(data.token);
      } catch (err) {
        console.error("Failed to fetch auth token:", err);
      }
    };
    fetchToken();
  }, []);

  // Live log ingestion from backend
  useEffect(() => {
    if (!isLive || !token) return;

    const fetchLogs = async () => {
      try {
        const response = await fetch("http://localhost:8000/mcp/logs", {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setLogs(data);
      } catch (error) {
        console.error("Error fetching logs from backend:", error);
      }
    };

    // Initial fetch
    fetchLogs();

    const logInterval = setInterval(fetchLogs, 3000);
    const memInterval = setInterval(() => {
      setMemUsed((prev) => {
        const delta = (Math.random() - 0.45) * 8;
        return Math.min(500, Math.max(180, Math.round(prev + delta)));
      });
    }, 1800);

    return () => {
      clearInterval(logInterval);
      clearInterval(memInterval);
    };
  }, [isLive, token]);

  const filtered = filter === "ALL" ? logs : filter === "OK" ? logs.filter((l) => l.statusCode === 200) : logs.filter((l) => l.statusCode !== 200);

  const stats = {
    total: logs.length,
    ok: logs.filter((l) => l.statusCode === 200).length,
    err: logs.filter((l) => l.statusCode !== 200).length,
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>

      {/* ── Header ── */}
      <header className="shrink-0 h-14 flex items-center justify-between px-5 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-sm z-10">
        <div className="flex items-center gap-3">
          {/* Shield icon (inline SVG) */}
          <svg className="w-6 h-6 text-sky-400" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.955 11.955 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
          </svg>
          <div>
            <div className="text-sm font-semibold tracking-tight text-zinc-100">Secure MCP Console</div>
            <div className="text-[10px] text-zinc-500 font-mono tracking-widest uppercase">Model Context Protocol · Monitor</div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Live / Pause toggle */}
          <button
            onClick={() => setIsLive((v) => !v)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-mono border transition-colors
              ${isLive ? "bg-emerald-950 border-emerald-700 text-emerald-400" : "bg-zinc-800 border-zinc-700 text-zinc-400"}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${isLive ? "bg-emerald-400 animate-pulse" : "bg-zinc-500"}`} />
            {isLive ? "LIVE" : "PAUSED"}
          </button>

          <MemoryRing usedMB={memUsed} totalMB={512} />
        </div>
      </header>

      {/* ── Stat bar ── */}
      <div className="shrink-0 flex items-center gap-0 border-b border-zinc-800 bg-zinc-900/40 text-[11px] font-mono">
        {[
          { label: "TOTAL REQUESTS", value: stats.total, color: "text-zinc-300" },
          { label: "SUCCESS", value: stats.ok, color: "text-emerald-400" },
          { label: "ERRORS", value: stats.err, color: "text-rose-400" },
          { label: "ERROR RATE", value: stats.total ? `${((stats.err / stats.total) * 100).toFixed(1)}%` : "0%", color: "text-amber-400" },
        ].map((s, i) => (
          <div key={i} className="flex-1 flex flex-col items-center py-2 border-r border-zinc-800 last:border-r-0">
            <div className="text-zinc-600 tracking-widest text-[9px] uppercase mb-0.5">{s.label}</div>
            <div className={`text-base font-semibold leading-none ${s.color}`}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* ── Main workspace ── */}
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT PANE: Chat UI */}
        <div className="w-1/2 flex flex-col border-r border-zinc-800 bg-zinc-950/50">
          <div className="shrink-0 px-4 py-3 border-b border-zinc-800 bg-zinc-900/50">
            <div className="text-xs font-semibold tracking-wide text-sky-400 uppercase">Interactive Assistant</div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4" style={{ scrollbarWidth: "thin", scrollbarColor: "#3f3f46 transparent" }}>
            {messages.length === 0 && (
              <div className="text-zinc-500 text-sm font-mono text-center mt-10">
                Type a message to begin the conversation...
              </div>
            )}
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm font-mono whitespace-pre-wrap break-words ${msg.role === "user" ? "bg-sky-900/40 text-sky-100 border border-sky-800" : "bg-zinc-800/80 text-zinc-300 border border-zinc-700"}`}>
                  {msg.content}
                </div>
              </div>
            ))}
            {isChatLoading && (
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-lg px-4 py-2.5 text-sm font-mono bg-zinc-800/50 text-zinc-400 border border-zinc-700 animate-pulse">
                  Thinking...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="shrink-0 p-4 border-t border-zinc-800 bg-zinc-950">
            <form onSubmit={handleSendMessage} className="flex gap-2">
              <input 
                type="text" 
                value={inputMsg}
                onChange={e => setInputMsg(e.target.value)}
                placeholder="Ask about critical tickets..." 
                className="flex-1 bg-zinc-900 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-sky-500 transition-colors font-mono"
                disabled={isChatLoading}
              />
              <button 
                type="submit" 
                disabled={!inputMsg.trim() || isChatLoading}
                className="bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white px-4 py-2 rounded-md text-sm font-semibold transition-colors"
              >
                Send
              </button>
            </form>
          </div>
        </div>

        {/* RIGHT PANE: Log Feed & Inspector */}
        <div className="w-1/2 flex overflow-hidden">
          {/* Right-Left: Log feed */}
          <div className="w-64 shrink-0 flex flex-col border-r border-zinc-800 bg-zinc-950">
            {/* Filter tabs */}
            <div className="flex border-b border-zinc-800 shrink-0">
              {["ALL", "OK", "ERR"].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`flex-1 text-[10px] font-mono py-2 tracking-widest transition-colors
                    ${filter === f ? "text-emerald-400 border-b-2 border-emerald-500 bg-zinc-900" : "text-zinc-600 hover:text-zinc-400"}`}
                >
                  {f}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: "thin", scrollbarColor: "#3f3f46 transparent" }}>
              {filtered.map((entry) => (
                <LogRow
                  key={entry.id}
                  entry={entry}
                  isSelected={selected?.id === entry.id}
                  onClick={() => setSelected(entry)}
                />
              ))}
              <div ref={logEndRef} />
            </div>
          </div>

          {/* Right-Right: JSON inspector */}
          <div className="flex-1 flex flex-col overflow-hidden bg-zinc-950/80">
            {selected ? (
              <>
                {/* Inspector header */}
                <div className="shrink-0 px-4 py-3 border-b border-zinc-800 bg-zinc-900/80 flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-emerald-400 truncate">{selected.endpoint}</span>
                    <StatusBadge code={selected.statusCode} label={selected.statusLabel} />
                  </div>
                  <div className="text-[10px] font-mono text-zinc-500 flex flex-wrap gap-x-3 gap-y-1">
                    <span><span className="text-zinc-600">id</span> <span className="text-zinc-300">{selected.id}</span></span>
                    <span><span className="text-zinc-600">usr</span> <span className="text-zinc-300">{selected.userId}</span></span>
                    <span><span className="text-zinc-600">tm</span> <span className="text-zinc-300">{selected.time}</span></span>
                  </div>
                </div>

                {/* JSON viewer */}
                <div
                  className="flex-1 overflow-auto p-3"
                  style={{ scrollbarWidth: "thin", scrollbarColor: "#3f3f46 transparent" }}
                >
                  <div className="bg-zinc-900/50 rounded border border-zinc-800/80 p-3">
                    <JsonToken value={selected.payload} />
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center gap-3 text-zinc-700 select-none">
                <svg className="w-10 h-10 opacity-30" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
                </svg>
                <p className="text-xs font-mono text-center px-4">Select a log entry to inspect its payload</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Footer ── */}
      <footer className="shrink-0 h-7 flex items-center px-4 border-t border-zinc-800 bg-zinc-950 gap-6 text-[9px] font-mono text-zinc-700 tracking-widest">
        <span>MCP SPEC v2025-03-26</span>
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          TLS 1.3 ENCRYPTED
        </span>
        <span className="ml-auto">FREE TIER · 512 MB RAM</span>
      </footer>
    </div>
  );
}
