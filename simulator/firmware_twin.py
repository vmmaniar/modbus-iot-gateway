"""Python twin of the STM32 firmware (`firmware-stm32/Core/Src/`).

Re-implements the application logic in Python so we can validate the protocol
chain end-to-end *before* flashing a real board:

  - Modbus RTU master polling (transport-pluggable: serial RTU or TCP)
  - CRC-16-Modbus  (matches Core/Src/crc16.c)
  - CBOR record encoding   (matches Core/Src/cbor_encode.c)
  - 0x7E/length/payload/XOR/0x7F framing  (matches Core/Src/bridge_uart.c)

The twin is used both as a development aid (you can wire it up to mosquitto
and see telemetry flowing today) and as the source-of-truth for the
integration test in test_end_to_end.py.

If the C code changes, the corresponding Python code here must change too.
"""

from __future__ import annotations

import dataclasses
import struct
import time
from typing import Callable, Iterable, Iterator, Protocol

from pymodbus.client import ModbusTcpClient, ModbusSerialClient

# ---------------------------------------------------------------------------
# CRC-16-Modbus (firmware-stm32/Core/Src/crc16.c equivalent)
# ---------------------------------------------------------------------------

def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


# ---------------------------------------------------------------------------
# CBOR encoder (firmware-stm32/Core/Src/cbor_encode.c equivalent)
# Hand-rolled, byte-for-byte compatible with the firmware's emitter.
# ---------------------------------------------------------------------------

_MT_UINT  = 0x00
_MT_TSTR  = 0x60
_MT_ARRAY = 0x80
_MT_MAP   = 0xA0


def _emit_type_argument(major: int, value: int) -> bytes:
    if value < 24:
        return bytes([major | value])
    if value <= 0xFF:
        return bytes([major | 24, value])
    if value <= 0xFFFF:
        return bytes([major | 25]) + value.to_bytes(2, "big")
    if value <= 0xFFFFFFFF:
        return bytes([major | 26]) + value.to_bytes(4, "big")
    raise ValueError(f"value too large: {value}")


def _emit_text(s: str) -> bytes:
    payload = s.encode("utf-8")
    return _emit_type_argument(_MT_TSTR, len(payload)) + payload


def cbor_encode_modbus_reading(label: str, slave: int, ts_ms: int,
                               regs: Iterable[int]) -> bytes:
    """Emit the exact 4-key map produced by cbor_encode.c."""
    regs = list(regs)
    out = _emit_type_argument(_MT_MAP, 4)
    out += _emit_text("label") + _emit_text(label)
    out += _emit_text("slave") + _emit_type_argument(_MT_UINT, slave)
    out += _emit_text("ts_ms") + _emit_type_argument(_MT_UINT, ts_ms)
    out += _emit_text("regs")  + _emit_type_argument(_MT_ARRAY, len(regs))
    for r in regs:
        out += _emit_type_argument(_MT_UINT, r)
    return out


# ---------------------------------------------------------------------------
# Bridge framing (firmware-stm32/Core/Src/bridge_uart.c equivalent)
# ---------------------------------------------------------------------------

START_BYTE = 0x7E
END_BYTE   = 0x7F


def frame_payload(payload: bytes) -> bytes:
    """Wrap a CBOR record in the 0x7E/len/payload/XOR/0x7F frame."""
    if len(payload) > 0xFFFF:
        raise ValueError("payload too long")
    xor_sum = 0
    for b in payload:
        xor_sum ^= b
    return (bytes([START_BYTE])
            + len(payload).to_bytes(2, "little")
            + payload
            + bytes([xor_sum & 0xFF, END_BYTE]))


# ---------------------------------------------------------------------------
# Poll table (matches the s_poll_table in firmware-stm32/Core/Src/main.c)
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class PollEntry:
    slave_id: int
    start_register: int
    register_count: int
    poll_interval_ms: int
    label: str


