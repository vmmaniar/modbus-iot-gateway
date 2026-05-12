"""Unit tests for the CBOR encoder and 0x7E/length/XOR/0x7F framing.

Verifies that the Python firmware-twin's wire format matches the C firmware's
emitter byte-for-byte, and that the host decoder round-trips correctly.

Reference C code:
  firmware-stm32/Core/Src/cbor_encode.c
  firmware-stm32/Core/Src/bridge_uart.c
  firmware-esp32/main/bridge_rx.c
"""

import unittest

import cbor2

from firmware_twin import (
    cbor_encode_modbus_reading, frame_payload, START_BYTE, END_BYTE,
)
from host_decoder import FrameDecoder, decode_cbor_record


class TestCborEncoder(unittest.TestCase):

    def test_round_trip_with_reference_library(self):
        payload = cbor_encode_modbus_reading(
            label="tank_pressure", slave=1, ts_ms=12345,
            regs=[0x0001, 0x15F5],
        )
        decoded = cbor2.loads(payload)
        self.assertEqual(decoded, {
            "label": "tank_pressure", "slave": 1, "ts_ms": 12345,
            "regs": [1, 0x15F5],
        })

    def test_canonical_byte_layout_short_record(self):
        # Map(4) + tstr "label" + tstr "x" + tstr "slave" + uint 0
        # + tstr "ts_ms" + uint 0 + tstr "regs" + array(0)
        payload = cbor_encode_modbus_reading(label="x", slave=0, ts_ms=0, regs=[])
        # Map of 4 entries: 0xA4
        self.assertEqual(payload[0], 0xA4)
        # "label" is 5 bytes of text: 0x65 + 'label'
        self.assertEqual(payload[1], 0x65)
        self.assertEqual(payload[2:7], b"label")
        # Round-trip must still decode
        self.assertEqual(cbor2.loads(payload)["label"], "x")

    def test_handles_max_125_registers(self):
        regs = list(range(125))
        payload = cbor_encode_modbus_reading("max", 1, 1000, regs)
        decoded = cbor2.loads(payload)
        self.assertEqual(decoded["regs"], regs)


class TestFraming(unittest.TestCase):

    def test_frame_start_and_end_bytes(self):
        framed = frame_payload(b"hello")
        self.assertEqual(framed[0], START_BYTE)
        self.assertEqual(framed[-1], END_BYTE)

    def test_frame_xor_checksum(self):
        framed = frame_payload(b"\x01\x02\x03")
        # xor of payload = 0x01 ^ 0x02 ^ 0x03 = 0x00
        self.assertEqual(framed[-2], 0x00)

        framed2 = frame_payload(b"\x10\x20")
        # xor = 0x30
        self.assertEqual(framed2[-2], 0x30)

    def test_frame_length_little_endian(self):
        framed = frame_payload(b"x" * 256)   # length = 0x0100
        self.assertEqual(framed[1], 0x00)
        self.assertEqual(framed[2], 0x01)


class TestDecoderRoundTrip(unittest.TestCase):

    def test_single_frame_through_decoder(self):
        cbor = cbor_encode_modbus_reading("tank_pressure", 1, 123, [1, 0x15F5])
        framed = frame_payload(cbor)
        dec = FrameDecoder()
        out = dec.feed(framed)
        self.assertEqual(len(out), 1)
        record = decode_cbor_record(out[0])
        self.assertEqual(record.label, "tank_pressure")
        self.assertEqual(record.slave, 1)
        self.assertEqual(record.registers, [1, 0x15F5])

    def test_multiple_concatenated_frames(self):
        f1 = frame_payload(cbor_encode_modbus_reading("a", 1, 100, [1]))
        f2 = frame_payload(cbor_encode_modbus_reading("b", 2, 200, [2, 3]))
        dec = FrameDecoder()
        out = dec.feed(f1 + f2)
        self.assertEqual(len(out), 2)
        self.assertEqual(decode_cbor_record(out[0]).label, "a")
        self.assertEqual(decode_cbor_record(out[1]).label, "b")

    def test_decoder_resilient_to_byte_chunking(self):
        """Feeding one byte at a time must give the same result as feeding all at once."""
        framed = frame_payload(cbor_encode_modbus_reading("chunk", 1, 50, [42]))
        dec = FrameDecoder()
        results = []
        for b in framed:
            r = dec.feed_byte(b)
            if r is not None:
                results.append(r)
        self.assertEqual(len(results), 1)
        self.assertEqual(decode_cbor_record(results[0]).label, "chunk")

    def test_decoder_rejects_xor_corruption(self):
        framed = bytearray(frame_payload(cbor_encode_modbus_reading("x", 1, 0, [0])))
        framed[-2] ^= 0xFF  # corrupt XOR byte
        dec = FrameDecoder()
        out = dec.feed(bytes(framed))
        self.assertEqual(out, [])
        self.assertEqual(dec.xor_errors, 1)
        self.assertEqual(dec.frames_seen, 0)

    def test_decoder_recovers_after_garbage(self):
        good = frame_payload(cbor_encode_modbus_reading("recovered", 1, 0, [99]))
        garbage = b"\x00\xFF\xAB\xCD"  # random junk that doesn't start with 0x7E
        dec = FrameDecoder()
        out = dec.feed(garbage + good)
        self.assertEqual(len(out), 1)
        self.assertEqual(decode_cbor_record(out[0]).label, "recovered")


if __name__ == "__main__":
    unittest.main()
