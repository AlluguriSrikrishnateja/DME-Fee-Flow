import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_smtp_alert():
    # 📝 ENTER THE EXACT SAME EMAIL CREDENTIALS YOU SET IN YOUR AUTOMATION.PY
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "srikrishnaalluguri@gmail.com"      # Your Gmail address
    sender_password = "zhcd dvxq oapf qtbi"           # Your 16-character App Password
    admin_email = "your_receiver_email@domain.com"     # The destination inbox

    print("🔌 Opening connection to Gmail SMTP Server...")
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = admin_email
    msg['Subject'] = "🧪 DME Fee Flow - Live SMTP Delivery Test"

    body = """
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #0284c7;">SMTP Verification Successful</h2>
        <p>If you are reading this message, your automated email connection framework is fully authenticating and clear to pass notifications.</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Secure the connection
            print("🔑 Authenticating with Google security keys...")
            server.login(sender_email, sender_password)
            
            print("📨 Sending test alert payload...")
            server.sendmail(sender_email, admin_email, msg.as_string())
            
        print("✅ Success! The test email has left the server and is heading to your inbox.")
        print("👉 Check your spam/junk folder if you don't see it in your primary inbox within 2 minutes.")
    except Exception as e:
        print("\n❌ SMTP Connection Refused!")
        print(f"Error Details: {e}")
        print("\n💡 Common Fixes:\n1. Ensure Two-Factor Authentication (2FA) is ON in your Google Account.\n2. Double-check that your App Password has no typos.")

if __name__ == "__main__":
    test_smtp_alert()