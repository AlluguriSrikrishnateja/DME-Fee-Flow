import os
import glob
import logging
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import pymysql

# Setup logging architecture
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)

# --- DATABASE CONFIGURATION ---
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "MySQL@123",  # Your local MySQL password
    "database": "medical_fee_db",
    "cursorclass": pymysql.cursors.DictCursor
}

# --- DIRECTORY CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'downloads')
EXTRACT_DIR = os.path.join(BASE_DIR, 'extracted')

# Ensure core directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)


@app.route('/', methods=['GET'])
def render_dashboard():
    """Serves the central administrative UI dashboard application."""
    return render_template('index.html')


@app.route('/api/pipeline/run', methods=['POST'])
def execute_ingestion():
    """Locates cached resources dynamically based on parameters and processes records."""
    payload = request.json or {}
    target_year = str(payload.get('year', '')).strip()
    target_quarter = str(payload.get('quarter', '')).strip().upper()  # e.g., "APR", "JAN"
    
    if not target_year or not target_quarter:
        return jsonify({"status": "error", "message": "Parameters 'year' and 'quarter' are required."}), 400

    # Map abbreviated quarters to full lowercase month folder names
    quarter_map = {
        "JAN": "january",
        "APR": "april",
        "JUL": "july",
        "OCT": "october"
    }
    month_name = quarter_map.get(target_quarter, "april")
    
    # 🔎 DYNAMIC SEARCH ARRAYS: Evaluates custom layout paths vs flat year pathing patterns
    possible_folders = [
        os.path.join(EXTRACT_DIR, f"{target_year}-{month_name}-dmepos-jurisdiction-list"),
        os.path.join(EXTRACT_DIR, f"{target_year}-dmepos-jurisdiction-list"),
        os.path.join(EXTRACT_DIR, target_year)  # Standard fallback for /extracted/2024 or /extracted/2025 folder roots
    ]
    
    target_folder = None
    for folder in possible_folders:
        if os.path.exists(folder):
            target_folder = folder
            break
            
    if not target_folder:
        return jsonify({
            "status": "error",
            "message": f"Data directory not found for Selection Matrix (Year: {target_year}, Quarter: {target_quarter})."
        }), 404

    # Recursively look for ANY target CSV file across nested folders inside the matched root directory
    csv_files = []
    for root, dirs, files in os.walk(target_folder):
        for file in files:
            if file.lower().endswith('.csv'):
                csv_files.append(os.path.join(root, file))

    if not csv_files:
        return jsonify({
            "status": "error", 
            "message": f"No target CSV dataset file found inside the matched hierarchy path: {os.path.basename(target_folder)}"
        }), 404
    
    # Pick the first valid CSV configuration encountered
    target_csv = csv_files[0]
    filename = os.path.basename(target_csv)
    logging.info(f"Processing Dynamic Ingestion Channel: {filename} from path: {target_csv}")

    try:
        import pandas as pd
        
        # ⚡ FIXED ENCODING & PARSING: Skips initial notes rows, decodes using local cp1252 rules safely
        df = pd.read_csv(target_csv, skiprows=6, encoding='cp1252')
        
        # Clean white spaces from columns if any exist
        df.columns = df.columns.str.strip()
        
        # Validate that the expected columns exist
        if 'HCPCS' not in df.columns:
            return jsonify({
                "status": "error", 
                "message": f"File tracking mismatch. 'HCPCS' header column not located on row 7 inside {filename}."
            }), 400

        # Extract values into database matrix rows safely
        parsed_records = []
        for _, row in df.iterrows():
            hcpcs_code = str(row.get('HCPCS', '')).strip()
            jurisdiction = str(row.get('JURISDICTION', '')).strip()
            
            # Skip empty rows or text spillover notes rows safely
            if not hcpcs_code or hcpcs_code == 'nan' or len(hcpcs_code) > 15:
                continue
                
            # Structuring the dataset row to align with MySQL Workbench schema columns
            parsed_records.append((
                hcpcs_code,
                jurisdiction if jurisdiction != 'nan' else 'ALL',
                int(target_year),
                0.00,  # Setting a standard placeholder allowance rate for jurisdiction mappings
                filename
            ))

        # Database Commit Execution Engine
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            # Drop older view records to keep current selection screen isolated
            cursor.execute("TRUNCATE TABLE fee_schedule_records;")
            
            sql = """
                INSERT INTO fee_schedule_records (procedure_cd, state_cd, pricing_year, allowance_amt, filename)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.executemany(sql, parsed_records)
            
            # Commit the pipeline history log table status update
            cursor.execute("TRUNCATE TABLE pipeline_status;")
            cursor.execute("""
                INSERT INTO pipeline_status (status, total_records_processed, error_message)
                VALUES ('SUCCESS', %s, 'Target context processed natively from local storage cache.')
            """, (len(parsed_records),))
            
            conn.commit()
            record_count = len(parsed_records)

        return jsonify({"status": "success", "inserted_rows": record_count}), 200

    except pymysql.MySQLError as db_err:
        logging.error(f"Database operation failed: {db_err}")
        return jsonify({"status": "error", "message": f"Database transactional exception: {str(db_err)}"}), 500
    except Exception as e:
        logging.error(f"Pipeline crashed during execution context: {e}")
        return jsonify({"status": "error", "message": f"Ingestion Engine Exception: {str(e)}"}), 500
    finally:
        if 'conn' in locals() and conn.open:
            conn.close()


@app.route('/api/pipeline/records', methods=['GET'])
def fetch_grid_data():
    """Retrieves target dataset outputs to populate the live dashboard grid view layout."""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, procedure_cd, state_cd, pricing_year, allowance_amt, filename FROM fee_schedule_records;")
            dataset = cursor.fetchall()
        return jsonify({"status": "success", "data": dataset}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'conn' in locals() and conn.open:
            conn.close()


if __name__ == '__main__':
    logging.info("Initializing DME Fee Flow Platform Engine Core...")
    app.run(debug=True, port=5000)