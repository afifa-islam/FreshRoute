from dataclasses import dataclass, field
from typing import List

from math import radians, sin, cos, sqrt, atan2


# =========================================================
# CONFIGURATION
# =========================================================

MAX_DETOUR_KM = 15.0
MIN_REMAINING_SHELF_LIFE_HOURS = 4.0


# =========================================================
# CROP PROFILES
# =========================================================

CROP_PROFILES = {
    "tomato": {
        "shelf_life_hours": 72,
        "preferred_temperature": 25,
        "vehicles": [
            "refrigerated",
            "covered",
            "open",
        ],
    },

    "mango": {
        "shelf_life_hours": 120,
        "preferred_temperature": 25,
        "vehicles": [
            "refrigerated",
            "covered",
            "open",
        ],
    },

    "banana": {
        "shelf_life_hours": 96,
        "preferred_temperature": 27,
        "vehicles": [
            "refrigerated",
            "covered",
            "open",
        ],
    },

    "strawberry": {
        "shelf_life_hours": 48,
        "preferred_temperature": 20,
        "vehicles": [
            "refrigerated",
        ],
    },

    "spinach": {
        "shelf_life_hours": 48,
        "preferred_temperature": 20,
        "vehicles": [
            "refrigerated",
            "covered",
        ],
    },

    "potato": {
        "shelf_life_hours": 168,
        "preferred_temperature": 25,
        "vehicles": [
            "covered",
            "open",
        ],
    },

    "onion": {
        "shelf_life_hours": 240,
        "preferred_temperature": 25,
        "vehicles": [
            "covered",
            "open",
        ],
    },
}


DEFAULT_CROP_PROFILE = {
    "shelf_life_hours": 72,
    "preferred_temperature": 25,
    "vehicles": [
        "refrigerated",
        "covered",
        "open",
    ],
}


# =========================================================
# DATA CLASSES
# =========================================================

@dataclass
class Location:

    name: str
    latitude: float
    longitude: float


@dataclass
class Shipment:

    farmer_id: str
    crop: str
    quantity_kg: float
    harvest_age_hours: float
    condition_score: float

    origin: Location
    destination: Location


@dataclass
class Driver:

    driver_id: str
    vehicle_type: str
    capacity_kg: float
    available_in_hours: float

    current_location: Location
    destination: Location

    refrigerated: bool = False
    reliability: float = 0.8


@dataclass
class Route:

    success: bool
    distance_km: float = 0.0
    duration_hours: float = 0.0

    geometry: List[List[float]] = field(
        default_factory=list
    )

    source: str = "unknown"
    error: str = ""


@dataclass
class ShipmentAnalysis:

    crop: str
    temperature_c: float

    base_shelf_life_hours: float
    effective_elapsed_hours: float
    remaining_shelf_life_hours: float

    urgency: str

    heat_factor: float
    condition_factor: float

    safe_vehicle_types: List[str]


@dataclass
class MatchResult:

    driver_id: str

    valid: bool
    reason: str

    detour_km: float = 0.0

    direct_distance_km: float = 0.0

    pickup_delivery_distance_km: float = 0.0

    direct_time_hours: float = 0.0

    pickup_delivery_time_hours: float = 0.0

    score: float = 0.0

    capacity_score: float = 0.0
    detour_score: float = 0.0
    time_score: float = 0.0
    temperature_score: float = 0.0
    reliability_score: float = 0.0

    route_geometry: List[List[float]] = field(
        default_factory=list
    )

    rejection_reasons: List[str] = field(
        default_factory=list
    )


# =========================================================
# CROP FUNCTIONS
# =========================================================

def get_crop_profile(crop: str):

    crop = crop.lower().strip()

    return CROP_PROFILES.get(
        crop,
        DEFAULT_CROP_PROFILE,
    )


# =========================================================
# SHELF-LIFE MODEL
# =========================================================

def calculate_heat_factor(
    temperature_c: float,
    preferred_temperature: float,
):

    if temperature_c <= preferred_temperature:
        return 1.0

    degrees_above = (
        temperature_c
        - preferred_temperature
    )

    return 1.0 + (
        degrees_above / 5.0
    ) * 0.25


def calculate_condition_factor(
    condition_score: float,
):

    condition_score = max(
        0.1,
        min(
            1.0,
            condition_score,
        ),
    )

    return 1.0 / condition_score


