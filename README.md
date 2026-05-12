# Industrial Modbus-RTU → MQTT IoT Gateway

A dual-MCU IIoT edge gateway. An STM32F103 polls industrial sensors over RS-485 using the Modbus RTU master protocol; an ESP32 forwards the data to AWS IoT Core over MQTT-TLS. Engineered for industrial deployment: galvanic isolation on the RS-485 port, TVS protection, JTAG/SWD test points, and a 4-layer Altium layout ready for DFM.

## System architecture

```
+----------------+   RS-485    +-------------+   UART     +-------------+   MQTT-TLS   +-------------+
| Modbus slaves  | <---------> | ADM2587E    | <--------> | STM32F103   | <---------> | ESP32-WROOM |
| (PLC sensors,  |  twisted-   | isolator    |  9600-8N1  | Modbus RTU  |  115200     |  Wi-Fi STA  |
|  energy meters)|    pair     | + TVS       |   master   |  master     |             |  + AWS IoT  |
+----------------+             +-------------+            +-------------+             +-------------+
                                                                                            |
                                                                                            v
                                                                                       +---------+
                                                                                       | AWS IoT |
                                                                                       |  Core   |
                                                                                       +---------+
```

* **STM32 layer** runs FreeRTOS with two tasks: a Modbus RTU master that round-robins through a configurable slave table, and a bridge task that frames each reading as a CBOR record and pipes it to the ESP32 over UART.
* **ESP32 layer** runs ESP-IDF, holds AWS IoT certs in NVS, and publishes to `iot/<device-id>/telemetry` over MQTT-TLS on port 8883. Local store-and-forward queue handles brief Wi-Fi outages.
* **Hardware** isolates the RS-485 transceiver from the digital side via an ADM2587E (2.5 kV ground isolation + integrated DC/DC), with PESD3V3 TVS on the differential pair and a self-resetting PTC fuse on the 24 V loop power tap.

## Repository layout

```
firmware-stm32/   STM32CubeIDE project (FreeRTOS, Modbus RTU master, UART bridge)
firmware-esp32/   ESP-IDF project (Wi-Fi + MQTT-TLS to AWS IoT Core)
simulator/        Python pymodbus slave that mimics a real industrial sensor
hardware/         Altium BOM, schematic notes, isolation strategy
docs/             Protocol bridge spec, AWS IoT provisioning, DFM checklist
```

## Quick start

### Phase 0: end-to-end software path (no hardware, no cables)

`simulator/` contains a Python twin of the entire firmware data path — Modbus master polling, CRC-16, CBOR encoding, and the 0x7E/length/XOR/0x7F framing protocol — plus a host-side decoder that mirrors the ESP32's `bridge_rx` state machine. The pytest suite spins up the TCP simulator and drives the full round-trip in software:

```bash
cd simulator
pip install -r requirements.txt
pytest -v                          # 17 tests in <5 s
```

A green run proves: Modbus polling works, the CRC matches the `crcmod` reference for 1000 random payloads, the CBOR encoder is byte-compatible with `cbor2`, the framing checksum and state machine reject corrupted/garbage input correctly, and the simulator's simulated sine-wave pressure values arrive intact through the full chain.

To watch live telemetry without tests:

```bash
python tcp_slave.py --port 5020 &           # background: TCP simulator
python -c "from firmware_twin import *; \
           t = TcpTransport('127.0.0.1', 5020); \
           [print(r.entry.label, r.registers) for r in run_master(t, max_readings=8)]"
```

### Run the RTU simulator (requires a USB-RS485 dongle)

```bash
cd simulator
python fake_slave.py --port COM5  # or /dev/ttyUSB0
```

This launches a Modbus slave at address `0x01` exposing simulated temperature, pressure, and flow registers.

### Build the STM32 firmware

```bash
cd firmware-stm32
make -j  # uses arm-none-eabi-gcc via the included Makefile
make flash  # via st-link or OpenOCD
```

Open in STM32CubeIDE for breakpoint debugging.

### Build the ESP32 firmware

```bash
cd firmware-esp32
idf.py set-target esp32
idf.py menuconfig   # set Wi-Fi creds and AWS IoT endpoint
idf.py build flash monitor
```

You'll also need to provision the device certificate — see [docs/aws_iot_provisioning.md](docs/aws_iot_provisioning.md).

## Full local stack (no AWS account needed)

```bash
docker compose up
```

Brings up Mosquitto (MQTT broker with TLS), Telegraf (MQTT → InfluxDB), InfluxDB 2.7, Grafana (with the gateway dashboard auto-provisioned), the Python TCP slave simulator, and the producer service that runs the firmware-twin as if it were the deployed gateway. Open http://localhost:3000 (admin/admin) and watch telemetry stream into the dashboard within ~30 seconds.

See [BUILD_PLAN.md](BUILD_PLAN.md) for the complete software + KiCad design plan.

## KiCad design package

Open [hardware/kicad/modbus-iot-gateway.kicad_pro](hardware/kicad/) in **KiCad 8**. The project file ships with all design rules and net classes pre-configured (5/5 mil JLCPCB 4-layer rules, 100 Ω RS-485 / 90 Ω USB diff-pair classes, named-net regex matching for power-class routing). The schematic and PCB layout are captured per the comprehensive [hardware/kicad/design_spec.md](hardware/kicad/design_spec.md) — every component, every net, every footprint.

## Why dual-MCU?

* **Security boundary.** Wi-Fi/Internet-facing code lives on the ESP32. The STM32 has no IP stack, no certs, no remote attack surface — it just talks Modbus on a dumb wire.
* **Real-time guarantees.** Modbus RTU has strict 3.5-character inter-frame silence requirements. The STM32 with FreeRTOS gives deterministic timing that you don't get when you cram Wi-Fi onto the same core.
* **Field-serviceable.** The ESP32 can be re-flashed OTA without touching the Modbus side; the STM32 firmware almost never needs to change.

## Hardware highlights

* 4-layer Altium PCB (signal / GND / 3V3 / signal)
* ADM2587E isolated RS-485 with integrated isoPower DC/DC
* PESD3V3L5UY TVS diodes on the A/B differential pair
* Polyfuse on the 24 V input rail with reverse-polarity protection
* JTAG (Cortex-10 pin) + SWD test points
* M3 fixing holes on all four corners, 35 mm DIN-rail snap-fit footprint

See [hardware/BOM.md](hardware/BOM.md) and [hardware/schematic_notes.md](hardware/schematic_notes.md).

## License

MIT — see [LICENSE](LICENSE).
