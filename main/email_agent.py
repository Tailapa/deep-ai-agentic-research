import os
from typing import Dict
import sendgrid
from sendgrid.helpers.mail import Mail, Email, Content, To
from agents import Agent, function_tool

@function_tool
def send_email(subject: str, html_body: str) -> Dict[str, str]:
    """Send an email with the given subject and HTML body"""
    sg = sendgrid.SendGridAPIClient(api_key=os.environ.get("SENDGRID_API_KEY"))
    from_email = Email("sstudios147@gmail.com")
    recipient_list = [
        To("shashankvshourya@gmail.com"),
        To("sstudios147@gmail.com")
    ]
    
    mail = Mail(
        from_email=from_email,
        to_emails=recipient_list,
        subject=subject,
        html_content=html_body
    )
    
    response = sg.send(mail)
    print("Email response:", response.status_code)
    return {"status": "success"}



INSTRUCTIONS = """You are able to send a nicely formatted HTML email based on a detailed report.
You will be provided with a detailed report. You should use your tool to send one email, providing the 
report converted into clean, well presented HTML with an appropriate subject line."""

email_agent = Agent(
    name="Email agent",
    instructions=INSTRUCTIONS,
    tools=[send_email],
    model="gpt-4o-mini",
)