import pymysql

def setup_database():
    # 📝 UPDATE THESE TO MATCH YOUR MYSQL WORKBENCH CREDENTIALS
    db_config = {
        "host": "localhost",          # Running locally
        "port": 3306,                 # Default MySQL port
        "user": "root",               # Your MySQL username (usually root)
        "password": "MySQL@123", # Change this to your actual MySQL Workbench password!
        "database": "medical_fee_db"   # The schema/database name
    }

    # The SQL blueprint for MySQL syntax
    create_status_table = """
    CREATE TABLE IF NOT EXISTS pipeline_status (
        id INT AUTO_INCREMENT PRIMARY KEY,
        status VARCHAR(50) NOT NULL,
        total_records_processed INT DEFAULT 0,
        last_run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        error_message TEXT DEFAULT NULL
    );
    """

    create_audit_table = """
    CREATE TABLE IF NOT EXISTS file_audit_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        filename VARCHAR(255) NOT NULL,
        records_extracted INT NOT NULL,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    try:
        print("🔌 Attempting to connect to your local MySQL server...")
        # Connect to MySQL (without database first, just in case the schema doesn't exist yet)
        conn = pymysql.connect(
            host=db_config["host"],
            port=db_config["port"],
            user=db_config["user"],
            password=db_config["password"]
        )
        cur = conn.cursor()
        
        # Create the database schema if you haven't created it in Workbench yet
        print(f"🏗️ Ensuring database '{db_config['database']}' exists...")
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']};")
        cur.execute(f"USE {db_config['database']};")
        
        print("🏗️ Building 'pipeline_status' and 'file_audit_logs' tables...")
        cur.execute(create_status_table)
        cur.execute(create_audit_table)
        
        # Commit the changes and close connections
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Success! MySQL Database setup is complete. Tables are ready.")
        
    except Exception as e:
        print("\n❌ MySQL Connection Failed!")
        print(f"Error Details: {e}")
        print("\n💡 Tip: Make sure your MySQL Workbench is running, and that the 'password' and 'user' fields match your login details exactly.")

if __name__ == "__main__":
    setup_database()