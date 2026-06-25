import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from scrapers.base import Posting


def send_digest(postings: list[Posting], address: str, app_password: str) -> None:
    if not postings:
        return

    subject = f"[Internship Alert] {len(postings)} new posting{'s' if len(postings) > 1 else ''}"
    html = _build_html(postings)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = address
    msg["To"] = address
    msg.attach(MIMEText(_build_plain(postings), "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(address, app_password)
        server.sendmail(address, address, msg.as_string())


def _build_plain(postings: list[Posting]) -> str:
    lines = ["New tech internship postings:\n"]
    for p in postings:
        lines.append(f"{p.company} — {p.role}")
        lines.append(f"  Location: {p.location}")
        lines.append(f"  Apply: {p.link}")
        lines.append(f"  Posted: {p.date_added}\n")
    return "\n".join(lines)


def _build_html(postings: list[Posting]) -> str:
    rows = ""
    for p in postings:
        rows += (
            f"<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'><b>{p.company}</b></td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{p.role}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{p.location}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{p.date_added}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>"
            f"<a href='{p.link}' style='background:#1a73e8;color:#fff;padding:4px 10px;"
            f"border-radius:4px;text-decoration:none;font-size:13px'>Apply</a></td>"
            f"</tr>"
        )
    return f"""
<html><body style='font-family:Arial,sans-serif;color:#222'>
<h2 style='color:#1a73e8'>New Internship Postings</h2>
<p>{len(postings)} new posting{'s' if len(postings) > 1 else ''} found. Apply within 24 hours!</p>
<table style='border-collapse:collapse;width:100%'>
  <thead>
    <tr style='background:#f5f5f5'>
      <th style='padding:8px;text-align:left'>Company</th>
      <th style='padding:8px;text-align:left'>Role</th>
      <th style='padding:8px;text-align:left'>Location</th>
      <th style='padding:8px;text-align:left'>Posted</th>
      <th style='padding:8px;text-align:left'>Link</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</body></html>
"""
