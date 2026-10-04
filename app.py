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
from i18n import tr
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

# Internal language names (also used for Groq prompts and voice).
LANGUAGE_CODES = {"English": "en", "Urdu": "ur", "Roman Urdu": None}
# What the user sees in the language picker.
LANGUAGE_LABELS = {"English": "English", "Urdu": "اردو", "Roman Urdu": "Roman Urdu"}

# The language picker is a widget with key="language"; Streamlit writes its
# value into session_state before the script reruns, so it is already
# available here, at the very top of the run.
st.session_state.setdefault("language", "English")


def is_urdu() -> bool:
    return st.session_state.get("language") == "Urdu"


def t(key: str, **params) -> str:
    """Translate a UI string. Urdu UI only when Urdu is selected."""
    return tr("ur" if is_urdu() else "en", key, **params)


def join_items(items: List[str]) -> str:
    return t("sep").join(items)


def crop_label(crop: str) -> str:
    key = f"crop_{crop}"
    label = t(key)
    return crop.title() if label == key else label


def vehicle_label(vehicle: str) -> str:
    key = f"vehicle_{vehicle}"
    label = t(key)
    return vehicle if label == key else label


BASE_CSS = """
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
"""

# Applied only when Urdu is selected: right-to-left layout and an Urdu font.
# The font is set on text elements only (not on "*") so Streamlit's icon
# fonts keep working.
URDU_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Naskh+Arabic:wght@400;600;700&display=swap');

.stApp {direction: rtl;}
.block-container {text-align: right;}

.stApp :is(p, h1, h2, h3, h4, h5, h6, label, li, button, input, textarea,
           [data-testid="stMarkdownContainer"],
           [data-testid="stMetricLabel"], [data-testid="stMetricValue"],
           [data-testid="stCaptionContainer"], [data-baseweb="tab"],
           [data-baseweb="select"], [data-testid="stChatMessageContent"]) {
    font-family: 'Noto Naskh Arabic', 'Jameel Noori Nastaleeq', 'Segoe UI',
                 Tahoma, sans-serif;
}
.stApp :is(p, li, label, [data-testid="stMarkdownContainer"],
           [data-testid="stCaptionContainer"]) {line-height: 1.9;}

/* Columns, tabs and text follow the right-to-left direction */
[data-testid="stHorizontalBlock"], [data-baseweb="tab-list"] {direction: rtl;}
h1, h2, h3, h4, h5, h6, p, label, li, .stCaption {text-align: right;}

