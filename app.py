"""FreshRoute: AI-powered agricultural backhaul matching (Streamlit app)."""

from __future__ import annotations

import math
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

st.set_page_config(page_title="FreshRoute", page_icon="🚚", layout="wide")


# =========================================================
# CONSTANTS
# =========================================================

CROPS = list(CROP_PROFILES.keys())

LANGUAGE_CODES = {"English": "en", "Urdu": "ur", "Roman Urdu": None}

FLEET_COLUMNS = [
    "driver_id",
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
        "vehicle_type": "covered",
        "capacity_kg": 5000.0,
        "available_in_hours": 0.0,
        "current_location": "Bahawalpur, Pakistan",
        "destination": "Multan, Pakistan",
        "reliability": 0.90,
    },
    {
        "driver_id": "TRUCK-002",
        "vehicle_type": "refrigerated",
        "capacity_kg": 3000.0,
        "available_in_hours": 1.0,
        "current_location": "Rahim Yar Khan, Pakistan",
        "destination": "Multan, Pakistan",
        "reliability": 0.95,
    },
    {
        "driver_id": "TRUCK-003",
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

URGENCY_ICONS = {"GREEN": "🟢", "YELLOW": "🟡", "ORANGE": "🟠", "RED": "🔴"}


class AnalysisError(Exception):
    """A problem the user can understand and fix."""


# =========================================================
# SESSION STATE
# =========================================================

def default_fleet() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_FLEET, columns=FLEET_COLUMNS)


def init_state() -> None:
    for key, value in FORM_DEFAULTS.items():
        st.session_state.setdefault(key, value)

    if "drivers" not in st.session_state:
        st.session_state.drivers = default_fleet()

    st.session_state.setdefault("result", None)
    st.session_state.setdefault("report", None)
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("voice_msg", None)
    st.session_state.setdefault("transcript_text", "")


init_state()


# =========================================================
# FLEET VALIDATION
# =========================================================

def clean_fleet(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Normalise the fleet table and report problems."""
    errors: List[str] = []
    df = df.copy()

    for column in FLEET_COLUMNS:
        if column not in df.columns:
            df[column] = None
    df = df[FLEET_COLUMNS]

    for column in ("driver_id", "vehicle_type", "current_location", "destination"):
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
            errors.append(f"{label}: 'Available in hours' must be 0 or more.")
        if pd.isna(row["reliability"]) or not 0 <= row["reliability"] <= 1:
            errors.append(f"{label}: reliability must be between 0 and 1.")
        if not row["current_location"]:
            errors.append(f"{label}: current location is required.")
        if not row["destination"]:
            errors.append(f"{label}: returning destination is required.")

    ids = df.loc[df["driver_id"] != "", "driver_id"]
    for duplicate in ids[ids.duplicated()].unique():
        errors.append(f"Truck ID '{duplicate}' is used more than once.")

    return df, errors


def build_drivers(df: pd.DataFrame) -> Tuple[List[Driver], List[str]]:
    """Geocode each truck's locations and build Driver objects."""
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
                )
            )
        except Exception as exc:
            warnings.append(f"{row['driver_id']} was skipped: {exc}")

    return drivers, warnings


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
    fleet = st.session_state.drivers.to_json()
    return f"{sorted(inputs.items())}|{fleet}"


def validate_inputs() -> List[str]:
    errors = []
    if not st.session_state.origin_name.strip():
        errors.append("Enter a farm / pickup location.")
    if not st.session_state.destination_name.strip():
        errors.append("Enter a buyer / destination.")
    if len(st.session_state.drivers) == 0:
        errors.append("The truck fleet is empty. Add trucks in the Driver Fleet tab.")
    return errors


def run_analysis() -> Dict[str, Any]:
    inputs = form_inputs()

    # --- locations -------------------------------------------------
    try:
        origin_data = geocode_location(inputs["origin_name"])
        destination_data = geocode_location(inputs["destination_name"])
    except Exception as exc:
        raise AnalysisError(f"Location lookup failed: {exc}") from exc

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

    # --- weather ---------------------------------------------------
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

    # --- trucks ----------------------------------------------------
    fleet, fleet_errors = clean_fleet(st.session_state.drivers)
    if fleet_errors:
        raise AnalysisError(
            "Fix the Driver Fleet table first: " + " ".join(fleet_errors)
        )

    drivers, fleet_warnings = build_drivers(fleet)
    if not drivers:
        raise AnalysisError(
            "No valid trucks are available. " + " ".join(fleet_warnings)
        )

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
# VOICE CALLBACKS
# =========================================================

