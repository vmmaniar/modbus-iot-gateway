#pragma once
#include <stdint.h>
#include <stddef.h>

// Standard Modbus CRC-16 (polynomial 0xA001, init 0xFFFF, LSB-first).
uint16_t crc16_modbus(const uint8_t *data, size_t len);
