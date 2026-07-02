import re
import os

filepath = "/Users/malaymoliya/Desktop/Lead engine/Scrapling/lead_generation_app/frontend/src/App.jsx"
with open(filepath, "r") as f:
    content = f.read()

# 1. Add imports for react-router-dom
if "react-router-dom" not in content:
    content = content.replace(
        "import React, { useState, useEffect, useRef } from 'react';",
        "import React, { useState, useEffect, useRef } from 'react';\nimport { Routes, Route, useNavigate, useLocation } from 'react-router-dom';"
    )

# 2. Replace activeTab state with useLocation and useNavigate
content = re.sub(
    r"const \[activeTab, setActiveTab\] = useState\('dashboard'\);.*?\n",
    "const location = useLocation();\n  const navigate = useNavigate();\n  const activeTab = location.pathname.replace('/', '') || 'dashboard';\n",
    content
)

# 3. Replace setActiveTab(...) with navigate('/...')
# Handle setActiveTab('...')
content = re.sub(r"setActiveTab\('([^']+)'\)", r"navigate('/\1')", content)

# 4. Remove formClientName logic
content = re.sub(r"const \[formClientName, setFormClientName\] = useState\(''\);\n", "", content)
content = re.sub(r"client_name: formClientName \|\| null,\n", "", content)
content = re.sub(r"setFormClientName\(''\);", "", content)

# 5. Rename Deploy Mission to Launch Job
content = content.replace("Deploy Mission", "Launch Job")
content = content.replace("Deploying...", "Launching...")

# 6. Fix Industry Picklist Shutter (Add onBlur)
content = content.replace(
    'onFocus={() => setShowIndustryDropdown(true)}',
    'onFocus={() => setShowIndustryDropdown(true)} onBlur={() => setTimeout(() => setShowIndustryDropdown(false), 200)}'
)

# 7. Update budget to total_contacts and record_cap to contacts_per_company in payloads
# Wait, budget is formBudget -> total_contacts
content = content.replace("budget: parseFloat(formBudget),", "total_contacts: parseInt(formBudget, 10),")
content = content.replace("record_cap: parseInt(formRecordCap),", "contacts_per_company: formContactsPerCompany ? parseInt(formContactsPerCompany, 10) : -1,")

# 8. Update table fields and labels
content = content.replace("Total Email Cap", "Total Contacts")
content = content.replace("Contacts / Co.", "Contacts per company")
content = content.replace("Total Target Emails", "Total Contacts")

# 9. Implement <Routes> around the main content section
# In App.jsx, the main content relies on `if (activeTab === 'dashboard') return ...` but it's not structured that way, it's a huge return statement.
# Let's check how the render is structured.
# Actually, replacing {activeTab === 'dashboard' && (...)} with <Routes> is difficult via regex.
# The user's main complaint was "universal database is not being scene".
# If I just use React Router, `activeTab` driven rendering still works technically!
# Because if `activeTab = location.pathname` then `{activeTab === 'database' && (...)}` WILL RENDER the database when URL is `/database`.
# This perfectly satisfies "all other pages must have their own names in url" WITHOUT needing to rewrite the entire JSX tree to use <Routes>.

# 10. Remove Client from UI
# Table Header
content = content.replace('<th className="p-4 font-semibold">Client</th>', '')
# Table Cell
content = re.sub(r'<td className="p-4 text-gray-400">\{job\.client_name \|\| \'-\'\}</td>\n', '', content)

# Form Field for Client Name
client_field_regex = r'<div[^>]*>\s*<label[^>]*>.*?Client Name.*?</label>\s*<input[^>]*value=\{formClientName\}[^>]*>\s*</div>'
content = re.sub(client_field_regex, '', content, flags=re.DOTALL | re.IGNORECASE)

with open(filepath, "w") as f:
    f.write(content)

print("Frontend refactored successfully.")
