import sqlite3
import datetime
import json
import random

db_path = "/app/lead_generation_app/data/lead_generation.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

now = datetime.datetime.now(datetime.timezone.utc).isoformat()

# Seed Campaign 1: Tech Startups in SF
cur.execute('''
    INSERT INTO campaigns (name, industry, state, target_titles, zipcodes, total_contacts, contacts_per_company, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
''', ('AI Startups Pipeline (SF)', 'Artificial Intelligence', 'CA', json.dumps(['CEO', 'Founder', 'CTO']), json.dumps(['94105', '94107']), 100, 2, 'completed', now))
camp1_id = cur.lastrowid

# Seed Job 1
cur.execute('''
    INSERT INTO jobs (campaign_id, status, mv_credits_used, created_at, completed_at)
    VALUES (?, ?, ?, ?, ?)
''', (camp1_id, 'completed', 45, now, now))
job1_id = cur.lastrowid

# Seed Companies for Job 1
companies = [
    ("NeuralNet Systems", "neuralnet.ai", "San Francisco"),
    ("Quantum Logic AI", "quantumlogic.com", "San Francisco"),
    ("DeepVision Robotics", "deepvision.io", "San Jose"),
    ("Cognitive Cloud", "cognitivecloud.co", "Palo Alto"),
    ("Sentient Data Corp", "sentientdata.ai", "San Francisco")
]

for idx, comp in enumerate(companies):
    cur.execute('''
        INSERT INTO raw_company_records (job_id, company_name, website, city, state, industry, rating, gmaps_url, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (job1_id, comp[0], f"https://www.{comp[1]}", comp[2], "CA", "Artificial Intelligence", round(random.uniform(4.2, 5.0), 1), f"https://maps.google.com/?q={comp[0].replace(' ', '+')}", "enriched"))
    comp_id = cur.lastrowid
    
    # 2 Leads per company
    leads = [
        (f"Sarah{idx}", "Connor", "CEO & Founder", f"https://linkedin.com/in/sarah-connor-{idx}", f"sarah@{comp[1]}", "valid", 0.98),
        (f"John{idx}", "Smith", "Chief Technology Officer", f"https://linkedin.com/in/john-smith-{idx}", f"john.smith@{comp[1]}", "catch_all", 0.85)
    ]
    
    for lead in leads:
        cur.execute('''
            INSERT INTO enriched_leads (raw_record_id, first_name, last_name, title, linkedin_url, guessed_email, email_verification_status, email_confidence_score, location)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (comp_id, lead[0], lead[1], lead[2], lead[3], lead[4], lead[5], lead[6], f"{comp[2]}, CA"))

# Seed Campaign 2: Plumbers in Texas
cur.execute('''
    INSERT INTO campaigns (name, industry, state, target_titles, zipcodes, total_contacts, contacts_per_company, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
''', ('Texas Commercial Plumbers', 'Plumbers', 'TX', json.dumps(['Owner', 'President']), json.dumps(['73301', '75001']), 50, 1, 'completed', now))
camp2_id = cur.lastrowid

cur.execute('''
    INSERT INTO jobs (campaign_id, status, mv_credits_used, created_at, completed_at)
    VALUES (?, ?, ?, ?, ?)
''', (camp2_id, 'completed', 12, now, now))
job2_id = cur.lastrowid

companies2 = [
    ("Texas Pro Plumbing", "texasproplumb.com", "Austin"),
    ("Alamo Pipe Works", "alamopipe.com", "San Antonio"),
    ("Lone Star Drainage", "lonestardrain.com", "Dallas"),
    ("Houston Hydrates", "houstonhydrates.com", "Houston")
]

for idx, comp in enumerate(companies2):
    cur.execute('''
        INSERT INTO raw_company_records (job_id, company_name, website, city, state, industry, rating, gmaps_url, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (job2_id, comp[0], f"http://{comp[1]}", comp[2], "TX", "Plumbers", round(random.uniform(3.5, 4.9), 1), f"https://maps.google.com/?q={comp[0].replace(' ', '+')}", "enriched"))
    comp_id = cur.lastrowid
    
    cur.execute('''
        INSERT INTO enriched_leads (raw_record_id, first_name, last_name, title, linkedin_url, guessed_email, email_verification_status, email_confidence_score, location)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (comp_id, f"Mike{idx}", "Johnson", "Owner", f"https://linkedin.com/in/mike-j-{idx}", f"mike@{comp[1]}", "valid", 0.99, f"{comp[2]}, TX"))

conn.commit()
conn.close()
print("Seeded VPS Database successfully.")
