import json
import time

import requests
import streamlit as st

from core import (
    Location,
    Route,
)


# =========================================================
# API URLS
# =========================================================

GEOCODING_URL = (
    "https://geocoding-api.open-meteo.com/v1/search"
)

WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
)

OSRM_URL = (
    "https://router.project-osrm.org/"
    "route/v1/driving"
)

GROQ_CHAT_URL = (
    "https://api.groq.com/openai/v1/chat/completions"
)

GROQ_TRANSCRIPTION_URL = (
    "https://api.groq.com/openai/v1/"
    "audio/transcriptions"
)


# =========================================================
# GEOCODING
# =========================================================

def geocode_location(
    location_name: str,
):

    if not location_name.strip():

        raise ValueError(
            "Location cannot be empty."
        )

    params = {
        "name": location_name.strip(),
        "count": 1,
        "language": "en",
        "format": "json",
        "countryCode": "PK",
    }

    headers = {
        "User-Agent":
            "FreshRoute/1.0",
    }

    last_error = None

    for attempt in range(3):

        try:

            response = requests.get(
                GEOCODING_URL,
                params=params,
                headers=headers,
                timeout=10,
            )

            response.raise_for_status()

            data = response.json()

            results = data.get(
                "results",
                [],
            )

            if not results:

                raise ValueError(
                    f"Location not found: "
                    f"{location_name}"
                )

            result = results[0]

            return {
                "name": result.get(
                    "name",
                    location_name,
                ),

                "latitude": float(
                    result["latitude"]
                ),

                "longitude": float(
                    result["longitude"]
                ),

                "country": result.get(
                    "country",
                    "Pakistan",
                ),

                "admin1": result.get(
                    "admin1",
                    "",
                ),
            }

        except Exception as exc:

            last_error = exc

            if attempt < 2:
                time.sleep(1.5)

    raise RuntimeError(
        f"Geocoding failed: {last_error}"
    )


# =========================================================
# WEATHER
# =========================================================

def get_current_weather(
    latitude: float,
    longitude: float,
):

    params = {
        "latitude": latitude,
        "longitude": longitude,

        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "wind_speed_10m,"
            "precipitation"
        ),

        "timezone": "auto",
    }

    last_error = None

    for attempt in range(3):

        try:

            response = requests.get(
                WEATHER_URL,
                params=params,
                timeout=10,
            )

            response.raise_for_status()

            data = response.json()

            current = data.get(
                "current",
                {},
            )

            return {
                "temperature_c":
                    float(
                        current[
                            "temperature_2m"
                        ]
                    ),

                "humidity":
                    float(
                        current.get(
                            "relative_humidity_2m",
                            0,
                        )
                    ),

                "wind_speed_kmh":
                    float(
                        current.get(
                            "wind_speed_10m",
                            0,
                        )
                    ),

                "precipitation_mm":
                    float(
                        current.get(
                            "precipitation",
                            0,
                        )
                    ),

                "timezone":
                    data.get(
                        "timezone",
                        "",
                    ),

                "source":
                    "Open-Meteo",
            }

        except Exception as exc:

            last_error = exc

            if attempt < 2:
                time.sleep(1.5)

    raise RuntimeError(
        f"Weather API unavailable: "
        f"{last_error}"
    )


# =========================================================
# ROUTING
# =========================================================

def get_route(
    start: Location,
    end: Location,
):

    coordinates = (
        f"{start.longitude},{start.latitude};"
        f"{end.longitude},{end.latitude}"
    )

    url = (
        f"{OSRM_URL}/{coordinates}"
    )

    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }

    headers = {
        "User-Agent":
            "FreshRoute/1.0",
    }

    last_error = None

    for attempt in range(3):

        try:

            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=15,
            )

            response.raise_for_status()

            data = response.json()

            if data.get("code") != "Ok":

                raise RuntimeError(
                    data.get(
                        "message",
                        "Routing failed.",
                    )
                )

            route = data[
                "routes"
            ][0]

            geometry = (
                route
                .get("geometry", {})
                .get("coordinates", [])
            )

            return Route(
                success=True,

                distance_km=(
                    route["distance"]
                    / 1000.0
                ),

                duration_hours=(
                    route["duration"]
                    / 3600.0
                ),

                geometry=geometry,

                source="OSRM",
            )

        except Exception as exc:

            last_error = exc

            if attempt < 2:
                time.sleep(1.5)

    # -----------------------------------------------------
    # Fallback
    # -----------------------------------------------------

    from core import fallback_route

    fallback = fallback_route(
        start,
        end,
    )

    fallback.error = str(
        last_error
    )

    return fallback


# =========================================================
# GROQ
# =========================================================

def get_groq_api_key():

    try:

        key = st.secrets[
            "GROQ_API_KEY"
        ]

    except Exception:

        key = None

    if not key:

        raise RuntimeError(
            "GROQ_API_KEY is missing. "
            "Add it to Streamlit Secrets."
        )

    return key


def get_groq_model():

    try:

        return st.secrets.get(
            "GROQ_MODEL",
            "openai/gpt-oss-120b",
        )

    except Exception:

        return "openai/gpt-oss-120b"


def get_whisper_model():

    try:

        return st.secrets.get(
            "GROQ_WHISPER_MODEL",
            "whisper-large-v3-turbo",
        )

    except Exception:

        return "whisper-large-v3-turbo"