def transcribe_callback() -> None:
    st.session_state.voice_msg = None
    audio = st.session_state.get("voice_audio")

    if audio is None:
        st.session_state.voice_msg = ("warning", "Record something first.")
        return

    language = LANGUAGE_CODES.get(st.session_state.get("language", "English"))

    try:
        st.session_state.transcript_text = transcribe_audio(audio.getvalue(), language)
        st.session_state.voice_msg = (
            "success",
            "Transcribed. Check the text, then fill the form.",
        )
    except Exception as exc:
        st.session_state.voice_msg = ("error", f"Voice transcription failed: {exc}")


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def fill_form_callback() -> None:
    st.session_state.voice_msg = None
    text = st.session_state.get("transcript_text", "").strip()

    if not text:
        st.session_state.voice_msg = ("warning", "There is no text to read.")
        return

    try:
        data = extract_shipment_from_text(text, CROPS)
    except Exception as exc:
        st.session_state.voice_msg = ("error", f"Could not read the text: {exc}")
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
        applied.append("harvest age")

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
            "Updated: " + ", ".join(applied) + ". Please review before analyzing.",
        )
    else:
        st.session_state.voice_msg = (
            "warning",
            "No shipment details were found in the text.",
        )


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
        "Orange: truck to farm. Green: farm to buyer. Grey: buyer to the "
        "truck's own destination. Routes come from OSRM; straight lines "
        "mean the routing service was unreachable."
    )


# =========================================================
# RESULTS
# =========================================================

