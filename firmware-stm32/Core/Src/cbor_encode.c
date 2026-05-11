#include "cbor_encode.h"
#include <string.h>

// CBOR major-type macros (RFC 8949)
#define MT_UINT      0x00
#define MT_TSTR      0x60
#define MT_ARRAY     0x80
#define MT_MAP       0xA0

static size_t emit_type_argument(uint8_t *out, size_t cap, size_t off,
                                 uint8_t major, uint64_t value)
{
    if (value < 24) {
        if (off + 1 > cap) return 0;
        out[off++] = major | (uint8_t)value;
    } else if (value <= 0xFF) {
        if (off + 2 > cap) return 0;
        out[off++] = major | 24;
        out[off++] = (uint8_t)value;
    } else if (value <= 0xFFFF) {
        if (off + 3 > cap) return 0;
        out[off++] = major | 25;
        out[off++] = (uint8_t)(value >> 8);
        out[off++] = (uint8_t)value;
    } else if (value <= 0xFFFFFFFFu) {
        if (off + 5 > cap) return 0;
        out[off++] = major | 26;
        out[off++] = (uint8_t)(value >> 24);
        out[off++] = (uint8_t)(value >> 16);
        out[off++] = (uint8_t)(value >> 8);
        out[off++] = (uint8_t)value;
    } else {
        return 0;
    }
    return off;
}

static size_t emit_text(uint8_t *out, size_t cap, size_t off, const char *s)
{
    size_t len = strlen(s);
    off = emit_type_argument(out, cap, off, MT_TSTR, (uint64_t)len);
    if (off == 0 || off + len > cap) return 0;
    memcpy(&out[off], s, len);
    return off + len;
}

size_t cbor_encode_modbus_reading(uint8_t *out, size_t cap,
                                  const modbus_poll_entry_t *entry,
                                  const modbus_response_t *resp)
{
    size_t off = 0;

    // map with 4 entries: label, slave, ts_ms, regs
    off = emit_type_argument(out, cap, off, MT_MAP, 4);
    if (!off) return 0;

    off = emit_text(out, cap, off, "label");          if (!off) return 0;
    off = emit_text(out, cap, off, entry->label);     if (!off) return 0;

    off = emit_text(out, cap, off, "slave");          if (!off) return 0;
    off = emit_type_argument(out, cap, off, MT_UINT, entry->slave_id);
    if (!off) return 0;

    off = emit_text(out, cap, off, "ts_ms");          if (!off) return 0;
    off = emit_type_argument(out, cap, off, MT_UINT, resp->timestamp_ms);
    if (!off) return 0;

    off = emit_text(out, cap, off, "regs");           if (!off) return 0;
    off = emit_type_argument(out, cap, off, MT_ARRAY, resp->register_count);
    if (!off) return 0;
    for (uint16_t i = 0; i < resp->register_count; i++) {
        off = emit_type_argument(out, cap, off, MT_UINT, resp->registers[i]);
        if (!off) return 0;
    }
    return off;
}
