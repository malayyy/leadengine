import re

filepath = "/Users/malaymoliya/Desktop/Lead engine/Scrapling/lead_generation_app/frontend/src/App.jsx"
with open(filepath, "r") as f:
    content = f.read()

# 1. Add `detailsTab` state
content = content.replace(
    "const [selectedJob, setSelectedJob] = useState(null);",
    "const [selectedJob, setSelectedJob] = useState(null);\n  const [detailsTab, setDetailsTab] = useState('unified');"
)

# 2. Fix formBudget -> formTotalContacts
content = content.replace("formBudget", "formTotalContacts")
content = content.replace("setFormBudget", "setFormTotalContacts")

# 3. Fix duplicate payload keys
payload_old = """        contacts_per_company: formContactsPerCompany ? parseInt(formContactsPerCompany, 10) : -1,
        contacts_per_company: formContactsPerCompany ? parseInt(formContactsPerCompany) : null"""

payload_new = """        contacts_per_company: formContactsPerCompany ? parseInt(formContactsPerCompany, 10) : -1"""
content = content.replace(payload_old, payload_new)

# 4. Rewrite the Job Details UI
job_details_old = r"\{/\* JOB DETAILS TAB \*/\}.*?\{/\* LAUNCH JOB TAB \*/\}"

job_details_new = """{/* JOB DETAILS TAB */}
          {activeTab === 'job_details' && selectedJob && (
             <div className="space-y-6 animate-in fade-in slide-in-from-right-8 duration-500 max-w-7xl mx-auto">
               <div className="flex flex-col md:flex-row items-start md:items-center justify-between bg-white/5 backdrop-blur-lg border border-white/10 p-6 rounded-2xl shadow-2xl">
                 <div>
                   <h2 className="text-3xl font-bold text-white tracking-tight flex items-center">
                     Job Workspace 
                     <span className="text-gray-500 ml-3 text-xl font-medium">#{selectedJob.job_id}</span>
                   </h2>
                   <div className="flex items-center mt-3 space-x-3">
                     <span className={`px-2 py-0.5 text-xs font-bold uppercase rounded ${selectedJob.status==='running' ? 'bg-blue-500 text-white animate-pulse' : selectedJob.status==='completed'?'bg-emerald-500 text-white' : 'bg-gray-700 text-gray-300'}`}>{selectedJob.status}</span>
                     <span className="text-gray-400 text-sm font-medium">{selectedJob.records.length} Raw Extracted</span>
                     <span className="text-gray-400 text-sm">&bull;</span>
                     <span className="text-gray-400 text-sm font-medium">{selectedJob.leads.length} Leads Enriched</span>
                   </div>
                 </div>
                 <div className="mt-4 md:mt-0">
                    <button onClick={() => downloadJobCSV(selectedJob.job_id)} className="flex items-center space-x-2 bg-white/10 hover:bg-white/20 text-white px-4 py-2 rounded-xl border border-white/10 transition-colors">
                      <Download size={16} /> <span>Export CSV</span>
                    </button>
                 </div>
               </div>

               {/* Tabs */}
               <div className="flex items-center space-x-2 bg-black/40 p-1.5 rounded-xl border border-white/5 w-fit">
                 <button onClick={() => setDetailsTab('unified')} className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${detailsTab === 'unified' ? 'bg-blue-600 text-white shadow' : 'text-gray-400 hover:text-white'}`}>Unified Data</button>
                 <button onClick={() => setDetailsTab('gmaps')} className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${detailsTab === 'gmaps' ? 'bg-blue-600 text-white shadow' : 'text-gray-400 hover:text-white'}`}>Raw GMaps</button>
                 <button onClick={() => setDetailsTab('linkedin')} className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${detailsTab === 'linkedin' ? 'bg-blue-600 text-white shadow' : 'text-gray-400 hover:text-white'}`}>LinkedIn Leads</button>
                 <button onClick={() => setDetailsTab('emails')} className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${detailsTab === 'emails' ? 'bg-blue-600 text-white shadow' : 'text-gray-400 hover:text-white'}`}>Verified Emails</button>
               </div>

               {/* Unified Master Table */}
               {detailsTab === 'unified' && (
                 <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl animate-in fade-in duration-300">
                  <div className="overflow-x-auto max-h-[600px] custom-scrollbar">
                    <table className="w-full text-left border-collapse text-sm whitespace-nowrap">
                      <thead className="sticky top-0 bg-[#0f172a] shadow-md z-10">
                        <tr className="uppercase tracking-widest text-[10px] text-gray-500 border-b border-white/10 bg-black/40">
                          <th className="p-4 font-semibold text-blue-400 border-r border-white/5">Candidate Name</th>
                          <th className="p-4 font-semibold text-blue-400 border-r border-white/5">Title</th>
                          <th className="p-4 font-semibold text-blue-400 border-r border-white/5">Email & Status</th>
                          <th className="p-4 font-semibold text-blue-400 border-r border-white/5">LinkedIn Profile</th>
                          <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Company</th>
                          <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Industry</th>
                          <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Website</th>
                          <th className="p-4 font-semibold text-emerald-400">Location</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {unifiedRows.length === 0 && <tr><td colSpan="8" className="p-8 text-center text-gray-500 italic">No merged data collected yet.</td></tr>}
                        {unifiedRows.map((r, i) => (
                          <tr key={i} className="hover:bg-white/5 transition-colors">
                            <td className="p-3 text-white border-r border-white/5 font-medium">{r.lead_first !== '-' ? `${r.lead_first} ${r.lead_last}` : <span className="text-gray-600">No Candidate Match</span>}</td>
                            <td className="p-3 text-gray-400 border-r border-white/5">{r.lead_title}</td>
                            <td className="p-3 border-r border-white/5">
                               {r.lead_email !== '-' && r.lead_email ? (
                                 <div className="flex flex-col">
                                   <span className="text-gray-200">{r.lead_email}</span>
                                   <span className={`text-[10px] uppercase font-bold mt-0.5 w-fit px-1.5 rounded ${r.email_status==='valid'||r.email_status==='catch_all'?'bg-emerald-500/20 text-emerald-400':'bg-red-500/20 text-red-400'}`}>{r.email_status}</span>
                                 </div>
                               ) : <span className="text-gray-600">-</span>}
                            </td>
                            <td className="p-3 border-r border-white/5">
                              {r.lead_linkedin !== '-' && r.lead_linkedin ? (
                                <a href={r.lead_linkedin} target="_blank" rel="noreferrer" className="text-blue-400 hover:text-blue-300 hover:underline flex items-center"><LinkIcon size={12} className="mr-1"/> Profile</a>
                              ) : <span className="text-gray-600">-</span>}
                            </td>
                            <td className="p-3 text-gray-300 border-r border-white/5 font-semibold">{r.company_name}</td>
                            <td className="p-3 text-gray-400 border-r border-white/5">{r.industry}</td>
                            <td className="p-3 border-r border-white/5">
                              {r.website ? <a href={r.website} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-white hover:underline transition-colors">{new URL(r.website).hostname.replace('www.','')}</a> : <span className="text-gray-600">-</span>}
                            </td>
                            <td className="p-3 text-gray-500">{r.address} <span className="text-gray-400 ml-1">{r.city}, {r.state}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                 </div>
               )}

               {/* GMaps Table */}
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
                        {selectedJob.records.length === 0 && <tr><td colSpan="8" className="p-8 text-center text-gray-500 italic">No companies extracted.</td></tr>}
                        {selectedJob.records.map((r, i) => (
                          <tr key={i} className="hover:bg-white/5 transition-colors">
                            <td className="p-3 text-white font-medium border-r border-white/5">{r.company_name}</td>
                            <td className="p-3 text-gray-400 border-r border-white/5">{r.industry}</td>
                            <td className="p-3 border-r border-white/5">
                              {r.website ? <a href={r.website} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-white hover:underline transition-colors">{r.website}</a> : <span className="text-gray-600">-</span>}
                            </td>
                            <td className="p-3 text-gray-400 border-r border-white/5">{r.phone || '-'}</td>
                            <td className="p-3 text-yellow-500 border-r border-white/5">{r.rating ? `${r.rating} ⭐` : '-'}</td>
                            <td className="p-3 text-gray-500 border-r border-white/5">{r.address || '-'}</td>
                            <td className="p-3 text-gray-400 border-r border-white/5">{r.city}, {r.state} {r.zip_code}</td>
                            <td className="p-3 text-gray-500">
                              {r.gmaps_url ? <a href={r.gmaps_url} target="_blank" rel="noreferrer" className="hover:text-white hover:underline">View Map</a> : '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                 </div>
               )}

               {/* LinkedIn Leads Table */}
               {detailsTab === 'linkedin' && (
                 <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl animate-in fade-in duration-300">
                  <div className="overflow-x-auto max-h-[600px] custom-scrollbar">
                    <table className="w-full text-left border-collapse text-sm whitespace-nowrap">
                      <thead className="sticky top-0 bg-[#0f172a] shadow-md z-10">
                        <tr className="uppercase tracking-widest text-[10px] text-gray-500 border-b border-white/10 bg-black/40">
                          <th className="p-4 font-semibold text-blue-400 border-r border-white/5">Candidate Name</th>
                          <th className="p-4 font-semibold text-blue-400 border-r border-white/5">Job Title</th>
                          <th className="p-4 font-semibold text-blue-400 border-r border-white/5">Company</th>
                          <th className="p-4 font-semibold text-blue-400 border-r border-white/5">LinkedIn URL</th>
                          <th className="p-4 font-semibold text-blue-400">Location / Info</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {selectedJob.leads.length === 0 && <tr><td colSpan="5" className="p-8 text-center text-gray-500 italic">No LinkedIn candidates found.</td></tr>}
                        {selectedJob.leads.map((l, i) => {
                          const company = selectedJob.records.find(rc => rc.id === l.raw_record_id);
                          return (
                          <tr key={i} className="hover:bg-white/5 transition-colors">
                            <td className="p-3 text-white font-medium border-r border-white/5 flex items-center">
                              {l.linkedin_profile_pic_url ? <img src={l.linkedin_profile_pic_url} className="w-6 h-6 rounded-full mr-2 object-cover border border-white/10"/> : <div className="w-6 h-6 rounded-full bg-gray-800 mr-2 flex items-center justify-center text-[10px] font-bold border border-white/10">{l.first_name?.[0] || '?'}</div>}
                              {l.first_name} {l.last_name}
                            </td>
                            <td className="p-3 text-gray-400 border-r border-white/5">{l.title}</td>
                            <td className="p-3 text-gray-300 border-r border-white/5 font-semibold">{company ? company.company_name : 'Unknown'}</td>
                            <td className="p-3 border-r border-white/5">
                              {l.linkedin_url ? <a href={l.linkedin_url} target="_blank" rel="noreferrer" className="text-blue-400 hover:text-blue-300 hover:underline">{l.linkedin_url}</a> : '-'}
                            </td>
                            <td className="p-3 text-gray-500">{l.location || '-'}</td>
                          </tr>
                        )})}
                      </tbody>
                    </table>
                  </div>
                 </div>
               )}

               {/* Verified Emails Table */}
               {detailsTab === 'emails' && (
                 <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl animate-in fade-in duration-300">
                  <div className="overflow-x-auto max-h-[600px] custom-scrollbar">
                    <table className="w-full text-left border-collapse text-sm whitespace-nowrap">
                      <thead className="sticky top-0 bg-[#0f172a] shadow-md z-10">
                        <tr className="uppercase tracking-widest text-[10px] text-gray-500 border-b border-white/10 bg-black/40">
                          <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Valid Email</th>
                          <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Status</th>
                          <th className="p-4 font-semibold text-emerald-400 border-r border-white/5">Confidence</th>
                          <th className="p-4 font-semibold text-gray-400 border-r border-white/5">Person</th>
                          <th className="p-4 font-semibold text-gray-400">Company</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {selectedJob.leads.filter(l => l.email_verification_status === 'valid' || l.email_verification_status === 'catch_all').length === 0 && <tr><td colSpan="5" className="p-8 text-center text-gray-500 italic">No verified emails generated yet.</td></tr>}
                        {selectedJob.leads.filter(l => l.email_verification_status === 'valid' || l.email_verification_status === 'catch_all').map((l, i) => {
                          const company = selectedJob.records.find(rc => rc.id === l.raw_record_id);
                          return (
                          <tr key={i} className="hover:bg-white/5 transition-colors">
                            <td className="p-3 text-white font-medium border-r border-white/5">{l.guessed_email}</td>
                            <td className="p-3 border-r border-white/5">
                              <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${l.email_verification_status==='valid'?'bg-emerald-500/20 text-emerald-400':'bg-yellow-500/20 text-yellow-400'}`}>{l.email_verification_status}</span>
                            </td>
                            <td className="p-3 text-gray-400 border-r border-white/5">
                              <div className="flex items-center space-x-2">
                                <div className="h-1.5 w-16 bg-gray-800 rounded-full overflow-hidden">
                                  <div className="h-full bg-emerald-500" style={{width: `${(l.email_confidence_score||0)*100}%`}}></div>
                                </div>
                                <span className="text-xs">{(l.email_confidence_score||0).toFixed(2)}</span>
                              </div>
                            </td>
                            <td className="p-3 text-gray-400 border-r border-white/5">{l.first_name} {l.last_name}</td>
                            <td className="p-3 text-gray-500">{company ? company.company_name : 'Unknown'}</td>
                          </tr>
                        )})}
                      </tbody>
                    </table>
                  </div>
                 </div>
               )}

             </div>
          )}

          {/* LAUNCH JOB TAB */}"""

content = re.sub(job_details_old, job_details_new, content, flags=re.DOTALL)

with open(filepath, "w") as f:
    f.write(content)

print("App.jsx Job Details Refactored successfully.")
