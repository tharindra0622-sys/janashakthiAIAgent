import random
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── In-memory OTP store ─────────────────────────────────────────────────────
# Structure: { customer_id: { 'otp': '123456', 'expires_at': <timestamp> } }
_otp_store: dict = {}


def generate_otp(customer_id: str, expiry_seconds: int = 300) -> str:
    """Generate a 6-digit OTP for the given customer and store it."""
    otp = str(random.randint(100000, 999999))
    _otp_store[customer_id] = {
        'otp': otp,
        'expires_at': time.time() + expiry_seconds
    }
    return otp


def verify_otp(customer_id: str, otp_input: str) -> tuple[bool, str]:
    """
    Verify the OTP submitted by the customer.
    Returns (True, 'ok') on success, or (False, reason) on failure.
    """
    record = _otp_store.get(customer_id)

    if not record:
        return False, "No OTP was sent. Please request a new code."

    if time.time() > record['expires_at']:
        del _otp_store[customer_id]
        return False, "OTP has expired. Please request a new code."

    if record['otp'] != otp_input.strip():
        return False, "Incorrect OTP. Please try again."

    # Success — remove used OTP
    del _otp_store[customer_id]
    return True, "ok"


def send_otp_email(
    to_email: str,
    otp: str,
    customer_name: str,
    mail_user: str,
    mail_password: str,
    mail_server: str = 'smtp.gmail.com',
    mail_port: int = 587
) -> tuple[bool, str]:
    """
    Send the OTP to the customer's registered email via Gmail SMTP.
    Returns (True, '') on success or (False, error_message) on failure.
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Janashakthi — Your Verification Code'
        msg['From']    = f'Janashakthi Insurance <{mail_user}>'
        msg['To']      = to_email

        # Plain-text version
        text_body = (
            f"Dear {customer_name},\n\n"
            f"Your Janashakthi verification code is:\n\n"
            f"  {otp}\n\n"
            f"This code is valid for 5 minutes. Do not share it with anyone.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"Janashakthi Insurance PLC"
        )

        # HTML version
        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;
                    border:1px solid #e0e0e0;border-radius:8px;overflow:hidden;">
          <div style="background:#003087;padding:20px 24px;">
            <h2 style="color:#fff;margin:0;font-size:18px;">Janashakthi Insurance</h2>
          </div>
          <div style="padding:24px;">
            <p style="margin:0 0 12px;">Dear <strong>{customer_name}</strong>,</p>
            <p style="margin:0 0 20px;color:#444;">
              Use the code below to verify your identity. It expires in <strong>5 minutes</strong>.
            </p>
            <div style="background:#f5f7ff;border:2px dashed #003087;border-radius:8px;
                        padding:20px;text-align:center;margin-bottom:20px;">
              <span style="font-size:36px;font-weight:bold;letter-spacing:10px;
                           color:#003087;">{otp}</span>
            </div>
            <p style="font-size:12px;color:#888;">
              Do not share this code with anyone. Janashakthi will never ask for your OTP.
            </p>
          </div>
        </div>
        """

        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(mail_server, mail_port) as server:
            server.ehlo()
            server.starttls()
            server.login(mail_user, mail_password)
            server.sendmail(mail_user, to_email, msg.as_string())

        return True, ''

    except smtplib.SMTPAuthenticationError:
        return False, "Email authentication failed. Check MAIL_USERNAME and MAIL_PASSWORD."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def mask_email(email: str) -> str:
    """Return a masked version of the email for display, e.g. ba****@email.com"""
    try:
        local, domain = email.split('@', 1)
        visible = local[:2] if len(local) >= 2 else local[0]
        return f"{visible}{'*' * 4}@{domain}"
    except Exception:
        return "****@****.com"
