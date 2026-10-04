"""FreshRoute: connecting farmers with trucks that are already heading their way."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st

from core import (
    CROP_PROFILES,
    MAX_DETOUR_KM,
    MIN_REMAINING_SHELF_LIFE_HOURS,
    VEHICLE_TYPES,
    Driver,
    Location,
    Shipment,
    analyze_shipment,
    rank_matches,
)
from services import (
    ask_freshroute_ai,
    extract_shipment_from_text,
    extract_vehicle_from_text,
    generate_ai_report,
    geocode_location,
    get_current_weather,
    get_route,
    groq_configured,
    transcribe_audio,
)


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="FreshRoute",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
.block-container {padding-top: 1.4rem; max-width: 1180px;}
#MainMenu, footer {visibility: hidden;}

.fr-hero {
    background: linear-gradient(135deg, #1B5E20 0%, #2E7D32 55%, #66BB6A 100%);
    padding: 2rem 2.2rem;
    border-radius: 16px;
    margin-bottom: 0.9rem;
}
.fr-hero h1 {color: #fff !important; margin: 0 0 0.3rem 0; padding: 0; font-size: 2.2rem;}
.fr-hero p  {color: #fff; margin: 0; font-size: 1.05rem; opacity: 0.95;}

.fr-card {
    border: 1px solid rgba(128,128,128,0.28);
    border-radius: 14px;
    padding: 1.1rem 1.2rem;
    height: 100%;
}
.fr-card .icon {font-size: 1.8rem;}
.fr-card h4 {margin: 0.3rem 0 0.4rem 0;}
.fr-card p  {margin: 0; opacity: 0.85; font-size: 0.95rem;}

[data-testid="stMetric"] {
    border: 1px solid rgba(128,128,128,0.25);
    border-radius: 12px;
    padding: 0.7rem 0.9rem;
}
button[data-baseweb="tab"] {font-size: 1rem; font-weight: 600;}
</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# CONSTANTS
# =========================================================

CROPS = list(CROP_PROFILES.keys())

LANGUAGE_CODES = {"English": "en", "Urdu": "ur", "Roman Urdu": None}

VEHICLE_LABELS = {
    "refrigerated": "Refrigerated truck",
    "covered": "Covered truck",
    "open": "Open truck",
}

DEFAULT_RELIABILITY = 0.80

FLEET_COLUMNS = [
    "driver_id",
    "driver_name",
    "phone",
    "vehicle_type",
    "capacity_kg",
    "available_in_hours",
    "current_location",
    "destination",
    "reliability",
]

DEFAULT_FLEET = [
    {
        "driver_id": "TRUCK-001",
        "driver_name": "Demo driver 1",
        "phone": "",
        "vehicle_type": "covered",
        "capacity_kg": 5000.0,
        "available_in_hours": 0.0,
        "current_location": "Bahawalpur, Pakistan",
        "destination": "Multan, Pakistan",
        "reliability": 0.90,
    },
    {
        "driver_id": "TRUCK-002",
        "driver_name": "Demo driver 2",
        "phone": "",
        "vehicle_type": "refrigerated",
        "capacity_kg": 3000.0,
        "available_in_hours": 1.0,
        "current_location": "Rahim Yar Khan, Pakistan",
        "destination": "Multan, Pakistan",
        "reliability": 0.95,
    },
    {
        "driver_id": "TRUCK-003",
        "driver_name": "Demo driver 3",
        "phone": "",
        "vehicle_type": "open",
        "capacity_kg": 7000.0,
        "available_in_hours": 2.0,
        "current_location": "Lodhran, Pakistan",
        "destination": "Bahawalpur, Pakistan",
        "reliability": 0.80,
    },
]

FORM_DEFAULTS: Dict[str, Any] = {
    "farmer_id": "FARMER-001",
    "crop": "tomato",
    "quantity": 500.0,
    "harvest_age": 8.0,
    "condition": 0.90,
    "origin_name": "Bahawalpur, Pakistan",
    "destination_name": "Multan, Pakistan",
    "fallback_temp": 30.0,
}

DRIVER_FORM_DEFAULTS: Dict[str, Any] = {
    "drv_name": "",
    "drv_phone": "",
    "drv_vehicle": "covered",
    "drv_capacity": 3000.0,
    "drv_available": 0.0,
    "drv_location": "",
    "drv_destination": "",
}

URGENCY_ICONS = {"GREEN": "🟢", "YELLOW": "🟡", "ORANGE": "🟠", "RED": "🔴"}
URGENCY_TEXT = {
    "GREEN": "Plenty of time",
    "YELLOW": "Move within a day",
    "ORANGE": "Move soon",
    "RED": "Critical, move immediately",
}


class AnalysisError(Exception):
    """A problem the user can understand and fix."""


# =========================================================
# FLEET HELPERS
# =========================================================

def default_fleet() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_FLEET, columns=FLEET_COLUMNS)


def next_truck_id(df: pd.DataFrame) -> str:
    numbers = []
    for value in df["driver_id"].astype(str):
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            numbers.append(int(digits))
    return f"TRUCK-{(max(numbers) if numbers else 0) + 1:03d}"


def set_fleet(df: pd.DataFrame) -> None:
    """Replace the fleet and reset the table editor's edit history."""
    st.session_state.drivers = df
    st.session_state.fleet_version += 1


