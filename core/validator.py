import os
import glob
import re
import warnings
import pandas as pd

# Mute the noisy fragmentation warnings from flooding the console
warnings.filterwarnings('ignore', category=pd.errors.PerformanceWarning)

class DMEValidator:
    def __init__(self, extract_dir="extracted"):
        self.extract_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), extract_dir)
        self.required_columns = [
            'PROCEDURE_CD', 'STATE_CD', 'PRICING_YEAR', 'ALLOWANCE_AMT',
            'PROCD_MOD_CD1', 'PROCD_MOD_EFF_DT1', 'PROCD_MOD_CD2', 'PROCD_MOD_EFF_DT2'
        ]

    def find_all_data_files(self):
        """Scans the entire tree depth of the extraction workspace for spreadsheet files."""
        return (glob.glob(os.path.join(self.extract_dir, "**/*.xlsx"), recursive=True) + 
                glob.glob(os.path.join(self.extract_dir, "**/*.xls"), recursive=True) +
                glob.glob(os.path.join(self.extract_dir, "**/*.csv"), recursive=True))

    def process_all_files(self):
        """Processes every discovered spreadsheet and returns a single merged collection of records."""
        file_paths = self.find_all_data_files()
        if not file_paths:
            print("❌ Validation Error: Extraction repository workspace is empty.")
            return None
            
        all_records = []
        print(f"📖 Batch Pipeline: Processing {len(file_paths)} extracted sheets...")
        
        for file_path in file_paths:
            filename = os.path.basename(file_path)
            print(f"📄 Scrubbing Sheet: {filename}")
            
            # Extract the calendar year from the filename using regex
            year_match = re.search(r'(20\d{2}|\d{2})', filename)
            inferred_year = 2026
            if year_match:
                extracted_year = year_match.group(1)
                inferred_year = int(extracted_year) if len(extracted_year) == 4 else int(f"20{extracted_year}")

            # --- PROTECTED ENCODING FILE READ SYSTEM ---
            if file_path.endswith('.csv'):
                try:
                    df_raw = pd.read_csv(file_path, header=None)
                except UnicodeDecodeError:
                    df_raw = pd.read_csv(file_path, header=None, encoding='latin1')
            else:
                df_raw = pd.read_excel(file_path, header=None)

            # Smart Scanner row alignment logic
            target_keywords = {
                'hcpcs', 'code', 'procedure code', 'procedure_cd', 
                'jurisdiction', 'description', 'category', 'state_cd',
                'pricing_year', 'allowance_amt'
            }
            skip_rows = 0
            found_headers = False

            for idx, row in df_raw.iterrows():
                row_vals = [str(val).strip().lower() for val in row.dropna()]
                if any(val in target_keywords for val in row_vals):
                    skip_rows = idx
                    found_headers = True
                    break

            # Reload with precise data offset grid positions and matching encoding fallbacks
            if found_headers:
                if file_path.endswith('.csv'):
                    try:
                        df = pd.read_csv(file_path, skiprows=skip_rows)
                    except UnicodeDecodeError:
                        df = pd.read_csv(file_path, skiprows=skip_rows, encoding='latin1')
                else:
                    df = pd.read_excel(file_path, skiprows=skip_rows)
            else:
                for idx, row in df_raw.iterrows():
                    first_cell = str(row.iloc[0]).strip().lower()
                    if first_cell and not first_cell.startswith('note') and not 'unnamed' in first_cell:
                        skip_rows = idx
                        break
                if file_path.endswith('.csv'):
                    try:
                        df = pd.read_csv(file_path, skiprows=skip_rows)
                    except UnicodeDecodeError:
                        df = pd.read_csv(file_path, skiprows=skip_rows, encoding='latin1')
                else:
                    df = pd.read_excel(file_path, skiprows=skip_rows)

            df.columns = [str(c).strip() for c in df.columns]
            
            mapping = {
                'PROCEDURE_CD': 'PROCEDURE_CD',
                'STATE_CD': 'STATE_CD',
                'PRICING_YEAR': 'PRICING_YEAR',
                'ALLOWANCE_AMT': 'ALLOWANCE_AMT',
                'PROCD_MOD_CD1': 'PROCD_MOD_CD1',
                'PROCD_MOD_EFF_DT1': 'PROCD_MOD_EFF_DT1',
                'PROCD_MOD_CD2': 'PROCD_MOD_CD2',
                'PROCD_MOD_EFF_DT2': 'PROCD_MOD_EFF_DT2',
                'HCPCS': 'PROCEDURE_CD', 
                'HCPCS Code': 'PROCEDURE_CD', 
                'Code': 'PROCEDURE_CD',
                'Jurisdiction': 'STATE_CD', 
                'Category': 'STATE_CD', 
                'STATE': 'STATE_CD', 
                'State': 'STATE_CD',
                'YEAR': 'PRICING_YEAR', 
                'Year': 'PRICING_YEAR',
                'FEE': 'ALLOWANCE_AMT', 
                'Fee': 'ALLOWANCE_AMT', 
                'Amount': 'ALLOWANCE_AMT',
                'MOD': 'PROCD_MOD_CD1', 
                'Mod': 'PROCD_MOD_CD1', 
                'MOD2': 'PROCD_MOD_CD2',
                'EFF_DATE': 'PROCD_MOD_EFF_DT1', 
                'EFF_DATE2': 'PROCD_MOD_EFF_DT2'
            }
            df = df.rename(columns=mapping)

            # Set robust safe defaults
            if 'PRICING_YEAR' not in df.columns or df['PRICING_YEAR'].isnull().all():
                df['PRICING_YEAR'] = inferred_year
            if 'PROCD_MOD_CD1' not in df.columns: df['PROCD_MOD_CD1'] = ''
            if 'PROCD_MOD_EFF_DT1' not in df.columns: df['PROCD_MOD_EFF_DT1'] = f'{inferred_year}-01-01'
            if 'PROCD_MOD_CD2' not in df.columns: df['PROCD_MOD_CD2'] = ''
            if 'PROCD_MOD_EFF_DT2' not in df.columns: df['PROCD_MOD_EFF_DT2'] = f'{inferred_year}-01-01'
            
            if 'STATE_CD' not in df.columns:
                for fallback_col in ['Jurisdiction Description', 'Fee Schedule', 'Description', 'Category']:
                    if fallback_col in df.columns:
                        df['STATE_CD'] = df[fallback_col]
                        break

            if 'ALLOWANCE_AMT' not in df.columns:
                df['ALLOWANCE_AMT'] = 0.0

            for col in self.required_columns:
                if col not in df.columns:
                    df[col] = None

            # Explicit copy to force internal de-fragmentation
            df = df[self.required_columns].copy()
            
            df['PROCEDURE_CD'] = df['PROCEDURE_CD'].fillna('UNKNOWN').astype(str).str.strip()
            df['STATE_CD'] = df['STATE_CD'].fillna('US').astype(str).str.strip()
            df['PRICING_YEAR'] = df['PRICING_YEAR'].fillna(inferred_year).astype(int)
            df['ALLOWANCE_AMT'] = pd.to_numeric(df['ALLOWANCE_AMT'], errors='coerce').fillna(0.0)

            df = df[~df['PROCEDURE_CD'].str.lower().isin(['hcpcs', 'hcpcs code', 'code', 'unknown'])]
            
            file_records = list(df.itertuples(index=False, name=None))
            print(f"✨ Extracted {len(file_records)} records from {filename}")
            all_records.extend(file_records)
            
        print(f"\n📊 Batch Processing Complete: Formatted {len(all_records)} total records.")
        return all_records

if __name__ == "__main__":
    validator = DMEValidator()
    validator.process_all_files()