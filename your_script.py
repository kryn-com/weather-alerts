import os
import smtplib
import requests
import datetime as dt
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

# =========================
# Configuration
# =========================
LOCATION_NAME = "Beaufort, NC"
LAT, LON = 34.72, -76.66
TIMEZONE = "America/New_York"
FORECAST_DAYS = 10

TO_EMAILS = ["9193800995@msg.fi.google.com"]

GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")


# =========================
# Scoring Functions
# =========================
def score_temperature(temp_f: float) -> tuple[str, int]:
    if temp_f < 76:
        return "➕", 3
    elif 76 <= temp_f <= 82:
        return "☑️", 2
    elif 83 <= temp_f <= 88:
        return "⚠️", 1
    else:  # 89+
        return "❌", 0


def score_dewpoint(dew_f: float) -> tuple[str, int]:
    if dew_f < 64:
        return "➕", 3
    elif 64 <= dew_f <= 68:
        return "☑️", 2
    elif 69 <= dew_f <= 73:
        return "⚠️", 1
    else:  # 74+
        return "❌", 0


def score_wind(wind_mph: float) -> tuple[str, int]:
    if 6 <= wind_mph <= 15:  # Ideal coastal breeze
        return "➕", 3
    elif (4 <= wind_mph <= 5) or (16 <= wind_mph <= 20):
        return "☑️", 1
    else:  # Stagnant (< 4) or Gale (> 20)
        return "❌", 0


# =========================
# Email Helper
# =========================
def send_email(subject: str, content: str, to_emails=TO_EMAILS):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise ValueError("GMAIL_USER or GMAIL_APP_PASSWORD environment variable is not set.")

    msg = MIMEText(content[:4000], "plain", "utf-8")
    msg["Subject"] = subject[:120]
    msg["From"] = GMAIL_USER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        for to in to_emails:
            msg["To"] = to
            server.sendmail(GMAIL_USER, to, msg.as_string())


# =========================
# Weather Fetch + Logic
# =========================
def fetch_weather_data(lat, lon, days=FORECAST_DAYS, tz=TIMEZONE):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max",
        "hourly": ["dew_point_2m", "wind_speed_10m"],
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": tz,
        "forecast_days": days,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    dates = data["daily"]["time"]
    highs = data["daily"]["temperature_2m_max"]
    hourly_dew = data["hourly"]["dew_point_2m"]
    hourly_wind = data["hourly"]["wind_speed_10m"]

    daily_scores = []

    for i in range(len(dates)):
        if highs[i] is None:
            continue

        start_idx = i * 24
        end_idx = start_idx + 24
        
        day_dews = [d for d in hourly_dew[start_idx:end_idx] if d is not None]
        day_winds = [w for w in hourly_wind[start_idx:end_idx] if w is not None]

        if not day_dews or not day_winds:
            continue

        peak_dew = max(day_dews)
        peak_wind = max(day_winds)
        high_temp = float(highs[i])

        temp_icon, temp_pts = score_temperature(high_temp)
        dew_icon, dew_pts = score_dewpoint(peak_dew)
        wind_icon, wind_pts = score_wind(peak_wind)

        total_pts = temp_pts + dew_pts + wind_pts

        daily_scores.append({
            "date": dt.date.fromisoformat(dates[i]),
            "high": high_temp,
            "dew": peak_dew,
            "wind": peak_wind,
            # Order aligned: Temp, Dew, Wind
            "icons": f"{temp_icon}{dew_icon}{wind_icon}",
            "score": total_pts,
        })

    daily_scores.sort(key=lambda x: x["date"])
    return daily_scores


def format_summary(scores):
    lines = []
    for s in scores:
        date_str = s["date"].strftime("%a %d")
        # Format: Sat 15 [8] ➕➕☑️ | T76F | D61F | W11mph
        line = f"{date_str} [{s['score']}] {s['icons']} | T{s['high']:.0f}F | D{s['dew']:.0f}F | W{s['wind']:.0f}mph"
        lines.append(line)
    return "\n".join(lines)


# =========================
# Main Run
# =========================
if __name__ == "__main__":
    try:
        scores = fetch_weather_data(LAT, LON, FORECAST_DAYS, TIMEZONE)

        if not scores:
            subject = "Beaufort Weather Score"
            body = "Unable to calculate weather scores for Beaufort."
        else:
            best_day = max(scores, key=lambda x: x["score"])
            subject = f"Beaufort 10-Day Outlook (Best: {best_day['date'].strftime('%a %d')} [{best_day['score']}])"
            body = format_summary(scores)

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