/* Things that must stay left-to-right so they behave normally */
[data-testid="stSlider"], [data-testid="stDataFrame"],
[data-testid="stDeckGlJsonChart"], input[type="number"] {direction: ltr;}
[data-testid="stSlider"] label, [data-testid="stSlider"] p {direction: rtl;}
</style>
"""

st.markdown(BASE_CSS, unsafe_allow_html=True)
if is_urdu():
    st.markdown(URDU_CSS, unsafe_allow_html=True)


# =========================================================
# CONSTANTS
# =========================================================

CROPS = list(CROP_PROFILES.keys())

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
        where = row["driver_id"] or t("row", n=i + 1)

        if not row["driver_id"]:
            errors.append(t("err_id_required", where=where))
        if row["vehicle_type"] not in VEHICLE_TYPES:
            errors.append(t("err_vehicle", where=where))
        if pd.isna(row["capacity_kg"]) or row["capacity_kg"] <= 0:
            errors.append(t("err_capacity", where=where))
        if pd.isna(row["available_in_hours"]) or row["available_in_hours"] < 0:
            errors.append(t("err_free", where=where))
        if pd.isna(row["reliability"]) or not 0 <= row["reliability"] <= 1:
            errors.append(t("err_rating", where=where))
        if not row["current_location"]:
            errors.append(t("err_location", where=where))
        if not row["destination"]:
            errors.append(t("err_destination", where=where))
        if row["phone"]:
            digits = sum(ch.isdigit() for ch in row["phone"])
            if not 7 <= digits <= 15:
                errors.append(t("err_phone", where=where))

    ids = df.loc[df["driver_id"] != "", "driver_id"]
    for duplicate in ids[ids.duplicated()].unique():
        errors.append(t("err_duplicate", id=duplicate))

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
            warnings.append(t("truck_skipped", id=row["driver_id"], err=exc))

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
# Voice messages are stored as (kind, key, params) and translated when
# they are shown, so they switch language together with the interface.

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
        st.session_state[msg_key] = ("warning", "voice_record_first", {})
        return

    language = LANGUAGE_CODES.get(st.session_state.get("language", "English"))

    try:
        st.session_state[text_key] = transcribe_audio(audio.getvalue(), language)
        st.session_state[msg_key] = ("success", "voice_done", {})
    except Exception as exc:
        st.session_state[msg_key] = ("error", "voice_fail", {"err": str(exc)})


def _filled_message(applied: List[str], next_key: str) -> Tuple[str, str, dict]:
    fields = join_items([t(f) for f in applied])
    return ("success", "voice_filled", {"fields": fields, "next": t(next_key)})


def fill_shipment_callback() -> None:
    st.session_state.voice_msg = None
    text = st.session_state.get("transcript_text", "").strip()

    if not text:
        st.session_state.voice_msg = ("warning", "voice_no_text", {})
        return

    try:
        data = extract_shipment_from_text(text, CROPS)
    except Exception as exc:
        st.session_state.voice_msg = ("error", "voice_read_fail", {"err": str(exc)})
        return

    applied: List[str] = []

    crop = str(data.get("crop") or "").strip().lower()
    if crop in CROP_PROFILES:
        st.session_state.crop = crop
        applied.append("f_crop")

    quantity = _to_float(data.get("quantity_kg"))
    if quantity is not None and quantity >= 1:
        st.session_state.quantity = quantity
        applied.append("f_quantity")

    age = _to_float(data.get("harvest_age_hours"))
    if age is not None and age >= 0:
        st.session_state.harvest_age = age
        applied.append("f_age")

    pickup = str(data.get("pickup_location") or "").strip()
    if pickup:
        st.session_state.origin_name = pickup
        applied.append("f_pickup")

    destination = str(data.get("destination") or "").strip()
    if destination:
        st.session_state.destination_name = destination
        applied.append("f_destination")

    if applied:
        st.session_state.voice_msg = _filled_message(applied, "voice_next_continue")
    else:
        st.session_state.voice_msg = ("warning", "voice_none_shipment", {})


def fill_vehicle_callback() -> None:
    st.session_state.driver_voice_msg = None
    text = st.session_state.get("driver_transcript_text", "").strip()

    if not text:
        st.session_state.driver_voice_msg = ("warning", "voice_no_text", {})
        return

    try:
        data = extract_vehicle_from_text(text, list(VEHICLE_TYPES))
    except Exception as exc:
        st.session_state.driver_voice_msg = (
            "error",
            "voice_read_fail",
            {"err": str(exc)},
        )
        return

    applied: List[str] = []

    name = str(data.get("driver_name") or "").strip()
    if name:
        st.session_state.drv_name = name
        applied.append("f_name")

    phone = re.sub(r"[^\d+]", "", str(data.get("phone") or ""))
    if phone:
        st.session_state.drv_phone = phone
        applied.append("f_phone")

    vehicle = str(data.get("vehicle_type") or "").strip().lower()
    if vehicle in VEHICLE_TYPES:
        st.session_state.drv_vehicle = vehicle
        applied.append("f_vehicle")

    capacity = _to_float(data.get("capacity_kg"))
    if capacity is not None and capacity >= 1:
        st.session_state.drv_capacity = capacity
        applied.append("f_capacity")

    available = _to_float(data.get("available_in_hours"))
    if available is not None and available >= 0:
        st.session_state.drv_available = available
        applied.append("f_availability")

    location = str(data.get("current_location") or "").strip()
    if location:
        st.session_state.drv_location = location
        applied.append("f_location")

    destination = str(data.get("destination") or "").strip()
    if destination:
        st.session_state.drv_destination = destination
        applied.append("f_destination")

    if applied:
        st.session_state.driver_voice_msg = _filled_message(
            applied, "voice_next_register"
        )
    else:
        st.session_state.driver_voice_msg = ("warning", "voice_none_vehicle", {})


def show_message(message) -> None:
    """Display a stored (kind, key, params) message in the current language."""
    kind, key, params = message
    getattr(st, kind)(t(key, **params))


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
            st.info(t("voice_unavailable"))
            return

        st.audio_input(t("voice_record"), sample_rate=16000, key=audio_key)

        st.button(
            t("voice_transcribe"),
            key=f"{audio_key}_transcribe",
            on_click=transcribe_callback,
            args=(audio_key, text_key, msg_key),
            width="stretch",
        )

        st.text_area(t("voice_heard"), key=text_key, height=100)

        st.button(
            t("voice_fill"),
            key=f"{audio_key}_fill",
            on_click=fill_callback,
            width="stretch",
        )

        if st.session_state[msg_key]:
            show_message(st.session_state[msg_key])


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
        state.driver_msg = (
            "error",
            "fix_prefix",
            {"errors": " ".join(errors)},
        )
        return

    for label_key, key in (
        ("label_current_location", "drv_location"),
        ("label_return_destination", "drv_destination"),
    ):
        try:
            geocode_location(state[key])
        except Exception as exc:
            state.driver_msg = (
                "error",
                "geo_fail",
                {"label": t(label_key), "value": state[key], "err": str(exc)},
            )
            return

    set_fleet(cleaned)
    state.driver_msg = ("success", "truck_registered", {"id": new_row["driver_id"]})

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
        errors.append(t("enter_pickup"))
    if not st.session_state.destination_name.strip():
        errors.append(t("enter_delivery"))
    if len(st.session_state.drivers) == 0:
        errors.append(t("no_trucks"))
    return errors


def run_analysis() -> Dict[str, Any]:
    inputs = form_inputs()

    try:
        origin_data = geocode_location(inputs["origin_name"])
        destination_data = geocode_location(inputs["destination_name"])
    except Exception as exc:
        raise AnalysisError(t("loc_not_found", err=exc)) from exc

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
        raise AnalysisError(t("fix_fleet_first", errors=" ".join(fleet_errors)))

    drivers, fleet_warnings = build_drivers(fleet)
    if not drivers:
        raise AnalysisError(t("no_usable_trucks", warnings=" ".join(fleet_warnings)))

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

# Keys match the English leg names produced by core.py.
LEG_COLORS = {
    "Truck to farm": [230, 126, 34],
    "Farm to buyer": [46, 125, 50],
    "Buyer to truck destination": [120, 120, 120],
}
LEG_KEYS = {
    "Truck to farm": "leg_truck_to_farm",
    "Farm to buyer": "leg_farm_to_buyer",
    "Buyer to truck destination": "leg_buyer_to_dest",
}

POINT_COLORS = {
    "Farm": [46, 125, 50],
    "Buyer": [30, 90, 200],
    "Recommended truck": [230, 126, 34],
}
POINT_KEYS = {
    "Farm": "pt_farm",
    "Buyer": "pt_buyer",
    "Recommended truck": "pt_truck",
}


def render_map(result: Dict[str, Any], best) -> None:
    shipment = result["shipment"]

    points = [
        {
            "name": f"{t('pt_farm')}: {shipment.origin.name}",
            "label": "Farm",
            "lat": shipment.origin.latitude,
            "lon": shipment.origin.longitude,
        },
        {
            "name": f"{t('pt_buyer')}: {shipment.destination.name}",
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
                        "name": t(LEG_KEYS.get(leg["name"], "leg_truck_to_farm"))
                        if leg["name"] in LEG_KEYS
                        else leg["name"],
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

    st.caption(t("map_caption"))


# =========================================================
# RESULTS
# =========================================================

def reason_text(match, crop: str) -> str:
    """Rejection reasons in the current language."""
    details = getattr(match, "rejection_details", None)
    if not details:
        return match.reason.replace("Rejected: ", "")

    parts = []
    for item in details:
        params = {k: v for k, v in item.items() if k != "code"}
        if "vehicle" in params:
            params["vehicle"] = vehicle_label(params["vehicle"])
        if "crop" in params:
            params["crop"] = crop_label(params["crop"])
        try:
            parts.append(t(f"rej_{item['code']}", **params))
        except (KeyError, IndexError):
            parts.append(match.reason.replace("Rejected: ", ""))
            break
    return " ".join(parts)


def match_table(matches, drivers: Dict[str, Driver], crop: str) -> pd.DataFrame:
    rows = []
    for m in matches:
        driver = drivers.get(m.driver_id)
        rows.append(
            {
                t("col_truck"): m.driver_id,
                t("col_driver"): driver.name if driver and driver.name else "-",
                t("col_result"): t("suitable") if m.valid else t("not_suitable"),
                t("col_score"): round(m.score * 100),
                t("col_extra"): round(m.detour_km, 1),
                t("col_to_farm"): round(m.pickup_distance_km, 1),
                t("col_hours"): round(m.time_to_delivery_hours, 1),
                t("col_fresh"): round(max(0.0, m.remaining_at_delivery_hours), 1),
                t("col_notes"): t("good_match") if m.valid else reason_text(m, crop),
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
    st.header(t("your_results"))
    st.caption(
        f"{crop_label(shipment.crop)} · {shipment.quantity_kg:.0f} kg · "
        f"{shipment.origin.name} → {shipment.destination.name}"
    )

    if result["signature"] != make_signature():
        st.warning(t("stale_warning"))
    if result["weather_failed"]:
        st.warning(t("weather_failed"))
    for message in result["fleet_warnings"]:
        st.warning(message)
    if any(m.used_fallback for m in matches):
        st.warning(t("road_fallback"))

    # ---------------- freshness summary ----------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("m_temp"), f"{analysis.temperature_c:.0f} °C")
    c2.metric(t("m_fresh_left"), f"{analysis.remaining_shelf_life_hours:.0f} h")
    c3.metric(
        t("m_urgency"),
        f"{URGENCY_ICONS.get(analysis.urgency, '')} "
        f"{t('urgency_' + analysis.urgency)}",
    )
    c4.metric(t("m_suitable"), len(valid))
    st.caption(
        t("fresh_caption", text=t("urgency_text_" + analysis.urgency))
    )

    with st.expander(t("how_fresh")):
        st.write(
            t(
                "how_fresh_text",
                crop=crop_label(shipment.crop),
                base=f"{analysis.base_shelf_life_hours:.0f}",
                age=f"{shipment.harvest_age_hours:.0f}",
                used=f"{analysis.effective_elapsed_hours:.0f}",
            )
        )
        st.caption(t("how_fresh_caption"))

    # ---------------- recommended truck ----------------------------
    best = valid[0] if valid else None

    if best is not None:
        truck = result["drivers"][best.driver_id]

        with st.container(border=True):
            st.subheader(t("recommended", id=best.driver_id))

            b1, b2, b3, b4 = st.columns(4)
            b1.metric(t("m_score"), f"{best.score * 100:.0f}%")
            b2.metric(t("m_extra"), f"{best.detour_km:.1f} km")
            b3.metric(t("m_time"), f"{best.time_to_delivery_hours:.1f} h")
            b4.metric(t("m_fresh_at"), f"{best.remaining_at_delivery_hours:.0f} h")

            details = [vehicle_label(truck.vehicle_type)]
            details.append(t("capacity_n", n=f"{truck.capacity_kg:.0f}"))
            if truck.name:
                details.append(t("driver_n", name=truck.name))
            if truck.phone:
                details.append(f"📞 {truck.phone}")
            st.write(" · ".join(details))
    else:
        st.error(t("no_suitable"))

    # ---------------- all trucks -----------------------------------
    st.subheader(t("all_trucks"))

    table = match_table(matches, result["drivers"], shipment.crop)
    st.dataframe(table, width="stretch", hide_index=True)
    st.download_button(
        t("download_csv"),
        # utf-8-sig so Excel shows Urdu text correctly
        table.to_csv(index=False).encode("utf-8-sig"),
        file_name="freshroute_matches.csv",
        mime="text/csv",
    )

    # ---------------- summary report -------------------------------
    st.subheader(t("summary_header"))

    if not groq_configured():
        st.info(t("summary_unavailable"))
    elif st.button(t("write_summary"), key="gen_report"):
        try:
            with st.spinner(t("writing_summary")):
                text = generate_ai_report(shipment, analysis, matches, weather, language)
            st.session_state.report = {"text": text, "language": language}
        except Exception as exc:
            st.error(t("summary_fail", err=exc))

    report = st.session_state.report
    if report:
        st.markdown(report["text"])
        st.download_button(
            t("download_summary"),
            report["text"].encode("utf-8"),
            file_name="freshroute_summary.md",
            mime="text/markdown",
        )

    # ---------------- map ------------------------------------------
    st.subheader(t("map_header"))
    render_map(result, best)


# =========================================================
# HEADER
# =========================================================

st.markdown(
    f"""