def clean_fleet(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Normalise the fleet table and report problems."""
    errors: List[str] = []
    df = df.copy()

    for column in FLEET_COLUMNS:
        if column not in df.columns:
            df[column] = None
    df = df[FLEET_COLUMNS]

    text_columns = (
        "driver_id",
        "driver_name",
        "phone",
        "vehicle_type",
        "current_location",
        "destination",
    )
    for column in text_columns:
        df[column] = df[column].fillna("").astype(str).str.strip()
    df["vehicle_type"] = df["vehicle_type"].str.lower()

    for column in ("capacity_kg", "available_in_hours", "reliability"):
        df[column] = pd.to_numeric(df[column], errors="coerce")

    blank = (
        (df["driver_id"] == "")
        & (df["current_location"] == "")
        & (df["destination"] == "")
    )
    df = df[~blank].reset_index(drop=True)

    for i, row in df.iterrows():
        label = row["driver_id"] or f"Row {i + 1}"

        if not row["driver_id"]:
            errors.append(f"Row {i + 1}: Truck ID is required.")
        if row["vehicle_type"] not in VEHICLE_TYPES:
            errors.append(f"{label}: choose refrigerated, covered or open.")
        if pd.isna(row["capacity_kg"]) or row["capacity_kg"] <= 0:
            errors.append(f"{label}: capacity must be greater than 0.")
        if pd.isna(row["available_in_hours"]) or row["available_in_hours"] < 0:
            errors.append(f"{label}: 'Free in (hours)' must be 0 or more.")
        if pd.isna(row["reliability"]) or not 0 <= row["reliability"] <= 1:
            errors.append(f"{label}: rating must be between 0 and 1.")
        if not row["current_location"]:
            errors.append(f"{label}: current location is required.")
        if not row["destination"]:
            errors.append(f"{label}: returning destination is required.")
        if row["phone"]:
            digits = sum(ch.isdigit() for ch in row["phone"])
            if not 7 <= digits <= 15:
                errors.append(f"{label}: the phone number does not look valid.")

    ids = df.loc[df["driver_id"] != "", "driver_id"]
    for duplicate in ids[ids.duplicated()].unique():
        errors.append(f"Truck ID '{duplicate}' is used more than once.")

    return df, errors


def build_drivers(df: pd.DataFrame) -> Tuple[List[Driver], List[str]]:
    """Locate each truck and build Driver objects."""
    drivers: List[Driver] = []
    warnings: List[str] = []

    for _, row in df.iterrows():
        try:
            current = geocode_location(row["current_location"])
            destination = geocode_location(row["destination"])

            drivers.append(
                Driver(
                    driver_id=row["driver_id"],
                    vehicle_type=row["vehicle_type"],
                    capacity_kg=float(row["capacity_kg"]),
                    available_in_hours=float(row["available_in_hours"]),
                    current_location=Location(
                        current["name"], current["latitude"], current["longitude"]
                    ),
                    destination=Location(
                        destination["name"],
                        destination["latitude"],
                        destination["longitude"],
                    ),
                    reliability=float(row["reliability"]),
                    name=row["driver_name"],
                    phone=row["phone"],
                )
            )
        except Exception as exc:
            warnings.append(f"{row['driver_id']} was skipped: {exc}")

    return drivers, warnings


# =========================================================
# SESSION STATE
# =========================================================

def init_state() -> None:
    if "drivers" not in st.session_state:
        st.session_state.drivers = default_fleet()

    st.session_state.setdefault("fleet_version", 0)
    st.session_state.setdefault("result", None)
    st.session_state.setdefault("report", None)
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("driver_msg", None)

    for key, value in FORM_DEFAULTS.items():
        st.session_state.setdefault(key, value)

    for key, value in DRIVER_FORM_DEFAULTS.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("drv_id", next_truck_id(st.session_state.drivers))

    for key in ("transcript_text", "driver_transcript_text"):
        st.session_state.setdefault(key, "")
    for key in ("voice_msg", "driver_voice_msg"):
        st.session_state.setdefault(key, None)


init_state()


# =========================================================
# VOICE
# =========================================================

def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def transcribe_callback(audio_key: str, text_key: str, msg_key: str) -> None:
    st.session_state[msg_key] = None
    audio = st.session_state.get(audio_key)

    if audio is None:
        st.session_state[msg_key] = ("warning", "Please record a message first.")
        return

    language = LANGUAGE_CODES.get(st.session_state.get("language", "English"))

    try:
        st.session_state[text_key] = transcribe_audio(audio.getvalue(), language)
        st.session_state[msg_key] = (
            "success",
            "Done. Check the text, then press the fill button.",
        )
    except Exception as exc:
        st.session_state[msg_key] = ("error", f"We could not process the recording: {exc}")


def fill_shipment_callback() -> None:
    st.session_state.voice_msg = None
    text = st.session_state.get("transcript_text", "").strip()

    if not text:
        st.session_state.voice_msg = ("warning", "There is no text to read yet.")
        return

    try:
        data = extract_shipment_from_text(text, CROPS)
    except Exception as exc:
        st.session_state.voice_msg = ("error", f"We could not read the text: {exc}")
        return

    applied: List[str] = []

    crop = str(data.get("crop") or "").strip().lower()
    if crop in CROP_PROFILES:
        st.session_state.crop = crop
        applied.append("crop")

    quantity = _to_float(data.get("quantity_kg"))
    if quantity is not None and quantity >= 1:
        st.session_state.quantity = quantity
        applied.append("quantity")

    age = _to_float(data.get("harvest_age_hours"))
    if age is not None and age >= 0:
        st.session_state.harvest_age = age
        applied.append("time since harvest")

    pickup = str(data.get("pickup_location") or "").strip()
    if pickup:
        st.session_state.origin_name = pickup
        applied.append("pickup location")

    destination = str(data.get("destination") or "").strip()
    if destination:
        st.session_state.destination_name = destination
        applied.append("destination")

    if applied:
        st.session_state.voice_msg = (
            "success",
            "Filled in: " + ", ".join(applied) + ". Please review before continuing.",
        )
    else:
        st.session_state.voice_msg = (
            "warning",
            "We could not find shipment details in that message.",
        )


def fill_vehicle_callback() -> None:
    st.session_state.driver_voice_msg = None
    text = st.session_state.get("driver_transcript_text", "").strip()

    if not text:
        st.session_state.driver_voice_msg = ("warning", "There is no text to read yet.")
        return

    try:
        data = extract_vehicle_from_text(text, list(VEHICLE_TYPES))
    except Exception as exc:
        st.session_state.driver_voice_msg = ("error", f"We could not read the text: {exc}")
        return

    applied: List[str] = []

    name = str(data.get("driver_name") or "").strip()
    if name:
        st.session_state.drv_name = name
        applied.append("name")

    phone = re.sub(r"[^\d+]", "", str(data.get("phone") or ""))
    if phone:
        st.session_state.drv_phone = phone
        applied.append("phone")

    vehicle = str(data.get("vehicle_type") or "").strip().lower()
    if vehicle in VEHICLE_TYPES:
        st.session_state.drv_vehicle = vehicle
        applied.append("vehicle type")

    capacity = _to_float(data.get("capacity_kg"))
    if capacity is not None and capacity >= 1:
        st.session_state.drv_capacity = capacity
        applied.append("capacity")

    available = _to_float(data.get("available_in_hours"))
    if available is not None and available >= 0:
        st.session_state.drv_available = available
        applied.append("availability")

    location = str(data.get("current_location") or "").strip()
    if location:
        st.session_state.drv_location = location
        applied.append("current location")

    destination = str(data.get("destination") or "").strip()
    if destination:
        st.session_state.drv_destination = destination
        applied.append("destination")

    if applied:
        st.session_state.driver_voice_msg = (
            "success",
            "Filled in: " + ", ".join(applied) + ". Please review before registering.",
        )
    else:
        st.session_state.driver_voice_msg = (
            "warning",
            "We could not find vehicle details in that message.",
        )


def voice_box(
    title: str,
    hint: str,
    audio_key: str,
    text_key: str,
    msg_key: str,
    fill_callback,
) -> None:
    """Optional voice input shared by the farmer and driver forms."""
    with st.expander(title):
        st.caption(hint)

        if not groq_configured():
            st.info("Voice input is not available right now. Please use the form below.")
            return

        st.audio_input("Record your message", sample_rate=16000, key=audio_key)

        st.button(
            "Convert recording to text",
            key=f"{audio_key}_transcribe",
            on_click=transcribe_callback,
            args=(audio_key, text_key, msg_key),
            width="stretch",
        )

        st.text_area("What we heard (you can edit it)", key=text_key, height=100)

        st.button(
            "Fill the form from this text",
            key=f"{audio_key}_fill",
            on_click=fill_callback,
            width="stretch",
        )

        if st.session_state[msg_key]:
            kind, message = st.session_state[msg_key]
            getattr(st, kind)(message)


# =========================================================
# DRIVER REGISTRATION
# =========================================================

def register_driver_callback() -> None:
    st.session_state.driver_msg = None
    state = st.session_state

    new_row = {
        "driver_id": state.drv_id,
        "driver_name": state.drv_name,
        "phone": state.drv_phone,
        "vehicle_type": state.drv_vehicle,
        "capacity_kg": float(state.drv_capacity),
        "available_in_hours": float(state.drv_available),
        "current_location": state.drv_location,
        "destination": state.drv_destination,
        "reliability": DEFAULT_RELIABILITY,
    }

    combined = pd.concat(
        [state.drivers, pd.DataFrame([new_row])], ignore_index=True
    )
    cleaned, errors = clean_fleet(combined)

    if errors:
        state.driver_msg = ("error", "Please fix: " + " ".join(errors))
        return

    for label, key in (
        ("current location", "drv_location"),
        ("returning destination", "drv_destination"),
    ):
        try:
            geocode_location(state[key])
        except Exception as exc:
            state.driver_msg = (
                "error",
                f"We could not find your {label} ('{state[key]}'). {exc}",
            )
            return

    set_fleet(cleaned)
    state.driver_msg = (
        "success",
        f"{new_row['driver_id']} is registered. Farmers can now be matched with it.",
    )

    for key, value in DRIVER_FORM_DEFAULTS.items():
        state[key] = value
    state.drv_id = next_truck_id(cleaned)
    state.driver_transcript_text = ""


# =========================================================
# ANALYSIS
# =========================================================

def form_inputs() -> Dict[str, Any]:
    return {key: st.session_state[key] for key in FORM_DEFAULTS}


def make_signature() -> str:
    """Fingerprint of everything that affects the result."""
    inputs = form_inputs()
    inputs["origin_name"] = inputs["origin_name"].strip().lower()
    inputs["destination_name"] = inputs["destination_name"].strip().lower()
    return f"{sorted(inputs.items())}|{st.session_state.drivers.to_json()}"


def validate_inputs() -> List[str]:
    errors = []
    if not st.session_state.origin_name.strip():
        errors.append("Enter the pickup location.")
    if not st.session_state.destination_name.strip():
        errors.append("Enter the delivery location.")
    if len(st.session_state.drivers) == 0:
        errors.append("No trucks are registered yet. Add one in the Drivers tab.")
    return errors


def run_analysis() -> Dict[str, Any]:
    inputs = form_inputs()

    try:
        origin_data = geocode_location(inputs["origin_name"])
        destination_data = geocode_location(inputs["destination_name"])
    except Exception as exc:
        raise AnalysisError(f"We could not find that location. {exc}") from exc

    origin = Location(
        origin_data["name"], origin_data["latitude"], origin_data["longitude"]
    )
    destination = Location(
        destination_data["name"],
        destination_data["latitude"],
        destination_data["longitude"],
    )

    shipment = Shipment(
        farmer_id=inputs["farmer_id"],
        crop=inputs["crop"],
        quantity_kg=float(inputs["quantity"]),
        harvest_age_hours=float(inputs["harvest_age"]),
        condition_score=float(inputs["condition"]),
        origin=origin,
        destination=destination,
    )

    weather_failed = False
    try:
        weather = get_current_weather(origin.latitude, origin.longitude)
    except Exception:
        weather_failed = True
        weather = {
            "temperature_c": float(inputs["fallback_temp"]),
            "humidity": None,
            "wind_speed_kmh": None,
            "precipitation_mm": None,
            "timezone": "",
            "source": "Manual fallback",
        }

    analysis = analyze_shipment(shipment, weather["temperature_c"])

    fleet, fleet_errors = clean_fleet(st.session_state.drivers)
    if fleet_errors:
        raise AnalysisError(
            "Please fix the truck list first: " + " ".join(fleet_errors)
        )

    drivers, fleet_warnings = build_drivers(fleet)
    if not drivers:
        raise AnalysisError("No usable trucks found. " + " ".join(fleet_warnings))

    matches = rank_matches(shipment, drivers, analysis, get_route)

    return {
        "signature": make_signature(),
        "shipment": shipment,
        "analysis": analysis,
        "matches": matches,
        "weather": weather,
        "weather_failed": weather_failed,
        "drivers": {d.driver_id: d for d in drivers},
        "fleet_warnings": fleet_warnings,
    }


# =========================================================
# MAP
# =========================================================

LEG_COLORS = {
    "Truck to farm": [230, 126, 34],
    "Farm to buyer": [46, 125, 50],
    "Buyer to truck destination": [120, 120, 120],
}

POINT_COLORS = {
    "Farm": [46, 125, 50],
    "Buyer": [30, 90, 200],
    "Recommended truck": [230, 126, 34],
}


def render_map(result: Dict[str, Any], best) -> None:
    shipment = result["shipment"]

    points = [
        {
            "name": f"Farm: {shipment.origin.name}",
            "label": "Farm",
            "lat": shipment.origin.latitude,
            "lon": shipment.origin.longitude,
        },
        {
            "name": f"Buyer: {shipment.destination.name}",
            "label": "Buyer",
            "lat": shipment.destination.latitude,
            "lon": shipment.destination.longitude,
        },
    ]
    paths: List[Dict[str, Any]] = []

    if best is not None:
        truck = result["drivers"][best.driver_id]
        points.append(
            {
                "name": f"{truck.driver_id}: {truck.current_location.name}",
                "label": "Recommended truck",
                "lat": truck.current_location.latitude,
                "lon": truck.current_location.longitude,
            }
        )
        for leg in best.route_legs:
            if leg["geometry"]:
                paths.append(
                    {
                        "name": leg["name"],
                        "path": leg["geometry"],
                        "color": LEG_COLORS.get(leg["name"], [90, 90, 90]),
                    }
                )

    for point in points:
        point["color"] = POINT_COLORS[point["label"]]

    try:
        import pydeck as pdk
    except ImportError:
        st.map(pd.DataFrame(points), latitude="lat", longitude="lon")
        return

    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    span = max(max(lats) - min(lats), max(lons) - min(lons), 0.05)
    zoom = max(3.0, min(11.0, math.log2(360 / span) - 1))

    layers = []
    if paths:
        layers.append(
            pdk.Layer(
                "PathLayer",
                data=paths,
                get_path="path",
                get_color="color",
                get_width=5,
                width_min_pixels=3,
                pickable=True,
            )
        )
    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=points,
            get_position="[lon, lat]",
            get_fill_color="color",
            get_radius=4000,
            radius_min_pixels=8,
            pickable=True,
        )
    )

    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(
                latitude=sum(lats) / len(lats),
                longitude=sum(lons) / len(lons),
                zoom=zoom,
            ),
            tooltip={"text": "{name}"},
        )
    )

    st.caption(
        "Orange: truck to your farm. Green: farm to buyer. "
        "Grey: buyer to the truck's own destination."
    )


# =========================================================
# RESULTS
# =========================================================

def match_table(matches, drivers: Dict[str, Driver]) -> pd.DataFrame:
    rows = []
    for m in matches:
        driver = drivers.get(m.driver_id)
        rows.append(
            {
                "Truck": m.driver_id,
                "Driver": driver.name if driver and driver.name else "-",
                "Result": "Suitable" if m.valid else "Not suitable",
                "Match score": round(m.score * 100),
                "Extra distance (km)": round(m.detour_km, 1),
                "Distance to farm (km)": round(m.pickup_distance_km, 1),
                "Hours to deliver": round(m.time_to_delivery_hours, 1),
                "Freshness left (h)": round(max(0.0, m.remaining_at_delivery_hours), 1),
                "Notes": "Good match." if m.valid else m.reason.replace("Rejected: ", ""),
            }
        )
    return pd.DataFrame(rows)


def render_results(result: Dict[str, Any], language: str) -> None:
    shipment = result["shipment"]
    analysis = result["analysis"]
    matches = result["matches"]
    weather = result["weather"]
    valid = [m for m in matches if m.valid]

    st.divider()
    st.header("Your results")
    st.caption(
        f"{shipment.crop.title()} · {shipment.quantity_kg:.0f} kg · "
        f"{shipment.origin.name} → {shipment.destination.name}"
    )

    if result["signature"] != make_signature():
        st.warning(
            "Your details or the truck list changed after this check. "
            "Press **Find trucks** again to refresh the results."
        )
    if result["weather_failed"]:
        st.warning(
            "Live weather is unavailable, so the temperature you entered "
            "under Advanced options was used."
        )
    for message in result["fleet_warnings"]:
        st.warning(message)
    if any(m.used_fallback for m in matches):
        st.warning(
            "Live road data is temporarily unavailable, so some distances "
            "are approximate."
        )

    # ---------------- freshness summary ----------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Temperature at farm", f"{analysis.temperature_c:.0f} °C")
    c2.metric("Freshness left", f"{analysis.remaining_shelf_life_hours:.0f} h")
    c3.metric("Urgency", f"{URGENCY_ICONS.get(analysis.urgency, '')} {analysis.urgency.title()}")
    c4.metric("Suitable trucks", len(valid))
    st.caption(
        f"{URGENCY_TEXT.get(analysis.urgency, '')}. Freshness is an estimate "
        "based on crop, time since harvest, condition and temperature."
    )

    with st.expander("How freshness was estimated"):
        st.write(
            f"A {shipment.crop} normally stays fresh for about "
            f"{analysis.base_shelf_life_hours:.0f} hours. After "
            f"{shipment.harvest_age_hours:.0f} hours since harvest, today's "
            f"heat and the produce condition, about "
            f"{analysis.effective_elapsed_hours:.0f} hours of that have been used."
        )
        st.caption(
            "This is a planning estimate, not a food-safety guarantee. "
            "Refrigerated trucks are assumed to keep produce at its ideal "
            "temperature while loaded."
        )

    # ---------------- recommended truck ----------------------------
    best = valid[0] if valid else None

    if best is not None:
        truck = result["drivers"][best.driver_id]

        with st.container(border=True):
            st.subheader(f"✅ Recommended: {best.driver_id}")

            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Match score", f"{best.score * 100:.0f}%")
            b2.metric("Extra distance", f"{best.detour_km:.1f} km")
            b3.metric("Time to deliver", f"{best.time_to_delivery_hours:.1f} h")
            b4.metric("Freshness at delivery", f"{best.remaining_at_delivery_hours:.0f} h")

            details = [VEHICLE_LABELS.get(truck.vehicle_type, truck.vehicle_type)]
            details.append(f"capacity {truck.capacity_kg:.0f} kg")
            if truck.name:
                details.append(f"driver {truck.name}")
            if truck.phone:
                details.append(f"📞 {truck.phone}")
            st.write(" · ".join(details))
    else:
        st.error(
            "No suitable truck was found right now. Try again later, "
            "or ask drivers to register more trucks in the Drivers tab."
        )

    # ---------------- all trucks -----------------------------------
    st.subheader("All trucks compared")

    table = match_table(matches, result["drivers"])
    st.dataframe(table, width="stretch", hide_index=True)
    st.download_button(
        "Download comparison (CSV)",
        table.to_csv(index=False).encode("utf-8"),
        file_name="freshroute_matches.csv",
        mime="text/csv",
    )

    # ---------------- summary report -------------------------------
    st.subheader("Shipment summary")

    if not groq_configured():
        st.info("The written summary is not available right now.")
    elif st.button("Write a shipment summary", key="gen_report"):
        try:
            with st.spinner("Writing your summary..."):
                text = generate_ai_report(shipment, analysis, matches, weather, language)
            st.session_state.report = {"text": text, "language": language}
        except Exception as exc:
            st.error(f"We could not write the summary: {exc}")

    report = st.session_state.report
    if report:
        st.markdown(report["text"])
        st.download_button(
            "Download summary",
            report["text"].encode("utf-8"),
            file_name="freshroute_summary.md",
            mime="text/markdown",
        )

    # ---------------- map ------------------------------------------
    st.subheader("Map")
    render_map(result, best)


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
<div class="fr-hero">
  <h1>🚚 FreshRoute</h1>
  <p>Get fresh produce to market faster, using trucks that are already heading your way.</p>
</div>
""",
    unsafe_allow_html=True,
)

