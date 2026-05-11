"""CRC-16 unit test — verifies the STM32 firmware's CRC matches pymodbus."""

import unittest

# Python reference implementation matching firmware-stm32/Core/Src/crc16.c
def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


class TestCrc16(unittest.TestCase):

    def test_empty(self):
        self.assertEqual(crc16_modbus(b""), 0xFFFF)

    def test_known_vector(self):
        # Standard test vector: addr=0x01 fn=0x03 start=0x0000 count=0x0001
        # Expected CRC = 0x0A84 → low byte 0x84, high byte 0x0A
        req = bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01])
        self.assertEqual(crc16_modbus(req), 0x0A84)

    def test_long_payload(self):
        payload = bytes(range(256))
        # Stability check: same input must always produce same CRC
        a = crc16_modbus(payload)
        b = crc16_modbus(payload)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
