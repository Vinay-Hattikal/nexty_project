# jobs/email_utils.py
import io
from datetime import datetime, timedelta
from django.core.mail import EmailMessage
from django.conf import settings
from email.utils import formataddr
import uuid

DEFAULT_FROM = getattr(settings, "DEFAULT_FROM_EMAIL", "Nexty <no-reply@nexty.local>")

def _format_from_name():
    # helpful helper in case you want to override
    return DEFAULT_FROM

def _build_ics(interview_dt, duration_minutes=30, summary="Interview", description="", organizer_name=None, organizer_email=None, location=None, uid=None):
    """
    Build a simple ICS calendar invite string.
    interview_dt: a naive or aware datetime - for dev we'll emit naive UTC-like time.
    """
    if uid is None:
        uid = str(uuid.uuid4())

    dtstart = interview_dt.strftime("%Y%m%dT%H%M%S")
    dtend = (interview_dt + timedelta(minutes=duration_minutes)).strftime("%Y%m%dT%H%M%S")

    # fallback organizer
    organizer_email = organizer_email or getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@nexty.local")
    organizer_name = organizer_name or "Nexty"
    location = location or "Virtual"

    ics = [
        "BEGIN:VCALENDAR",
        "PRODID:-//Nexty//EN",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{dtstart}",
        f"DTEND:{dtend}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        f"LOCATION:{location}",
        f"ORGANIZER;CN={organizer_name}:MAILTO:{organizer_email}",
        "END:VEVENT",
        "END:VCALENDAR"
    ]
    return "\r\n".join(ics)

def send_shortlist_email(student_email, student_name, hr_name, job_title, interview_dt, meeting_link=None, message="", duration_minutes=30):
    """
    Sends shortlist email with optional ICS attachment.
    - student_email: recipient email
    - interview_dt: datetime object (naive; interpret as server timezone or UTC)
    """
    subject = f"[{job_title}] Interview invitation from {hr_name}"
    body_lines = [
        f"Hi {student_name},",
        "",
        f"Good news — you have been shortlisted for the role: {job_title}.",
        f"{'' if not message else 'Message from recruiter: ' + message}",
        "",
        f"Interview details:",
        f"Date/time: {interview_dt.strftime('%Y-%m-%d %H:%M')}",
    ]
    if meeting_link:
        body_lines.append(f"Join link: {meeting_link}")
    body_lines.append("")
    body_lines.append("If you cannot attend, please reply to this email to reschedule.")
    body = "\n".join([l for l in body_lines if l is not None and l != ""])

    email = EmailMessage(subject=subject, body=body, from_email=_format_from_name(), to=[student_email])
    # attach an ics calendar invite
    try:
        ics_text = _build_ics(interview_dt, duration_minutes=duration_minutes,
                              summary=f"{job_title} interview with {hr_name}",
                              description=message or f"Interview for {job_title}",
                              organizer_name=hr_name,
                              organizer_email=getattr(settings, 'EMAIL_HOST_USER', None) or DEFAULT_FROM,
                              location=meeting_link or "Virtual meeting")
        email.attach(filename="invite.ics", content=ics_text, mimetype="text/calendar")
    except Exception:
        # if ICS creation fails, continue without attachment
        pass

    email.send(fail_silently=False)
    return True

def send_reject_email(student_email, student_name, hr_name, job_title, message=""):
    """
    Sends rejection email (plain text).
    """
    subject = f"[{job_title}] Application update from {hr_name}"
    lines = [
        f"Hi {student_name},",
        "",
        f"Thank you for applying for {job_title}. We appreciate your interest.",
        "",
    ]
    if message:
        lines.append("Message from recruiter:")
        lines.append(message)
        lines.append("")
    lines.append("We wish you all the best in your job search.")
    body = "\n".join(lines)

    email = EmailMessage(subject=subject, body=body, from_email=_format_from_name(), to=[student_email])
    email.send(fail_silently=False)
    return True
