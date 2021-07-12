from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from notifications_python_client.notifications import NotificationsAPIClient


def send_sms(to, text):
    notifications_client = NotificationsAPIClient(settings.NOTIFY_API_KEY)
    notifications_client.send_sms_notification(
        phone_number=to,
        template_id=settings.NOTIFY_TEMPLATE_ID,
        personalisation={"text": text},
    )


def send_email(to, subject, template, data):
    body_text = render_to_string(f"{template}.txt", data)
    body_html = render_to_string(f"{template}.html", data)
    send_mail(subject, body_text, None, [to], html_message=body_html)
