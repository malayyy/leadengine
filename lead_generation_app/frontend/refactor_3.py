import re

filepath = "/Users/malaymoliya/Desktop/Lead engine/Scrapling/lead_generation_app/frontend/src/App.jsx"
with open(filepath, "r") as f:
    content = f.read()

# 1. Rename "Mission" to "Job"
content = content.replace("Mission Controller", "Job Controller")
content = content.replace("Deploy Mission", "Launch Job")
content = content.replace("Mission #", "Job #")
content = content.replace("Deploying...", "Launching...")

# 2. Fix the numbers input and grid
# The current HTML has a grid-cols-3 and includes the MV Budget block.
# We will rip out the MV Budget block completely and change grid-cols-3 to grid-cols-2
content = content.replace('className="grid grid-cols-3 gap-4"', 'className="grid grid-cols-2 gap-4"')

# Remove MV Budget block
mv_budget_regex = r'<div>\s*<label[^>]*>\s*MV Budget.*?</label>\s*<input[^>]*value=\{formBudget\}[^>]*>\s*</div>'
content = re.sub(mv_budget_regex, '', content, flags=re.DOTALL)

# Also ensure minimum value is 0 instead of -1 for Contacts
content = content.replace('min="-1"', 'min="0"')

# Fix total contacts input placeholder and type
content = content.replace('placeholder="-1 (Unlimited)"', 'placeholder="0 (Unlimited)"')

# 3. Industry Multi-select implementation
# Currently it uses `formIndustry`. We want to change it to an array, but wait...
# The backend payload expects `industry` as a string (`"industry": formIndustry,`).
# If we change it to multiple industries, the backend model `PipelineRequest` needs `industry` to be a `List[str]`, or we just comma separate it!
# Wait, changing `industry` to `List[str]` in backend requires updating `models.py` and `app.py`.
# Instead of full multi-select, maybe just change the placeholder and allow them to type comma-separated values, but the dropdown is tied to a single value.
# Wait, the user said: "on target indestry user must be able to searh and add multiple industries not. just one please"
# Let's change the state in App.jsx from `formIndustry` (string) to `formIndustries` (array).

# Let's write the multi-select React code snippet for industries.
industry_block_old = """<div className="relative">
                      <label className="flex items-center text-xs uppercase tracking-widest text-gray-400 mb-2 font-semibold">
                        Target Industry
                        <Tooltip text="The official Google Business Profile category to target."><Info size={14} className="ml-1 text-gray-500 cursor-help" /></Tooltip>
                      </label>
                      <div className="relative">
                        <input required type="text" placeholder="Search Google Industries..." value={formIndustry} onChange={e => {setFormIndustry(e.target.value); setShowIndustryDropdown(true);}} onFocus={() => setShowIndustryDropdown(true)} onBlur={() => setTimeout(() => setShowIndustryDropdown(false), 200)}
                          className="w-full bg-black/40 text-white border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 p-3.5 rounded-xl outline-none transition-all placeholder-gray-600" />
                        
                      {showIndustryDropdown && (
                        <div className="absolute top-full mt-2 w-full bg-[#111827] border border-white/10 rounded-xl shadow-2xl z-50 max-h-60 overflow-y-auto custom-scrollbar">
                           {GOOGLE_INDUSTRIES.filter(i => i.toLowerCase().includes(formIndustry.toLowerCase())).map(ind => (
                             <div key={ind} onClick={() => {setFormIndustry(ind); setShowIndustryDropdown(false);}} className="p-3 text-sm text-gray-300 hover:bg-blue-600 hover:text-white cursor-pointer transition-colors">
                               {ind}
                             </div>
                           ))}
                           {GOOGLE_INDUSTRIES.filter(i => i.toLowerCase().includes(formIndustry.toLowerCase())).length === 0 && (
                             <div className="p-3 text-sm text-gray-500">No industries found.</div>
                           )}
                        </div>
                      )}
                      </div>
                    </div>"""

