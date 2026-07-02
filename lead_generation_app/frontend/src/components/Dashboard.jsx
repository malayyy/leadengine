import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Briefcase, Database, Users, Shield, BarChart2, Activity, MapPin } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts';
import { MetricSkeleton, ChartSkeleton, TableSkeleton } from './Skeleton';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export default function Dashboard({ onJobSelect }) {
  const [metrics, setMetrics] = useState(null);
  const [realtimeMetrics, setRealtimeMetrics] = useState(null);
  const [mvCredits, setMvCredits] = useState(null);
  const [jobsList, setJobsList] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [metricsRes, creditsRes, jobsRes, realtimeRes] = await Promise.all([
        axios.get(`${API_BASE}/dashboard/metrics`),
        axios.get(`${API_BASE}/dashboard/credits`),
        axios.get(`${API_BASE}/jobs?limit=20`),
        axios.get(`${API_BASE}/dashboard/realtime-metrics`),
      ]);
      setMetrics(metricsRes.data);
      setMvCredits(creditsRes.data.credits);
      setJobsList(jobsRes.data);
      setRealtimeMetrics(realtimeRes.data);
    } catch (err) {
      console.error('Dashboard fetch error', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); const interval = setInterval(fetchAll, 30000); return () => clearInterval(interval); }, [fetchAll]);

  if (loading) {
    return (
      <div className="space-y-8 animate-in fade-in duration-500">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
          {Array.from({ length: 5 }).map((_, i) => <MetricSkeleton key={i} />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <ChartSkeleton /><ChartSkeleton />
        </div>
        <TableSkeleton rows={5} cols={5} />
      </div>
    );
  }

  const statusColor = (status) => {
    const map = { completed: 'bg-emerald-500/20 text-emerald-400', running: 'bg-blue-500/20 text-blue-400 animate-pulse', paused: 'bg-yellow-500/20 text-yellow-400', cancelled: 'bg-red-500/20 text-red-400', failed: 'bg-red-500/20 text-red-400' };
    return map[status] || 'bg-gray-500/20 text-gray-400';
  };

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
        <MetricCard icon={Briefcase} label="Jobs" value={metrics?.total_jobs} color="text-gray-400" />
        <MetricCard icon={Database} label="Companies" value={metrics?.total_records} color="text-gray-400" />
        <MetricCard icon={Users} label="Leads" value={metrics?.total_enriched} color="text-gray-400" />
        <div className="bg-gradient-to-br from-white to-gray-200 p-6 rounded-2xl shadow-xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:scale-110 transition-transform"><Shield size={64} className="text-black" /></div>
          <div className="flex items-center space-x-3 text-gray-800 mb-2 relative z-10"><Shield size={18} /><span className="text-xs uppercase tracking-widest font-bold">Verified Emails</span></div>
          <div className="text-4xl font-bold text-black relative z-10">{metrics?.total_valid_emails}</div>
        </div>
        <div className="bg-gradient-to-br from-blue-900/40 to-blue-800/40 backdrop-blur-lg border border-blue-500/30 p-6 rounded-2xl shadow-xl hover:border-blue-500/60 transition-all">
          <div className="flex items-center space-x-3 text-blue-300 mb-2"><Shield size={18} /><span className="text-xs uppercase tracking-widest font-bold">Live MV Credits</span></div>
          <div className="text-4xl font-bold text-white drop-shadow-md">{mvCredits !== null ? mvCredits.toLocaleString() : '...'}</div>
        </div>
      </div>

      {realtimeMetrics && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl p-6">
            <div className="flex items-center space-x-3 mb-6">
              <div className="p-2 bg-blue-500/20 rounded-lg border border-blue-500/30 text-blue-400"><BarChart2 size={20} /></div>
              <h3 className="text-lg font-bold text-white tracking-tight">Campaign & Industry Spread</h3>
            </div>
            <div className="space-y-6 max-h-[500px] overflow-y-auto custom-scrollbar pr-2">
              {realtimeMetrics.campaigns.length === 0 && <div className="text-gray-500 text-sm italic py-10 text-center">No campaign data yet.</div>}
              {realtimeMetrics.campaigns.map((camp, idx) => (
                <div key={idx} className="space-y-3">
                  <h4 className="text-sm uppercase tracking-widest text-blue-400 font-bold border-b border-white/10 pb-2">{camp.campaign}</h4>
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={camp.industries} layout="vertical" margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                        <XAxis type="number" hide />
                        <YAxis type="category" dataKey="name" stroke="#9ca3af" fontSize={11} width={120} tickLine={false} axisLine={false} />
                        <RechartsTooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ backgroundColor: 'rgba(17,24,39,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
                        <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={16} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-8">
            <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl p-6">
              <div className="flex items-center space-x-3 mb-6">
                <div className="p-2 bg-emerald-500/20 rounded-lg border border-emerald-500/30 text-emerald-400"><Activity size={20} /></div>
                <h3 className="text-lg font-bold text-white tracking-tight">Extraction Velocity (24h)</h3>
              </div>
              <div className="h-48">
                {realtimeMetrics.velocity.length === 0 ? <div className="text-gray-500 text-sm italic py-10 text-center">No extraction data in the last 24h.</div> : (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={realtimeMetrics.velocity} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                      <XAxis dataKey="time" stroke="#6b7280" fontSize={10} tickFormatter={(tick) => tick.split(' ')[1]} tickLine={false} axisLine={false} />
                      <YAxis stroke="#6b7280" fontSize={10} tickLine={false} axisLine={false} />
                      <RechartsTooltip cursor={{ stroke: 'rgba(255,255,255,0.1)' }} contentStyle={{ backgroundColor: 'rgba(17,24,39,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} labelFormatter={(label) => `Time: ${label}`} />
                      <Line type="monotone" dataKey="count" stroke="#10b981" strokeWidth={3} dot={{ r: 3, fill: '#10b981', strokeWidth: 0 }} activeDot={{ r: 6, fill: '#fff' }} />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl p-6">
              <div className="flex items-center space-x-3 mb-6">
                <div className="p-2 bg-purple-500/20 rounded-lg border border-purple-500/30 text-purple-400"><MapPin size={20} /></div>
                <h3 className="text-lg font-bold text-white tracking-tight">Top Active Zipcodes</h3>
              </div>
              <div className="h-48">
                {realtimeMetrics.zipcodes.length === 0 ? <div className="text-gray-500 text-sm italic py-10 text-center">No zipcode data found.</div> : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={realtimeMetrics.zipcodes} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                      <XAxis dataKey="zipcode" stroke="#6b7280" fontSize={10} tickLine={false} axisLine={false} />
                      <YAxis stroke="#6b7280" fontSize={10} tickLine={false} axisLine={false} />
                      <RechartsTooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ backgroundColor: 'rgba(17,24,39,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
                      <Bar dataKey="count" fill="#a855f7" radius={[4, 4, 0, 0]} barSize={24} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
        <div className="p-5 border-b border-white/10 bg-black/20 flex items-center justify-between">
          <h3 className="font-semibold text-white">Active & Recent Jobs</h3>
          <span className="text-xs text-gray-500">Auto-refreshes every 30s</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-black/40 uppercase tracking-widest text-xs text-gray-500 border-b border-white/10">
                <th className="p-4 font-semibold">Job ID</th>
                <th className="p-4 font-semibold">Campaign</th>
                <th className="p-4 font-semibold">Status</th>
                <th className="p-4 font-semibold">Records</th>
                <th className="p-4 font-semibold">MV Credits</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {jobsList.map((job) => (
                <tr key={job.id} onClick={() => onJobSelect(job.id)} className="hover:bg-white/5 transition-colors cursor-pointer group">
                  <td className="p-4 text-blue-400 font-medium group-hover:text-blue-300">#{job.id}</td>
                  <td className="p-4 text-gray-200">{job.campaign_name}</td>
                  <td className="p-4"><span className={`px-2 py-1 rounded text-xs font-medium ${statusColor(job.status)}`}>{job.status.toUpperCase()}</span></td>
                  <td className="p-4 text-gray-300">{job.records_extracted}</td>
                  <td className="p-4 text-red-400 font-medium">{job.mv_credits_used} <span className="text-gray-600 text-xs ml-1">/ {job.budget > 0 ? job.budget : '∞'}</span></td>
                </tr>
              ))}
              {jobsList.length === 0 && (
                <tr><td colSpan="5" className="p-8 text-center text-gray-500 italic">No jobs yet. Launch your first campaign.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-white/5 backdrop-blur-lg border border-white/10 p-6 rounded-2xl shadow-xl hover:bg-white/10 transition-all">
      <div className={`flex items-center space-x-3 ${color} mb-2`}><Icon size={18} /><span className="text-xs uppercase tracking-widest font-semibold">{label}</span></div>
      <div className="text-4xl font-bold text-white">{value ?? '...'}</div>
    </div>
  );
}