def groq_chat(
    system_prompt: str,
    user_prompt: str,
):

    api_key = get_groq_api_key()

    headers = {
        "Authorization":
            f"Bearer {api_key}",

        "Content-Type":
            "application/json",
    }

    payload = {
        "model":
            get_groq_model(),

        "messages": [
            {
                "role":
                    "system",

                "content":
                    system_prompt,
            },

            {
                "role":
                    "user",

                "content":
                    user_prompt,
            },
        ],

        "temperature": 0.2,

        "max_tokens": 1000,
    }

    response = requests.post(
        GROQ_CHAT_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    return (
        data[
            "choices"
        ][0][
            "message"
        ][
            "content"
        ]
    )


# =========================================================
# VOICE TRANSCRIPTION
# =========================================================

def transcribe_audio(
    audio_bytes: bytes,
    language=None,
):

    api_key = get_groq_api_key()

    headers = {
        "Authorization":
            f"Bearer {api_key}",
    }

    files = {
        "file": (
            "freshroute_recording.wav",
            audio_bytes,
            "audio/wav",
        )
    }

    data = {
        "model":
            get_whisper_model(),

        "response_format":
            "json",

        "temperature":
            "0",
    }

    if language in [
        "en",
        "ur",
    ]:

        data["language"] = language

    response = requests.post(
        GROQ_TRANSCRIPTION_URL,
        headers=headers,
        files=files,
        data=data,
        timeout=60,
    )

    response.raise_for_status()

    result = response.json()

    return result.get(
        "text",
        "",
    ).strip()


# =========================================================
# AI SHIPMENT REPORT
# =========================================================

def generate_ai_report(
    shipment,
    analysis,
    best_match,
    weather,
    language,
):

    match_data = None

    if best_match:

        match_data = {
            "driver_id":
                best_match.driver_id,

            "valid":
                best_match.valid,

            "score":
                round(
                    best_match.score,
                    3,
                ),

            "detour_km":
                round(
                    best_match.detour_km,
                    2,
                ),

            "delivery_distance_km":
                round(
                    best_match
                    .pickup_delivery_distance_km,
                    2,
                ),

            "delivery_time_hours":
                round(
                    best_match
                    .pickup_delivery_time_hours,
                    2,
                ),

            "rejection_reasons":
                best_match
                .rejection_reasons,
        }

    context = {
        "shipment": {
            "crop":
                shipment.crop,

            "quantity_kg":
                shipment.quantity_kg,

            "harvest_age_hours":
                shipment.harvest_age_hours,

            "condition_score":
                shipment.condition_score,

            "origin":
                shipment.origin.name,

            "destination":
                shipment.destination.name,
        },

        "weather": weather,

        "shelf_life": {
            "base_hours":
                analysis
                .base_shelf_life_hours,

            "remaining_hours":
                round(
                    analysis
                    .remaining_shelf_life_hours,
                    2,
                ),

            "urgency":
                analysis.urgency,

            "temperature_c":
                analysis.temperature_c,
        },

        "best_match":
            match_data,
    }

    system_prompt = """
You are FreshRoute AI.

FreshRoute is an agricultural logistics
decision-support application.

Its deterministic algorithm has already
calculated the transportation result.

You MUST NOT change or override that result.

Your job is to explain the result in
simple, practical language.

Rules:

1. Never invent route, weather,
   capacity or timing information.

2. Never claim a rejected truck is safe.

3. Clearly distinguish algorithmic facts
   from recommendations.

4. Explain the main spoilage/logistics risk.

5. Give practical next actions.

6. Keep the response concise.

7. If information is unavailable,
   explicitly say so.

The shelf-life model is a heuristic
prototype and must not be presented as
scientifically validated food-safety
prediction.
"""

    user_prompt = f"""
Respond in: {language}

FreshRoute shipment analysis:

{json.dumps(
    context,
    indent=2,
)}

Provide:

1. Shipment status
2. Selected truck explanation
3. Main risk
4. Recommended actions
5. Buyer-ready shipment summary
"""

    return groq_chat(
        system_prompt,
        user_prompt,
    )


# =========================================================
# AI Q&A
# =========================================================

def ask_freshroute_ai(
    question,
    shipment,
    analysis,
    matches,
):

    context = {
        "shipment": {
            "crop":
                shipment.crop,

            "quantity_kg":
                shipment.quantity_kg,

            "harvest_age_hours":
                shipment.harvest_age_hours,

            "condition_score":
                shipment.condition_score,

            "origin":
                shipment.origin.name,

            "destination":
                shipment.destination.name,
        },

        "analysis": {
            "temperature_c":
                analysis.temperature_c,

            "remaining_shelf_life_hours":
                analysis
                .remaining_shelf_life_hours,

            "urgency":
                analysis.urgency,
        },

        "matches": [
            {
                "driver_id":
                    result.driver_id,

                "valid":
                    result.valid,

                "score":
                    round(
                        result.score,
                        3,
                    ),

                "detour_km":
                    round(
                        result.detour_km,
                        2,
                    ),

                "travel_time_hours":
                    round(
                        result
                        .pickup_delivery_time_hours,
                        2,
                    ),

                "rejection_reasons":
                    result
                    .rejection_reasons,
            }

            for result
            in matches
        ],
    }

    system_prompt = """
You are the FreshRoute AI assistant.

Use only the supplied FreshRoute data.

The deterministic matching engine is
authoritative.

You may explain the decision but you
must never override it.

Never invent missing information.

If something is unavailable, say:
"The available FreshRoute data does
not contain that information."

Keep answers practical and concise.
"""

    user_prompt = f"""
FreshRoute shipment data:

{json.dumps(
    context,
    indent=2,
)}

User question:

{question}
"""

    return groq_chat(
        system_prompt,
        user_prompt,
    )
