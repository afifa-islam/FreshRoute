"""FreshRoute core logic.

Pure Python, no network and no Streamlit imports, so it is easy to test.

Contents
- crop profiles and the heuristic shelf-life model
- haversine distance and an offline fallback route
- match validation and scoring for returning (backhaul) trucks
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, cos, radians, sin, sqrt
from typing import Callable, Dict, List


# =========================================================
# CONFIGURATION
# =========================================================

MAX_DETOUR_KM = 15.0
MIN_REMAINING_SHELF_LIFE_HOURS = 4.0

VEHICLE_TYPES = ("refrigerated", "covered", "open")

# Fallback routing (only used when OSRM is unreachable).
ROAD_FACTOR = 1.3          # road distance ~ 1.3 x straight line
FALLBACK_SPEED_KMH = 40.0

# Extra heat exposure of an open truck compared with ambient air.
OPEN_TRUCK_HEAT_PENALTY = 1.10


# =========================================================
# CROP PROFILES
# =========================================================

CROP_PROFILES: Dict[str, dict] = {
    "tomato": {
        "shelf_life_hours": 72,
        "preferred_temperature": 25,
        "vehicles": ["refrigerated", "covered", "open"],
    },
    "mango": {
        "shelf_life_hours": 120,
        "preferred_temperature": 25,
        "vehicles": ["refrigerated", "covered", "open"],
    },
    "banana": {
        "shelf_life_hours": 96,
        "preferred_temperature": 27,
        "vehicles": ["refrigerated", "covered", "open"],
    },
    "strawberry": {
        "shelf_life_hours": 48,
        "preferred_temperature": 20,
        "vehicles": ["refrigerated"],
    },
    "spinach": {
        "shelf_life_hours": 48,
        "preferred_temperature": 20,
        "vehicles": ["refrigerated", "covered"],
    },
    "potato": {
        "shelf_life_hours": 168,
        "preferred_temperature": 25,
        "vehicles": ["covered", "open"],
    },
    "onion": {
        "shelf_life_hours": 240,
        "preferred_temperature": 25,
        "vehicles": ["covered", "open"],
    },
}

DEFAULT_CROP_PROFILE = {
    "shelf_life_hours": 72,
    "preferred_temperature": 25,
    "vehicles": ["refrigerated", "covered", "open"],
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
    reliability: float = 0.8
    name: str = ""
    phone: str = ""

    @property
    def refrigerated(self) -> bool:
        """Refrigeration is derived from the vehicle type so the two
        can never contradict each other."""
        return self.vehicle_type.strip().lower() == "refrigerated"


@dataclass
class Route:
    success: bool
    distance_km: float = 0.0
    duration_hours: float = 0.0
    geometry: List[List[float]] = field(default_factory=list)  # [lon, lat]
    source: str = "unknown"
    estimated: bool = False   # True when not a real road route
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
    pickup_distance_km: float = 0.0
    delivery_distance_km: float = 0.0
    return_distance_km: float = 0.0

    time_to_delivery_hours: float = 0.0
    remaining_at_delivery_hours: float = 0.0

    score: float = 0.0
    detour_score: float = 0.0
    utilization_score: float = 0.0
    time_score: float = 0.0
    temperature_score: float = 0.0
    reliability_score: float = 0.0

    used_fallback: bool = False

    # [{"name": str, "geometry": [[lon, lat], ...]}, ...]
    route_legs: List[dict] = field(default_factory=list)

    rejection_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# =========================================================
# SHELF-LIFE MODEL (heuristic, not food-safety validated)
# =========================================================

def get_crop_profile(crop: str) -> dict:
    return CROP_PROFILES.get(crop.lower().strip(), DEFAULT_CROP_PROFILE)


def calculate_heat_factor(temperature_c: float, preferred_temperature: float) -> float:
    """Spoilage speeds up by 25% for every 5 degrees above the ideal."""
    if temperature_c <= preferred_temperature:
        return 1.0
    degrees_above = temperature_c - preferred_temperature
    return 1.0 + (degrees_above / 5.0) * 0.25


def calculate_condition_factor(condition_score: float) -> float:
    condition_score = max(0.1, min(1.0, condition_score))
    return 1.0 / condition_score


def calculate_urgency(remaining_hours: float) -> str:
    if remaining_hours > 24:
        return "GREEN"
    if remaining_hours > 8:
        return "YELLOW"
    if remaining_hours > 2:
        return "ORANGE"
    return "RED"


def transit_heat_factor(vehicle_type: str, ambient_heat_factor: float) -> float:
    """Heat exposure while the produce is on the truck.

    Refrigerated trucks keep produce at its preferred temperature (1.0).
    Covered trucks see ambient heat. Open trucks see slightly more.
    """
    vehicle_type = vehicle_type.strip().lower()
    if vehicle_type == "refrigerated":
        return 1.0
    if vehicle_type == "open":
        return ambient_heat_factor * OPEN_TRUCK_HEAT_PENALTY
    return ambient_heat_factor


def analyze_shipment(shipment: Shipment, temperature_c: float) -> ShipmentAnalysis:
    profile = get_crop_profile(shipment.crop)

    base_shelf_life = float(profile["shelf_life_hours"])
    heat_factor = calculate_heat_factor(temperature_c, profile["preferred_temperature"])
    condition_factor = calculate_condition_factor(shipment.condition_score)

    effective_elapsed = shipment.harvest_age_hours * heat_factor * condition_factor
    remaining = max(0.0, base_shelf_life - effective_elapsed)

    return ShipmentAnalysis(
        crop=shipment.crop,
        temperature_c=temperature_c,
        base_shelf_life_hours=base_shelf_life,
        effective_elapsed_hours=effective_elapsed,
        remaining_shelf_life_hours=remaining,
        urgency=calculate_urgency(remaining),
        heat_factor=heat_factor,
        condition_factor=condition_factor,
        safe_vehicle_types=list(profile["vehicles"]),
    )


# =========================================================
# DISTANCE FALLBACK
# =========================================================

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0

    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)      # difference of the DEGREE values
    delta_lambda = radians(lon2 - lon1)

    a = (
        sin(delta_phi / 2) ** 2
        + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return earth_radius_km * c


def fallback_route(start: Location, end: Location) -> Route:
    straight = haversine_km(
        start.latitude, start.longitude, end.latitude, end.longitude
    )
    road_distance = straight * ROAD_FACTOR
    duration = road_distance / FALLBACK_SPEED_KMH

    return Route(
        success=True,
        distance_km=road_distance,
        duration_hours=duration,
        geometry=[
            [start.longitude, start.latitude],
            [end.longitude, end.latitude],
        ],
        source="Estimated (straight-line)",
        estimated=True,
    )


# =========================================================
# MATCH SCORING
# =========================================================

def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def calculate_match(
    shipment: Shipment,
    driver: Driver,
    analysis: ShipmentAnalysis,
    direct_route: Route,
    pickup_route: Route,
    delivery_route: Route,
    return_route: Route,
) -> MatchResult:
    """Evaluate one truck.

    Routes:
      direct_route    truck location  -> truck's own destination (original plan)
      pickup_route    truck location  -> farm
      delivery_route  farm            -> buyer
      return_route    buyer           -> truck's own destination
    """
    reasons: List[str] = []
    warnings: List[str] = []

    vehicle = driver.vehicle_type.strip().lower()
    allowed = [v.lower() for v in analysis.safe_vehicle_types]

    # ----- vehicle ------------------------------------------------
    if vehicle not in VEHICLE_TYPES:
        reasons.append(f"Unknown vehicle type '{vehicle}'.")
    elif vehicle not in allowed:
        reasons.append(
            f"Vehicle type '{vehicle}' is not recommended for {shipment.crop}."
        )

    # ----- capacity -----------------------------------------------
    if driver.capacity_kg <= 0:
        reasons.append("Truck capacity must be greater than zero.")
    elif driver.capacity_kg < shipment.quantity_kg:
        reasons.append(
            f"Truck capacity ({driver.capacity_kg:.0f} kg) is below "
            f"shipment quantity ({shipment.quantity_kg:.0f} kg)."
        )

    # ----- availability -------------------------------------------
    if driver.available_in_hours < 0:
        reasons.append("Driver availability time is invalid.")

    # ----- routing data -------------------------------------------
    routes = (direct_route, pickup_route, delivery_route, return_route)
    if not all(r.success for r in routes):
        reasons.append("Routing data is unavailable for this truck.")

    used_fallback = any(r.estimated for r in routes)
    if used_fallback:
        warnings.append(
            "Distances are straight-line estimates because the routing "
            "service was unreachable."
        )

    # ----- detour -------------------------------------------------
    # Truck must still reach its own destination after delivering.
    new_trip = (
        pickup_route.distance_km
        + delivery_route.distance_km
        + return_route.distance_km
    )
    detour = max(0.0, new_trip - direct_route.distance_km)

    if detour > MAX_DETOUR_KM:
        reasons.append(
            f"Detour is {detour:.1f} km, which exceeds the "
            f"{MAX_DETOUR_KM:.0f} km limit."
        )

    # ----- shelf life ---------------------------------------------
    # Until pickup the produce waits at ambient temperature. Once loaded
    # it experiences the vehicle's temperature. All time is scaled by the
    # produce condition factor, like the elapsed time in the analysis.
    waiting_hours = driver.available_in_hours + pickup_route.duration_hours
    transit_hours = delivery_route.duration_hours
    time_to_delivery = waiting_hours + transit_hours

    consumed = (
        waiting_hours * analysis.heat_factor
        + transit_hours * transit_heat_factor(vehicle, analysis.heat_factor)
    ) * analysis.condition_factor

    remaining_at_delivery = analysis.remaining_shelf_life_hours - consumed

    if analysis.remaining_shelf_life_hours < MIN_REMAINING_SHELF_LIFE_HOURS:
        reasons.append(
            "Remaining shelf life is below the minimum safety buffer "
            f"({MIN_REMAINING_SHELF_LIFE_HOURS:.0f} h)."
        )
    elif remaining_at_delivery < MIN_REMAINING_SHELF_LIFE_HOURS:
        reasons.append(
            "Delivery would leave only "
            f"{max(0.0, remaining_at_delivery):.1f} h of shelf life "
            f"(minimum {MIN_REMAINING_SHELF_LIFE_HOURS:.0f} h)."
        )

    # ----- scores (0..1, higher is better) -------------------------
    detour_score = _clamp01(1.0 - detour / MAX_DETOUR_KM)

    # Backhaul economics: a better-filled truck is better, up to full.
    utilization_score = (
        _clamp01(shipment.quantity_kg / driver.capacity_kg)
        if driver.capacity_kg > 0
        else 0.0
    )

    if analysis.remaining_shelf_life_hours > 0:
        time_score = _clamp01(
            remaining_at_delivery / analysis.remaining_shelf_life_hours
        )
    else:
        time_score = 0.0

    if vehicle == "refrigerated":
        temperature_score = 1.0
    elif vehicle in ("covered", "open"):
        temperature_score = _clamp01(1.0 / max(analysis.heat_factor, 1.0))
        if vehicle == "open":
            temperature_score *= 0.8
    else:
        temperature_score = 0.0

    reliability_score = _clamp01(driver.reliability)

    score = (
        0.30 * detour_score
        + 0.25 * time_score
        + 0.20 * utilization_score
        + 0.15 * temperature_score
        + 0.10 * reliability_score
    )

    valid = not reasons
    reason = (
        "Valid returning-truck match."
        if valid
        else "Rejected: " + " ".join(reasons)
    )

    route_legs = [
        {"name": "Truck to farm", "geometry": pickup_route.geometry},
        {"name": "Farm to buyer", "geometry": delivery_route.geometry},
        {"name": "Buyer to truck destination", "geometry": return_route.geometry},
    ]

    return MatchResult(
        driver_id=driver.driver_id,
        valid=valid,
        reason=reason,
        detour_km=detour,
        direct_distance_km=direct_route.distance_km,
        pickup_distance_km=pickup_route.distance_km,
        delivery_distance_km=delivery_route.distance_km,
        return_distance_km=return_route.distance_km,
        time_to_delivery_hours=time_to_delivery,
        remaining_at_delivery_hours=remaining_at_delivery,
        score=score,
        detour_score=detour_score,
        utilization_score=utilization_score,
        time_score=time_score,
        temperature_score=temperature_score,
        reliability_score=reliability_score,
        used_fallback=used_fallback,
        route_legs=route_legs,
        rejection_reasons=reasons,
        warnings=warnings,
    )


def rank_matches(
    shipment: Shipment,
    drivers: List[Driver],
    analysis: ShipmentAnalysis,
    route_function: Callable[[Location, Location], Route],
) -> List[MatchResult]:
    """Score every driver. Valid matches come first, best score first."""

    # Identical for every truck, so only request it once.
    delivery_route = route_function(shipment.origin, shipment.destination)

    results: List[MatchResult] = []

    for driver in drivers:
        try:
            direct_route = route_function(driver.current_location, driver.destination)
            pickup_route = route_function(driver.current_location, shipment.origin)
            return_route = route_function(shipment.destination, driver.destination)

            result = calculate_match(
                shipment,
                driver,
                analysis,
                direct_route,
                pickup_route,
                delivery_route,
                return_route,
            )
        except Exception as exc:  # one bad truck must not break the ranking
            message = f"Could not evaluate this truck: {exc}"
            result = MatchResult(
                driver_id=driver.driver_id,
                valid=False,
                reason=f"Rejected: {message}",
                rejection_reasons=[message],
            )

        results.append(result)

    results.sort(
        key=lambda r: (
            not r.valid,
            -r.score,
            r.detour_km,
            r.time_to_delivery_hours,
        )
    )
    return results
