import os
import time
from typing import Dict
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To
from agents import Agent, function_tool


@function_tool
def send_email(subject: str, html_body: str, to_emails: str) -> Dict[str, str]:
    """Send an HTML email via SendGrid.

    Args:
        subject: Email subject line.
        html_body: Full HTML content of the email.
        to_emails: Comma-separated recipient addresses. If empty, falls back to the default list.
    """
    # Read env vars at call time so load_dotenv() is guaranteed to have run
    api_key = os.environ.get("SENDGRID_API_KEY", "")
    from_addr = os.environ.get("SENDGRID_FROM_EMAIL", "")
    default_recipients = [
        e.strip()
        for e in (os.environ.get("SENDGRID_RECIPIENTS_EMAIL") or "").split(",")
        if e.strip()
    ]

    addresses = [a.strip() for a in to_emails.split(",") if a.strip()]
    if not addresses:
        addresses = default_recipients

    sg = sendgrid.SendGridAPIClient(api_key=api_key)
    mail = Mail(
        from_email=Email(from_addr),
        to_emails=[To(addr) for addr in addresses],
        subject=subject,
        html_content=html_body,
    )

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            response = sg.send(mail)
            print(f"[Email] Sent to {addresses} — status {response.status_code}")
            return {"status": "success", "recipients": ", ".join(addresses)}
        except Exception as e:
            last_err = e
            print(f"[Email] Attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s, 2s back-off

    return {"status": "error", "error": str(last_err)}


INSTRUCTIONS = """You are able to send a nicely formatted HTML email based on a detailed report.

You will be provided with:
1. The markdown report to convert and send.
2. Optionally a recipient list on the very first line, formatted as: "Send to: email1@x.com, email2@x.com"

Convert the report into clean, well-presented HTML with a clear layout and appropriate subject line.
Then call send_email with:
- subject: a descriptive subject derived from the report content
- html_body: the rendered HTML
- to_emails: the recipient list from the input (or empty string to use the default recipients)"""

email_agent = Agent(
    name="Email agent",
    instructions=INSTRUCTIONS,
    tools=[send_email],
    model="gpt-4o-mini",
)
