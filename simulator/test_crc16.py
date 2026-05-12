"""CRC-16-Modbus tests — verifies our implementation against known vectors and
a fuzz comparison to the reference `crcmod` library.

This is the unit-test gate referenced by BUILD_PLAN.md §7.1:
   "Every random byte string matches reference (crcmod)."
"""

import random
import unittest

import crcmod

from firmware_twin import crc16_modbus


# crcmod's canonical Modbus CRC: poly 0x18005, init 0xFFFF, reflected, no xor-out
_crcmod_ref = crcmod.mkCrcFun(poly=0x18005, initCrc=0xFFFF, rev=True, xorOut=0x0000)


class TestCrc16(unittest.TestCase):

    def test_empty(self):
        self.assertEqual(crc16_modbus(b""), 0xFFFF)

    def test_known_vector(self):
        # addr=0x01 fn=0x03 start=0x0000 count=0x0001 → CRC = 0x0A84
        req = bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01])
        self.assertEqual(crc16_modbus(req), 0x0A84)
        self.assertEqual(crc16_modbus(req), _crcmod_ref(req))

    def test_long_payload_stability(self):
        payload = bytes(range(256))
        a = crc16_modbus(payload)
        b = crc16_modbus(payload)
        self.assertEqual(a, b)

    def test_fuzz_against_crcmod(self):
        """1000 random payloads, length 0-1024. Our CRC must equal crcmod's."""
        rng = random.Random(0xC0FFEE)
        for _ in range(1000):
            n = rng.randint(0, 1024)
            data = bytes(rng.randint(0, 255) for _ in range(n))
            self.assertEqual(crc16_modbus(data), _crcmod_ref(data),
                             f"mismatch on payload of length {n}")


if __name__ == "__main__":
    unittest.main()