def calculate_urgency(
    remaining_hours: float,
):

    if remaining_hours > 24:
        return "GREEN"

    if remaining_hours > 8:
        return "YELLOW"

    if remaining_hours > 2:
        return "ORANGE"

    return "RED"


def analyze_shipment(
    shipment: Shipment,
    temperature_c: float,
):

    profile = get_crop_profile(
        shipment.crop
    )

    base_shelf_life = profile[
        "shelf_life_hours"
    ]

    preferred_temperature = profile[
        "preferred_temperature"
    ]

    heat_factor = calculate_heat_factor(
        temperature_c,
        preferred_temperature,
    )

    condition_factor = (
        calculate_condition_factor(
            shipment.condition_score
        )
    )

    effective_elapsed = (
        shipment.harvest_age_hours
        * heat_factor
        * condition_factor
    )

    remaining = max(
        0.0,
        base_shelf_life
        - effective_elapsed,
    )

    urgency = calculate_urgency(
        remaining
    )

    return ShipmentAnalysis(
        crop=shipment.crop,
        temperature_c=temperature_c,
        base_shelf_life_hours=base_shelf_life,
        effective_elapsed_hours=effective_elapsed,
        remaining_shelf_life_hours=remaining,
        urgency=urgency,
        heat_factor=heat_factor,
        condition_factor=condition_factor,
        safe_vehicle_types=profile[
            "vehicles"
        ],
    )


# =========================================================
# HAVERSINE FALLBACK
# =========================================================

def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):

    earth_radius = 6371.0

    lat1 = radians(lat1)
    lat2 = radians(lat2)

    delta_lat = radians(
        lat2
        - lat1
    )

    delta_lon = radians(
        lon2
        - lon1
    )

    a = (
        sin(delta_lat / 2) ** 2
        +
        cos(lat1)
        * cos(lat2)
        * sin(delta_lon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a),
    )

    return earth_radius * c


def fallback_route(
    start: Location,
    end: Location,
):

    distance = haversine_km(
        start.latitude,
        start.longitude,
        end.latitude,
        end.longitude,
    )

    # Approximate road distance.
    road_distance = distance * 1.3

    # Conservative average speed.
    duration = road_distance / 40.0

    geometry = [
        [
            start.longitude,
            start.latitude,
        ],
        [
            end.longitude,
            end.latitude,
        ],
    ]

    return Route(
        success=True,
        distance_km=road_distance,
        duration_hours=duration,
        geometry=geometry,
        source="Haversine fallback",
    )


# =========================================================
# MATCH SCORING
# =========================================================