DEFAULT_POLL_TABLE: tuple[PollEntry, ...] = (
    PollEntry(slave_id=1, start_register=0x0000, register_count=2,
              poll_interval_ms=500,  label="tank_pressure"),
    PollEntry(slave_id=1, start_register=0x0010, register_count=1,
              poll_interval_ms=1000, label="ambient_temp"),
    PollEntry(slave_id=2, start_register=0x0020, register_count=4,
              poll_interval_ms=2000, label="flow_meter"),
)


# ---------------------------------------------------------------------------
# Transport abstraction — the firmware always uses RTU-over-RS485, but the
# twin can additionally talk Modbus TCP for cable-free testing on one machine.
# ---------------------------------------------------------------------------

class Transport(Protocol):
    """Minimal interface the master needs from a Modbus client."""

    def read_holding(self, slave: int, address: int, count: int) -> list[int] | None:
        ...

    def close(self) -> None:
        ...


class TcpTransport:
    def __init__(self, host: str, port: int) -> None:
        self.client = ModbusTcpClient(host=host, port=port, timeout=1.0)
        if not self.client.connect():
            raise ConnectionError(f"could not connect to Modbus TCP {host}:{port}")

    def read_holding(self, slave: int, address: int, count: int) -> list[int] | None:
        rr = self.client.read_holding_registers(address=address, count=count,
                                                device_id=slave)
        if rr.isError():
            return None
        return list(rr.registers)

    def close(self) -> None:
        self.client.close()


class SerialTransport:
    """RTU over a real or virtual serial port — mirrors the STM32 firmware path."""

    def __init__(self, port: str, baudrate: int = 9600) -> None:
        self.client = ModbusSerialClient(
            port=port, baudrate=baudrate, parity="N", stopbits=1, bytesize=8,
            framer="rtu", timeout=0.5,
        )
        if not self.client.connect():
            raise ConnectionError(f"could not open serial port {port}")

    def read_holding(self, slave: int, address: int, count: int) -> list[int] | None:
        rr = self.client.read_holding_registers(address=address, count=count,
                                                device_id=slave)
        if rr.isError():
            return None
        return list(rr.registers)

    def close(self) -> None:
        self.client.close()


# ---------------------------------------------------------------------------
# Master loop
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class TwinReading:
    entry: PollEntry
    timestamp_ms: int
    registers: list[int]

    def to_framed_cbor(self) -> bytes:
        cbor = cbor_encode_modbus_reading(
            label=self.entry.label, slave=self.entry.slave_id,
            ts_ms=self.timestamp_ms, regs=self.registers,
        )
        return frame_payload(cbor)


def run_master(transport: Transport,
               *,
               poll_table: tuple[PollEntry, ...] = DEFAULT_POLL_TABLE,
               max_readings: int | None = None,
               clock_ms: Callable[[], int] | None = None) -> Iterator[TwinReading]:
    """Generator that yields readings one at a time as they're polled.

    Mirrors the modbus_master_task in firmware-stm32/Core/Src/main.c. Tests
    that need bounded iteration pass `max_readings`; otherwise this runs
    indefinitely.
    """
    if clock_ms is None:
        t_start = time.monotonic()
        clock_ms = lambda: int((time.monotonic() - t_start) * 1000)

    next_poll: list[int] = [0] * len(poll_table)
    produced = 0
    while True:
        now = clock_ms()
        for i, entry in enumerate(poll_table):
            if now < next_poll[i]:
                continue
            regs = transport.read_holding(entry.slave_id,
                                          entry.start_register,
                                          entry.register_count)
            next_poll[i] = now + entry.poll_interval_ms
            if regs is None:
                continue
            yield TwinReading(entry=entry, timestamp_ms=now, registers=regs)
            produced += 1
            if max_readings is not None and produced >= max_readings:
                return
        # In the firmware the FreeRTOS scheduler does this; here we just sleep.
        time.sleep(0.01)
