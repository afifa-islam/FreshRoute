"""Plain-assert tests for core.py.

Run with either:  python tests/test_core.py   or   pytest
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (  # noqa: E402
    Driver,
    Location,
    Route,
    Shipment,
    analyze_shipment,
    calculate_match,
    fallback_route,
    haversine_km,
    rank_matches,
)


def loc(name, lat, lon):
    return Location(name, lat, lon)


def route(km, hours=None):
    return Route(
        success=True,
        distance_km=km,
        duration_hours=km / 50 if hours is None else hours,
        source="OSRM",
    )


def make_shipment(crop="tomato", qty=500, age=8, cond=0.9):
    return Shipment(
        "F1", crop, qty, age, cond,
        loc("Farm", 29.40, 71.68), loc("Buyer", 30.16, 71.52),
    )


def make_driver(vehicle="covered", capacity=5000, wait=0):
    return Driver(
        "T1", vehicle, capacity, wait,
        loc("Here", 29.40, 71.68), loc("Home", 30.16, 71.52), 0.9,
    )


def test_haversine_bahawalpur_multan():
    km = haversine_km(29.3956, 71.6836, 30.1575, 71.5249)
    assert 80 < km < 95, km


def test_fallback_route_is_flagged_and_sane():
    r = fallback_route(loc("A", 29.3956, 71.6836), loc("B", 30.1575, 71.5249))
    assert r.estimated and r.success
    assert 100 < r.distance_km < 125, r.distance_km


def test_detour_includes_return_leg():
    shipment = make_shipment()
    analysis = analyze_shipment(shipment, 25)
    # direct 100, pickup 10, delivery 90, return 30 -> 10+90+30-100 = 30
    m = calculate_match(
        shipment, make_driver(), analysis,
        route(100), route(10), route(90), route(30),
    )
    assert abs(m.detour_km - 30) < 1e-9
    assert not m.valid
    assert any("Detour" in r for r in m.rejection_reasons)


def test_valid_match_when_truck_already_heads_to_buyer():
    shipment = make_shipment()
    analysis = analyze_shipment(shipment, 25)
    m = calculate_match(
        shipment, make_driver(), analysis,
        route(100), route(5), route(95), route(0, 0),
    )
    assert m.valid, m.reason
    assert m.detour_km == 0


def test_capacity_and_vehicle_rejections():
    shipment = make_shipment(crop="strawberry", qty=6000)
    analysis = analyze_shipment(shipment, 25)
    m = calculate_match(
        shipment, make_driver("open", 5000), analysis,
        route(100), route(5), route(95), route(0, 0),
    )
    assert not m.valid
    text = " ".join(m.rejection_reasons)
    assert "not recommended" in text and "capacity" in text


def test_refrigeration_preserves_shelf_life():
    shipment = make_shipment(age=10)
    analysis = analyze_shipment(shipment, 40)   # hot day
    args = (route(100), route(5), route(95, 6), route(0, 0))
    cold = calculate_match(shipment, make_driver("refrigerated"), analysis, *args)
    open_ = calculate_match(shipment, make_driver("open"), analysis, *args)
    assert cold.remaining_at_delivery_hours > open_.remaining_at_delivery_hours


def test_shelf_life_rejection():
    shipment = make_shipment(crop="spinach", age=30, cond=0.7)
    analysis = analyze_shipment(shipment, 35)
    m = calculate_match(
        shipment, make_driver("covered"), analysis,
        route(100), route(5), route(95), route(0, 0),
    )
    assert not m.valid


def test_rank_matches_orders_valid_first_and_reuses_delivery_route():
    shipment = make_shipment()
    analysis = analyze_shipment(shipment, 25)
    calls = []

    legs = {
        ("Here", "Home"): route(100),    # truck's original trip
        ("Here", "Farm"): route(5),      # truck to farm
        ("Farm", "Buyer"): route(95),    # farm to buyer
        ("Buyer", "Home"): route(0, 0),  # buyer to truck destination
    }

    def fake_route(a, b):
        calls.append((a.name, b.name))
        return legs[(a.name, b.name)]

    good = make_driver("covered")
    too_small = Driver("T2", "covered", 100, 0, good.current_location, good.destination, 0.9)
    results = rank_matches(shipment, [too_small, good], analysis, fake_route)

    assert results[0].driver_id == "T1" and results[0].valid
    assert results[1].driver_id == "T2" and not results[1].valid
    assert calls.count(("Farm", "Buyer")) == 1


def test_refrigerated_flag_follows_vehicle_type():
    assert make_driver("refrigerated").refrigerated
    assert not make_driver("covered").refrigerated


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"\n{len(tests)} tests passed")
