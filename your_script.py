!pip install sendgrid requests -q

import requests, datetime as dt
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# =========================
# Configuration
# =========================
LOCATION_NAME   = "Beaufort, NC"
LAT, LON        = 34.72, -76.66
TIMEZONE        = "America/New_York"
THRESHOLD_F     = 78                 # testing threshold per request
FORECAST_DAYS   = 10                 # look-ahead window

FROM_EMAIL      = "kryn@kryn.com"  # must be a verified SendGrid sender
TO_EMAILS       = ["9193800995@msg.fi.google.com"]

# Replace with your key or set via environment var and read it instead.
SENDGRID_API_KEY = "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"

# =========================
# Email helper
# =========================
def send_email(subject: str, content: str, to_emails=TO_EMAILS):
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    for to in to_emails:
        msg = Mail(
            from_email=FROM_EMAIL,
            to_emails=to,
            subject=subject[:120],
            plain_text_content=content[:4000],
        )
        sg.send(msg)

# =========================
# Weather fetch + logic
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
        day = dt.date.fromisoformat(d)
        if float(h) <= threshold_f:
            matches.append((day, float(h)))
    matches.sort(key=lambda x: x[0])
    return matches

def format_match_lines(matches):
    # Format: "Sat 09 Aug 2025 82F"
    return [f"{d.strftime('%a %d %b %Y')} {t:.0f}F" for d, t in matches]

# =========================
# Main run
# =========================
try:
    dates, highs = fetch_daily_highs_f(LAT, LON, FORECAST_DAYS, TIMEZONE)
    matches = pick_matching_dates(dates, highs, THRESHOLD_F)

    if not matches:
        subject = "Beaufort weather"
        body    = "No cool days in sight in Beaufort"
        send_email(subject, body)
        print(body)
    else:
        lines = format_match_lines(matches)
        subject = "Beaufort upcoming cool days"
        body    = "\n".join(lines)
        send_email(subject, body)
        print("Sent:\n" + body)

except Exception as e:
    # Send a simple failure email as requested
    try:
        send_email("Beaufort weather check failed", "Beaufort weather check failed")
    except Exception:
        pass
    print(f"Failed with error: {type(e).__name__}: {e}")
    raise
