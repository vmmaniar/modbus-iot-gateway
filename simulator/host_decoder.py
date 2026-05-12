"""Python twin of the ESP32 bridge-RX state machine.

Re-implements `firmware-esp32/main/bridge_rx.c` so we can decode framed CBOR
records produced by the firmware-twin (or, later, captured from a real STM32
on a UART tap) on the host. Used by:

  * tests/test_end_to_end.py — round-trip verification
  * tools/dump_uart.py        — live decode of UART captures (future)

The state machine is byte-fed and stateful, identical to the C version.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Callable

import cbor2

# ---------------------------------------------------------------------------
# Frame state machine — mirrors bridge_rx.c
# ---------------------------------------------------------------------------

START_BYTE = 0x7E
END_BYTE   = 0x7F
MAX_PAYLOAD = 512


class _State(enum.Enum):
    IDLE     = 0
    LEN_LO   = 1
    LEN_HI   = 2
    PAYLOAD  = 3
    XOR      = 4
    END      = 5


@dataclass
class DecodedRecord:
    """Decoded form of a CBOR record from the gateway."""
    label: str
    slave: int
    ts_ms: int
    registers: list[int]


class FrameDecoder:
    """Byte-fed parser. Calls `on_payload(bytes)` for each complete frame."""

    def __init__(self, on_payload: Callable[[bytes], None] | None = None) -> None:
        self._state = _State.IDLE
        self._payload = bytearray()
        self._expected_len = 0
        self._xor = 0
        self.on_payload = on_payload
        self.frames_seen = 0
        self.xor_errors  = 0
        self.framing_errors = 0

    def feed_byte(self, b: int) -> bytes | None:
        """Feed one byte. Returns the payload if a complete frame was decoded."""
        if self._state == _State.IDLE:
            if b == START_BYTE:
                self._payload.clear()
                self._xor = 0
                self._state = _State.LEN_LO
        elif self._state == _State.LEN_LO:
            self._expected_len = b
            self._state = _State.LEN_HI
        elif self._state == _State.LEN_HI:
            self._expected_len |= b << 8
            if self._expected_len == 0 or self._expected_len > MAX_PAYLOAD:
                self.framing_errors += 1
                self._state = _State.IDLE
            else:
                self._state = _State.PAYLOAD
        elif self._state == _State.PAYLOAD:
            self._payload.append(b)
            self._xor ^= b
            if len(self._payload) >= self._expected_len:
                self._state = _State.XOR
        elif self._state == _State.XOR:
            if b != (self._xor & 0xFF):
                self.xor_errors += 1
                self._state = _State.IDLE
            else:
                self._state = _State.END
        elif self._state == _State.END:
            if b == END_BYTE:
                payload = bytes(self._payload)
                self.frames_seen += 1
                if self.on_payload is not None:
                    self.on_payload(payload)
                self._state = _State.IDLE
                return payload
            else:
                self.framing_errors += 1
                self._state = _State.IDLE
        return None

    def feed(self, chunk: bytes) -> list[bytes]:
        """Feed many bytes. Returns list of complete frames in this chunk."""
        out = []
        for b in chunk:
            frame = self.feed_byte(b)
            if frame is not None:
                out.append(frame)
        return out


def decode_cbor_record(payload: bytes) -> DecodedRecord:
    """Decode a CBOR-encoded telemetry record into a typed dataclass."""
    obj = cbor2.loads(payload)
    if not isinstance(obj, dict):
        raise ValueError(f"expected CBOR map, got {type(obj).__name__}")
    return DecodedRecord(
        label=obj["label"],
        slave=obj["slave"],
        ts_ms=obj["ts_ms"],
        registers=list(obj["regs"]),
    )
