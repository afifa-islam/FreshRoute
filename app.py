import pandas as pd
import streamlit as st

from core import (
    Driver,
    Location,
    Shipment,
    analyze_shipment,
    rank_matches,
)

from services import (
    geocode_location,
    get_current_weather,
    get_route,
    transcribe_audio,
    generate_ai_report,
    ask_freshroute_ai,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="FreshRoute",
    page_icon="🚚",
    layout="wide",
)


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_DRIVERS = [
    {
        "driver_id": "TRUCK-001",
        "vehicle_type": "covered",
        "capacity_kg": 5000,
        "available_in_hours": 0.0,
        "current_location": "Bahawalpur",
        "destination": "Multan",
        "refrigerated": False,
        "reliability": 0.90,
    },
    {
        "driver_id": "TRUCK-002",
        "vehicle_type": "refrigerated",
        "capacity_kg": 3000,
        "available_in_hours": 1.0,
        "current_location": "Rahim Yar Khan",
        "destination": "Multan",
        "refrigerated": True,
        "reliability": 0.95,
    },
    {
        "driver_id": "TRUCK-003",
        "vehicle_type": "open",
        "capacity_kg": 7000,
        "available_in_hours": 2.0,
        "current_location": "Lodhran",
        "destination": "Bahawalpur",
        "refrigerated": False,
        "reliability": 0.80,
    },
]


if "fleet_df" not in st.session_state:

    st.session_state.fleet_df = pd.DataFrame(
        DEFAULT_DRIVERS
    )


if "shipment" not in st.session_state:
    st.session_state.shipment = None


if "analysis" not in st.session_state:
    st.session_state.analysis = None


if "matches" not in st.session_state:
    st.session_state.matches = []


if "weather" not in st.session_state:
    st.session_state.weather = None


if "origin_coords" not in st.session_state:
    st.session_state.origin_coords = None


if "destination_coords" not in st.session_state:
    st.session_state.destination_coords = None


if "driver_coords" not in st.session_state:
    st.session_state.driver_coords = {}


if "ai_report" not in st.session_state:
    st.session_state.ai_report = None


# ============================================================
# HELPER: CREATE DRIVER OBJECTS
# ============================================================

def get_drivers_from_session():

    drivers = []

    df = st.session_state.fleet_df

    for _, row in df.iterrows():

        try:

            driver = Driver(
                driver_id=str(row["driver_id"]),
                vehicle_type=str(row["vehicle_type"]),
                capacity_kg=float(row["capacity_kg"]),
                available_in_hours=float(
                    row["available_in_hours"]
                ),
                current_location=str(
                    row["current_location"]
                ),
                destination=str(
                    row["destination"]
                ),
                refrigerated=bool(
                    row["refrigerated"]
                ),
                reliability=float(
                    row["reliability"]
                ),
            )

            drivers.append(driver)

        except Exception:
            continue

    return drivers


# ============================================================
# HELPER: DISPLAY LOCATION MAP
# ============================================================

def display_map():

    shipment = st.session_state.shipment

    if shipment is None:
        return

    origin = st.session_state.origin_coords
    destination = st.session_state.destination_coords

    if origin is None or destination is None:
        return

    rows = [
        {
            "name": "Farm",
            "latitude": origin[0],
            "longitude": origin[1],
        },
        {
            "name": "Buyer",
            "latitude": destination[0],
            "longitude": destination[1],
        },
    ]

    # Add available driver locations.
    driver_coords = st.session_state.driver_coords

    for driver_id, coords in driver_coords.items():

        if coords is not None:

            rows.append(
                {
                    "name": driver_id,
                    "latitude": coords[0],
                    "longitude": coords[1],
                }
            )

    map_df = pd.DataFrame(rows)

    st.map(
        map_df,
        latitude="latitude",
        longitude="longitude",
    )


# ============================================================
# HEADER
# ============================================================

st.title("🚚 FreshRoute")

