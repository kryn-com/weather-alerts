import os
import requests
import datetime as dt
import resend
from dotenv import load_dotenv

# Load environment variables from a local .env file (if running locally)
load_dotenv()

# =========================
# Configuration
# =========================
LOCATION_NAME = "Beaufort, NC"
LAT, LON = 34.72, -76.66
TIMEZONE = "America/New_York"
THRESHOLD_F = 78
FORECAST_DAYS = 10

# Default Resend onboarding sender (use this unless you verify a custom domain)
FROM_EMAIL = "Beaufort Weather <onboarding@resend.dev>"
TO_EMAILS = ["9193800995@msg.fi.google.com"]

# Set the Resend API key from environment variables
resend.api_key = os.environ.get("RESEND_API_KEY")


# =========================
# Email Helper (Resend)
# =========================
def send_email(subject: str, content: str, to_emails=TO_EMAILS):
    if not resend.api_key:
        raise ValueError("RESEND_API_KEY environment variable is not set.")

    params: resend.Emails.SendParams = {
        "from": FROM_EMAIL,
        "to": to_emails,
        "subject": subject[:120],
        "text": content[:4000],
    }
    
    return resend.Emails.send(params)


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