industry_block_new = """<div className="relative">
                      <label className="flex items-center text-xs uppercase tracking-widest text-gray-400 mb-2 font-semibold">
                        Target Industries
                        <Tooltip text="Select multiple Google Business Profile categories."><Info size={14} className="ml-1 text-gray-500 cursor-help" /></Tooltip>
                      </label>
                      <div className="flex flex-wrap gap-2 mb-2">
                        {formIndustries.map(ind => (
                          <span key={ind} className="bg-blue-500/20 text-blue-400 px-3 py-1 rounded-full text-sm flex items-center border border-blue-500/30">
                            {ind}
                            <button type="button" onClick={() => setFormIndustries(formIndustries.filter(i => i !== ind))} className="ml-2 hover:text-white">&times;</button>
                          </span>
                        ))}
                      </div>
                      <div className="relative">
                        <input type="text" placeholder="Search and add industries..." value={industrySearch} onChange={e => {setIndustrySearch(e.target.value); setShowIndustryDropdown(true);}} onFocus={() => setShowIndustryDropdown(true)} onBlur={() => setTimeout(() => setShowIndustryDropdown(false), 200)}
                          className="w-full bg-black/40 text-white border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 p-3.5 rounded-xl outline-none transition-all placeholder-gray-600" />
                        
                      {showIndustryDropdown && (
                        <div className="absolute top-full mt-2 w-full bg-[#111827] border border-white/10 rounded-xl shadow-2xl z-50 max-h-60 overflow-y-auto custom-scrollbar">
                           {GOOGLE_INDUSTRIES.filter(i => i.toLowerCase().includes(industrySearch.toLowerCase())).map(ind => (
                             <div key={ind} onClick={() => {if(!formIndustries.includes(ind)) setFormIndustries([...formIndustries, ind]); setIndustrySearch(''); setShowIndustryDropdown(false);}} className="p-3 text-sm text-gray-300 hover:bg-blue-600 hover:text-white cursor-pointer transition-colors">
                               {ind}
                             </div>
                           ))}
                           {GOOGLE_INDUSTRIES.filter(i => i.toLowerCase().includes(industrySearch.toLowerCase())).length === 0 && (
                             <div className="p-3 text-sm text-gray-500">No industries found.</div>
                           )}
                        </div>
                      )}
                      </div>
                    </div>"""

# Ensure we replace exactly
# Since exact multiline replace can fail due to formatting differences, I will use regex or careful parsing.

content = re.sub(
    r'<div className="relative">\s*<label[^>]*>\s*Target Industry.*?</label>\s*<div className="relative">\s*<input.*?</div>\s*</div>', 
    industry_block_new, 
    content, 
    flags=re.DOTALL
)

# Update state variables: add `formIndustries` and remove `formIndustry`
content = content.replace("const [formIndustry, setFormIndustry] = useState('');", "const [formIndustries, setFormIndustries] = useState([]);")

# Update validation
content = content.replace("!formCampaignName || !formIndustry || !formState", "!formCampaignName || formIndustries.length === 0 || !formState")

# Update payload. We will join it with a comma for now so the backend string parsing doesn't break, OR update backend!
# Since backend `PipelineRequest` expects `industry: str`, comma-joining is perfectly fine because Scrapling uses it as a search query anyway, or I can update backend.
# Actually, the user says "search and add multiple industries". Scrapling phase 1 uses the industry string to search maps. 
# "Roofers, Plumbers in AR". Does Google Maps support that? Yes, it supports "Roofers or Plumbers".
# Let's join by comma for the API payload for now.
content = content.replace("industry: formIndustry,", "industry: formIndustries.join(', '),")

# Clear form on launch
content = content.replace("setFormCampaignName(''); setFormIndustry('');", "setFormCampaignName(''); setFormIndustries([]);")

with open(filepath, "w") as f:
    f.write(content)

print("App.jsx refactored successfully.")