hint_col, lang_col = st.columns([3, 1], vertical_alignment="center")
hint_col.caption("You can speak or type in English, Urdu or Roman Urdu.")
language = lang_col.selectbox(
    "Language",
    list(LANGUAGE_CODES.keys()),
    key="language",
    help="Used for voice input and written answers.",
)

home_tab, farmer_tab, driver_tab, assistant_tab, about_tab = st.tabs(
    ["🏠 Home", "🌾 Farmers", "🚚 Drivers", "💬 Assistant", "ℹ️ About"]
)


# =========================================================
# HOME
# =========================================================

with home_tab:
    st.header("How FreshRoute works")

    steps = [
        (
            "🌾",
            "Farmers describe their produce",
            "Say or type the crop, quantity and where it needs to go.",
        ),
        (
            "🚚",
            "Drivers register their truck",
            "Share the vehicle, free space and the route the truck is returning on.",
        ),
        (
            "✅",
            "FreshRoute finds the best match",
            "We check space, extra distance and how fresh the produce will "
            "still be when it arrives.",
        ),
    ]

    for column, (icon, title, text) in zip(st.columns(3), steps):
        column.markdown(
            f'<div class="fr-card"><div class="icon">{icon}</div>'
            f"<h4>{title}</h4><p>{text}</p></div>",
            unsafe_allow_html=True,
        )

    st.write("")
    fleet_now = st.session_state.drivers
    s1, s2, s3 = st.columns(3)
    s1.metric("Trucks registered", len(fleet_now))
    s2.metric(
        "Refrigerated trucks",
        int((fleet_now["vehicle_type"] == "refrigerated").sum()),
    )
    s3.metric("Crops supported", len(CROPS))

    st.write("")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("🌾 For farmers")
            st.write(
                "Find a truck for your harvest before it spoils. "
                "Open the **Farmers** tab to get started."
            )
    with right:
        with st.container(border=True):
            st.subheader("🚚 For drivers")
            st.write(
                "Earn from empty return trips. "
                "Open the **Drivers** tab to register your truck."
            )