def calculate_match(
    shipment: Shipment,
    driver: Driver,
    analysis: ShipmentAnalysis,
    direct_route: Route,
    pickup_route: Route,
    delivery_route: Route,
):

    rejection_reasons = []

    vehicle_type = (
        driver.vehicle_type
        .strip()
        .lower()
    )

    allowed_vehicles = [
        vehicle.lower()
        for vehicle
        in analysis.safe_vehicle_types
    ]

    # -----------------------------------------------------
    # Vehicle compatibility
    # -----------------------------------------------------

    if vehicle_type not in allowed_vehicles:

        rejection_reasons.append(
            f"Vehicle type '{vehicle_type}' "
            f"is not recommended for "
            f"{shipment.crop}."
        )

    # -----------------------------------------------------
    # Capacity
    # -----------------------------------------------------

    if (
        driver.capacity_kg
        < shipment.quantity_kg
    ):

        rejection_reasons.append(
            f"Truck capacity "
            f"({driver.capacity_kg:.0f} kg) "
            f"is below shipment quantity "
            f"({shipment.quantity_kg:.0f} kg)."
        )

    # -----------------------------------------------------
    # Refrigeration
    # -----------------------------------------------------

    if (
        vehicle_type == "refrigerated"
        and not driver.refrigerated
    ):

        rejection_reasons.append(
            "Truck is marked as refrigerated "
            "but refrigeration is disabled."
        )

    # -----------------------------------------------------
    # Driver availability
    # -----------------------------------------------------

    if driver.available_in_hours < 0:

        rejection_reasons.append(
            "Driver availability time is invalid."
        )

    # -----------------------------------------------------
    # Distance
    # -----------------------------------------------------

    combined_distance = (
        pickup_route.distance_km
        + delivery_route.distance_km
    )

    combined_time = (
        pickup_route.duration_hours
        + delivery_route.duration_hours
    )

    detour = max(
        0.0,
        combined_distance
        - direct_route.distance_km,
    )

    if detour > MAX_DETOUR_KM:

        rejection_reasons.append(
            f"Detour is {detour:.1f} km, "
            f"which exceeds the "
            f"{MAX_DETOUR_KM:.0f} km limit."
        )

    # -----------------------------------------------------
    # Shelf-life constraint
    # -----------------------------------------------------

    required_time = (
        driver.available_in_hours
        + combined_time
        + MIN_REMAINING_SHELF_LIFE_HOURS
    )

    if (
        required_time
        > analysis.remaining_shelf_life_hours
    ):

        rejection_reasons.append(
            "Estimated delivery time does not "
            "fit safely within the remaining "
            "produce shelf-life window."
        )

    # -----------------------------------------------------
    # Minimum shelf life
    # -----------------------------------------------------

    if (
        analysis.remaining_shelf_life_hours
        < MIN_REMAINING_SHELF_LIFE_HOURS
    ):

        rejection_reasons.append(
            "Remaining shelf life is below "
            "the minimum safety buffer."
        )

    # -----------------------------------------------------
    # Score
    # -----------------------------------------------------

    capacity_ratio = (
        shipment.quantity_kg
        / max(
            driver.capacity_kg,
            1,
        )
    )

    capacity_score = max(
        0.0,
        1.0 - capacity_ratio,
    )

    detour_score = max(
        0.0,
        1.0 - (
            detour
            / MAX_DETOUR_KM
        ),
    )

    if (
        analysis.remaining_shelf_life_hours
        > 0
    ):

        time_score = max(
            0.0,
            min(
                1.0,
                1.0
                - (
                    combined_time
                    / analysis.remaining_shelf_life_hours
                ),
            ),
        )

    else:

        time_score = 0.0

    if vehicle_type == "refrigerated":

        temperature_score = 1.0

    elif vehicle_type in [
        "covered",
        "open",
    ]:

        temperature_score = (
            1.0
            if analysis.temperature_c <= 25
            else 0.5
        )

    else:

        temperature_score = 0.0

    reliability_score = max(
        0.0,
        min(
            1.0,
            driver.reliability,
        ),
    )

    score = (
        0.30 * detour_score
        + 0.25 * capacity_score
        + 0.20 * time_score
        + 0.15 * temperature_score
        + 0.10 * reliability_score
    )

    valid = (
        len(rejection_reasons)
        == 0
    )

    if valid:

        reason = (
            "Valid returning-truck match."
        )

    else:

        reason = (
            "Rejected: "
            + " ".join(
                rejection_reasons
            )
        )

    route_geometry = (
        pickup_route.geometry
        + delivery_route.geometry
    )

    return MatchResult(
        driver_id=driver.driver_id,
        valid=valid,
        reason=reason,

        detour_km=detour,

        direct_distance_km=(
            direct_route.distance_km
        ),

        pickup_delivery_distance_km=(
            combined_distance
        ),

        direct_time_hours=(
            direct_route.duration_hours
        ),

        pickup_delivery_time_hours=(
            combined_time
        ),

        score=score,

        capacity_score=capacity_score,
        detour_score=detour_score,
        time_score=time_score,
        temperature_score=temperature_score,
        reliability_score=reliability_score,

        route_geometry=route_geometry,

        rejection_reasons=rejection_reasons,
    )


def rank_matches(
    shipment,
    drivers,
    analysis,
    route_function,
):

    results = []

    for driver in drivers:

        direct_route = route_function(
            driver.current_location,
            driver.destination,
        )

        pickup_route = route_function(
            driver.current_location,
            shipment.origin,
        )

        delivery_route = route_function(
            shipment.origin,
            shipment.destination,
        )

        result = calculate_match(
            shipment,
            driver,
            analysis,
            direct_route,
            pickup_route,
            delivery_route,
        )

        results.append(result)

    results.sort(
        key=lambda result: (
            not result.valid,
            -result.score,
            result.detour_km,
            result.pickup_delivery_time_hours,
        )
    )

    return results