<div class="fr-hero">
  <h1>{t("hero_title")}</h1>
  <p>{t("hero_sub")}</p>
</div>
""",
    unsafe_allow_html=True,
)

hint_col, lang_col = st.columns([3, 1], vertical_alignment="center")
hint_col.caption(t("hint_voice"))
language = lang_col.selectbox(
    t("language"),
    list(LANGUAGE_CODES.keys()),
    key="language",
    format_func=LANGUAGE_LABELS.get,
    help=t("language_help"),
)

home_tab, farmer_tab, driver_tab, assistant_tab, about_tab = st.tabs(
    [
        t("tab_home"),
        t("tab_farmers"),
        t("tab_drivers"),
        t("tab_assistant"),
        t("tab_about"),
    ]
)


# =========================================================
# HOME
# =========================================================

with home_tab:
    st.header(t("how_works"))

    steps = [
        ("🌾", t("step1_t"), t("step1_d")),
        ("🚚", t("step2_t"), t("step2_d")),
        ("✅", t("step3_t"), t("step3_d")),
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
    s1.metric(t("s_trucks"), len(fleet_now))
    s2.metric(
        t("s_fridge"),
        int((fleet_now["vehicle_type"] == "refrigerated").sum()),
    )
    s3.metric(t("s_crops"), len(CROPS))

    st.write("")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader(t("for_farmers"))
            st.write(t("for_farmers_d"))
    with right:
        with st.container(border=True):
            st.subheader(t("for_drivers"))
            st.write(t("for_drivers_d"))


# =========================================================
# FARMERS
# =========================================================

with farmer_tab:
    st.header(t("farmer_header"))
    st.write(t("farmer_intro"))

    voice_box(
        title=t("farmer_voice_title"),
        hint=t("farmer_voice_hint"),
        audio_key="voice_audio",
        text_key="transcript_text",
        msg_key="voice_msg",
        fill_callback=fill_shipment_callback,
    )

    with st.container(border=True):
        st.subheader(t("your_produce"))
        p1, p2 = st.columns(2)

        with p1:
            st.text_input(t("farmer_id"), key="farmer_id")
            st.selectbox(t("crop"), CROPS, key="crop", format_func=crop_label)
            st.number_input(t("quantity"), min_value=1.0, step=50.0, key="quantity")

        with p2:
            st.number_input(
                t("harvest_age"), min_value=0.0, step=1.0, key="harvest_age"
            )
            st.slider(
                t("condition"),
                min_value=0.1,
                max_value=1.0,
                step=0.05,
                key="condition",
                help=t("condition_help"),
            )

    with st.container(border=True):
        st.subheader(t("pickup_delivery"))
        l1, l2 = st.columns(2)
        l1.text_input(t("pickup_loc"), key="origin_name")
        l2.text_input(t("delivery_loc"), key="destination_name")

    with st.expander(t("advanced")):
        st.number_input(
            t("fallback_temp"),
            min_value=-10.0,
            max_value=60.0,
            step=0.5,
            key="fallback_temp",
        )

    if st.button(t("find_trucks"), type="primary", width="stretch"):
        problems = validate_inputs()

        if problems:
            for problem in problems:
                st.error(problem)
        else:
            try:
                with st.spinner(t("looking")):
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
    st.header(t("driver_header"))
    st.write(t("driver_intro"))

    voice_box(
        title=t("driver_voice_title"),
        hint=t("driver_voice_hint"),
        audio_key="driver_voice_audio",
        text_key="driver_transcript_text",
        msg_key="driver_voice_msg",
        fill_callback=fill_vehicle_callback,
    )

    with st.container(border=True):
        st.subheader(t("you_and_truck"))
        d1, d2 = st.columns(2)

        with d1:
            st.text_input(t("your_name"), key="drv_name")
            st.text_input(t("your_phone"), key="drv_phone")
            st.text_input(t("truck_id"), key="drv_id")

        with d2:
            st.selectbox(
                t("vehicle_type"),
                list(VEHICLE_TYPES),
                key="drv_vehicle",
                format_func=vehicle_label,
            )
            st.number_input(
                t("free_capacity"), min_value=1.0, step=100.0, key="drv_capacity"
            )
            st.number_input(
                t("free_in"),
                min_value=0.0,
                step=0.5,
                key="drv_available",
            )

    with st.container(border=True):
        st.subheader(t("your_route"))
        r1, r2 = st.columns(2)
        r1.text_input(t("truck_now"), key="drv_location")
        r2.text_input(t("truck_returning"), key="drv_destination")

    st.button(
        t("register_truck"),
        type="primary",
        width="stretch",
        on_click=register_driver_callback,
    )

    if st.session_state.driver_msg:
        show_message(st.session_state.driver_msg)

    # ---------------- registered trucks ----------------------------
    st.divider()
    st.subheader(t("registered_trucks"))

    overview = st.session_state.drivers.copy()
    overview["vehicle_type"] = overview["vehicle_type"].map(
        lambda v: vehicle_label(str(v).lower())
    )
    overview = overview.rename(
        columns={
            "driver_id": t("ov_truck"),
            "driver_name": t("ov_driver"),
            "phone": t("ov_phone"),
            "vehicle_type": t("ov_vehicle"),
            "capacity_kg": t("ov_capacity"),
            "available_in_hours": t("ov_free"),
            "current_location": t("ov_from"),
            "destination": t("ov_to"),
        }
    ).drop(columns=["reliability"])
    st.dataframe(overview, width="stretch", hide_index=True)

    with st.expander(t("edit_trucks")):
        edited = st.data_editor(
            st.session_state.drivers,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            key=f"fleet_editor_{st.session_state.fleet_version}",
            column_config={
                "driver_id": st.column_config.TextColumn(
                    t("ed_truck_id"), required=True
                ),
                "driver_name": st.column_config.TextColumn(t("ed_driver")),
                "phone": st.column_config.TextColumn(t("ed_phone")),
                "vehicle_type": st.column_config.SelectboxColumn(
                    t("ed_vehicle"), options=list(VEHICLE_TYPES), required=True
                ),
                "capacity_kg": st.column_config.NumberColumn(
                    t("ed_capacity"), min_value=1, step=100, required=True
                ),
                "available_in_hours": st.column_config.NumberColumn(
                    t("ed_free"), min_value=0, step=0.5, required=True
                ),
                "current_location": st.column_config.TextColumn(
                    t("ed_current"), required=True
                ),
                "destination": st.column_config.TextColumn(
                    t("ed_returning"), required=True
                ),
                "reliability": st.column_config.NumberColumn(
                    t("ed_rating"),
                    min_value=0.0,
                    max_value=1.0,
                    step=0.05,
                    required=True,
                ),
            },
        )

        save_col, reset_col = st.columns(2)

        if save_col.button(t("save_changes"), type="primary", width="stretch"):
            cleaned, fleet_errors = clean_fleet(edited)
            if fleet_errors:
                for error in fleet_errors:
                    st.error(error)
            elif cleaned.empty:
                st.error(t("keep_one"))
            else:
                set_fleet(cleaned)
                st.success(t("changes_saved"))

        if reset_col.button(t("restore_sample"), width="stretch"):
            set_fleet(default_fleet())
            st.rerun()

    st.caption(
        t(
            "rules_caption",
            km=f"{MAX_DETOUR_KM:.0f}",
            h=f"{MIN_REMAINING_SHELF_LIFE_HOURS:.0f}",
        )
    )


# =========================================================
# ASSISTANT
# =========================================================

with assistant_tab:
    st.header(t("assistant_header"))

    result = st.session_state.result

    if result is None:
        st.info(t("assistant_need_result"))
    elif not groq_configured():
        st.info(t("assistant_unavailable"))
    else:
        shipment = result["shipment"]
        st.write(
            t(
                "current_shipment",
                crop=crop_label(shipment.crop),
                qty=f"{shipment.quantity_kg:.0f}",
            )
        )
        st.caption(t("assistant_try"))

        if st.button(t("clear_chat")):
            st.session_state.chat = []

        for message in st.session_state.chat:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        question = st.chat_input(t("chat_input"))

        if question and question.strip():
            history = list(st.session_state.chat)
            st.session_state.chat.append({"role": "user", "content": question})

            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                try:
                    with st.spinner(t("thinking")):
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
                    st.error(t("answer_fail", err=exc))


# =========================================================
# ABOUT
# =========================================================

with about_tab:
    st.header(t("about_header"))
    st.markdown(t("about_md"))
