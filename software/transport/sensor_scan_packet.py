"""Strict wire parser for the target Version 3 S1/S2/S3 scan packet."""

from __future__ import annotations

import json
from math import isfinite
from typing import Optional

from software.game.sensor_scan import SensorId, SensorReading, SensorScan


SENSOR_SCAN_VERSION = 3
SENSOR_SCAN_TYPE = "sensor_scan"
_PACKET_FIELDS = {"version", "type", "cycle_id", "readings"}
_READING_FIELDS = {"sensor_id", "distance_mm", "valid", "sample_time_ms"}


def parse_sensor_scan_packet(raw_packet: object) -> Optional[SensorScan]:
    """Parse one complete scan, returning ``None`` for unsupported input.

    The target packet contains exactly S1, S2, and S3. Extra fields or sensor
    identities—including spare S4—are rejected so architecture drift is
    visible rather than silently ignored.
    """

    payload = _decode_json(raw_packet)
    if not isinstance(payload, dict) or set(payload) != _PACKET_FIELDS:
        return None
    if payload.get("version") != SENSOR_SCAN_VERSION:
        return None
    if payload.get("type") != SENSOR_SCAN_TYPE:
        return None

    cycle_id = _non_negative_integer(payload.get("cycle_id"))
    raw_readings = payload.get("readings")
    if cycle_id is None or not isinstance(raw_readings, list):
        return None

    readings: list[SensorReading] = []
    for raw_reading in raw_readings:
        reading = _parse_reading(raw_reading)
        if reading is None:
            return None
        readings.append(reading)

    try:
        return SensorScan(cycle_id=cycle_id, readings=tuple(readings))
    except (TypeError, ValueError):
        return None


def _parse_reading(raw_reading: object) -> Optional[SensorReading]:
    if not isinstance(raw_reading, dict) or set(raw_reading) != _READING_FIELDS:
        return None

    try:
        sensor_id = SensorId(raw_reading.get("sensor_id"))
    except (TypeError, ValueError):
        return None

    valid = raw_reading.get("valid")
    sample_time_ms = _non_negative_integer(raw_reading.get("sample_time_ms"))
    if not isinstance(valid, bool) or sample_time_ms is None:
        return None

    raw_distance_mm = raw_reading.get("distance_mm")
    if valid:
        distance_mm = _positive_number(raw_distance_mm)
        if distance_mm is None:
            return None
    elif raw_distance_mm is None:
        distance_mm = None
    else:
        return None

    try:
        return SensorReading(
            sensor_id=sensor_id,
            distance_mm=distance_mm,
            valid=valid,
            sample_time_ms=sample_time_ms,
        )
    except (TypeError, ValueError):
        return None


def _decode_json(raw_packet: object) -> object:
    if isinstance(raw_packet, dict):
        return raw_packet
    if isinstance(raw_packet, bytes):
        try:
            raw_packet = raw_packet.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if not isinstance(raw_packet, str):
        return None
    try:
        return json.loads(raw_packet)
    except (json.JSONDecodeError, TypeError):
        return None


def _non_negative_integer(value: object) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _positive_number(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not isfinite(number) or number <= 0.0:
        return None
    return number