# =========================================================
# FARMERS
# =========================================================

with farmer_tab:
    st.header("Find a truck for your produce")
    st.write("Tell us about your harvest and where it needs to go.")

    voice_box(
        title="🎙️ Prefer to speak? Describe your shipment",
        hint=(
            "Example: \"I have 800 kg of tomatoes harvested 6 hours ago in "
            "Bahawalpur. I need to send them to Multan.\""
        ),
        audio_key="voice_audio",
        text_key="transcript_text",
        msg_key="voice_msg",
        fill_callback=fill_shipment_callback,
    )

    with st.container(border=True):
        st.subheader("Your produce")
        p1, p2 = st.columns(2)

        with p1:
            st.text_input("Your name or ID", key="farmer_id")
            st.selectbox("Crop", CROPS, key="crop", format_func=str.title)
            st.number_input("Quantity (kg)", min_value=1.0, step=50.0, key="quantity")

        with p2:
            st.number_input(
                "Hours since harvest", min_value=0.0, step=1.0, key="harvest_age"
            )
            st.slider(
                "Produce condition",
                min_value=0.1,
                max_value=1.0,
                step=0.05,
                key="condition",
                help="1.0 = excellent, 0.1 = badly deteriorated.",
            )

    with st.container(border=True):
        st.subheader("Pickup and delivery")
        l1, l2 = st.columns(2)
        l1.text_input("Pickup location (your farm)", key="origin_name")
        l2.text_input("Delivery location (buyer)", key="destination_name")

    with st.expander("Advanced options"):
        st.number_input(
            "Temperature to use if live weather is unavailable (°C)",
            min_value=-10.0,
            max_value=60.0,
            step=0.5,
            key="fallback_temp",
        )

    if st.button("Find trucks", type="primary", width="stretch"):
        problems = validate_inputs()

        if problems:
            for problem in problems:
                st.error(problem)
        else:
            try:
                with st.spinner("Looking for the best truck for you..."):
                    new_result = run_analysis()
            except AnalysisError as exc:
                st.error(str(exc))
            else:
                st.session_state.result = new_result
                st.session_state.report = None
                st.session_state.chat = []

    if st.session_state.result is not None:
        render_results(st.session_state.result, language)


