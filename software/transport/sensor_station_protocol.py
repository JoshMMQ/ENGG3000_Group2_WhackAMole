"""Strict little-endian laptop/station control protocol for S1/S2/S3."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import struct
from typing import Optional


HELLO_MAGIC = 0x57414D48
COMMAND_MAGIC = 0x57414D33
RESULT_MAGIC = 0x57414D53
PROTOCOL_VERSION = 1

S1_INDEX = 1
S2_INDEX = 2
S3_INDEX = 3
SENSOR_INDICES = (S1_INDEX, S2_INDEX, S3_INDEX)

HELLO_FORMAT = "<IBB"
MEASURE_COMMAND_FORMAT = "<IIB"
MEASURE_RESULT_FORMAT = "<IIfIBB"

HELLO_SIZE = struct.calcsize(HELLO_FORMAT)
MEASURE_COMMAND_SIZE = struct.calcsize(MEASURE_COMMAND_FORMAT)
MEASURE_RESULT_SIZE = struct.calcsize(MEASURE_RESULT_FORMAT)

STATION_CONTROL_PORT = 5006
UINT32_MAX = 0xFFFFFFFF


@dataclass(frozen=True)
class StationHello:
    sensor_index: int


@dataclass(frozen=True)
class MeasureCommand:
    cycle_id: int
    target_sensor_index: int


@dataclass(frozen=True)
class MeasureResult:
    cycle_id: int
    distance_mm: float
    command_to_sample_us: int
    valid: bool
    sensor_index: int


def encode_hello(sensor_index: int) -> bytes:
    """Encode a station heartbeat/registration datagram."""

    return struct.pack(
        HELLO_FORMAT,
        HELLO_MAGIC,
        PROTOCOL_VERSION,
        _require_sensor_index(sensor_index),
    )


def decode_hello(packet: object) -> Optional[StationHello]:
    """Decode a hello only when its complete binary contract is valid."""

    values = _unpack_exact(HELLO_FORMAT, HELLO_SIZE, packet)
    if values is None:
        return None
    magic, version, sensor_index = values
    if (
        magic != HELLO_MAGIC
        or version != PROTOCOL_VERSION
        or sensor_index not in SENSOR_INDICES
    ):
        return None
    return StationHello(sensor_index=sensor_index)


def encode_measure_command(cycle_id: int, target_sensor_index: int) -> bytes:
    """Encode one command for exactly one active station."""

    return struct.pack(
        MEASURE_COMMAND_FORMAT,
        COMMAND_MAGIC,
        _require_uint32(cycle_id, "cycle_id"),
        _require_sensor_index(target_sensor_index),
    )


def decode_measure_command(packet: object) -> Optional[MeasureCommand]:
    """Decode a measure command using the exact nine-byte layout."""

    values = _unpack_exact(MEASURE_COMMAND_FORMAT, MEASURE_COMMAND_SIZE, packet)
    if values is None:
        return None
    magic, cycle_id, target_sensor_index = values
    if magic != COMMAND_MAGIC or target_sensor_index not in SENSOR_INDICES:
        return None
    return MeasureCommand(
        cycle_id=cycle_id,
        target_sensor_index=target_sensor_index,
    )


def encode_measure_result(
    cycle_id: int,
    distance_mm: float,
    command_to_sample_us: int,
    valid: bool,
    sensor_index: int,
) -> bytes:
    """Encode one station result using the exact eighteen-byte layout."""

    if isinstance(distance_mm, bool) or not isinstance(distance_mm, (int, float)):
        raise ValueError("distance_mm must be a finite number")
    normalized_distance = float(distance_mm)
    if not isfinite(normalized_distance):
        raise ValueError("distance_mm must be a finite number")
    if not isinstance(valid, bool):
        raise TypeError("valid must be a bool")

    return struct.pack(
        MEASURE_RESULT_FORMAT,
        RESULT_MAGIC,
        _require_uint32(cycle_id, "cycle_id"),
        normalized_distance,
        _require_uint32(command_to_sample_us, "command_to_sample_us"),
        int(valid),
        _require_sensor_index(sensor_index),
    )


def decode_measure_result(packet: object) -> Optional[MeasureResult]:
    """Decode a result and reject malformed values at the wire boundary."""

    values = _unpack_exact(MEASURE_RESULT_FORMAT, MEASURE_RESULT_SIZE, packet)
    if values is None:
        return None
    (
        magic,
        cycle_id,
        distance_mm,
        command_to_sample_us,
        valid,
        sensor_index,
    ) = values
    if (
        magic != RESULT_MAGIC
        or not isfinite(distance_mm)
        or valid not in (0, 1)
        or sensor_index not in SENSOR_INDICES
    ):
        return None
    return MeasureResult(
        cycle_id=cycle_id,
        distance_mm=float(distance_mm),
        command_to_sample_us=command_to_sample_us,
        valid=bool(valid),
        sensor_index=sensor_index,
    )


def _unpack_exact(
    packet_format: str,
    expected_size: int,
    packet: object,
) -> Optional[tuple]:
    if not isinstance(packet, (bytes, bytearray, memoryview)):
        return None
    if len(packet) != expected_size:
        return None
    try:
        return struct.unpack(packet_format, packet)
    except struct.error:
        return None


def _require_sensor_index(sensor_index: int) -> int:
    if (
        isinstance(sensor_index, bool)
        or not isinstance(sensor_index, int)
        or sensor_index not in SENSOR_INDICES
    ):
        raise ValueError("sensor_index must be 1, 2, or 3")
    return sensor_index


def _require_uint32(value: int, field_name: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > UINT32_MAX
    ):
        raise ValueError(f"{field_name} must be an unsigned 32-bit integer")
    return value
