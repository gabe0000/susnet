#!/usr/bin/env python3
from collections import defaultdict

from aprs_helpers import (
    get_last_location,
    get_weather_for_stations,
    speak,
    haversine_km,
    c_to_f,
    ms_to_mph,
    wind_direction_to_cardinal,
    aprs_get,
)

MY_CALL = "W4VDX-9"

# TODO: replace these with real nearby WX stations around your normal area.
# You can find them on aprs.fi by filtering for wx icons near your QTH.
WX_CANDIDATES = [
    "WX1CALL",
    "WX2CALL",
    "WX3CALL",
    "WX4CALL",
    "WX5CALL",
]


def get_locations_for_stations(names):
    """Return dict name -> loc entry for a list of stations."""
    if not names:
        return {}
    name_str = ",".join(names)
    data = aprs_get({
        "what": "loc",
        "name": name_str,
    })
    locs = {}
    for e in data.get("entries", []):
        name = e.get("name")
        if not name:
            continue
        locs[name] = e
    return locs


def main():
    my_loc = get_last_location(MY_CALL)
    if not my_loc:
        speak("I could not find a recent APRS position for W 4 V D X dash 9.")
        return

    try:
        my_lat = float(my_loc["lat"])
        my_lng = float(my_loc["lng"])
    except Exception:
        speak("Your APRS position does not have valid coordinates.")
        return

    if not WX_CANDIDATES:
        speak("No weather stations configured for the APRS weather report.")
        return

    # Get locations of candidate WX stations
    wx_locs = get_locations_for_stations(WX_CANDIDATES)
    if not wx_locs:
        speak("I could not find locations for the configured weather stations.")
        return

    # Compute distances
    distances = []
    for name, loc in wx_locs.items():
        try:
            lat = float(loc["lat"])
            lng = float(loc["lng"])
        except Exception:
            continue
        d_km = haversine_km(my_lat, my_lng, lat, lng)
        distances.append((d_km, name))

    if not distances:
        speak("I could not compute distances to any weather stations.")
        return

    distances.sort(key=lambda x: x[0])
    nearest = [name for _, name in distances[:3]]

    wx_entries = get_weather_for_stations(nearest)
    if not wx_entries:
        speak("No recent weather data from the nearby APRS stations.")
        return

    # Aggregate values
    sums = defaultdict(float)
    counts = defaultdict(int)

    # temp (C), humidity (%), wind_speed (m/s), wind_direction (deg)
    for e in wx_entries:
        if "temp" in e:
            try:
                t_c = float(e["temp"])
                sums["temp_c"] += t_c
                counts["temp_c"] += 1
            except Exception:
                pass

        if "humidity" in e:
            try:
                h = float(e["humidity"])
                sums["humidity"] += h
                counts["humidity"] += 1
            except Exception:
                pass

        if "wind_speed" in e:
            try:
                w = float(e["wind_speed"])
                sums["wind_speed_ms"] += w
                counts["wind_speed_ms"] += 1
            except Exception:
                pass

        if "wind_direction" in e:
            try:
                d = float(e["wind_direction"])
                sums["wind_dir_deg"] += d
                counts["wind_dir_deg"] += 1
            except Exception:
                pass

    parts = []

    # Temperature
    if counts["temp_c"]:
        avg_c = sums["temp_c"] / counts["temp_c"]
        avg_f = c_to_f(avg_c)
        parts.append(f"Temperature is around {avg_f:.0f} degrees Fahrenheit.")
    else:
        parts.append("No recent temperature readings.")

    # Humidity
    if counts["humidity"]:
        avg_h = sums["humidity"] / counts["humidity"]
        parts.append(f"Humidity is about {avg_h:.0f} percent.")
    else:
        parts.append("Humidity is not available.")

    # Wind
    wind_phrase = None
    if counts["wind_speed_ms"]:
        avg_ms = sums["wind_speed_ms"] / counts["wind_speed_ms"]
        avg_mph = ms_to_mph(avg_ms)

        if counts["wind_dir_deg"]:
            avg_deg = sums["wind_dir_deg"] / counts["wind_dir_deg"]
            card = wind_direction_to_cardinal(avg_deg)
        else:
            card = None

        if avg_mph < 2:
            wind_phrase = "Winds are basically calm."
        else:
            if card:
                wind_phrase = f"Winds are around {avg_mph:.0f} miles per hour from the {card}."
            else:
                wind_phrase = f"Winds are around {avg_mph:.0f} miles per hour."

    if wind_phrase:
        parts.append(wind_phrase)

    text = "Weather around your last APRS position. " + " ".join(parts)
    speak(text)


if __name__ == "__main__":
    main()