st.markdown(
    """
### Agricultural Backhaul Matching Platform

FreshRoute helps connect **farmers with available return trucks**
so agricultural produce can reach buyers faster while reducing
empty backhaul capacity and potential food waste.
"""
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("FreshRoute")

    language = st.selectbox(
        "Interface Language",
        [
            "English",
            "Urdu",
            "Roman Urdu",
        ],
    )

    st.divider()

    st.caption(
        "AI: Groq + OpenAI GPT-OSS 120B"
    )

    st.caption(
        "Weather: Open-Meteo"
    )

    st.caption(
        "Routing: OSRM"
    )

    st.caption(
        "Frontend: Streamlit"
    )


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📦 Shipment Planner",
        "🚛 Driver Fleet",
        "🤖 AI Assistant",
        "ℹ️ About",
    ]
)


# ============================================================
# TAB 1 — SHIPMENT PLANNER
# ============================================================

with tab1:

    st.header("Shipment Planner")

    col1, col2 = st.columns(2)

    with col1:

        farmer_id = st.text_input(
            "Farmer ID",
            value="FARMER-001",
        )

        crop = st.selectbox(
            "Crop",
            [
                "Tomato",
                "Mango",
                "Banana",
                "Strawberry",
                "Spinach",
                "Potato",
                "Onion",
            ],
        )

        quantity_kg = st.number_input(
            "Quantity (kg)",
            min_value=1.0,
            value=1000.0,
            step=50.0,
        )

        harvest_age_hours = st.number_input(
            "Hours Since Harvest",
            min_value=0.0,
            value=4.0,
            step=1.0,
        )

        condition = st.selectbox(
            "Produce Condition",
            [
                "Excellent",
                "Good",
                "Fair",
                "Poor",
            ],
        )

    with col2:

        pickup = st.text_input(
            "Pickup Location",
            value="Bahawalpur",
        )

        destination = st.text_input(
            "Buyer / Destination",
            value="Multan",
        )

        fallback_temperature = st.number_input(
            "Fallback Temperature °C",
            value=30.0,
            step=1.0,
            help=(
                "Used if the weather API cannot be reached."
            ),
        )

        st.write("")

        st.markdown("#### Optional Voice Input")

        audio_value = st.audio_input(
            "Describe shipment using your voice",
        )

        if audio_value is not None:

            if st.button(
                "Transcribe Voice Input",
                use_container_width=True,
            ):

                try:

                    with st.spinner(
                        "Transcribing..."
                    ):

                        voice_text = transcribe_audio(
                            audio_value.getvalue(),
                            language=language,
                        )

                    st.success(
                        "Transcription completed."
                    )

                    st.text_area(
                        "Transcribed text",
                        value=voice_text,
                        height=100,
                    )

                except Exception as exc:

                    st.error(
                        f"Voice transcription failed: {exc}"
                    )

    st.divider()

    analyze_button = st.button(
        "🔍 Analyze Shipment & Find Trucks",
        type="primary",
        use_container_width=True,
    )


    # ========================================================
    # ANALYZE SHIPMENT
    # ========================================================

    if analyze_button:

        if not pickup.strip():
            st.error(
                "Please enter a pickup location."
            )
            st.stop()

        if not destination.strip():
            st.error(
                "Please enter a destination."
            )
            st.stop()

        with st.spinner(
            "Finding locations and analyzing shipment..."
        ):

            # -----------------------------------------------
            # GEOCODE FARM
            # -----------------------------------------------

            origin_coords = geocode_location(
                pickup
            )

            if origin_coords is None:

                st.error(
                    f"Could not locate pickup location: "
                    f"{pickup}"
                )

                st.stop()

            # -----------------------------------------------
            # GEOCODE BUYER
            # -----------------------------------------------

            destination_coords = geocode_location(
                destination
            )

            if destination_coords is None:

                st.error(
                    f"Could not locate destination: "
                    f"{destination}"
                )

                st.stop()

            st.session_state.origin_coords = (
                origin_coords
            )

            st.session_state.destination_coords = (
                destination_coords
            )

            # -----------------------------------------------
            # WEATHER
            # -----------------------------------------------

            weather = get_current_weather(
                origin_coords[0],
                origin_coords[1],
            )

            if weather.get("available"):

                temperature = weather.get(
                    "temperature"
                )

            else:

                temperature = fallback_temperature

                weather = {
                    **weather,
                    "temperature": temperature,
                    "using_fallback": True,
                }

            st.session_state.weather = weather

            # -----------------------------------------------
            # SHIPMENT
            # -----------------------------------------------

            shipment = Shipment(
                farmer_id=farmer_id,
                crop=crop,
                quantity_kg=quantity_kg,
                harvest_age_hours=harvest_age_hours,
                condition=condition,
                pickup=Location(
                    name=pickup,
                    latitude=origin_coords[0],
                    longitude=origin_coords[1],
                ),
                destination=Location(
                    name=destination,
                    latitude=destination_coords[0],
                    longitude=destination_coords[1],
                ),
            )

            # -----------------------------------------------
            # ANALYZE
            # -----------------------------------------------

            analysis = analyze_shipment(
                shipment,
                temperature,
            )

            # -----------------------------------------------
            # GET DRIVERS FROM SESSION STATE
            # -----------------------------------------------

            drivers = get_drivers_from_session()

            # -----------------------------------------------
            # GEOCODE DRIVER LOCATIONS
            # -----------------------------------------------

            driver_coords = {}

            for driver in drivers:

                coords = geocode_location(
                    driver.current_location
                )

                driver_coords[
                    driver.driver_id
                ] = coords

            st.session_state.driver_coords = (
                driver_coords
            )

            # -----------------------------------------------
            # ROUTE EACH DRIVER
            # -----------------------------------------------

            driver_routes = {}

            for driver in drivers:

                coords = driver_coords.get(
                    driver.driver_id
                )

                if coords is None:
                    continue

                route = get_route(
                    coords[0],
                    coords[1],
                    destination_coords[0],
                    destination_coords[1],
                )

                driver_routes[
                    driver.driver_id
                ] = route

            # -----------------------------------------------
            # MATCHING
            # -----------------------------------------------

            matches = rank_matches(
                shipment=shipment,
                analysis=analysis,
                drivers=drivers,
                driver_routes=driver_routes,
            )

            # -----------------------------------------------
            # SAVE EVERYTHING
            # -----------------------------------------------

            st.session_state.shipment = shipment
            st.session_state.analysis = analysis
            st.session_state.matches = matches
            st.session_state.ai_report = None

        st.success(
            "Shipment analyzed successfully."
        )


    # ========================================================
    # RESULTS
    # ========================================================

    if st.session_state.shipment is not None:

        shipment = st.session_state.shipment
        analysis = st.session_state.analysis
        matches = st.session_state.matches
        weather = st.session_state.weather

        st.divider()

        st.header("Shipment Results")

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Crop",
                shipment.crop,
            )

        with col2:
            st.metric(
                "Quantity",
                f"{shipment.quantity_kg:,.0f} kg",
            )

        with col3:
            st.metric(
                "Urgency",
                analysis.urgency,
            )

        with col4:
            st.metric(
                "Risk",
                analysis.risk_level,
            )

        # ----------------------------------------------------
        # WEATHER
        # ----------------------------------------------------

        st.subheader("Current Conditions")

        if weather:

            col1, col2, col3, col4 = st.columns(4)

            with col1:

                temperature = weather.get(
                    "temperature"
                )

                if temperature is not None:
                    st.metric(
                        "Temperature",
                        f"{temperature:.1f} °C",
                    )

            with col2:

                humidity = weather.get(
                    "humidity"
                )

                if humidity is not None:
                    st.metric(
                        "Humidity",
                        f"{humidity:.0f}%",
                    )

            with col3:

                precipitation = weather.get(
                    "precipitation"
                )

                if precipitation is not None:
                    st.metric(
                        "Precipitation",
                        f"{precipitation:.1f} mm",
                    )

            with col4:

                wind = weather.get(
                    "wind_speed"
                )

                if wind is not None:
                    st.metric(
                        "Wind",
                        f"{wind:.1f} km/h",
                    )

            if weather.get("using_fallback"):

                st.warning(
                    "Weather API was unavailable. "
                    "The manually entered temperature "
                    "was used for the analysis."
                )

        # ----------------------------------------------------
        # SHELF LIFE
        # ----------------------------------------------------

        st.subheader(
            "Shelf-Life Assessment"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "Estimated Remaining Shelf Life",
                f"{analysis.estimated_remaining_shelf_life_hours:.1f} h",
            )

        with col2:

            st.metric(
                "Heat Factor",
                f"{analysis.heat_factor:.2f}",
            )

        with col3:

            st.metric(
                "Condition Factor",
                f"{analysis.condition_factor:.2f}",
            )

        st.info(
            analysis.reason
        )

        st.caption(
            "Note: This is a logistics heuristic, "
            "not a laboratory food-safety assessment."
        )

        # ----------------------------------------------------
        # MATCHES
        # ----------------------------------------------------

        st.subheader(
            "Available Truck Matches"
        )

        if matches:

            match_rows = []

            for match in matches:

                match_rows.append(
                    {
                        "Truck": match.driver.driver_id,
                        "Vehicle": match.driver.vehicle_type,
                        "Capacity (kg)": (
                            match.driver.capacity_kg
                        ),
                        "Refrigerated": (
                            "Yes"
                            if match.driver.refrigerated
                            else "No"
                        ),
                        "Distance (km)": round(
                            match.route.distance_km,
                            1,
                        ),
                        "Travel Time (h)": round(
                            match.route.duration_hours,
                            1,
                        ),
                        "Detour (km)": round(
                            match.detour_km,
                            1,
                        ),
                        "Score": round(
                            match.score,
                            3,
                        ),
                        "Status": (
                            "Recommended"
                            if match.valid
                            else "Rejected"
                        ),
                    }
                )

            match_df = pd.DataFrame(
                match_rows
            )

            st.dataframe(
                match_df,
                use_container_width=True,
                hide_index=True,
            )

            # ------------------------------------------------
            # BEST MATCH
            # ------------------------------------------------

            valid_matches = [
                match
                for match in matches
                if match.valid
            ]

            if valid_matches:

                best_match = valid_matches[0]

                st.success(
                    f"Recommended Truck: "
                    f"{best_match.driver.driver_id}"
                )

                col1, col2, col3, col4 = st.columns(4)

                with col1:

                    st.metric(
                        "Truck",
                        best_match.driver.driver_id,
                    )

                with col2:

                    st.metric(
                        "Match Score",
                        f"{best_match.score:.3f}",
                    )

                with col3:

                    st.metric(
                        "Detour",
                        f"{best_match.detour_km:.1f} km",
                    )

                with col4:

                    st.metric(
                        "Travel Time",
                        f"{best_match.route.duration_hours:.1f} h",
                    )

                if best_match.reasons:

                    st.markdown(
                        "**Why this truck was selected:**"
                    )

                    for reason in best_match.reasons:
                        st.write(
                            f"- {reason}"
                        )

            else:

                st.warning(
                    "No valid truck match was found."
                )

            # ------------------------------------------------
            # REJECTION REASONS
            # ------------------------------------------------

            rejected = [
                match
                for match in matches
                if not match.valid
            ]

            if rejected:

                with st.expander(
                    "View rejected trucks and reasons"
                ):

                    for match in rejected:

                        st.markdown(
                            f"**{match.driver.driver_id}**"
                        )

                        if match.reasons:

                            for reason in match.reasons:
                                st.write(
                                    f"- {reason}"
                                )

                        else:

                            st.write(
                                "- Did not satisfy "
                                "matching constraints."
                            )

            # ------------------------------------------------
            # AI REPORT
            # ------------------------------------------------

            st.subheader(
                "AI Shipment Report"
            )

            if st.button(
                "🤖 Generate AI Shipment Report",
                use_container_width=True,
            ):

                try:

                    with st.spinner(
                        "Generating AI shipment report..."
                    ):

                        report = generate_ai_report(
                            shipment,
                            analysis,
                            matches,
                            weather,
                        )

                    st.session_state.ai_report = (
                        report
                    )

                except Exception as exc:

                    st.error(
                        f"AI report failed: {exc}"
                    )

            if st.session_state.ai_report:

                st.markdown(
                    st.session_state.ai_report
                )

        else:

            st.warning(
                "No truck data is currently available."
            )

        # ----------------------------------------------------
        # MAP
        # ----------------------------------------------------

        st.subheader(
            "Shipment Locations"
        )

        display_map()