# =========================================================
# DRIVERS
# =========================================================

with driver_tab:
    st.header("Register your truck")
    st.write(
        "Returning with an empty or half-empty truck? Tell us about your "
        "vehicle and route, and farmers can be matched with you."
    )

    voice_box(
        title="🎙️ Prefer to speak? Describe your truck",
        hint=(
            "Example: \"My name is Ali, phone 0300 1234567. I have a covered "
            "truck with 4 tons capacity in Lodhran, returning to Bahawalpur, "
            "free in 2 hours.\""
        ),
        audio_key="driver_voice_audio",
        text_key="driver_transcript_text",
        msg_key="driver_voice_msg",
        fill_callback=fill_vehicle_callback,
    )

    with st.container(border=True):
        st.subheader("You and your truck")
        d1, d2 = st.columns(2)

        with d1:
            st.text_input("Your name", key="drv_name")
            st.text_input(
                "Phone number (shown to the farmer you are matched with)",
                key="drv_phone",
            )
            st.text_input("Truck ID", key="drv_id")

        with d2:
            st.selectbox(
                "Vehicle type",
                list(VEHICLE_TYPES),
                key="drv_vehicle",
                format_func=VEHICLE_LABELS.get,
            )
            st.number_input(
                "Free capacity (kg)", min_value=1.0, step=100.0, key="drv_capacity"
            )
            st.number_input(
                "Free in how many hours? (0 = free now)",
                min_value=0.0,
                step=0.5,
                key="drv_available",
            )

    with st.container(border=True):
        st.subheader("Your route")
        r1, r2 = st.columns(2)
        r1.text_input("Where is the truck now?", key="drv_location")
        r2.text_input("Where is it returning to?", key="drv_destination")

    st.button(
        "Register truck",
        type="primary",
        width="stretch",
        on_click=register_driver_callback,
    )

    if st.session_state.driver_msg:
        kind, message = st.session_state.driver_msg
        getattr(st, kind)(message)

    # ---------------- registered trucks ----------------------------
    st.divider()
    st.subheader("Registered trucks")

    overview = st.session_state.drivers.rename(
        columns={
            "driver_id": "Truck",
            "driver_name": "Driver",
            "phone": "Phone",
            "vehicle_type": "Vehicle",
            "capacity_kg": "Capacity (kg)",
            "available_in_hours": "Free in (h)",
            "current_location": "From",
            "destination": "To",
        }
    ).drop(columns=["reliability"])
    st.dataframe(overview, width="stretch", hide_index=True)

    with st.expander("Edit or remove trucks"):
        edited = st.data_editor(
            st.session_state.drivers,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            key=f"fleet_editor_{st.session_state.fleet_version}",
            column_config={
                "driver_id": st.column_config.TextColumn("Truck ID", required=True),
                "driver_name": st.column_config.TextColumn("Driver name"),
                "phone": st.column_config.TextColumn("Phone"),
                "vehicle_type": st.column_config.SelectboxColumn(
                    "Vehicle", options=list(VEHICLE_TYPES), required=True
                ),
                "capacity_kg": st.column_config.NumberColumn(
                    "Capacity (kg)", min_value=1, step=100, required=True
                ),
                "available_in_hours": st.column_config.NumberColumn(
                    "Free in (h)", min_value=0, step=0.5, required=True
                ),
                "current_location": st.column_config.TextColumn(
                    "Current location", required=True
                ),
                "destination": st.column_config.TextColumn(
                    "Returning to", required=True
                ),
                "reliability": st.column_config.NumberColumn(
                    "Rating (0-1)",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.05,
                    required=True,
                ),
            },
        )

        save_col, reset_col = st.columns(2)

        if save_col.button("Save changes", type="primary", width="stretch"):
            cleaned, fleet_errors = clean_fleet(edited)
            if fleet_errors:
                for error in fleet_errors:
                    st.error(error)
            elif cleaned.empty:
                st.error("Keep at least one truck.")
            else:
                set_fleet(cleaned)
                st.success("Changes saved.")

        if reset_col.button("Restore sample trucks", width="stretch"):
            set_fleet(default_fleet())
            st.rerun()

    st.caption(
        f"A truck is only matched if the extra distance is at most "
        f"{MAX_DETOUR_KM:.0f} km and the produce will still have at least "
        f"{MIN_REMAINING_SHELF_LIFE_HOURS:.0f} hours of freshness left on arrival."
    )


