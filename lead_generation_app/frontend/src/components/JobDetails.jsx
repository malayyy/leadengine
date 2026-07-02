import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Download, PauseCircle, StopCircle, PlayCircle, Link as LinkIcon, ArrowLeft, AlertTriangle } from 'lucide-react';
import { useToast } from './Toast';
import ConfirmDialog from './ConfirmDialog';
import Pagination from './Pagination';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const PAGE_SIZE = 25;

export default function JobDetails({ jobId, onBack }) {
  const toast = useToast();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailsTab, setDetailsTab] = useState('unified');
  const [page, setPage] = useState(1);
  const [confirmAction, setConfirmAction] = useState(null);

  useEffect(() => {
    if (!jobId) return;
    setLoading(true);
    axios.get(`${API_BASE}/jobs/${jobId}/details`).then(res => {
      setJob(res.data);
      setLoading(false);
    }).catch(err => {
      toast('Failed to load job details', 'error');
      setLoading(false);
    });
  }, [jobId, toast]);

  const controlJob = async (action) => {
    try {
      const res = await axios.post(`${API_BASE}/jobs/${jobId}/${action}`);
      setJob(prev => ({ ...prev, status: res.data.status }));
      toast(`Job ${action} successful`, 'success');
    } catch {
      toast(`Failed to ${action} job`, 'error');
    }
    setConfirmAction(null);
  };

  const handleCancel = () => {
    setConfirmAction({
      title: 'Cancel Job',
      message: 'This will stop the job immediately. Cancelled jobs cannot be resumed. Proceed?',
      confirmLabel: 'Cancel Job',
      variant: 'danger',
      onConfirm: () => controlJob('cancel'),
    });
  };

  const handlePause = () => controlJob('pause');

  const handleResume = () => controlJob('resume');

  const unifiedRows = job ? job.records.flatMap(r => {
    const companyLeads = job.leads.filter(l => l.company_name === r.company_name);
    if (companyLeads.length === 0) return [{ ...r, lead_first: '-', lead_last: '-', lead_title: '-', lead_email: '-', lead_linkedin: '-', email_status: '-' }];
    return companyLeads.map(l => ({ ...r, lead_first: l.first_name, lead_last: l.last_name, lead_title: l.title, lead_email: l.email, lead_linkedin: l.linkedin_url, email_status: l.email_status }));
  }) : [];

  const totalPages = Math.ceil(unifiedRows.length / PAGE_SIZE);
  const paginatedRows = unifiedRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (loading) {
    return (
      <div className="space-y-6 animate-in fade-in max-w-7xl mx-auto">
        <div className="bg-white/5 backdrop-blur-lg border border-white/10 p-6 rounded-2xl shadow-2xl animate-pulse">
          <div className="h-8 w-48 bg-white/10 rounded mb-4" />
          <div className="h-4 w-64 bg-white/10 rounded" />
        </div>
        <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl shadow-2xl p-6 animate-pulse">
          <div className="h-64 bg-white/5 rounded-lg" />
        </div>
      </div>
    );
  }

  if (!job) return null;

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-right-8 duration-500 max-w-7xl mx-auto">
      <ConfirmDialog {...confirmAction} open={!!confirmAction} onCancel={() => setConfirmAction(null)} />

      <div className="flex flex-col md:flex-row items-start md:items-center justify-between bg-white/5 backdrop-blur-lg border border-white/10 p-6 rounded-2xl shadow-2xl">
        <div>
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="p-1.5 hover:bg-white/10 rounded-lg transition-colors text-gray-400 hover:text-white">
              <ArrowLeft size={20} />
            </button>
            <h2 className="text-3xl font-bold text-white tracking-tight flex items-center">
              Job Workspace
              <span className="text-gray-500 ml-3 text-xl font-medium">#{job.job_id}</span>
            </h2>
          </div>
          <div className="flex items-center mt-3 ml-10 space-x-3">
            <span className={`px-2 py-0.5 text-xs font-bold uppercase rounded ${job.status === 'running' || job.status === 'in_progress' ? 'bg-blue-500 text-white animate-pulse' : job.status === 'completed' ? 'bg-emerald-500 text-white' : job.status === 'paused' ? 'bg-yellow-500 text-white' : job.status === 'failed' ? 'bg-red-500 text-white' : 'bg-gray-700 text-gray-300'}`}>{job.status}</span>
            <span className="text-gray-400 text-sm">{job.records.length} Raw Extracted</span>
            <span className="text-gray-400 text-sm">&bull;</span>
            <span className="text-gray-400 text-sm">{job.leads.length} Leads Enriched</span>
          </div>
        </div>
        <div className="flex items-center gap-2 mt-4 md:mt-0 ml-10 md:ml-0">
          {(job.status === 'in_progress' || job.status === 'running') && (
            <>
              <button onClick={handlePause} className="flex items-center space-x-2 bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 px-4 py-2 rounded-xl transition-all font-medium border border-yellow-500/20">
                <PauseCircle size={16} /><span>Pause</span>
              </button>
              <button onClick={handleCancel} className="flex items-center space-x-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 px-4 py-2 rounded-xl transition-all font-medium border border-red-500/20">
                <StopCircle size={16} /><span>Cancel</span>
              </button>
            </>
          )}
          {job.status === 'paused' && (
            <>
              <button onClick={handleResume} className="flex items-center space-x-2 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 px-4 py-2 rounded-xl transition-all font-medium border border-emerald-500/20">
                <PlayCircle size={16} /><span>Resume</span>
              </button>
              <button onClick={handleCancel} className="flex items-center space-x-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 px-4 py-2 rounded-xl transition-all font-medium border border-red-500/20">
                <StopCircle size={16} /><span>Cancel</span>
              </button>
            </>
          )}
          <button onClick={() => window.open(`${API_BASE}/jobs/${jobId}/export`, '_blank')} className="flex items-center space-x-2 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 px-4 py-2 rounded-xl transition-all font-medium border border-blue-500/20">
            <Download size={16} /><span>Export CSV</span>
          </button>
        </div>
      </div>

      <div className="flex items-center space-x-2 bg-black/40 p-1.5 rounded-xl border border-white/5 w-fit">
        {[
          { key: 'unified', label: 'Unified Data' },
          { key: 'gmaps', label: 'Raw GMaps' },
          { key: 'linkedin', label: 'LinkedIn Leads' },
          { key: 'emails', label: 'Verified Emails' },
        ].map(tab => (
          <button key={tab.key} onClick={() => { setDetailsTab(tab.key); setPage(1); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${detailsTab === tab.key ? 'bg-blue-600 text-white shadow' : 'text-gray-400 hover:text-white'}`}>{tab.label}</button>
        ))}
      </div>

      {detailsTab === 'unified' && (
        <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl animate-in fade-in duration-300">
          <div className="overflow-x-auto max-h-[600px] custom-scrollbar">
            <table className="w-full text-left border-collapse text-sm whitespace-nowrap">
              <thead className="sticky top-0 bg-[#0f172a] shadow-md z-10">
                <tr className="uppercase tracking-widest text-[10px] text-gray-500 border-b border-white/10 bg-black/40">
                  <th className="p-4 font-semibold text-blue-400 border-r border-white/5">Candidate Name</th>
                  <th className="p-4 font-semibold text-blue-400 border-r border-white/5">Title</th>
                  <th className="p-4 font-semibold text-blue-400 border-r border-white/5">Email & Status</th>
                  <th className="p-4 font-semibold text-blue-400 border-r border-white/5">LinkedIn</th>
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Company</th>
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Industry</th>
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Website</th>
                  <th className="p-4 font-semibold text-emerald-400">Location</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {paginatedRows.length === 0 && <tr><td colSpan="8" className="p-8 text-center text-gray-500 italic">No merged data collected yet.</td></tr>}
                {paginatedRows.map((r, i) => (
                  <tr key={i} className="hover:bg-white/5 transition-colors">
                    <td className="p-3 text-white border-r border-white/5 font-medium">{r.lead_first !== '-' ? `${r.lead_first} ${r.lead_last}` : <span className="text-gray-600">No Match</span>}</td>
                    <td className="p-3 text-gray-400 border-r border-white/5">{r.lead_title}</td>
                    <td className="p-3 border-r border-white/5">
                      {r.lead_email !== '-' && r.lead_email ? (
                        <div className="flex flex-col">
                          <span className="text-gray-200">{r.lead_email}</span>
                          <span className={`text-[10px] uppercase font-bold mt-0.5 w-fit px-1.5 rounded ${['valid', 'catch_all'].includes(r.email_status) ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>{r.email_status}</span>
                        </div>
                      ) : <span className="text-gray-600">-</span>}
                    </td>
                    <td className="p-3 border-r border-white/5">
                      {r.lead_linkedin !== '-' && r.lead_linkedin ? (
                        <a href={r.lead_linkedin} target="_blank" rel="noreferrer" className="text-blue-400 hover:text-blue-300 hover:underline flex items-center"><LinkIcon size={12} className="mr-1" /> Profile</a>
                      ) : <span className="text-gray-600">-</span>}
                    </td>
                    <td className="p-3 text-gray-300 border-r border-white/5 font-semibold">{r.company_name}</td>
                    <td className="p-3 text-gray-400 border-r border-white/5">{r.industry}</td>
                    <td className="p-3 border-r border-white/5">
                      {r.website ? <a href={r.website} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-white hover:underline">{new URL(r.website).hostname.replace('www.', '')}</a> : <span className="text-gray-600">-</span>}
                    </td>
                    <td className="p-3 text-gray-500">{r.address} <span className="text-gray-400 ml-1">{r.city}, {r.state}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </div>
      )}

      {detailsTab === 'gmaps' && (
        <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl animate-in fade-in duration-300">
          <div className="overflow-x-auto max-h-[600px] custom-scrollbar">
            <table className="w-full text-left border-collapse text-sm whitespace-nowrap">
              <thead className="sticky top-0 bg-[#0f172a] shadow-md z-10">
                <tr className="uppercase tracking-widest text-[10px] text-gray-500 border-b border-white/10 bg-black/40">
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Company Name</th>
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Industry</th>
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Website</th>
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Phone</th>
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Rating</th>
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Address</th>
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">City/State/Zip</th>
                  <th className="p-4 font-semibold text-emerald-400">GMaps Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {job.records.length === 0 && <tr><td colSpan="8" className="p-8 text-center text-gray-500 italic">No companies extracted.</td></tr>}
                {job.records.map((r, i) => (
                  <tr key={i} className="hover:bg-white/5 transition-colors">
                    <td className="p-3 text-white font-medium border-r border-white/5">{r.company_name}</td>
                    <td className="p-3 text-gray-400 border-r border-white/5">{r.industry}</td>
                    <td className="p-3 border-r border-white/5">{r.website ? <a href={r.website} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-white hover:underline">{r.website}</a> : <span className="text-gray-600">-</span>}</td>
                    <td className="p-3 text-gray-400 border-r border-white/5">{r.phone || '-'}</td>
                    <td className="p-3 text-yellow-500 border-r border-white/5">{r.rating ? `${r.rating} ⭐` : '-'}</td>
                    <td className="p-3 text-gray-500 border-r border-white/5">{r.address || '-'}</td>
                    <td className="p-3 text-gray-400 border-r border-white/5">{r.city}, {r.state} {r.zip_code}</td>
                    <td className="p-3 text-gray-500">{r.gmaps_url ? <a href={r.gmaps_url} target="_blank" rel="noreferrer" className="hover:text-white hover:underline">View Map</a> : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {detailsTab === 'linkedin' && (
        <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl animate-in fade-in duration-300">
          <div className="overflow-x-auto max-h-[600px] custom-scrollbar">
            <table className="w-full text-left border-collapse text-sm whitespace-nowrap">
              <thead className="sticky top-0 bg-[#0f172a] shadow-md z-10">
                <tr className="uppercase tracking-widest text-[10px] text-gray-500 border-b border-white/10 bg-black/40">
                  <th className="p-4 font-semibold text-blue-400 border-r border-white/5">Candidate</th>
                  <th className="p-4 font-semibold text-blue-400 border-r border-white/5">Title</th>
                  <th className="p-4 font-semibold text-blue-400 border-r border-white/5">Company</th>
                  <th className="p-4 font-semibold text-blue-400 border-r border-white/5">LinkedIn URL</th>
                  <th className="p-4 font-semibold text-blue-400">Location</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {job.leads.length === 0 && <tr><td colSpan="5" className="p-8 text-center text-gray-500 italic">No LinkedIn candidates found.</td></tr>}
                {job.leads.map((l, i) => {
                  const company = job.records.find(rc => rc.id === l.raw_record_id);
                  return (
                    <tr key={i} className="hover:bg-white/5 transition-colors">
                      <td className="p-3 text-white font-medium border-r border-white/5 flex items-center">
                        <div className="w-6 h-6 rounded-full bg-gray-800 mr-2 flex items-center justify-center text-[10px] font-bold border border-white/10">{l.first_name?.[0] || '?'}</div>
                        {l.first_name} {l.last_name}
                      </td>
                      <td className="p-3 text-gray-400 border-r border-white/5">{l.title}</td>
                      <td className="p-3 text-gray-300 border-r border-white/5 font-semibold">{company ? company.company_name : 'Unknown'}</td>
                      <td className="p-3 border-r border-white/5">
                        {l.linkedin_url ? <a href={l.linkedin_url} target="_blank" rel="noreferrer" className="text-blue-400 hover:text-blue-300 hover:underline">{l.linkedin_url}</a> : '-'}
                      </td>
                      <td className="p-3 text-gray-500">{l.location || '-'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {detailsTab === 'emails' && (
        <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl animate-in fade-in duration-300">
          <div className="overflow-x-auto max-h-[600px] custom-scrollbar">
            <table className="w-full text-left border-collapse text-sm whitespace-nowrap">
              <thead className="sticky top-0 bg-[#0f172a] shadow-md z-10">
                <tr className="uppercase tracking-widest text-[10px] text-gray-500 border-b border-white/10 bg-black/40">
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Email</th>
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Status</th>
                  <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Confidence</th>
                  <th className="p-4 font-semibold text-gray-400 border-r border-white/5">Person</th>
                  <th className="p-4 font-semibold text-gray-400">Company</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {job.leads.filter(l => l.email_status === 'valid' || l.email_status === 'catch_all').length === 0 && (
                  <tr><td colSpan="5" className="p-8 text-center text-gray-500 italic">No verified emails generated yet.</td></tr>
                )}
                {job.leads.filter(l => l.email_status === 'valid' || l.email_status === 'catch_all').map((l, i) => {
                  const company = job.records.find(rc => rc.id === l.raw_record_id);
                  return (
                    <tr key={i} className="hover:bg-white/5 transition-colors">
                      <td className="p-3 text-white font-medium border-r border-white/5">{l.email}</td>
                      <td className="p-3 border-r border-white/5">
                        <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${l.email_status === 'valid' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{l.email_status}</span>
                      </td>
                      <td className="p-3 text-gray-400 border-r border-white/5">{l.email_confidence_score || '-'}</td>
                      <td className="p-3 text-gray-400 border-r border-white/5">{l.first_name} {l.last_name}</td>
                      <td className="p-3 text-gray-500">{company ? company.company_name : 'Unknown'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
