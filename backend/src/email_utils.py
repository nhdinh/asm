import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from models import EmailConfig
import logging

logger = logging.getLogger(__name__)


def send_email_smtp(config, to_email, subject, body_html, body_text=None):
    """
    Send email using SMTP

    Args:
        config: EmailConfig object
        to_email: Recipient email address
        subject: Email subject
        body_html: HTML content of the email
        body_text: Plain text content (optional, fallback)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    # Create message
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{config.from_name} <{config.from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    # Attach plain text and HTML parts
    if body_text:
        part1 = MIMEText(body_text, "plain")
        msg.attach(part1)

    part2 = MIMEText(body_html, "html")
    msg.attach(part2)

    # Connect to SMTP server
    if config.use_ssl:
        server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port)
    else:
        server = smtplib.SMTP(config.smtp_host, config.smtp_port)
        if config.use_tls:
            server.starttls()

    # Login and send
    try:
        if config.smtp_username and config.smtp_password:
            server.login(config.smtp_username, config.smtp_password)
        server.send_message(msg)
        server.quit()

        logger.info(f"Email sent successfully via SMTP to {to_email}")
        return True
    except Exception as e:
        raise e


def send_email_sendgrid(config, to_email, subject, body_html, body_text=None):
    """
    Send email using SendGrid API

    Args:
        config: EmailConfig object
        to_email: Recipient email address
        subject: Email subject
        body_html: HTML content of the email
        body_text: Plain text content (optional, fallback)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Content

    # Create message
    message = Mail(
        from_email=(config.from_email, config.from_name),
        to_emails=to_email,
        subject=subject,
    )

    # Add content (HTML is primary, text is fallback)
    if body_text:
        message.add_content(Content("text/plain", body_text))
    message.add_content(Content("text/html", body_html))

    # Send via SendGrid API
    sg = SendGridAPIClient(config.sendgrid_api_key)
    response = sg.send(message)

    logger.info(
        f"Email sent successfully via SendGrid to {to_email} (status: {response.status_code})"
    )
    return True


def send_email(to_email, subject, body_html, body_text=None):
    """
    Send an email using the configured email provider (SMTP or SendGrid)

    Args:
        to_email: Recipient email address
        subject: Email subject
        body_html: HTML content of the email
        body_text: Plain text content (optional, fallback)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Get email configuration
        config = EmailConfig.query.first()

        if not config or not config.enabled:
            logger.warning("Email configuration not found or not enabled")
            return False

        # Route to appropriate email provider
        if config.provider == "sendgrid":
            send_email_sendgrid(config, to_email, subject, body_html, body_text)
        else:  # Default to SMTP
            send_email_smtp(config, to_email, subject, body_html, body_text)

        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False


def send_welcome_email(user_email, username, password, fullname=None):
    """
    Send welcome email to newly created user with login credentials

    Args:
        user_email: User's email address
        username: User's username
        password: User's temporary password
        fullname: User's full name (optional)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    config = EmailConfig.query.first()

    if not config or not config.enabled or not config.send_welcome_email:
        logger.info("Welcome email sending is disabled")
        return False

    display_name = fullname if fullname else username

    subject = "Welcome to Asset Management System"

    body_html = f"""
    <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background-color: #4CAF50;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 5px 5px 0 0;
                }}
                .content {{
                    background-color: #f9f9f9;
                    padding: 20px;
                    border: 1px solid #ddd;
                }}
                .credentials {{
                    background-color: #fff;
                    padding: 15px;
                    margin: 15px 0;
                    border-left: 4px solid #4CAF50;
                }}
                .footer {{
                    text-align: center;
                    padding: 10px;
                    font-size: 12px;
                    color: #777;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: #4CAF50;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 10px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Asset Management System</h1>
                </div>
                <div class="content">
                    <p>Hello {display_name},</p>

                    <p>Your account has been created in the Asset Management System. Below are your login credentials:</p>

                    <div class="credentials">
                        <p><strong>Username:</strong> {username}</p>
                        <p><strong>Temporary Password:</strong> {password}</p>
                    </div>

                    <p><strong>Important:</strong> For security reasons, you will be required to change your password upon first login.</p>

                    <p>You can access the system at: <a href="http://localhost:8080">http://localhost:8080</a></p>

                    <p>If you have any questions or need assistance, please contact your system administrator.</p>

                    <p>Best regards,<br>
                    Asset Management System Team</p>
                </div>
                <div class="footer">
                    <p>This is an automated email. Please do not reply to this message.</p>
                </div>
            </div>
        </body>
    </html>
    """

    body_text = f"""
    Welcome to Asset Management System

    Hello {display_name},

    Your account has been created in the Asset Management System. Below are your login credentials:

    Username: {username}
    Temporary Password: {password}

    IMPORTANT: For security reasons, you will be required to change your password upon first login.

    You can access the system at: http://localhost:8080

    If you have any questions or need assistance, please contact your system administrator.

    Best regards,
    Asset Management System Team

    ---
    This is an automated email. Please do not reply to this message.
    """

    return send_email(user_email, subject, body_html, body_text)


def send_test_email(config, to_email):
    """
    Send a test email to verify email configuration (SMTP or SendGrid)

    Args:
        config: EmailConfig object
        to_email: Test recipient email address

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    provider_name = "SendGrid" if config.provider == "sendgrid" else "SMTP"
    subject = f"Test Email - Asset Management System ({provider_name})"

    body_html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #4CAF50;">Email Configuration Test</h2>
            <p>This is a test email from the Asset Management System.</p>
            <p>If you received this email, your <strong>{provider_name}</strong> configuration is working correctly.</p>
            <hr>
            <p style="font-size: 12px; color: #777;">Asset Management System</p>
        </body>
    </html>
    """

    body_text = f"""
    Email Configuration Test

    This is a test email from the Asset Management System.
    If you received this email, your {provider_name} configuration is working correctly.

    ---
    Asset Management System
    """

    try:
        # Route to appropriate email provider
        if config.provider == "sendgrid":
            send_email_sendgrid(config, to_email, subject, body_html, body_text)
        else:  # Default to SMTP
            send_email_smtp(config, to_email, subject, body_html, body_text)

        logger.info(f"Test email sent successfully to {to_email} via {provider_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to send test email via {provider_name}: {str(e)}")
        raise e
