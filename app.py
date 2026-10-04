import pandas as pd
import streamlit as st

from core import (
    Location,
    Shipment,
    Driver,
    analyze_shipment,
    rank_matches,
    MAX_DETOUR_KM,
)

from services import (
    geocode_location,
    get_current_weather,
    get_route,
    generate_ai_report,
    ask_freshroute_ai,
    transcribe_audio,
)


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="FreshRoute",
    page_icon="🚚",
    layout="wide",
)


# =========================================================
# SESSION STATE
# =========================================================

if "drivers" not in st.session_state:

    st.session_state.drivers = pd.DataFrame(
        [
            {
                "driver_id":
                    "TRUCK-001",

                "vehicle_type":
                    "covered",

                "capacity_kg":
                    5000,

                "available_in_hours":
                    0,

                "current_location":
                    "Bahawalpur, Pakistan",

                "destination":
                    "Multan, Pakistan",

                "refrigerated":
                    False,

                "reliability":
                    0.90,
            },

            {
                "driver_id":
                    "TRUCK-002",

                "vehicle_type":
                    "refrigerated",

                "capacity_kg":
                    3000,

                "available_in_hours":
                    1,

                "current_location":
                    "Rahim Yar Khan, Pakistan",

                "destination":
                    "Multan, Pakistan",

                "refrigerated":
                    True,

                "reliability":
                    0.95,
            },

            {
                "driver_id":
                    "TRUCK-003",

                "vehicle_type":
                    "open",

                "capacity_kg":
                    7000,

                "available_in_hours":
                    2,

                "current_location":
                    "Lodhran, Pakistan",

                "destination":
                    "Bahawalpur, Pakistan",

                "refrigerated":
                    False,

                "reliability":
                    0.80,
            },
        ]
    )


if "shipment" not in st.session_state:
    st.session_state.shipment = None


if "analysis" not in st.session_state:
    st.session_state.analysis = None


if "matches" not in st.session_state:
    st.session_state.matches = []


if "weather" not in st.session_state:
    st.session_state.weather = None


# =========================================================
# HEADER
# =========================================================

st.title("FreshRoute")

st.subheader(
    "AI-powered agricultural backhaul matching"
)

