import React, { useState, useEffect, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export default function LiveTerminal({ jobId }) {
  const [logs, setLogs] = useState([]);
  const [connected, setConnected] = useState(false);
  const terminalEndRef = useRef(null);

  useEffect(() => {
    if (!jobId) return;
    setLogs([]);
    const source = new EventSource(`${API_BASE}/jobs/${jobId}/stream`);
    setConnected(true);

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const timestamp = new Date().toLocaleTimeString();
        let logMsg = '';
        if (data.type === 'progress') logMsg = `[SYSTEM] ${data.message}`;
        else if (data.type === 'email_found') logMsg = `[SUCCESS] Email found: ${data.data.email} (${data.data.type})`;
        else if (data.type === 'verification_log') logMsg = `[VERIFY] ${data.data.message}`;
        else if (data.type === 'raw_record_found') logMsg = `[EXTRACT] Extracted company: ${data.data.company_name}`;
        else if (data.type === 'status') logMsg = `[STATUS] Job marked as ${data.status}`;
        else if (data.type === 'log_msg') logMsg = `[SYSTEM] ${data.message}`;
        else if (data.type === 'enrichment_log') logMsg = `[LINKEDIN] ${data.message}`;
        else logMsg = `[INFO] ${JSON.stringify(data)}`;

        if (logMsg) {
          setLogs(prev => [...prev, `${timestamp} > ${logMsg}`]);
        }
        if (data.type === 'status' && ['completed', 'failed', 'cancelled'].includes(data.status)) {
          setTimeout(() => source.close(), 1000);
        }
      } catch (e) { /* ignore */ }
    };

    source.onerror = () => { setConnected(false); source.close(); };
    source.onopen = () => setConnected(true);

    return () => { source.close(); setConnected(false); };
  }, [jobId]);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="h-full flex flex-col bg-[#0a0a0a] rounded-2xl border border-white/10 shadow-2xl overflow-hidden font-mono text-sm animate-in fade-in zoom-in-95 duration-500">
      <div className="bg-white/5 border-b border-white/10 p-4 flex items-center justify-between backdrop-blur-md">
        <div className="flex items-center space-x-4">
          <div className="flex space-x-2">
            <div className="w-3 h-3 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]" />
            <div className="w-3 h-3 rounded-full bg-yellow-500 shadow-[0_0_10px_rgba(234,179,8,0.5)]" />
            <div className={`w-3 h-3 rounded-full ${connected ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]' : 'bg-gray-500'}`} />
          </div>
          <span className="text-gray-400 font-semibold tracking-wider">root@lead-engine:~# Job #{jobId}</span>
        </div>
        {connected && (
          <div className="flex items-center space-x-3 bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            <span className="text-emerald-400 text-xs font-bold tracking-widest">LIVE</span>
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-6 space-y-1.5 custom-scrollbar">
        {logs.length === 0 && <div className="text-gray-600 italic">Connecting to job stream...</div>}
        {logs.map((log, i) => {
          let color = 'text-gray-400';
          if (log.includes('[SUCCESS]')) color = 'text-emerald-400 drop-shadow-[0_0_5px_rgba(52,211,153,0.5)]';
          else if (log.includes('[VERIFY]')) color = 'text-blue-400';
          else if (log.includes('[EXTRACT]')) color = 'text-yellow-400';
          else if (log.includes('[LINKEDIN]')) color = 'text-purple-400';
          else if (log.includes('[STATUS]')) color = 'text-white font-bold bg-white/10 px-2 py-0.5 rounded';
          return <div key={i} className={color}>{log}</div>;
        })}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}
