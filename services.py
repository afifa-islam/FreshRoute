import json
import time
from typing import Any, Dict, Optional, Tuple

import requests


# ============================================================
# API ENDPOINTS
# ============================================================

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_CHAT_URL = f"{GROQ_BASE_URL}/chat/completions"
GROQ_TRANSCRIPTION_URL = f"{GROQ_BASE_URL}/audio/transcriptions"


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_WHISPER_MODEL = "whisper-large-v3-turbo"

REQUEST_TIMEOUT = 20
MAX_RETRIES = 3


# ============================================================
# GENERIC REQUEST HELPER
# ============================================================

def _request_with_retry(
    method: str,
    url: str,
    **kwargs
) -> requests.Response:

    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.request(
                method,
                url,
                timeout=REQUEST_TIMEOUT,
                **kwargs
            )

            # Retry temporary server errors.
            if response.status_code >= 500:
                last_error = (
                    f"HTTP {response.status_code}: "
                    f"{response.text[:500]}"
                )

                if attempt < MAX_RETRIES - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue

            return response

        except requests.RequestException as exc:
            last_error = str(exc)

            if attempt < MAX_RETRIES - 1:
                time.sleep(1.5 * (attempt + 1))
            else:
                raise

    raise requests.RequestException(
        last_error or "Request failed."
    )


# ============================================================
# GEOCODING
# ============================================================

def geocode_location(location_name: str) -> Optional[Tuple[float, float]]:
    """
    Convert a Pakistani location name into latitude/longitude.

    Returns:
        (latitude, longitude)
        or None if the location cannot be found.
    """

    if not location_name:
        return None

    params = {
        "name": location_name.strip(),
        "count": 5,
        "language": "en",
        "format": "json",
        "countryCode": "PK",
    }

    try:
        response = _request_with_retry(
            "GET",
            GEOCODING_URL,
            params=params
        )

        response.raise_for_status()

        data = response.json()

        results = data.get("results", [])

        if not results:
            return None

        first = results[0]

        latitude = first.get("latitude")
        longitude = first.get("longitude")

        if latitude is None or longitude is None:
            return None

        return float(latitude), float(longitude)

    except Exception:
        return None


# ============================================================
# WEATHER
# ============================================================

def get_current_weather(
    latitude: float,
    longitude: float
) -> Dict[str, Any]:

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "precipitation,"
            "wind_speed_10m"
        ),
        "timezone": "auto",
    }

    try:
        response = _request_with_retry(
            "GET",
            WEATHER_URL,
            params=params
        )

        response.raise_for_status()

        data = response.json()

        current = data.get("current", {})

        return {
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation"),
            "wind_speed": current.get("wind_speed_10m"),
            "available": True,
        }

    except Exception as exc:

        return {
            "temperature": None,
            "humidity": None,
            "precipitation": None,
            "wind_speed": None,
            "available": False,
            "error": str(exc),
        }


# ============================================================
# ROUTING
# ============================================================

def get_route(
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float
) -> Dict[str, Any]:

    coordinates = (
        f"{origin_lon},{origin_lat};"
        f"{destination_lon},{destination_lat}"
    )

    url = f"{OSRM_URL}/{coordinates}"

    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }

    try:
        response = _request_with_retry(
            "GET",
            url,
            params=params
        )

        response.raise_for_status()

        data = response.json()

        routes = data.get("routes", [])

        if not routes:
            raise ValueError("No route returned by OSRM.")

        route = routes[0]

        distance_km = route["distance"] / 1000
        duration_hours = route["duration"] / 3600

        geometry = route.get("geometry", {})

        return {
            "distance_km": distance_km,
            "duration_hours": duration_hours,
            "geometry": geometry,
            "source": "OSRM",
        }

    except Exception as exc:

        # ----------------------------------------------------
        # FALLBACK TO STRAIGHT-LINE DISTANCE
        # ----------------------------------------------------

        try:
            from core import fallback_route

            fallback = fallback_route(
                origin_lat,
                origin_lon,
                destination_lat,
                destination_lon
            )

            fallback["source"] = "Haversine fallback"
            fallback["error"] = str(exc)

            return fallback

        except Exception:

            return {
                "distance_km": 0.0,
                "duration_hours": 0.0,
                "geometry": {},
                "source": "Unavailable",
                "error": str(exc),
            }


# ============================================================
# GROQ CONFIGURATION
# ============================================================