st.write(
    """
FreshRoute connects agricultural produce with
suitable returning trucks while considering
capacity, route compatibility, detour,
availability, weather and estimated remaining
shelf life.
"""
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header("FreshRoute")

    language = st.selectbox(
        "AI response language",
        [
            "English",
            "Urdu",
            "Roman Urdu",
        ],
    )

    st.divider()

    st.caption(
        "Routing: OSRM"
    )

    st.caption(
        "Weather: Open-Meteo"
    )

    st.caption(
        "LLM: OpenAI GPT-OSS 120B via Groq"
    )

    st.caption(
        "Speech: Whisper Large V3 Turbo via Groq"
    )

    st.divider()

    st.caption(
        "Prototype decision-support system"
    )


# =========================================================
# TABS
# =========================================================

planner_tab, fleet_tab, ai_tab, about_tab = st.tabs(
    [
        "Shipment Planner",
        "Driver Fleet",
        "AI Assistant",
        "About",
    ]
)


# =========================================================
# SHIPMENT PLANNER
# =========================================================

with planner_tab:

    st.header(
        "Plan a shipment"
    )

    left, right = st.columns(2)

    # -----------------------------------------------------
    # SHIPMENT INFORMATION
    # -----------------------------------------------------

    with left:

        farmer_id = st.text_input(
            "Farmer ID",
            "FARMER-001",
        )

        crop = st.selectbox(
            "Crop",
            [
                "tomato",
                "mango",
                "banana",
                "strawberry",
                "spinach",
                "potato",
                "onion",
            ],
        )

        quantity = st.number_input(
            "Produce quantity (kg)",
            min_value=1.0,
            value=500.0,
            step=50.0,
        )

        harvest_age = st.number_input(
            "Hours since harvest",
            min_value=0.0,
            value=8.0,
            step=1.0,
        )

        condition = st.slider(
            "Produce condition",
            min_value=0.1,
            max_value=1.0,
            value=0.90,
            step=0.05,
        )

        st.caption(
            "1.0 = excellent condition; "
            "0.1 = severely deteriorated."
        )


    # -----------------------------------------------------
    # LOCATION
    # -----------------------------------------------------

    with right:

        origin_name = st.text_input(
            "Farm / pickup location",
            "Bahawalpur, Pakistan",
        )

        destination_name = st.text_input(
            "Buyer / destination",
            "Multan, Pakistan",
        )

        fallback_temperature = st.number_input(
            "Fallback temperature °C",
            min_value=-10.0,
            max_value=60.0,
            value=30.0,
            step=0.5,
        )

        st.caption(
            "Used only if the weather API "
            "cannot be reached."
        )


    # -----------------------------------------------------
    # VOICE
    # -----------------------------------------------------

    st.subheader(
        "Voice input"
    )

    audio = st.audio_input(
        "Record shipment information",
        sample_rate=16000,
    )

    if audio:

        st.audio(audio)

        if st.button(
            "Transcribe voice",
        ):

            try:

                if language == "English":
                    lang_code = "en"

                elif language == "Urdu":
                    lang_code = "ur"

                else:
                    lang_code = None

                with st.spinner(
                    "Transcribing..."
                ):

                    transcript = transcribe_audio(
                        audio.getvalue(),
                        lang_code,
                    )

                st.text_area(
                    "Transcript",
                    transcript,
                    height=100,
                )

            except Exception as exc:

                st.error(
                    f"Voice transcription failed: "
                    f"{exc}"
                )


    # -----------------------------------------------------
    # ANALYZE
    # -----------------------------------------------------

    st.divider()

    analyze_button = st.button(
        "Analyze & Find Returning Trucks",
        type="primary",
        use_container_width=True,
    )


    if analyze_button:

        # -----------------------------------------------
        # GEOCODING
        # -----------------------------------------------

        try:

            with st.spinner(
                "Finding pickup and destination..."
            ):

                origin_data = (
                    geocode_location(
                        origin_name
                    )
                )

                destination_data = (
                    geocode_location(
                        destination_name
                    )
                )

        except Exception as exc:

            st.error(
                f"Location lookup failed: {exc}"
            )

            st.stop()


        origin = Location(
            name=origin_data["name"],
            latitude=origin_data["latitude"],
            longitude=origin_data["longitude"],
        )

        destination = Location(
            name=destination_data["name"],
            latitude=destination_data["latitude"],
            longitude=destination_data["longitude"],
        )


        shipment = Shipment(
            farmer_id=farmer_id,
            crop=crop,
            quantity_kg=quantity,
            harvest_age_hours=harvest_age,
            condition_score=condition,
            origin=origin,
            destination=destination,
        )


        # -----------------------------------------------
        # WEATHER
        # -----------------------------------------------

        weather_failed = False

        try:

            with st.spinner(
                "Getting current weather..."
            ):

                weather = (
                    get_current_weather(
                        origin.latitude,
                        origin.longitude,
                    )
                )

            temperature = (
                weather["temperature_c"]
            )

        except Exception:

            weather_failed = True

            temperature = (
                fallback_temperature
            )

            weather = {
                "temperature_c":
                    fallback_temperature,

                "humidity":
                    None,

                "wind_speed_kmh":
                    None,

                "precipitation_mm":
                    None,

                "timezone":
                    "",

                "source":
                    "Manual fallback",
            }

            st.warning(
                "Weather service is temporarily "
                "unavailable. The fallback "
                "temperature is being used."
            )


        # -----------------------------------------------
        # SHELF-LIFE
        # -----------------------------------------------

        analysis = analyze_shipment(
            shipment,
            temperature,
        )


        # -----------------------------------------------
        # DRIVER OBJECTS
        # -----------------------------------------------

        drivers = []

        for _, row in (
            st.session_state
            .drivers
            .iterrows()
        ):

            try:

                current_data = (
                    geocode_location(
                        str(
                            row[
                                "current_location"
                            ]
                        )
                    )
                )

                destination_data_driver = (
                    geocode_location(
                        str(
                            row[
                                "destination"
                            ]
                        )
                    )
                )

                driver = Driver(
                    driver_id=str(
                        row["driver_id"]
                    ),

                    vehicle_type=str(
                        row["vehicle_type"]
                    ),

                    capacity_kg=float(
                        row["capacity_kg"]
                    ),

                    available_in_hours=float(
                        row[
                            "available_in_hours"
                        ]
                    ),

                    current_location=Location(
                        name=current_data["name"],
                        latitude=current_data[
                            "latitude"
                        ],
                        longitude=current_data[
                            "longitude"
                        ],
                    ),

                    destination=Location(
                        name=(
                            destination_data_driver[
                                "name"
                            ]
                        ),
                        latitude=(
                            destination_data_driver[
                                "latitude"
                            ]
                        ),
                        longitude=(
                            destination_data_driver[
                                "longitude"
                            ]
                        ),
                    ),

                    refrigerated=bool(
                        row["refrigerated"]
                    ),

                    reliability=float(
                        row["reliability"]
                    ),
                )

                drivers.append(
                    driver
                )

            except Exception as exc:

                st.warning(
                    f"Could not process "
                    f"{row['driver_id']}: "
                    f"{exc}"
                )


        if not drivers:

            st.error(
                "No valid trucks are available."
            )

            st.stop()


        # -----------------------------------------------
        # MATCH
        # -----------------------------------------------

        with st.spinner(
            "Calculating routes and "
            "ranking returning trucks..."
        ):

            matches = rank_matches(
                shipment,
                drivers,
                analysis,
                get_route,
            )


        # -----------------------------------------------
        # SAVE STATE
        # -----------------------------------------------

        st.session_state.shipment = (
            shipment
        )

        st.session_state.analysis = (
            analysis
        )

        st.session_state.matches = (
            matches
        )

        st.session_state.weather = (
            weather
        )


    # =====================================================
    # DISPLAY RESULTS
    # =====================================================

    if (
        st.session_state.shipment
        and st.session_state.analysis
    ):

        shipment = (
            st.session_state.shipment
        )

        analysis = (
            st.session_state.analysis
        )

        matches = (
            st.session_state.matches
        )

        weather = (
            st.session_state.weather
        )


        st.divider()

        st.header(
            "Shipment Analysis"
        )


        metric1, metric2, metric3, metric4 = (
            st.columns(4)
        )


        metric1.metric(
            "Temperature",
            f"{analysis.temperature_c:.1f} °C",
        )

        metric2.metric(
            "Remaining shelf life",
            f"{analysis.remaining_shelf_life_hours:.1f} h",
        )

        metric3.metric(
            "Urgency",
            analysis.urgency,
        )

        valid_matches = [
            result
            for result
            in matches
            if result.valid
        ]

        metric4.metric(
            "Valid trucks",
            len(valid_matches),
        )


        # -------------------------------------------------
        # SHELF LIFE DETAIL
        # -------------------------------------------------

        with st.expander(
            "Shelf-life calculation details"
        ):

            st.write(
                f"Base shelf life: "
                f"{analysis.base_shelf_life_hours:.1f} hours"
            )

            st.write(
                f"Effective elapsed time: "
                f"{analysis.effective_elapsed_hours:.1f} hours"
            )

            st.write(
                f"Heat factor: "
                f"{analysis.heat_factor:.2f}"
            )

            st.write(
                f"Condition factor: "
                f"{analysis.condition_factor:.2f}"
            )

            st.caption(
                "These are heuristic estimates for "
                "the prototype and are not validated "
                "food-safety predictions."
            )


        # -------------------------------------------------
        # MATCH TABLE
        # -------------------------------------------------

        st.header(
            "Returning Truck Matches"
        )

        table = []

        for result in matches:

            table.append(
                {
                    "Truck":
                        result.driver_id,

                    "Status":
                        "MATCH"
                        if result.valid
                        else "REJECTED",

                    "Score":
                        round(
                            result.score,
                            3,
                        ),

                    "Detour (km)":
                        round(
                            result.detour_km,
                            1,
                        ),

                    "Delivery (km)":
                        round(
                            result
                            .pickup_delivery_distance_km,
                            1,
                        ),

                    "Time (hours)":
                        round(
                            result
                            .pickup_delivery_time_hours,
                            2,
                        ),

                    "Reason":
                        result.reason,
                }
            )


        st.dataframe(
            pd.DataFrame(table),
            use_container_width=True,
            hide_index=True,
        )


        # -------------------------------------------------
        # BEST MATCH
        # -------------------------------------------------

        if valid_matches:

            best_match = (
                valid_matches[0]
            )

            st.header(
                "Recommended Returning Truck"
            )

            b1, b2, b3, b4 = (
                st.columns(4)
            )

            b1.metric(
                "Truck",
                best_match.driver_id,
            )

            b2.metric(
                "Match score",
                f"{best_match.score:.2f}",
            )

            b3.metric(
                "Detour",
                f"{best_match.detour_km:.1f} km",
            )

            b4.metric(
                "Travel time",
                f"{best_match.pickup_delivery_time_hours:.1f} h",
            )


            st.success(
                "FreshRoute found a valid "
                "returning-truck match."
            )


            # ---------------------------------------------
            # AI REPORT
            # ---------------------------------------------

            if st.button(
                "Generate AI Shipment Report",
                type="secondary",
            ):

                try:

                    with st.spinner(
                        "Generating FreshRoute AI report..."
                    ):

                        report = (
                            generate_ai_report(
                                shipment,
                                analysis,
                                best_match,
                                weather,
                                language,
                            )
                        )

                    st.markdown(
                        "### AI Shipment Report"
                    )

                    st.markdown(
                        report
                    )

                except Exception as exc:

                    st.error(
                        f"AI report failed: {exc}"
                    )


        else:

            st.error(
                "FreshRoute could not find "
                "a valid returning truck."
            )

            for result in matches:

                if result.rejection_reasons:

                    with st.expander(
                        f"{result.driver_id} "
                        "— rejection reasons"
                    ):

                        for reason in (
                            result.rejection_reasons
                        ):

                            st.write(
                                f"- {reason}"
                            )


        # -------------------------------------------------
        # MAP
        # -------------------------------------------------

        st.header(
            "Shipment Locations"
        )

        map_rows = [
            {
                "location":
                    "Farm",

                "latitude":
                    shipment
                    .origin
                    .latitude,

                "longitude":
                    shipment
                    .origin
                    .longitude,
            },

            {
                "location":
                    "Buyer",

                "latitude":
                    shipment
                    .destination
                    .latitude,

                "longitude":
                    shipment
                    .destination
                    .longitude,
            },
        ]


        if valid_matches:

            best_driver_id = (
                valid_matches[0]
                .driver_id
            )

            best_driver = next(
                driver
                for driver
                in drivers
                if driver.driver_id
                == best_driver_id
            )

            map_rows.append(
                {
                    "location":
                        "Recommended truck",

                    "latitude":
                        best_driver
                        .current_location
                        .latitude,

                    "longitude":
                        best_driver
                        .current_location
                        .longitude,
                }
            )


        map_df = pd.DataFrame(
            map_rows
        )

        st.map(
            map_df,
            latitude="latitude",
            longitude="longitude",
            size=120,
        )

        st.caption(
            "Map locations are geocoded using "
            "Open-Meteo. Road calculations use OSRM."
        )


# =========================================================
# DRIVER FLEET
# =========================================================

with fleet_tab:

    st.header(
        "Returning Truck Fleet"
    )

    st.write(
        """
Add or edit returning trucks here.
FreshRoute uses this information when
searching for backhaul matches.
"""
    )


    edited_drivers = st.data_editor(
        st.session_state.drivers,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,

        column_config={

            "driver_id":
                st.column_config.TextColumn(
                    "Truck ID",
                    required=True,
                ),

            "vehicle_type":
                st.column_config.SelectboxColumn(
                    "Vehicle",
                    options=[
                        "refrigerated",
                        "covered",
                        "open",
                    ],
                    required=True,
                ),

            "capacity_kg":
                st.column_config.NumberColumn(
                    "Capacity (kg)",
                    min_value=1,
                    step=100,
                ),

            "available_in_hours":
                st.column_config.NumberColumn(
                    "Available in hours",
                    min_value=0,
                    step=0.5,
                ),

            "current_location":
                st.column_config.TextColumn(
                    "Current location",
                    required=True,
                ),

            "destination":
                st.column_config.TextColumn(
                    "Returning destination",
                    required=True,
                ),

            "refrigerated":
                st.column_config.CheckboxColumn(
                    "Refrigerated",
                ),

            "reliability":
                st.column_config.NumberColumn(
                    "Reliability",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.05,
                ),
        },
    )


    if st.button(
        "Save Fleet",
        type="primary",
    ):

        st.session_state.drivers = (
            edited_drivers.copy()
        )

        st.success(
            "Truck fleet saved for this session."
        )


    st.info(
        f"""
Maximum allowed detour:
**{MAX_DETOUR_KM:.0f} km**

Minimum remaining shelf-life buffer:
**4 hours**
"""
    )


# =========================================================
# AI ASSISTANT
# =========================================================

with ai_tab:

    st.header(
        "FreshRoute AI Assistant"
    )

    if (
        st.session_state.shipment
        is None
    ):

        st.info(
            "Analyze a shipment first."
        )

    else:

        shipment = (
            st.session_state.shipment
        )

        analysis = (
            st.session_state.analysis
        )

        matches = (
            st.session_state.matches
        )


        st.write(
            f"Current shipment: "
            f"**{shipment.crop.title()} — "
            f"{shipment.quantity_kg:.0f} kg**"
        )


        question = st.text_area(
            "Ask FreshRoute AI",
            placeholder=(
                "Why was this truck selected?\n"
                "What is the main risk?\n"
                "What should the farmer do next?"
            ),
        )


        if st.button(
            "Ask FreshRoute AI",
            type="primary",
        ):

            if not question.strip():

                st.warning(
                    "Enter a question first."
                )

            else:

                try:

                    with st.spinner(
                        "FreshRoute AI is analyzing..."
                    ):

                        answer = (
                            ask_freshroute_ai(
                                question,
                                shipment,
                                analysis,
                                matches,
                            )
                        )

                    st.markdown(
                        answer
                    )

                except Exception as exc:

                    st.error(
                        f"AI request failed: {exc}"
                    )


# =========================================================
# ABOUT
# =========================================================

with about_tab:

    st.header(
        "About FreshRoute"
    )

    st.markdown(
        """
## The problem

Agricultural producers may struggle to find
timely transportation while trucks returning
from deliveries can have unused capacity.

This creates two simultaneous inefficiencies:

- Produce can lose value while waiting for transport.
- Returning trucks can travel with unused capacity.

## The FreshRoute solution

FreshRoute attempts to connect the two.

It evaluates:

- Produce quantity
- Crop type
- Harvest age
- Produce condition
- Current temperature
- Estimated remaining shelf life
- Truck capacity
- Vehicle compatibility
- Truck availability
- Existing route
- Additional detour
- Estimated delivery time

## AI enhancement

FreshRoute uses AI for:

- Shipment explanations
- Operational recommendations
- Buyer-ready summaries
- Natural-language Q&A
- Voice-to-text input

The AI does not override the deterministic
matching engine.

## Prototype limitations

The shelf-life model is heuristic.

It is not a scientifically validated
food-safety prediction system.

The public OSRM routing service is intended
for prototype use.

Fleet information is session-based and is
not permanently stored.

The current application is a decision-support
prototype rather than a production logistics
marketplace.
"""
    )
