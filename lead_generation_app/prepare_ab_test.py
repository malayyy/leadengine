import pandas as pd
import json
import os
import glob
import math

TARGET_ACCOUNTS = [
    "AdvancedCleaning.csv",
    "AppellStripingNorthJersey.xlsx",
    "AstraCleaningServices.xlsx",
    "BHSSolutionsLLC.xlsx",
    "DiscoveriesBroughtToLife.xlsx",
    "FlatRoofWaterproofingSolutions.xlsx",
    "LawPracticeAI.xlsx",
    "MerchantPayConnect.xlsx",
    "PrestigeBuildingMaintenance.xlsx",
    "StratusTwinCities.xlsx",
    "System4NorthFlorida.xlsx",
    "HSCGroup.xlsx"
]

def find_file(filename):
    for root, dirs, files in os.walk('For ICP Campiagns'):
        if filename in files:
            return os.path.join(root, filename)
    return None

def clean_value(val):
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, float):
        if math.isnan(val):
            return ""
        if val.is_integer():
            return str(int(val))
    return str(val).strip()

def process_accounts():
    all_payloads = []
    
    # Read the main mapping sheet to get the Verticals (Industries) for each account
    try:
        master_df = pd.read_excel('ICP Order For 2 Moths.xlsx')
    except Exception as e:
        print(f"Error reading master excel: {e}")
        return

    for account_file in TARGET_ACCOUNTS:
        file_path = find_file(account_file)
        if not file_path:
            print(f"Warning: Could not find {account_file}")
            continue
            
        print(f"Processing {account_file}...")
        
        # Determine account name from filename (rough mapping to match master sheet)
        account_basename = account_file.replace('.xlsx', '').replace('.csv', '')
        
        # Read the specific account file
        try:
            if account_file.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue
            
        # Extract job titles
        titles = set()
        if 'Job_Title' in df.columns:
            for t in df['Job_Title'].dropna().unique():
                t = str(t).replace('%', '').strip()
                if t: titles.add(t)
        
        # Extract locations
        zip_codes = set()
        if 'zip_code' in df.columns:
            for z in df['zip_code'].dropna().unique():
                z_clean = clean_value(z)
                if z_clean: zip_codes.add(z_clean)
        
        states = set()
        if 'State' in df.columns:
            for s in df['State'].dropna().unique():
                s_clean = clean_value(s)
                if s_clean: states.add(s_clean)
                
        # Find the matching verticals in the master sheet
        # We'll just do a rough string match on the Account Name column
        verticals = set()
        for idx, row in master_df.iterrows():
            master_name = str(row.get('Account Name', '')).replace(' ', '').lower()
            target_name = account_basename.replace(' ', '').lower()
            if target_name in master_name or master_name in target_name:
                for col in range(1, 7):
                    vert_col = f"Vertical # {col}"
                    if vert_col in master_df.columns:
                        v = row.get(vert_col)
                        if pd.notna(v) and str(v).strip():
                            verticals.add(str(v).strip())
                break # found the account
                
        # If we couldn't find verticals in the master sheet, see if it's in the sub-file
        if not verticals and 'industry' in df.columns:
             for i in df['industry'].dropna().unique():
                i_clean = clean_value(i)
                if i_clean: verticals.add(i_clean)
        
        payload = {
            "campaign_name": account_basename,
            "target_industries": list(verticals),
            "target_titles": list(titles),
            "target_locations": list(zip_codes) if zip_codes else list(states),
            "total_contacts": 50,
            "contacts_per_company": 2
        }
        all_payloads.append(payload)
        
    with open('test_payloads.json', 'w') as f:
        json.dump(all_payloads, f, indent=4)
        
    print(f"\nSuccessfully generated payloads for {len(all_payloads)} accounts.")
    print("Saved to test_payloads.json")

if __name__ == "__main__":
    process_accounts()
