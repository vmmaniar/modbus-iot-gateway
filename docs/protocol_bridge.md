# Wire protocol: STM32 ↔ ESP32

A simple length-prefixed binary framing wraps a CBOR-encoded telemetry record. CBOR is used (vs JSON) because the STM32 firmware encodes from raw u16 registers and the ESP32 forwards to AWS without re-encoding — saving CPU and bandwidth.

## Frame layout

| Byte    | Meaning                              |
|---------|--------------------------------------|
| 0       | Start of frame: `0x7E`               |
| 1..2    | Payload length (little-endian u16)   |
| 3..N    | CBOR payload                         |
| N+1     | XOR checksum of payload bytes        |
| N+2     | End of frame: `0x7F`                 |

Max payload length: 512 bytes (caps at one Modbus response).

## CBOR record schema

```cbor
{
  "label": tstr,        // human-readable register label
  "slave": u8,          // Modbus slave id (1..247)
  "ts_ms": u32,         // STM32 tick ms since boot
  "regs":  [u16, ...]   // raw register values
}
```

Example (decoded):

```json
{
  "label": "tank_pressure",
  "slave": 1,
  "ts_ms": 158420,
  "regs": [1, 35733]    // u32 BE → 0x000115F5 → 71157 Pa
}
```

## Why CBOR and not JSON?

| Property              | JSON                            | CBOR (this design)        |
|-----------------------|---------------------------------|---------------------------|
| Encoder size on STM32 | 2-4 KB (snprintf chain)         | ~300 bytes (this repo's)  |
| Bytes on the wire     | ~120 for the example above      | ~32                       |
| Type fidelity         | numbers become ASCII            | u16 / u32 preserved       |
| AWS IoT Rules support | Native                          | Via base64 decode in rule |

CBOR is a clear win on the wire and on flash; the cost is one extra step in any IoT Rule that fans the data out to a DynamoDB or Lambda.

## Test plan

* `simulator/fake_slave.py` runs on a host PC and emits known register values.
* The STM32 firmware polls it, encodes CBOR, and frames it.
* Run `simulator/test_bridge_decode.py` to round-trip a recorded UART capture through the decoder.
