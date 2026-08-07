import os
import smtplib
import requests
import datetime as dt
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables from a local .env file (for local testing)
load_dotenv()

# =========================
# Configuration
# =========================
LOCATION_NAME = "Beaufort, NC"
LAT, LON = 34.72, -76.66
TIMEZONE = "America/New_York"
THRESHOLD_F = 78
FORECAST_DAYS = 10

TO_EMAILS = ["9193800995@msg.fi.google.com"]

# Retrieve Gmail credentials from environment variables
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")


# =========================
# Email Helper (Gmail SMTP)
# =========================
def send_email(subject: str, content: str, to_emails=TO_EMAILS):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise ValueError("GMAIL_USER or GMAIL_APP_PASSWORD environment variable is not set.")

    # Truncate content to safe lengths
    msg = MIMEText(content[:4000], "plain", "utf-8")
    msg["Subject"] = subject[:120]
    msg["From"] = GMAIL_USER

    # Connect to Google's SSL SMTP server on port 465
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        for to in to_emails:
            msg["To"] = to
            server.sendmail(GMAIL_USER, to, msg.as_string())


# =========================
# Weather Fetch + Logic
# =========================
def fetch_daily_highs_f(lat, lon, days=FORECAST_DAYS, tz=TIMEZONE):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max",
        "temperature_unit": "fahrenheit",
        "timezone": tz,
        "forecast_days": days,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    dates = data["daily"]["time"]
    highs = data["daily"]["temperature_2m_max"]
    return dates, highs


def pick_matching_dates(dates, highs, threshold_f=THRESHOLD_F):
    matches = []
    for d, h in zip(dates, highs):
        if h is None:
            continue
        day = dt.date.fromisoformat(d)
        if float(h) <= threshold_f:
            matches.append((day, float(h)))
    matches.sort(key=lambda x: x[0])
    return matches


def format_match_lines(matches):
    # Format: "Sat 09 Aug 2025 78F"
    return [f"{d.strftime('%a %d %b %Y')} {t:.0f}F" for d, t in matches]


# =========================
# Main Run
# =========================
if __name__ == "__main__":
    try:
        dates, highs = fetch_daily_highs_f(LAT, LON, FORECAST_DAYS, TIMEZONE)
        matches = pick_matching_dates(dates, highs, THRESHOLD_F)

        if not matches:
            subject = "Beaufort weather"
            body = "No cool days in sight in Beaufort"
            send_email(subject, body)
            print(body)
        else:
            lines = format_match_lines(matches)
            subject = "Beaufort upcoming cool days"
            body = "\n".join(lines)
            send_email(subject, body)
            print("Sent:\n" + body)

    except Exception as e:
        error_msg = f"Failed with error: {type(e).__name__}: {e}"
        print(error_msg)
        try:
            send_email("Beaufort weather check failed", error_msg)
        except Exception as send_err:
            print(f"Could not send failure notification email: {send_err}")
        raise