def get_groq_settings() -> Dict[str, str]:

    try:
        import streamlit as st

        api_key = st.secrets.get("GROQ_API_KEY", "")
        model = st.secrets.get(
            "GROQ_MODEL",
            DEFAULT_GROQ_MODEL
        )
        whisper_model = st.secrets.get(
            "GROQ_WHISPER_MODEL",
            DEFAULT_WHISPER_MODEL
        )

    except Exception:

        api_key = ""
        model = DEFAULT_GROQ_MODEL
        whisper_model = DEFAULT_WHISPER_MODEL

    return {
        "api_key": str(api_key).strip(),
        "model": str(model).strip(),
        "whisper_model": str(whisper_model).strip(),
    }


# ============================================================
# GROQ ERROR EXTRACTION
# ============================================================

def _groq_error_message(response: requests.Response) -> str:

    try:
        data = response.json()

        error = data.get("error")

        if isinstance(error, dict):
            message = error.get("message")
            error_type = error.get("type")
            code = error.get("code")

            parts = []

            if message:
                parts.append(str(message))

            if error_type:
                parts.append(f"type={error_type}")

            if code:
                parts.append(f"code={code}")

            if parts:
                return " | ".join(parts)

        if isinstance(error, str):
            return error

    except Exception:
        pass

    text = response.text.strip()

    if text:
        return text[:1000]

    return f"HTTP {response.status_code}"


# ============================================================
# GROQ CHAT
# ============================================================

def groq_chat(
    messages,
    temperature: float = 0.2,
    max_tokens: int = 1200
) -> str:

    settings = get_groq_settings()

    api_key = settings["api_key"]
    model = settings["model"]

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing from Streamlit Secrets."
        )

    if not model:
        raise RuntimeError(
            "GROQ_MODEL is empty."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
    }

    try:

        response = _request_with_retry(
            "POST",
            GROQ_CHAT_URL,
            headers=headers,
            json=payload,
        )

    except requests.RequestException as exc:

        raise RuntimeError(
            f"Could not connect to Groq API: {exc}"
        ) from exc

    if not response.ok:

        error_detail = _groq_error_message(response)

        raise RuntimeError(
            f"Groq API error "
            f"(HTTP {response.status_code}): "
            f"{error_detail}"
        )

    try:

        data = response.json()

    except ValueError as exc:

        raise RuntimeError(
            "Groq returned an invalid JSON response."
        ) from exc

    try:

        content = data["choices"][0]["message"]["content"]

    except (KeyError, IndexError, TypeError) as exc:

        raise RuntimeError(
            f"Unexpected Groq response: {json.dumps(data)[:1000]}"
        ) from exc

    if not content:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    return content.strip()


# ============================================================
# AUDIO TRANSCRIPTION
# ============================================================

