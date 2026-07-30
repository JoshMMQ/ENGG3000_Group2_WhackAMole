"""Versioned UDP telemetry packet parsing for ESP32 sensor nodes."""

from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError, loads
from math import isfinite
from typing import Any, Optional


SUPPORTED_PACKET_VERSION = 1


@dataclass(frozen=True)
class SensorReading:
    sensor_id: str
    distance_mm: Optional[int]
    valid: bool


@dataclass(frozen=True)
class TelemetryPacket:
    version: int
    node_id: str
    sequence: int
    sent_ms: int
    readings: tuple[SensorReading, ...]
    battery_mv: Optional[int]
    status: str


def parse_telemetry_packet(raw_packet: object) -> Optional[TelemetryPacket]:
    """Parse a UDP packet payload into validated telemetry.

    Invalid packets return None so the receiver can drop them safely.
    """

    payload = _decode_json(raw_packet)
    if not isinstance(payload, dict):
        return None

    version = _required_int(payload.get("v"))
    if version != SUPPORTED_PACKET_VERSION:
        return None

    node_id = _required_text(payload.get("node_id"))
    sequence = _required_int(payload.get("seq"))
    sent_ms = _required_int(payload.get("sent_ms"))
    status = _required_text(payload.get("status"))
    battery_mv = _optional_int(payload.get("battery_mv"))
    readings = _parse_readings(payload.get("readings"))

    if node_id is None or sequence is None or sent_ms is None or status is None:
        return None
    if sequence < 0 or sent_ms < 0:
        return None
    if battery_mv is not None and battery_mv < 0:
        return None
    if readings is None:
        return None

    return TelemetryPacket(
        version=version,
        node_id=node_id,
        sequence=sequence,
        sent_ms=sent_ms,
        readings=tuple(readings),
        battery_mv=battery_mv,
        status=status,
    )


def _decode_json(raw_packet: object) -> Any:
    if isinstance(raw_packet, bytes):
        try:
            return loads(raw_packet.decode("utf-8"))
        except (UnicodeDecodeError, JSONDecodeError):
            return None
    if isinstance(raw_packet, str):
        try:
            return loads(raw_packet)
        except JSONDecodeError:
            return None
    if isinstance(raw_packet, dict):
        return raw_packet
    return None


def _parse_readings(value: object) -> Optional[list[SensorReading]]:
    if not isinstance(value, list) or not value:
        return None

    readings = []
    for item in value:
        if not isinstance(item, dict):
            return None

        sensor_id = _required_text(item.get("sensor_id"))
        valid = item.get("valid")
        if sensor_id is None or not isinstance(valid, bool):
            return None

        distance_mm = _optional_int(item.get("distance_mm"))
        if valid and (distance_mm is None or distance_mm < 0):
            return None
        if distance_mm is not None and distance_mm < 0:
            return None

        readings.append(SensorReading(sensor_id=sensor_id, distance_mm=distance_mm, valid=valid))

    return readings


def _required_text(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _required_int(value: object) -> Optional[int]:
    number = _optional_int(value)
    return number


def _optional_int(value: object) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number) or number != int(number):
        return None
    return int(number)