# ============================================================
# TAB 2 — DRIVER FLEET
# ============================================================

with tab2:

    st.header("Driver Fleet")

    st.write(
        "Add or edit available trucks used by "
        "the FreshRoute matching engine."
    )

    edited_fleet = st.data_editor(
        st.session_state.fleet_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "driver_id": st.column_config.TextColumn(
                "Truck ID",
                required=True,
            ),
            "vehicle_type": st.column_config.SelectboxColumn(
                "Vehicle Type",
                options=[
                    "open",
                    "covered",
                    "refrigerated",
                ],
            ),
            "capacity_kg": st.column_config.NumberColumn(
                "Capacity (kg)",
                min_value=0,
            ),
            "available_in_hours": st.column_config.NumberColumn(
                "Available In (hours)",
                min_value=0,
            ),
            "current_location": st.column_config.TextColumn(
                "Current Location"
            ),
            "destination": st.column_config.TextColumn(
                "Truck Destination"
            ),
            "refrigerated": st.column_config.CheckboxColumn(
                "Refrigerated"
            ),
            "reliability": st.column_config.NumberColumn(
                "Reliability",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
            ),
        },
    )

    if st.button(
        "💾 Save Fleet",
        type="primary",
        use_container_width=True,
    ):

        st.session_state.fleet_df = (
            edited_fleet.copy()
        )

        # Clear old matching results because the fleet changed.
        st.session_state.matches = []
        st.session_state.ai_report = None

        st.success(
            "Fleet saved for this session."
        )

    st.info(
        "Current fleet data is stored only in the "
        "Streamlit session. A database can be added "
        "in a later version."
    )


