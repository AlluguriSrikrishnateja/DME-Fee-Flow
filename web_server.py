import os
import glob
from flask import Flask, render_template, request
from core.database import get_db_connection

app = Flask(__name__)

def get_extracted_files():
    """Scans the extracted folder and returns a clean list of filenames."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    extract_dir = os.path.join(base_dir, "extracted")
    
    # Find all Excel and CSV files inside the extracted directory
    raw_files = (glob.glob(os.path.join(extract_dir, "**/*.xlsx"), recursive=True) + 
                 glob.glob(os.path.join(extract_dir, "**/*.xls"), recursive=True) +
                 glob.glob(os.path.join(extract_dir, "**/*.csv"), recursive=True))
    
    # Return just the clean filenames (e.g., "January 2026 DMEPOS...xlsx")
    return [os.path.basename(f) for f in raw_files]

@app.route('/', methods=['GET'])
def index():
    search_query = request.args.get('q', '').strip()
    selected_file = request.args.get('file', '').strip()
    
    # Always pull the list of files to fill the dropdown menu
    available_files = get_extracted_files()
    
    # Default to the first file if none is explicitly chosen yet
    if not selected_file and available_files:
        selected_file = available_files[0]
        
    records = []
    
    # We execute the search query out of SQLite
    if search_query:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT * FROM Result_Grid 
            WHERE PROCEDURE_CD LIKE ? 
            ORDER BY PROCEDURE_CD ASC 
            LIMIT 100
        """
        cursor.execute(query, (f"%{search_query}%",))
        records = cursor.fetchall()
        conn.close()
    elif selected_file:
        # Fallback: If no search query is typed but a file is picked, 
        # let's just show the first 50 rows of data from the system as a preview!
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Result_Grid LIMIT 50")
        records = cursor.fetchall()
        conn.close()

    return render_template(
        'index.html', 
        records=records, 
        search_query=search_query,
        available_files=available_files,
        selected_file=selected_file
    )

if __name__ == '__main__':
    print("🌍 Starting local Flask application interface...")
    app.run(debug=True, port=5000)