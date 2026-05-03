"""Unit conversions for ride data."""

KM_TO_MILES = 0.621371


def meters_to_miles(meters: float) -> float:
    return meters / 1000 * KM_TO_MILES


def kmh_to_mph(kmh: float) -> float:
    return kmh * KM_TO_MILES
