import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Download, Search, Filter } from 'lucide-react';
import { useToast } from './Toast';
import Pagination from './Pagination';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const PAGE_SIZE = 50;

export default function UniversalDatabase() {
  const toast = useToast();
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [searchTitle, setSearchTitle] = useState('');
  const [searchIndustry, setSearchIndustry] = useState('');
  const [searching, setSearching] = useState(false);

  const fetchLeads = useCallback(async (title = '', industry = '') => {
    setLoading(true);
    try {
      if (title || industry) {
        const res = await axios.get(`${API_BASE}/leads/search?title=${encodeURIComponent(title)}&industry=${encodeURIComponent(industry)}`);
        setLeads(res.data);
      } else {
        const res = await axios.get(`${API_BASE}/leads?limit=200`);
        setLeads(res.data);
      }
    } catch (err) {
      toast('Failed to load leads', 'error');
    }
    setLoading(false);
  }, [toast]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  const handleSearch = (e) => {
    e.preventDefault();
    setSearching(true);
    fetchLeads(searchTitle, searchIndustry).then(() => setSearching(false));
    setPage(1);
  };

  const totalPages = Math.ceil(leads.length / PAGE_SIZE);
  const paginatedLeads = leads.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl shadow-2xl p-6">
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-3.5 text-gray-500" />
            <input type="text" placeholder="Search by job title..." value={searchTitle} onChange={e => setSearchTitle(e.target.value)}
              className="w-full bg-black/40 text-white border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 pl-9 pr-3 py-2.5 rounded-xl outline-none transition-all placeholder-gray-600" />
          </div>
          <div className="relative flex-1">
            <Filter size={16} className="absolute left-3 top-3.5 text-gray-500" />
            <input type="text" placeholder="Filter by industry..." value={searchIndustry} onChange={e => setSearchIndustry(e.target.value)}
              className="w-full bg-black/40 text-white border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 pl-9 pr-3 py-2.5 rounded-xl outline-none transition-all placeholder-gray-600" />
          </div>
          <button type="submit" disabled={searching} className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl transition-colors font-medium disabled:opacity-50">
            {searching ? 'Searching...' : 'Search'}
          </button>
          <button type="button" onClick={() => window.open(`${API_BASE}/leads/export`, '_blank')} className="flex items-center gap-2 px-6 py-2.5 bg-white/10 hover:bg-white/20 text-white rounded-xl transition-colors font-medium border border-white/10">
            <Download size={16} /> Export All
          </button>
        </form>
      </div>

      <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
        <div className="overflow-x-auto max-h-[700px] custom-scrollbar">
          <table className="w-full text-left border-collapse text-sm whitespace-nowrap">
            <thead className="sticky top-0 bg-[#0f172a] shadow-md z-10">
              <tr className="uppercase tracking-widest text-[10px] text-gray-500 border-b border-white/10 bg-black/40">
                <th className="p-4 font-semibold">ID</th>
                <th className="p-4 font-semibold">Name</th>
                <th className="p-4 font-semibold">Title</th>
                <th className="p-4 font-semibold">Email</th>
                <th className="p-4 font-semibold">Status</th>
                <th className="p-4 font-semibold">LinkedIn</th>
                <th className="p-4 font-semibold">Company</th>
                <th className="p-4 font-semibold">Industry</th>
                <th className="p-4 font-semibold">Location</th>
                <th className="p-4 font-semibold">Job ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {loading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 10 }).map((_, j) => (
                      <td key={j} className="p-3"><div className="h-3 bg-white/10 rounded animate-pulse" /></td>
                    ))}
                  </tr>
                ))
              ) : paginatedLeads.length === 0 ? (
                <tr><td colSpan="10" className="p-8 text-center text-gray-500 italic">No leads found. Launch a job to get started.</td></tr>
              ) : paginatedLeads.map((lead, i) => (
                <tr key={lead.id || i} className="hover:bg-white/5 transition-colors">
                  <td className="p-3 text-blue-400 font-medium">#{lead.id}</td>
                  <td className="p-3 text-white font-medium">{lead.first_name} {lead.last_name}</td>
                  <td className="p-3 text-gray-400">{lead.title}</td>
                  <td className="p-3 text-gray-200">{lead.email || '-'}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${lead.email_status === 'valid' || lead.email_status === 'catch_all' ? 'bg-emerald-500/20 text-emerald-400' : lead.email_status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400'}`}>{lead.email_status || 'N/A'}</span>
                  </td>
                  <td className="p-3">
                    {lead.linkedin_url ? <a href={lead.linkedin_url} target="_blank" rel="noreferrer" className="text-blue-400 hover:underline">Link</a> : '-'}
                  </td>
                  <td className="p-3 text-gray-300 font-semibold">{lead.company_name}</td>
                  <td className="p-3 text-gray-500">{lead.industry}</td>
                  <td className="p-3 text-gray-500">{lead.city}, {lead.state}</td>
                  <td className="p-3 text-gray-500">#{lead.job_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
      </div>
    </div>
  );
}
