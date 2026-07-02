import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Play, Info, ChevronDown, Search, Database } from 'lucide-react';
import { GOOGLE_INDUSTRIES } from '../industries';
import { useToast } from './Toast';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const US_STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"];

const Tooltip = ({ children, text }) => (
  <div className="relative group flex items-center">
    {children}
    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block w-48 p-2 bg-gray-800 text-xs text-white text-center rounded-md shadow-xl z-50 pointer-events-none">
      {text}
      <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-800" />
    </div>
  </div>
);

export default function LaunchJob({ onJobLaunched }) {
  const toast = useToast();
  const [campaignName, setCampaignName] = useState('');
  const [industries, setIndustries] = useState([]);
  const [industrySearch, setIndustrySearch] = useState('');
  const [showIndustryDropdown, setShowIndustryDropdown] = useState(false);
  const [titles, setTitles] = useState('');
  const [state, setState] = useState('');
  const [zipcodes, setZipcodes] = useState([]);
  const [totalContacts, setTotalContacts] = useState(100);
  const [contactsPerCompany, setContactsPerCompany] = useState('');
  const [availableZipcodes, setAvailableZipcodes] = useState([]);
  const [zipSearch, setZipSearch] = useState('');
  const [launching, setLaunching] = useState(false);

  useEffect(() => {
    if (state) {
      axios.get(`${API_BASE}/locations/zipcodes?state=${state}`).then(res => {
        setAvailableZipcodes(res.data.zipcodes || []);
        setZipcodes([]);
      }).catch(err => console.error(err));
    } else {
      setAvailableZipcodes([]);
    }
  }, [state]);

  const handleLaunch = async (e) => {
    e.preventDefault();
    if (!campaignName || industries.length === 0 || !state || zipcodes.length === 0 || !titles) {
      toast('Please fill all required fields!', 'error');
      return;
    }
    setLaunching(true);
    try {
      const payload = {
        campaign_name: campaignName,
        industry: industries.join(', '),
        state,
        zipcodes,
        titles: titles.split(',').map(t => t.trim()).filter(t => t),
        total_contacts: parseInt(totalContacts, 10),
        contacts_per_company: contactsPerCompany ? parseInt(contactsPerCompany, 10) : -1,
      };
      const res = await axios.post(`${API_BASE}/jobs/pipeline`, payload);
      toast(`Job #${res.data.job_id} launched successfully!`, 'success');
      onJobLaunched(res.data.job_id);
      setCampaignName('');
      setIndustries([]);
    } catch (err) {
      toast('Error launching job: ' + (err.response?.data?.detail || err.message), 'error');
    }
    setLaunching(false);
  };

  return (
    <div className="max-w-5xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      <form onSubmit={handleLaunch} className="bg-white/5 backdrop-blur-2xl border border-white/10 rounded-3xl shadow-[0_0_50px_rgba(0,0,0,0.5)] p-8">
        <div className="flex items-center justify-between mb-8 pb-6 border-b border-white/10">
          <div>
            <h2 className="text-3xl font-bold text-white tracking-tight">Configure Deployment</h2>
            <p className="text-gray-400 mt-2 text-sm">Launch a distributed scraping and verification pipeline.</p>
          </div>
          <button type="submit" disabled={launching} className="flex items-center space-x-2 bg-gradient-to-r from-blue-600 to-blue-500 text-white px-8 py-3 rounded-xl shadow-lg hover:shadow-[0_0_20px_rgba(37,99,235,0.4)] transition-all font-semibold disabled:opacity-50">
            <Play size={18} fill="currentColor" /><span>{launching ? 'Firing Job...' : 'Launch Job'}</span>
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          <div className="space-y-6">
            <div>
              <label className="flex items-center text-xs uppercase tracking-widest text-gray-400 mb-2 font-semibold">
                Campaign Name <Tooltip text="A friendly name to identify this run in the Command Center."><Info size={14} className="ml-1 text-gray-500 cursor-help" /></Tooltip>
              </label>
              <input type="text" placeholder="e.g. Q3 Roofers Push" value={campaignName} onChange={e => setCampaignName(e.target.value)}
                className="w-full bg-black/40 text-white border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 p-3.5 rounded-xl outline-none transition-all placeholder-gray-600" />
            </div>

            <div>
              <label className="flex items-center text-xs uppercase tracking-widest text-gray-400 mb-2 font-semibold">
                Job Titles <Tooltip text="Comma-separated titles (e.g. CEO, Owner, Founder)."><Info size={14} className="ml-1 text-gray-500 cursor-help" /></Tooltip>
              </label>
              <input type="text" placeholder="e.g. CEO, Founder" value={titles} onChange={e => setTitles(e.target.value)}
                className="w-full bg-black/40 text-white border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 p-3.5 rounded-xl outline-none transition-all placeholder-gray-600" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="flex items-center text-xs uppercase tracking-widest text-gray-400 mb-2 font-semibold">
                  Total Contacts <Tooltip text="Maximum contacts to extract for this campaign."><Info size={14} className="ml-1 text-gray-500 cursor-help" /></Tooltip>
                </label>
                <input type="number" min="0" placeholder="e.g. 50" value={totalContacts} onChange={e => setTotalContacts(e.target.value)}
                  className="w-full bg-black/40 text-white border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 p-3.5 rounded-xl outline-none transition-all placeholder-gray-600" />
              </div>
              <div>
                <label className="flex items-center text-xs uppercase tracking-widest text-gray-400 mb-2 font-semibold">
                  Per Company <Tooltip text="Max contacts per company."><Info size={14} className="ml-1 text-gray-500 cursor-help" /></Tooltip>
                </label>
                <input type="number" min="1" placeholder="e.g. 2" value={contactsPerCompany} onChange={e => setContactsPerCompany(e.target.value)}
                  className="w-full bg-black/40 text-white border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 p-3.5 rounded-xl outline-none transition-all placeholder-gray-600" />
              </div>
            </div>

            <div className="relative">
              <label className="flex items-center text-xs uppercase tracking-widest text-gray-400 mb-2 font-semibold">
                Target Industries <Tooltip text="Select multiple Google Business Profile categories."><Info size={14} className="ml-1 text-gray-500 cursor-help" /></Tooltip>
              </label>
              <div className="flex flex-wrap gap-2 mb-2">
                {industries.map(ind => (
                  <span key={ind} className="bg-blue-500/20 text-blue-400 px-3 py-1 rounded-full text-sm flex items-center border border-blue-500/30">
                    {ind}
                    <button type="button" onClick={() => setIndustries(industries.filter(i => i !== ind))} className="ml-2 hover:text-white">&times;</button>
                  </span>
                ))}
              </div>
              <div className="relative">
                <input type="text" placeholder="Search and add industries..." value={industrySearch}
                  onChange={e => { setIndustrySearch(e.target.value); setShowIndustryDropdown(true); }}
                  onFocus={() => setShowIndustryDropdown(true)}
                  onBlur={() => setTimeout(() => setShowIndustryDropdown(false), 200)}
                  className="w-full bg-black/40 text-white border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 p-3.5 rounded-xl outline-none transition-all placeholder-gray-600" />
                {showIndustryDropdown && (
                  <div className="absolute top-full mt-2 w-full bg-[#111827] border border-white/10 rounded-xl shadow-2xl z-50 max-h-60 overflow-y-auto custom-scrollbar">
                    {GOOGLE_INDUSTRIES.filter(i => i.toLowerCase().includes(industrySearch.toLowerCase())).map(ind => (
                      <div key={ind} onClick={() => { if (!industries.includes(ind)) setIndustries([...industries, ind]); setIndustrySearch(''); setShowIndustryDropdown(false); }}
                        className="p-3 text-sm text-gray-300 hover:bg-blue-600 hover:text-white cursor-pointer transition-colors">{ind}</div>
                    ))}
                    {GOOGLE_INDUSTRIES.filter(i => i.toLowerCase().includes(industrySearch.toLowerCase())).length === 0 && (
                      <div className="p-3 text-sm text-gray-500">No industries found.</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div>
              <label className="flex items-center text-xs uppercase tracking-widest text-gray-400 mb-2 font-semibold">
                State Target <Tooltip text="Select a US State. Zipcodes will automatically populate."><Info size={14} className="ml-1 text-gray-500 cursor-help" /></Tooltip>
              </label>
              <div className="relative">
                <select value={state} onChange={e => setState(e.target.value)} className="w-full bg-black/40 text-white border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 p-3.5 rounded-xl outline-none transition-all appearance-none">
                  <option value="" disabled>Select a State</option>
                  {US_STATES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                <ChevronDown size={18} className="absolute right-4 top-4 text-gray-500 pointer-events-none" />
              </div>
            </div>

            <div className="bg-black/40 border border-white/10 rounded-xl flex flex-col shadow-inner" style={{ height: '310px' }}>
              <div className="p-3 border-b border-white/10 flex justify-between items-center bg-white/5 rounded-t-xl">
                <span className="text-xs text-white font-semibold uppercase tracking-widest px-2 py-1 bg-blue-500/20 rounded-md">{zipcodes.length} Selected</span>
                <div className="space-x-3 text-xs font-semibold">
                  <button type="button" onClick={() => setZipcodes(availableZipcodes.map(z => z.zipcode))} className="text-blue-400 hover:text-blue-300">Select All</button>
                  <span className="text-gray-600">|</span>
                  <button type="button" onClick={() => setZipcodes([])} className="text-red-400 hover:text-red-300">Clear</button>
                </div>
              </div>
              <div className="p-3 border-b border-white/10 bg-black/20">
                <div className="relative">
                  <Search size={14} className="absolute left-3 top-2.5 text-gray-500" />
                  <input type="text" placeholder="Filter Zipcode or City..." value={zipSearch} onChange={e => setZipSearch(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 text-sm text-white placeholder-gray-500 outline-none pl-9 pr-3 py-2 rounded-lg focus:border-blue-500" />
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-3 space-y-1 custom-scrollbar">
                {availableZipcodes.length === 0 ? (
                  <div className="text-center text-gray-500 text-sm mt-12 flex flex-col items-center">
                    <Database size={24} className="mb-2 opacity-50" />
                    Select a state to load top 500 zipcodes...
                  </div>
                ) : (
                  availableZipcodes.filter(z => z.zipcode.includes(zipSearch) || (z.city && z.city.toLowerCase().includes(zipSearch.toLowerCase())))
                    .map(z => (
                      <label key={z.zipcode} className="flex items-center space-x-3 p-2.5 hover:bg-white/5 rounded-lg cursor-pointer border border-transparent hover:border-white/5">
                        <input type="checkbox" checked={zipcodes.includes(z.zipcode)} onChange={() => {
                          setZipcodes(prev => prev.includes(z.zipcode) ? prev.filter(x => x !== z.zipcode) : [...prev, z.zipcode]);
                        }} className="w-4 h-4 rounded bg-black/50 border-white/20 text-blue-500 focus:ring-0 cursor-pointer" />
                        <span className="text-sm font-medium text-gray-200">{z.zipcode} <span className="text-gray-500 ml-2 font-normal">{z.city}</span></span>
                      </label>
                    ))
                )}
              </div>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