# =========================================================
# ASSISTANT
# =========================================================

with assistant_tab:
    st.header("Ask FreshRoute")

    result = st.session_state.result

    if result is None:
        st.info("Find trucks for a shipment first, then ask questions about the result.")
    elif not groq_configured():
        st.info("The assistant is not available right now.")
    else:
        shipment = result["shipment"]
        st.write(
            f"Current shipment: **{shipment.crop.title()}, "
            f"{shipment.quantity_kg:.0f} kg**"
        )
        st.caption(
            "Try: Why was this truck chosen? What is the biggest risk? "
            "What should I do next?"
        )

        if st.button("Clear conversation"):
            st.session_state.chat = []

        for message in st.session_state.chat:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        question = st.chat_input("Type your question")

        if question and question.strip():
            history = list(st.session_state.chat)
            st.session_state.chat.append({"role": "user", "content": question})

            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                try:
                    with st.spinner("Thinking..."):
                        answer = ask_freshroute_ai(
                            question,
                            shipment,
                            result["analysis"],
                            result["matches"],
                            result["weather"],
                            language,
                            history,
                        )
                    st.markdown(answer)
                    st.session_state.chat.append(
                        {"role": "assistant", "content": answer}
                    )
                except Exception as exc:
                    st.error(f"We could not answer that: {exc}")


# =========================================================
# ABOUT
# =========================================================

with about_tab:
    st.header("About FreshRoute")

    st.markdown(
        """
### Why it exists

Farmers often struggle to find transport before their produce spoils, while
trucks returning from deliveries travel with empty space. FreshRoute connects
the two, so produce reaches buyers fresher and trucks earn from trips that
would otherwise be wasted.

### What we check for every truck

- The vehicle suits the crop (for example, strawberries need refrigeration)
- The truck has enough space and is free in time
- The extra distance to collect and deliver the produce is small
- The produce will still be fresh when it arrives

### Good to know

- Freshness is a planning estimate, not a food-safety guarantee.
- Distances are approximate because places are located by town or city.
- Trucks you register are kept only for your current visit. They are not
  stored permanently.
- FreshRoute is a prototype that supports decisions. Please confirm
  details directly with the driver or farmer before loading.
"""
    )