def transcribe_audio(
    audio_bytes: bytes,
    language: str = "English"
) -> str:

    settings = get_groq_settings()

    api_key = settings["api_key"]
    whisper_model = settings["whisper_model"]

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing from Streamlit Secrets."
        )

    if not audio_bytes:
        raise RuntimeError(
            "No audio data was received."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    files = {
        "file": (
            "freshroute_audio.wav",
            audio_bytes,
            "audio/wav"
        )
    }

    data = {
        "model": whisper_model,
        "response_format": "json",
        "temperature": "0",
    }

    # Whisper language parameter is optional.
    # Only explicitly specify Urdu/English when known.
    if language.lower() == "urdu":
        data["language"] = "ur"

    elif language.lower() == "english":
        data["language"] = "en"

    try:

        response = _request_with_retry(
            "POST",
            GROQ_TRANSCRIPTION_URL,
            headers=headers,
            files=files,
            data=data,
        )

    except requests.RequestException as exc:

        raise RuntimeError(
            f"Could not connect to Groq transcription API: {exc}"
        ) from exc

    if not response.ok:

        error_detail = _groq_error_message(response)

        raise RuntimeError(
            f"Groq transcription error "
            f"(HTTP {response.status_code}): "
            f"{error_detail}"
        )

    try:

        result = response.json()

    except ValueError as exc:

        raise RuntimeError(
            "Groq transcription returned invalid JSON."
        ) from exc

    text = result.get("text", "").strip()

    if not text:
        raise RuntimeError(
            "No speech was detected in the recording."
        )

    return text


# ============================================================
# AI SHIPMENT REPORT
# ============================================================

def generate_ai_report(
    shipment,
    analysis,
    matches,
    weather
) -> str:

    best_match = None

    if matches:
        best_match = matches[0]

    shipment_data = {
        "farmer_id": shipment.farmer_id,
        "crop": shipment.crop,
        "quantity_kg": shipment.quantity_kg,
        "harvest_age_hours": shipment.harvest_age_hours,
        "condition": shipment.condition,
        "pickup": shipment.pickup.name,
        "destination": shipment.destination.name,
    }

    analysis_data = {
        "shelf_life_hours": analysis.estimated_remaining_shelf_life_hours,
        "urgency": analysis.urgency,
        "heat_factor": analysis.heat_factor,
        "condition_factor": analysis.condition_factor,
        "risk_level": analysis.risk_level,
        "reason": analysis.reason,
    }

    weather_data = weather or {}

    best_match_data = None

    if best_match:

        best_match_data = {
            "driver_id": best_match.driver.driver_id,
            "vehicle_type": best_match.driver.vehicle_type,
            "capacity_kg": best_match.driver.capacity_kg,
            "refrigerated": best_match.driver.refrigerated,
            "route_distance_km": best_match.route.distance_km,
            "route_duration_hours": best_match.route.duration_hours,
            "detour_km": best_match.detour_km,
            "score": best_match.score,
            "valid": best_match.valid,
            "reasons": best_match.reasons,
        }

    prompt = f"""
You are the AI decision-support assistant for FreshRoute,
an agricultural backhaul matching application.

FreshRoute connects farmers carrying harvested produce with
trucks that have available return/backhaul capacity.

IMPORTANT:
The deterministic FreshRoute matching algorithm is authoritative.
You must NOT override its matching decision.
You must NOT invent weather, routes, truck capacity, prices,
food-safety facts, or other information.

Your job is to explain the results clearly and provide practical
logistics guidance.

SHIPMENT:
{json.dumps(shipment_data, indent=2, default=str)}

DETERMINISTIC SHIPMENT ANALYSIS:
{json.dumps(analysis_data, indent=2, default=str)}

CURRENT WEATHER:
{json.dumps(weather_data, indent=2, default=str)}

BEST MATCH:
{json.dumps(best_match_data, indent=2, default=str)}

Write the report using these sections:

### Shipment Assessment
Explain the urgency and remaining shelf-life estimate.

### Recommended Transport
Explain whether the recommended truck is suitable.

### Logistics Risks
List the most important practical risks.

### Recommended Actions
Give 3 to 5 concrete actions the farmer/driver should take.

### Buyer Summary
Write a short summary that could be shown to the buyer.

Keep the language simple and practical.
Do not claim that the shelf-life estimate is a laboratory food-safety
assessment.
"""

    messages = [
        {
            "role": "system",
            "content": (
                "You are FreshRoute's logistics decision-support "
                "assistant. The deterministic matching engine is "
                "authoritative. Never invent missing data."
            ),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    return groq_chat(
        messages,
        temperature=0.2,
        max_tokens=1400
    )


# ============================================================
# FRESHROUTE AI ASSISTANT
# ============================================================

def ask_freshroute_ai(
    question: str,
    shipment,
    analysis,
    matches,
    weather
) -> str:

    if not question.strip():
        raise RuntimeError(
            "Please enter a question."
        )

    shipment_data = {
        "farmer_id": shipment.farmer_id,
        "crop": shipment.crop,
        "quantity_kg": shipment.quantity_kg,
        "harvest_age_hours": shipment.harvest_age_hours,
        "condition": shipment.condition,
        "pickup": shipment.pickup.name,
        "destination": shipment.destination.name,
    }

    analysis_data = {
        "remaining_shelf_life_hours":
            analysis.estimated_remaining_shelf_life_hours,
        "urgency": analysis.urgency,
        "risk_level": analysis.risk_level,
        "reason": analysis.reason,
    }

    matches_data = []

    for match in matches[:5]:

        matches_data.append({
            "driver_id": match.driver.driver_id,
            "vehicle_type": match.driver.vehicle_type,
            "capacity_kg": match.driver.capacity_kg,
            "refrigerated": match.driver.refrigerated,
            "distance_km": match.route.distance_km,
            "duration_hours": match.route.duration_hours,
            "detour_km": match.detour_km,
            "score": match.score,
            "valid": match.valid,
            "reasons": match.reasons,
        })

    context = {
        "shipment": shipment_data,
        "analysis": analysis_data,
        "weather": weather or {},
        "matches": matches_data,
    }

    prompt = f"""
You are the FreshRoute AI Assistant.

Answer the user's question using ONLY the FreshRoute data
provided below.

FreshRoute's deterministic matching engine is authoritative.
Do not invent information.

CURRENT FRESHROUTE DATA:
{json.dumps(context, indent=2, default=str)}

USER QUESTION:
{question}

Rules:
- Give a direct answer.
- Explain technical logistics concepts simply.
- If the requested information is not available, say so.
- Do not invent prices, availability, weather, routes, or food-safety claims.
- Do not override the deterministic matching result.
"""

    messages = [
        {
            "role": "system",
            "content": (
                "You are a factual logistics assistant for "
                "FreshRoute."
            ),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    return groq_chat(
        messages,
        temperature=0.2,
        max_tokens=1000
    )
