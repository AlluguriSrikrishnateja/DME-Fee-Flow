import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pymysql

class AutomationEngine:
    def __init__(self):
        # 📝 Match these exactly with the credentials that just worked in your setup!
        self.db_config = {
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "MySQL@123", # Update with your working password
            "database": "medical_fee_db"
        }
        
        # SMTP email server configuration (Example using Gmail SMTP)
        # 💡 Note: If you don't have an active SMTP server yet, the code catches the error gracefully
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = "srikrishnaalluguri@gmail.com"
        self.sender_password = "zhcd dvxq oapf qtbi"
        self.admin_email = "admin-alert-recipient@company.com"

    def _get_connection(self):
        return pymysql.connect(**self.db_config)

    def update_pipeline_status(self, status, records_count=0, error_msg=None):
        """Updates the tracking row so the UI dashboard knows the exact state of the pipeline."""
        query = """
            INSERT INTO pipeline_status (status, total_records_processed, error_message)
            VALUES (%s, %s, %s);
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(query, (status, records_count, error_msg))
                conn.commit()
            conn.close()
            print(f"🗄️ Database Alert State Logged: {status}")
        except Exception as e:
            print(f"❌ Failed to write pipeline status to MySQL: {e}")

    def log_file_ingestion(self, filename, record_count):
        """Tracks separate files processed for an itemized audit trail view on the UI."""
        query = "INSERT INTO file_audit_logs (filename, records_extracted) VALUES (%s, %s);"
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(query, (filename, record_count))
                conn.commit()
            conn.close()
            print(f"📄 Audit Trail Logged: {filename} ({record_count} rows)")
        except Exception as e:
            print(f"❌ Failed to log file audit trail: {e}")

    def send_missing_assets_email(self, details="No valid CMS files found."):
        """Dispatches an email warning if the scraping phase returns empty."""
        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['To'] = self.admin_email
        msg['Subject'] = "🚨 AUTOMATION INTERRUPT: CMS Source Files Missing"

        body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #d9534f;">Pipeline Halted Automatically</h2>
            <p>The <b>DME Fee Flow Engine</b> checked for incoming source files but could not proceed.</p>
            <table border="1" cellpadding="8" style="border-collapse: collapse; border-color: #eee; width: 100%;">
              <tr bgcolor="#f5f5f5"><td><b>System Event</b></td><td>Asset Discrepancy Alert</td></tr>
              <tr><td><b>Details Logged</b></td><td>{details}</td></tr>
              <tr bgcolor="#f9f9f9"><td><b>Database Status Flag</b></td><td><span style="color: red; font-weight: bold;">FAILED_MISSING_ASSETS</span></td></tr>
            </table>
            <p><i>The system database alert status has been changed to notify the UI dashboard. Please verify the extraction folder directory.</i></p>
          </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, self.admin_email, msg.as_string())
            print("📧 Alert Email dispatched successfully to the monitoring queue.")
        except Exception as e:
            print(f"⚠️ Email dispatch skipped or SMTP not configured ({e}). Database status fallback active.")