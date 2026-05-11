#pragma once

#include <stdint.h>
#include <stddef.h>
#include "modbus_rtu.h"

// Minimal CBOR encoder for one telemetry record:
//   { "label": tstr, "slave": u8, "ts_ms": u32, "regs": [u16, u16, ...] }
// Returns the number of bytes written, or 0 on overflow.
size_t cbor_encode_modbus_reading(uint8_t *out, size_t cap,
                                  const modbus_poll_entry_t *entry,
                                  const modbus_response_t *resp);