# ============================================================
# TAB 3 — AI ASSISTANT
# ============================================================

with tab3:

    st.header(
        "🤖 FreshRoute AI Assistant"
    )

    if st.session_state.shipment is None:

        st.info(
            "Analyze a shipment first. "
            "The AI Assistant uses the current "
            "FreshRoute shipment and matching data."
        )

    else:

        question = st.text_area(
            "Ask about the current shipment",
            placeholder=(
                "Example: Why was this truck recommended?"
            ),
            height=120,
        )

        if st.button(
            "Ask FreshRoute AI",
            type="primary",
            use_container_width=True,
        ):

            if not question.strip():

                st.warning(
                    "Please enter a question."
                )

            else:

                try:

                    with st.spinner(
                        "Thinking..."
                    ):

                        answer = ask_freshroute_ai(
                            question,
                            st.session_state.shipment,
                            st.session_state.analysis,
                            st.session_state.matches,
                            st.session_state.weather,
                        )

                    st.markdown(answer)

                except Exception as exc:

                    st.error(
                        f"AI Assistant failed: {exc}"
                    )


# ============================================================
# TAB 4 — ABOUT
# ============================================================

with tab4:

    st.header(
        "About FreshRoute"
    )

    st.markdown(
        """
### Problem

Farmers may struggle to find affordable and timely
transport for harvested produce. At the same time,
trucks returning from deliveries may travel with unused
capacity.

### FreshRoute Solution

FreshRoute attempts to match agricultural shipments with
available backhaul trucks based on:

- Produce type
- Quantity
- Estimated remaining shelf life
- Truck capacity
- Refrigeration
- Route distance
- Detour
- Truck availability
- Reliability

### AI Enhancement

The deterministic algorithm makes the actual matching
decision.

The AI layer uses **OpenAI GPT-OSS 120B through Groq**
to explain the result, summarize risks, and answer
questions about the shipment.

### External Services

- Open-Meteo — geocoding and weather
- OSRM — road routing
- Groq — GPT-OSS and Whisper

### Important Limitation

FreshRoute's shelf-life calculation is a prototype
logistics heuristic. It should not be treated as a
certified food-safety or quality-control system.
"""
    )
