import os
import glob
import logging
import io
import zipfile
import pandas as pd
import requests
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import pymysql

# Setup logging architecture
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)

# --- DATABASE CONFIGURATION ---
DB_CONFIG = {
    "host": "127.0.0.1",  # Updated to 127.0.0.1 for stability
    "port": 3306,
    "user": "root",
    "password": "MySQL@123",
    "database": "medical_fee_db",
    "cursorclass": pymysql.cursors.DictCursor
}


# --- DIRECTORY CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'downloads')
EXTRACT_DIR = os.path.join(BASE_DIR, 'extracted')

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)


# =====================================================================
# --- CORE DME WORKFLOW ROUTES (ORIGINAL CODE) ------------------------
# =====================================================================

@app.route('/', methods=['GET'])
def render_dashboard():
    return render_template('index.html')


@app.route('/api/pipeline/run', methods=['POST'])
def execute_ingestion():
    payload = request.json or {}
    target_year = str(payload.get('year', '')).strip()
    target_quarter = str(payload.get('quarter', '')).strip().upper()
    
    if not target_year or not target_quarter:
        return jsonify({"status": "error", "message": "Parameters 'year' and 'quarter' are required."}), 400

    quarter_map = {"JAN": "january", "APR": "april", "JUL": "july", "OCT": "october"}
    month_name = quarter_map.get(target_quarter, "april")
    
    possible_folders = [
        os.path.join(EXTRACT_DIR, f"{target_year}-{month_name}-dmepos-jurisdiction-list"),
        os.path.join(EXTRACT_DIR, f"{target_year}-dmepos-jurisdiction-list"),
        os.path.join(EXTRACT_DIR, target_year)
    ]
    
    target_folder = next((f for f in possible_folders if os.path.exists(f)), None)
    if not target_folder:
        return jsonify({"status": "error", "message": "Data directory not found."}), 404

    csv_files = [os.path.join(root, f) for root, _, files in os.walk(target_folder) for f in files if f.lower().endswith('.csv')]
    if not csv_files:
        return jsonify({"status": "error", "message": "No CSV file found."}), 404
    
    target_csv = csv_files[0]
    filename = os.path.basename(target_csv)

    try:
        df = pd.read_csv(target_csv, skiprows=6, encoding='cp1252')
        df.columns = df.columns.str.strip()
        
        parsed_records = []
        for _, row in df.iterrows():
            hcpcs_code = str(row.get('HCPCS', '')).strip()
            jurisdiction = str(row.get('JURISDICTION', '')).strip()
            if not hcpcs_code or hcpcs_code == 'nan' or len(hcpcs_code) > 15: continue
            parsed_records.append((hcpcs_code, jurisdiction if jurisdiction != 'nan' else 'ALL', int(target_year), 0.00, filename))

        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE fee_schedule_records;")
            cursor.executemany("INSERT INTO fee_schedule_records (procedure_cd, state_cd, pricing_year, allowance_amt, filename) VALUES (%s, %s, %s, %s, %s)", parsed_records)
            cursor.execute("TRUNCATE TABLE pipeline_status;")
            cursor.execute("INSERT INTO pipeline_status (status, total_records_processed, error_message) VALUES ('SUCCESS', %s, 'Processed.')", (len(parsed_records),))
            conn.commit()
        return jsonify({"status": "success", "inserted_rows": len(parsed_records)}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'conn' in locals() and conn.open: conn.close()


@app.route('/api/pipeline/records', methods=['GET'])
def fetch_grid_data():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, procedure_cd, state_cd, pricing_year, allowance_amt, filename FROM fee_schedule_records;")
            dataset = cursor.fetchall()
        return jsonify({"status": "success", "data": dataset}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'conn' in locals() and conn.open: conn.close()


# =====================================================================
# --- ZIP CODES EXTENSION (ORIGINAL CODE) -----------------------------
# =====================================================================

@app.route('/api/zip-codes/import', methods=['POST'])
def import_zip_codes():
    payload = request.json or {}
    url = payload.get('url', '').strip()
    if not url: return jsonify({"status": "error", "message": "URL required."}), 400
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        response.raise_for_status()
        excel_data = response.content
        if url.lower().endswith('.zip') or zipfile.is_zipfile(io.BytesIO(response.content)):
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                files = [f for f in z.namelist() if f.lower().endswith(('.xlsx', '.xls'))]
                excel_data = z.read(files[0])
        df = pd.read_excel(io.BytesIO(excel_data))
        df.columns = df.columns.str.strip()
        df_mapped = df[['YEAR/QTR', 'ZIP CODE', 'CARRIER', 'LOCALITY']].rename(columns={
            'YEAR/QTR': 'zip_fee_year', 'ZIP CODE': 'zip_code', 'CARRIER': 'mdcr_carrier_id', 'LOCALITY': 'mdcr_fee_schd_id'
        })
        parsed_records = list(df_mapped.itertuples(index=False, name=None))
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE dme_zip_fee_flow;")
            cursor.executemany("INSERT INTO dme_zip_fee_flow (zip_fee_year, zip_code, mdcr_carrier_id, mdcr_fee_schd_id) VALUES (%s, %s, %s, %s)", parsed_records)
            conn.commit()
        return jsonify({"status": "success", "inserted_rows": len(parsed_records)}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'conn' in locals() and conn.open: conn.close()


@app.route('/api/zip-codes/records', methods=['GET'])
def fetch_zip_grid_data():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, zip_fee_year, zip_code, mdcr_carrier_id, mdcr_fee_schd_id FROM dme_zip_fee_flow;")
            dataset = cursor.fetchall()
        return jsonify({"status": "success", "data": dataset}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'conn' in locals() and conn.open: conn.close()


# =====================================================================
# --- ANESTHESIA EXTENSION (UPDATED WITH DEBUGGING) -------------------
# =====================================================================

@app.route('/api/anesthesia/import', methods=['POST'])
def import_anesthesia():
    payload = request.json or {}
    url = payload.get('url', '').strip()
    if not url: return jsonify({"status": "error", "message": "URL is required."}), 400
    
    try:
        # Debugging step: Check connection
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE();")
            print(f"DEBUG: Flask is connected to database: {cursor.fetchone()}")
        
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        response.raise_for_status()
        excel_data = response.content
        if url.lower().endswith('.zip') or zipfile.is_zipfile(io.BytesIO(response.content)):
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                files = [f for f in z.namelist() if f.lower().endswith(('.xlsx', '.xls'))]
                if not files: return jsonify({"status": "error", "message": "No spreadsheet in ZIP."}), 400
                excel_data = z.read(files[0])
        
        df = pd.read_excel(io.BytesIO(excel_data), skiprows=4)
        df.columns = df.columns.str.strip()
        target_col = next((c for c in df.columns if 'National Anes' in c), None)
        if not target_col:
            return jsonify({"status": "error", "message": f"Could not find conversion factor column. Available: {df.columns.tolist()}"}), 400

        df = df.rename(columns={'Contractor': 'mdcr_carrier_id', 'Locality': 'mdcr_fee_schd_id', target_col: 'conv_factor_amt'})
        df['pricing_year'] = 2026
        df = df[['pricing_year', 'mdcr_carrier_id', 'mdcr_fee_schd_id', 'conv_factor_amt']].dropna()
        
        records = df.to_dict('records')
        
        with conn.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE anesthesia_fee_schedules;")
            sql = "INSERT INTO anesthesia_fee_schedules (pricing_year, mdcr_carrier_id, mdcr_fee_schd_id, conv_factor_amt) VALUES (%s, %s, %s, %s)"
            for row in records:
                cursor.execute(sql, (row['pricing_year'], row['mdcr_carrier_id'], row['mdcr_fee_schd_id'], row['conv_factor_amt']))
            conn.commit()
            
        return jsonify({"status": "success", "inserted_rows": len(records)}), 200
    except Exception as e:
        logging.error(f"Anesthesia import error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'conn' in locals() and conn.open: conn.close()


@app.route('/api/anesthesia/records', methods=['GET'])
def fetch_anesthesia_records():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, pricing_year, mdcr_carrier_id, mdcr_fee_schd_id, conv_factor_amt FROM anesthesia_fee_schedules;")
            dataset = cursor.fetchall()
        return jsonify({"status": "success", "data": dataset}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'conn' in locals() and conn.open: conn.close()


if __name__ == '__main__':
    logging.info("Initializing DME Fee Flow Platform Engine Core...")
    app.run(debug=True, port=5000)