def match_table(matches) -> pd.DataFrame:
    rows = []
    for m in matches:
        rows.append(
            {
                "Truck": m.driver_id,
                "Status": "MATCH" if m.valid else "REJECTED",
                "Score": round(m.score, 3),
                "Detour (km)": round(m.detour_km, 1),
                "To farm (km)": round(m.pickup_distance_km, 1),
                "Farm to buyer (km)": round(m.delivery_distance_km, 1),
                "Time to delivery (h)": round(m.time_to_delivery_hours, 2),
                "Shelf life left (h)": round(max(0.0, m.remaining_at_delivery_hours), 1),
                "Distances": "Estimated" if m.used_fallback else "OSRM",
                "Reason": m.reason,
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

    if result["signature"] != make_signature():
        st.warning(
            "The inputs or fleet changed after this analysis. "
            "Press **Analyze & Find Returning Trucks** to refresh the results."
        )

    if result["weather_failed"]:
        st.warning(
            "Weather service unavailable. The fallback temperature was used."
        )
    for message in result["fleet_warnings"]:
        st.warning(message)
    if any(m.used_fallback for m in matches):
        st.warning(
            "Routing service unreachable for some legs. Distances marked "
            "'Estimated' are straight-line approximations."
        )

    st.header("Shipment Analysis")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Temperature", f"{analysis.temperature_c:.1f} °C")
    c2.metric("Remaining shelf life", f"{analysis.remaining_shelf_life_hours:.1f} h")
    c3.metric("Urgency", f"{URGENCY_ICONS.get(analysis.urgency, '')} {analysis.urgency}")
    c4.metric("Valid trucks", len(valid))

    with st.expander("Shelf-life calculation details"):
        st.write(f"Base shelf life: {analysis.base_shelf_life_hours:.1f} hours")
        st.write(f"Effective elapsed time: {analysis.effective_elapsed_hours:.1f} hours")
        st.write(f"Heat factor: {analysis.heat_factor:.2f}")
        st.write(f"Condition factor: {analysis.condition_factor:.2f}")
        st.write(f"Weather source: {weather.get('source', 'unknown')}")
        st.caption(
            "Heuristic estimates for the prototype, not validated "
            "food-safety predictions. Refrigerated trucks are assumed to "
            "hold the produce at its ideal temperature while loaded."
        )

    # ---------------- matches --------------------------------------
    st.header("Returning Truck Matches")

    table = match_table(matches)
    st.dataframe(table, width="stretch", hide_index=True)
    st.download_button(
        "Download match table (CSV)",
        table.to_csv(index=False).encode("utf-8"),
        file_name="freshroute_matches.csv",
        mime="text/csv",
    )

    best = valid[0] if valid else None

    if best is not None:
        st.header("Recommended Returning Truck")

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Truck", best.driver_id)
        b2.metric("Match score", f"{best.score:.2f}")
        b3.metric("Detour", f"{best.detour_km:.1f} km")
        b4.metric("Shelf life left at delivery", f"{best.remaining_at_delivery_hours:.1f} h")

        st.success("FreshRoute found a valid returning-truck match.")
    else:
        st.error("FreshRoute could not find a valid returning truck.")
        for m in matches:
            if m.rejection_reasons:
                with st.expander(f"{m.driver_id}: rejection reasons"):
                    for reason in m.rejection_reasons:
                        st.write(f"- {reason}")

    # ---------------- AI report ------------------------------------
    st.subheader("AI Shipment Report")

    if not groq_configured():
        st.info("Add GROQ_API_KEY to enable the AI report, assistant and voice input.")
    elif st.button("Generate AI Shipment Report", key="gen_report"):
        try:
            with st.spinner("Generating FreshRoute AI report..."):
                text = generate_ai_report(shipment, analysis, matches, weather, language)
            st.session_state.report = {"text": text, "language": language}
        except Exception as exc:
            st.error(f"AI report failed: {exc}")

    report = st.session_state.report
    if report:
        st.markdown(report["text"])
        st.download_button(
            "Download report (Markdown)",
            report["text"].encode("utf-8"),
            file_name="freshroute_report.md",
            mime="text/markdown",
        )

    # ---------------- map ------------------------------------------
    st.header("Shipment Map")
    render_map(result, best)


# =========================================================
# HEADER AND SIDEBAR
# =========================================================

st.title("FreshRoute")
st.subheader("AI-powered agricultural backhaul matching")
st.write(
    "FreshRoute connects agricultural produce with suitable returning "
    "trucks, considering capacity, route compatibility, detour, "
    "availability, weather and estimated remaining shelf life."
)

with st.sidebar:
    st.header("FreshRoute")

    language = st.selectbox(
        "AI response language",
        list(LANGUAGE_CODES.keys()),
        key="language",
    )

    st.divider()
    st.caption("Routing: OSRM")
    st.caption("Weather and geocoding: Open-Meteo")
    st.caption("LLM: OpenAI GPT-OSS 120B via Groq")
    st.caption("Speech: Whisper Large V3 Turbo via Groq")

    if groq_configured():
        st.success("AI features ready", icon="✅")
    else:
        st.warning("GROQ_API_KEY not set. AI features are off.", icon="⚠️")

    st.divider()
    st.caption("Prototype decision-support system")


# =========================================================
# TABS
# =========================================================

planner_tab, fleet_tab, ai_tab, about_tab = st.tabs(
    ["Shipment Planner", "Driver Fleet", "AI Assistant", "About"]
)


# =========================================================
# SHIPMENT PLANNER
# =========================================================

with planner_tab:
    st.header("Plan a shipment")

    left, right = st.columns(2)

    with left:
        st.text_input("Farmer ID", key="farmer_id")
        st.selectbox("Crop", CROPS, key="crop")
        st.number_input(
            "Produce quantity (kg)", min_value=1.0, step=50.0, key="quantity"
        )
        st.number_input(
            "Hours since harvest", min_value=0.0, step=1.0, key="harvest_age"
        )
        st.slider(
            "Produce condition",
            min_value=0.1,
            max_value=1.0,
            step=0.05,
            key="condition",
        )
        st.caption("1.0 = excellent condition; 0.1 = severely deteriorated.")

    with right:
        st.text_input("Farm / pickup location", key="origin_name")
        st.text_input("Buyer / destination", key="destination_name")
        st.number_input(
            "Fallback temperature °C",
            min_value=-10.0,
            max_value=60.0,
            step=0.5,
            key="fallback_temp",
        )
        st.caption("Used only if the weather API cannot be reached.")

    # ---------------- voice ----------------------------------------
    with st.expander("Voice input (optional)"):
        st.audio_input("Record shipment information", sample_rate=16000, key="voice_audio")

        st.button(
            "Transcribe voice",
            on_click=transcribe_callback,
            disabled=not groq_configured(),
        )

        st.text_area("Transcript (you can edit it)", key="transcript_text", height=100)

        st.button(
            "Fill form from transcript",
            on_click=fill_form_callback,
            disabled=not groq_configured(),
        )

        if st.session_state.voice_msg:
            kind, message = st.session_state.voice_msg
            getattr(st, kind)(message)

    # ---------------- analyze --------------------------------------
    st.divider()

    if st.button(
        "Analyze & Find Returning Trucks",
        type="primary",
        width="stretch",
    ):
        problems = validate_inputs()

        if problems:
            for problem in problems:
                st.error(problem)
        else:
            try:
                with st.spinner(
                    "Analyzing shipment, locating trucks and calculating routes..."
                ):
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
# DRIVER FLEET
# =========================================================

with fleet_tab:
    st.header("Returning Truck Fleet")
    st.write(
        "Add or edit returning trucks here. FreshRoute uses this information "
        "when searching for backhaul matches. Refrigeration is determined by "
        "the vehicle type."
    )

    edited = st.data_editor(
        st.session_state.drivers,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key="fleet_editor",
        column_config={
            "driver_id": st.column_config.TextColumn("Truck ID", required=True),
            "vehicle_type": st.column_config.SelectboxColumn(
                "Vehicle", options=list(VEHICLE_TYPES), required=True
            ),
            "capacity_kg": st.column_config.NumberColumn(
                "Capacity (kg)", min_value=1, step=100, required=True
            ),
            "available_in_hours": st.column_config.NumberColumn(
                "Available in hours", min_value=0, step=0.5, required=True
            ),
            "current_location": st.column_config.TextColumn(
                "Current location", required=True
            ),
            "destination": st.column_config.TextColumn(
                "Returning destination", required=True
            ),
            "reliability": st.column_config.NumberColumn(
                "Reliability (0-1)",
                min_value=0.0,
                max_value=1.0,
                step=0.05,
                required=True,
            ),
        },
    )

    save_col, reset_col = st.columns(2)

    if save_col.button("Save Fleet", type="primary", width="stretch"):
        cleaned, fleet_errors = clean_fleet(edited)
        if fleet_errors:
            for error in fleet_errors:
                st.error(error)
        elif cleaned.empty:
            st.error("Add at least one truck.")
        else:
            st.session_state.drivers = cleaned
            st.success("Truck fleet saved for this session.")

    if reset_col.button("Reset to demo fleet", width="stretch"):
        st.session_state.drivers = default_fleet()
        st.session_state.pop("fleet_editor", None)
        st.rerun()

    st.info(
        f"Maximum allowed detour: **{MAX_DETOUR_KM:.0f} km**. "
        f"Minimum remaining shelf-life buffer at delivery: "
        f"**{MIN_REMAINING_SHELF_LIFE_HOURS:.0f} hours**."
    )


# =========================================================
# AI ASSISTANT
# =========================================================

with ai_tab:
    st.header("FreshRoute AI Assistant")

    result = st.session_state.result

    if result is None:
        st.info("Analyze a shipment first.")
    elif not groq_configured():
        st.info("Add GROQ_API_KEY to enable the AI assistant.")
    else:
        shipment = result["shipment"]
        st.write(
            f"Current shipment: **{shipment.crop.title()}, "
            f"{shipment.quantity_kg:.0f} kg**"
        )
        st.caption(
            "Try: Why was this truck selected? What is the main risk? "
            "What should the farmer do next?"
        )

        if st.button("Clear conversation"):
            st.session_state.chat = []

        for message in st.session_state.chat:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        question = st.chat_input("Ask FreshRoute AI")

        if question and question.strip():
            history = list(st.session_state.chat)
            st.session_state.chat.append({"role": "user", "content": question})

            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                try:
                    with st.spinner("FreshRoute AI is analyzing..."):
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
                    st.error(f"AI request failed: {exc}")


# =========================================================
# ABOUT
# =========================================================

with about_tab:
    st.header("About FreshRoute")

    st.markdown(
        """
## The problem

Agricultural producers may struggle to find timely transportation while
trucks returning from deliveries can have unused capacity. This creates
two inefficiencies:

- Produce can lose value while waiting for transport.
- Returning trucks can travel with unused capacity.

## The FreshRoute solution

FreshRoute connects the two. For every truck it evaluates:

- Vehicle compatibility and capacity
- Truck availability
- The extra distance caused by collecting and delivering the produce and
  then continuing to the truck's own destination (the detour)
- Estimated delivery time
- Shelf life remaining at delivery, based on crop, harvest age, condition,
  weather and whether the truck is refrigerated

## AI enhancement

FreshRoute uses AI for shipment reports, operational recommendations,
buyer-ready summaries, natural-language Q&A, voice-to-text and filling the
form from a spoken description. The AI never overrides the deterministic
matching engine.

## Prototype limitations

- The shelf-life model is heuristic, not a validated food-safety system.
- Locations are geocoded to place centres, so detours are approximate.
- The public OSRM server is meant for prototypes and may rate-limit.
  When it fails, FreshRoute shows straight-line estimates and says so.
- Fleet information is session-based and is not stored permanently.
- This is a decision-support prototype, not a production logistics
  marketplace.
"""
    )
