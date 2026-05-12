# Build Plan — Industrial Modbus-RTU → MQTT IoT Gateway

> **Scope:** software + CAD only. The deliverable is a complete design package — firmware that compiles in CI, a cloud stack that runs end-to-end on a laptop, and KiCad schematic + PCB files that a fab house could pick up and build. **No physical hardware, no soldering, no procurement.**

> **Owner:** Vansh Mehul Maniar — Electronics & Instrumentation, BITS Pilani Goa

> **Status of Phase 0** (host-side Python twin): ✓ complete — 17 pytest tests passing in ~4 s, CI gating on every push.

---

## 1. Executive summary

A complete *paper* gateway: every artefact a real industrial product would have — firmware (STM32 + ESP32), broker/cloud (Mosquitto + InfluxDB + Grafana), schematic + PCB layout — exists in this repo and is verified by automation. The artefact you can demo today is reproducible with two commands:

```bash
cd simulator && pytest -v                   # 17/17 green
docker compose --profile demo up            # full broker + database + dashboard
```

The KiCad project (Phase 4-5) is the design artefact you would hand to a fab. Nothing gets manufactured in this plan — but a recruiter or hiring manager can clone the repo, open the schematic in KiCad, see the netlist, run the firmware locally against a simulated PLC, and watch real telemetry stream into a Grafana dashboard. That's the demo.

**Time estimate:** 4–5 weeks of evening work for one person.
**Cost:** ₹0 — everything is open source (KiCad, Mosquitto, InfluxDB OSS, Grafana OSS, Python, ESP-IDF, gcc-arm-none-eabi).

## 2. What's in, what's out

| Capability | In | Out |
|---|---|---|
| Modbus RTU master logic | ✓ STM32 firmware (compiled in CI) + Python twin | — |
| Modbus TCP master logic | ✓ Python twin (for software-only demos) | — |
| RS-485 PHY signalling | ✓ schematic + PCB net design | ✗ real RS-485 driver IC, real cable |
| Wi-Fi + MQTT bridge | ✓ ESP-IDF code, compiled in CI | ✗ real Wi-Fi connection (uses local broker) |
| TLS to broker | ✓ Mosquitto with self-signed certs, full handshake exercised | ✗ AWS IoT Core production endpoint |
| AWS IoT cloud | Skipped: replaced with local Mosquitto + InfluxDB | ✗ |
| Observability | ✓ Grafana dashboard fed by InfluxDB via Telegraf | — |
| Schematic | ✓ KiCad 8 project with hierarchical sheets | — |
| PCB layout | ✓ KiCad 8 4-layer layout, DRC clean, Gerber export | ✗ fabrication, soldering, assembly |
| BOM | ✓ CSV with manufacturer P/N + library symbols | ✗ procurement |
| Test infrastructure | ✓ pytest + GitHub Actions CI on every push | — |

**Why this scope makes sense.** A complete design package is what most embedded engineering job interviews care about — proving you can architect, specify, and implement a system, not that you can solder. The artefact this plan produces is more reproducible (and more easily reviewed by a hiring panel) than a physical board sitting on your desk.

## 3. Phase-by-phase plan

> All phases are sequenced for solo execution. Where two phases can run in parallel, that's flagged.

### Phase 0 — Python twin & end-to-end software loop  ✓ COMPLETE

**Deliverable.** `cd simulator && pytest -v` runs 17 tests in <5 s, exercising:
- CRC-16-Modbus fuzz comparison against `crcmod` (1000 random payloads)
- CBOR encoder byte-equivalence to `cbor2` reference
- 0x7E/length/XOR/0x7F framing protocol with full state-machine recovery testing
- A live `tcp_slave` simulator → `firmware_twin` master → frame decoder → typed records round-trip

**What landed:** `simulator/firmware_twin.py`, `simulator/host_decoder.py`, `simulator/tcp_slave.py`, three pytest modules, pinned `pymodbus==3.13.0`, GitHub Actions CI. See [commit a3866dd](https://github.com/vmmaniar/modbus-iot-gateway/commit/a3866dd) and the `simulator/` README section.

### Phase 1 — STM32 firmware buildable in CI (Week 1, ~10 hrs)

**Deliverable.** `make -j` in `firmware-stm32/` produces a valid `.elf` + `.bin` inside the GitHub Actions runner. The firmware is never flashed; the build artefact proves the C compiles, links, and fits inside the STM32F103C8's flash budget (64 KB).

| # | Subtask | Hours |
|---|---------|-------|
| 1.1 | Vendor a minimal CMSIS-Core (no HAL needed — the existing code is bare-metal register access) into `firmware-stm32/Drivers/CMSIS/`. Source: ARM's [CMSIS-Core release on GitHub](https://github.com/ARM-software/CMSIS_5). | 2 |
| 1.2 | Vendor FreeRTOS kernel sources into `firmware-stm32/Middlewares/FreeRTOS/`. Use the CMSIS-RTOS2 API wrapper for portability. Configure `FreeRTOSConfig.h` for Cortex-M3 + tickless idle. | 3 |
| 1.3 | Write a minimal `STM32F103C8Tx_FLASH.ld` linker script + `startup_stm32f103xb.s` startup file. Both are <100 lines; cribbed from the ST CubeIDE templates and committed in-repo. | 2 |
| 1.4 | Add the `stm32-firmware-build` job to `.github/workflows/ci.yml` — installs `gcc-arm-none-eabi` and runs `make -j`. Fails the build on warnings (`-Werror`). | 1 |
| 1.5 | Add `arm-none-eabi-size` output to the CI summary so we track flash/RAM usage over time. Soft-cap: flash <40 KB, RAM <12 KB (well under the F103C8's 64 KB / 20 KB limits). | 1 |
| 1.6 | Static analysis: add `cppcheck` to CI with the embedded profile. Fail on errors (warnings allowed for now). | 1 |

**Verification.** The CI badge on `README.md` shows green. The build summary panel shows: `text: 23456 bytes, data: 412 bytes, bss: 4123 bytes`. The `cppcheck` step reports zero errors.

### Phase 2 — STM32 firmware emulated in Renode (Week 1–2, ~12 hrs, optional but high-value)

**Deliverable.** The compiled firmware runs in [Renode](https://renode.io/) (the open-source ARM emulator from Antmicro) with a virtual UART connected to `simulator/firmware_twin.py`. End-to-end Modbus polling happens entirely in software — STM32 code executes on emulated hardware against the real Python simulator.

| # | Subtask | Hours |
|---|---------|-------|
| 2.1 | Install Renode 1.14 LTS. Verify with their built-in `stm32f103` test platform. | 1 |
| 2.2 | Write `emulation/stm32_modbus.resc` script that loads the Blue Pill peripheral set, attaches the firmware ELF, and bridges USART1 + USART2 to host TCP sockets. | 4 |
| 2.3 | Glue script `emulation/run_renode_test.py` that spins up Renode + the Python TCP simulator + a UART-bridge consumer for USART2, asserts a complete CBOR record arrives within 5 seconds. | 4 |
| 2.4 | Wire this into CI as a separate `renode-emulation` job. Renode has a headless mode (`--disable-xwt`) suitable for CI. | 2 |
| 2.5 | Document the Renode workflow in `docs/emulation.md` so reviewers can run the same loop on their laptops. | 1 |

**Verification.** `python emulation/run_renode_test.py` returns 0 in CI. The test asserts: a Modbus request frame is observed on the emulated USART1, the slave (Python simulator) responds, the response CRC validates, the CBOR encoder runs, and the framed record appears on USART2 within the time budget.

### Phase 3 — ESP32 firmware buildable in CI (Week 2, ~8 hrs)

**Deliverable.** `idf.py build` runs inside a Dockerized ESP-IDF v5.4 LTS container in CI and produces a valid `.bin`.

| # | Subtask | Hours |
|---|---------|-------|
| 3.1 | Use the official `espressif/idf:v5.4` Docker image in a `.github/workflows/esp-idf-build.yml` workflow. | 2 |
| 3.2 | Pin `esp_mqtt_client` version via `idf_component_manager.yml`. | 1 |
| 3.3 | Add host-runnable unit tests for `bridge_rx.c`'s state machine using ESP-IDF's host-test framework (Unity + Linux target). Test cases mirror the Python `host_decoder` test suite. | 4 |
| 3.4 | Static analysis: enable `clang-tidy` via the ESP-IDF toolchain. | 1 |

**Verification.** CI green. Binary size is reported in the workflow summary. Host-test job reports `0 failures` for the state-machine tests.

### Phase 4 — KiCad 8 schematic (Week 2–3, ~15 hrs)

**Deliverable.** Hierarchical schematic in `hardware/kicad/`, ERC clean, exporting to PDF. Three hierarchical sheets:

1. **Power input + protection + LDOs** — 24 V input, polyfuse, reverse-polarity diode, LM2596 buck to 5 V, two AMS1117-3V3 LDOs (one each side of the iso barrier).
2. **Digital core** — STM32F103 with HSE crystal, ESP32-WROOM-32E, USART bridge between them, SWD + USB-C headers.
3. **Isolated RS-485 front-end** — ADM2587E, PESD3V3 TVS, 120 Ω termination, 680 Ω fail-safe bias resistors, Phoenix screw terminal.

| # | Subtask | Hours |
|---|---------|-------|
| 4.1 | Install KiCad 8 (free, open source). Set up the project at `hardware/kicad/modbus-iot-gateway.kicad_pro`. | 1 |
| 4.2 | Install symbol libraries: KiCad's built-in `MCU_ST_STM32F1` and `RF_Module` (for ESP32), plus `Analog_ADC` for ADM2587E. Add `digikey-kicad-library` if needed for ADM2587E. | 1 |
| 4.3 | Capture Sheet 1 (Power). 9 components + connectors. | 3 |
| 4.4 | Capture Sheet 2 (Digital). ~30 components — both MCUs, decoupling caps, crystal, pull-ups, headers. | 5 |
| 4.5 | Capture Sheet 3 (RS-485 frontend). ~10 components. | 2 |
| 4.6 | Hierarchical sheet wiring — ensure all signal names match across sheet pins. | 1 |
| 4.7 | Run ERC. Fix every error, classify remaining warnings (e.g. unconnected nets on debug headers are OK if explicitly marked). | 2 |

**Verification.** ERC clean. PDF export checked into `hardware/kicad/exports/schematic.pdf`.

### Phase 5 — KiCad 8 PCB layout (Week 3–4, ~25 hrs)

**Deliverable.** 4-layer PCB, ~80 × 60 mm, DRC clean against JLCPCB's JLC04161H-7628 design rules, Gerbers + drill + pick-and-place + BOM exported to `hardware/kicad/exports/`.

| # | Subtask | Hours |
|---|---------|-------|
| 5.1 | Stackup: Signal / GND / 3V3 / Signal (4-layer, 1.6 mm). Set in Board Setup → Physical Stackup. | 1 |
| 5.2 | Define design rules: 5 mil/5 mil trace+space, 0.3 mm drill, 0.6 mm via. Set isolation slot (8 mm) and creepage zone keep-outs. | 2 |
| 5.3 | Place components — ICs on top layer per `schematic_notes.md`. ADM2587E straddles the iso barrier slot. ESP32 antenna corner has 5 mm copper-keepout per Espressif AN. | 4 |
| 5.4 | Route in order: (a) RS-485 differential pair (100 Ω diff), (b) USB-C diff pair, (c) 24 V & 5 V power, (d) crystal traces (short, shielded), (e) bridge UART, (f) everything else. | 12 |
| 5.5 | Pour ground + 3V3 polygons. Stitch with thermal-relieved vias on every IC GND pin. | 2 |
| 5.6 | Add fiducials (3 each side), board outline cutouts (M3 mounting holes × 4), and silkscreen labels for all test points + connectors. | 2 |
| 5.7 | Run DRC. Iterate to clean. | 1 |
| 5.8 | Export Gerbers (RS-274X), drill (Excellon), pick-and-place CSV, BOM CSV. Zip into `exports/gerbers.zip` and check in. | 1 |

**Verification.** DRC clean. Gerber zip opens correctly in `gerbv`. PDF of board top + bottom checked into `exports/`.

### Phase 6 — Local cloud stack (Week 4, ~8 hrs)

**Deliverable.** `docker compose up` brings up a complete TLS-secured broker + time-series DB + dashboard, with the Python firmware-twin publishing real CBOR telemetry into the pipeline.

| # | Subtask | Hours |
|---|---------|-------|
| 6.1 | `docker/mosquitto/` — Mosquitto 2.x with self-signed TLS certs generated by an `init-certs.sh` script. Configured for client-cert auth (mirrors AWS IoT Core's mTLS model). | 2 |
| 6.2 | `docker/telegraf/telegraf.conf` — MQTT consumer plugin subscribes to `iot/+/telemetry`, base64-decodes the CBOR payload, ships to InfluxDB. | 2 |
| 6.3 | `docker/influxdb/` — InfluxDB 2.7 with a `nilm` bucket (wrong name kept consistent with the NILM project for muscle-memory). 14-day retention. | 1 |
| 6.4 | `docker/grafana/provisioning/` — auto-loaded dashboard showing pressure / temperature / flow time-series, identical layout to the deployed-at-AWS version this would replace. | 2 |
| 6.5 | `docker/producer/` — small Python service (Dockerfile + entrypoint) that imports `simulator.firmware_twin`, runs the master loop in a container, and publishes CBOR frames to the broker over TLS. The producer is the "firmware twin acting as a real gateway in production". | 1 |

**Verification.** `docker compose up` brings everything up. Browse to `localhost:3000`, the dashboard auto-loads and shows live data within 30 seconds.

### Phase 7 — Polish for resume / portfolio (Week 5, ~6 hrs)

**Deliverable.** A repo that an interviewer can clone, run `docker compose up`, and instantly understand the scope of what was built.

| # | Subtask | Hours |
|---|---------|-------|
| 7.1 | Top-of-README screenshot of the Grafana dashboard showing live telemetry. | 1 |
| 7.2 | Top-of-README screenshot of the KiCad PCB top layer. | 1 |
| 7.3 | Animated GIF (use `terminalizer` or `vhs`) of `pytest -v` running green + `docker compose up` bringing up the stack. | 2 |
| 7.4 | Architecture diagram (Mermaid or PlantUML, rendered to PNG and committed). | 1 |
| 7.5 | Update resume bullets per §10. | 1 |

**Verification.** A non-technical reader can scroll the README in 30 seconds and grasp what was built; a technical reader can clone and run in 5 minutes.

## 4. Repository layout (final)

```
modbus-iot-gateway/
├── .github/workflows/
│   ├── ci.yml                       # Phase 0+1+3 jobs
│   └── kicad-checks.yml             # ERC/DRC in CI (Phase 4/5)
├── BUILD_PLAN.md                    # this file
├── README.md                        # top-level overview + demos
├── docker-compose.yml               # full local stack (Phase 6)
├── docker/
│   ├── mosquitto/                   # broker + TLS certs
│   ├── telegraf/                    # MQTT → InfluxDB
│   ├── influxdb/                    # time-series DB
│   ├── grafana/                     # dashboard provisioning
│   └── producer/                    # Python firmware-twin in a container
├── docs/
│   ├── architecture.md              # system block diagram
│   ├── aws_iot_provisioning.md      # how to swap local Mosquitto → real AWS IoT
│   ├── emulation.md                 # Renode setup (Phase 2)
│   └── protocol_bridge.md           # STM32↔ESP32 wire format
├── emulation/
│   ├── stm32_modbus.resc            # Renode platform script
│   └── run_renode_test.py           # CI emulation test harness
├── firmware-esp32/                  # ESP-IDF project (Phase 3)
├── firmware-stm32/                  # bare-metal + FreeRTOS (Phase 1)
├── hardware/
│   ├── BOM.md                       # human-readable
│   └── kicad/
│       ├── modbus-iot-gateway.kicad_pro
│       ├── modbus-iot-gateway.kicad_sch  (hierarchical root)
│       ├── sheets/                  # Phase 4 hierarchical sheets
│       ├── modbus-iot-gateway.kicad_pcb  # Phase 5 layout
│       ├── libraries/               # custom symbols/footprints
│       └── exports/                 # PDFs + Gerbers + BOM CSV
└── simulator/                       # Python firmware-twin + tests (Phase 0)
```

## 5. Tools needed (all free / open-source)

| Tool | Why |
|---|---|
| Python 3.11+ | Firmware-twin, simulator, tests |
| Docker Desktop / Docker Engine | Cloud stack (Phase 6) |
| `gcc-arm-none-eabi` | STM32 firmware build (Phase 1) — installed in CI |
| ESP-IDF v5.4 LTS | ESP32 firmware build (Phase 3) — via Docker image |
| Renode 1.14 | Emulation (Phase 2) |
| KiCad 8 | Schematic + PCB (Phase 4–5) |
| Mosquitto 2.x | Local MQTT broker |
| InfluxDB 2.7 + Telegraf + Grafana 11 | Observability stack |
| `cppcheck`, `clang-tidy` | Static analysis in CI |
| `gerbv` | Gerber preview |
| `terminalizer` or `vhs` | Demo GIFs |

## 6. Reference designs and learning resources

* **FreeMODBUS** — canonical open-source Modbus library. The protocol logic in `firmware-stm32/Core/Src/modbus_rtu.c` is a simplified, FreeRTOS-friendly re-implementation. [Repo](https://github.com/cwalter-at/freemodbus).
* **ESP-Modbus library** — Espressif's official Modbus stack. Cross-reference for the ESP32 side, but our architecture explicitly separates Modbus to the STM32 for real-time and security boundary reasons (see §8 ADR).
* **OpenEnergyMonitor's emonHub** — open-source MQTT-to-InfluxDB pipeline; useful pattern reference for Phase 6 even though we use Telegraf instead of emonHub.
* **EclipseFoundation/sparkplug** — industrial MQTT payload spec; CBOR is our chosen alternative for size efficiency but Sparkplug B's schema design is worth studying.
* **Antmicro Renode docs** — [renode.readthedocs.io](https://renode.readthedocs.io/) for the emulation setup.
* **AWS IoT Core Pricing** — [aws.amazon.com/iot-core/pricing](https://aws.amazon.com/iot-core/pricing/) — for when you eventually swap Mosquitto → real AWS.

## 7. Risk register (software-scope)

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| pymodbus 4.0 breaks API again | M | M | Pin `pymodbus==3.13.0`; track release notes. CI catches it on next dependency bump. |
| ESP-IDF v6 GA disrupts CI before we upgrade | L | M | Docker image pins `idf:v5.4` (LTS until 2027). |
| Renode emulation diverges from real STM32 timing | M | L | Renode is for protocol correctness, not timing fidelity. Phase 2 explicitly does not certify timing — that's noted in `docs/emulation.md`. |
| KiCad 9 release changes file format mid-project | L | L | Lock to KiCad 8.0 LTS. File format is text-based S-expressions; future migration is mechanical. |
| Mosquitto's self-signed cert chain confuses Telegraf | M | L | Bundle the CA into the Telegraf container at build time; CI integration test asserts a successful publish. |
| Grafana dashboard becomes stale | L | L | Provision via JSON in source control, not via UI clicks. |
| KiCad DRC pass doesn't catch every real-world fab issue | M | L | DRC is necessary but not sufficient. Document that the PCB is "fab-ready but unfabricated" — the next step (if it ever happens) is JLCPCB's Engineering Question process. |

## 8. Architecture decision records (ADRs)

Short-form decisions that the resume narrative depends on:

### ADR-1: Local Mosquitto instead of AWS IoT Core

**Decision:** Use Mosquitto in Docker as the broker for development; document the AWS IoT swap as a follow-up.

**Reasoning:** AWS IoT Core is a great production target but introduces friction for a portfolio project: an AWS account, certs, IAM policies, a ₹0 Free Tier that nonetheless requires a credit card on file. A local Mosquitto with self-signed TLS certs exercises the same mTLS handshake that AWS IoT requires; swapping endpoint URIs at the end is a 1-line change. Reviewers can clone + run without AWS.

### ADR-2: Dual-MCU (STM32 + ESP32) instead of ESP32-only

**Decision:** Keep the dual-MCU split even though `esp_modbus` could let the ESP32 handle everything.

**Reasoning:** Real industrial gateways have a security boundary between the field bus (Modbus) and the WAN (Wi-Fi/cellular). Splitting MCUs makes that boundary physical, not just architectural. The STM32 has no IP stack and no certs, so a compromised broker can't extract a private key or open a reverse shell into the Modbus side. This is the kind of decision a hiring manager will ask about — having a defensible answer is worth more than the 30 USD of BOM savings.

### ADR-3: KiCad over Altium

**Decision:** Switch the PCB CAD from Altium (mentioned in the resume) to KiCad.

**Reasoning:** Altium's student license requires re-renewal annually and the resulting `.PrjPcb` files aren't easily reviewable on GitHub. KiCad is fully open source, the files are text S-expressions (git-diffable), and KiCad 8 has caught up to Altium for boards of this complexity. The resume's "Altium" claim can stay — the user has Altium experience from coursework — but the project deliverable is KiCad.

### ADR-4: CBOR over JSON for the bridge protocol

**Decision:** Bridge protocol between STM32 ↔ ESP32 is binary CBOR, not JSON.

**Reasoning:** The STM32 has 20 KB of RAM and 64 KB of flash. A JSON encoder pulls in ~3 KB of code; the hand-rolled CBOR encoder in `firmware-stm32/Core/Src/cbor_encode.c` is ~300 bytes. Wire-format size is ~3× smaller. The cost is one base64 decode at the AWS IoT Rules layer (or one CBOR decode in Telegraf), which we handle cleanly.

## 9. Test and verification plan

| Layer | Test | Pass criterion |
|---|---|---|
| CRC-16 | `simulator/test_crc16.py` — known vectors + 1000-payload fuzz vs `crcmod` | All match |
| CBOR encode | `simulator/test_cbor_and_framing.py::TestCborEncoder` | Byte-equivalent to `cbor2` |
| Framing | `simulator/test_cbor_and_framing.py::TestFraming` + `::TestDecoderRoundTrip` | Correct framing, XOR corruption detected, garbage prefix recovered |
| Modbus loop | `simulator/test_end_to_end.py::test_one_cycle_through_decoder` | Each poll-table entry produces a decoded record; pressure ≈ 101 kPa |
| Modbus burst | `simulator/test_end_to_end.py::test_burst_of_readings_remains_intact` | 3 s burst, zero XOR/framing errors |
| STM32 firmware | `make -j -Werror` in CI | Build succeeds; flash <40 KB, RAM <12 KB |
| STM32 cppcheck | CI | Zero errors |
| STM32 Renode | `emulation/run_renode_test.py` (Phase 2) | One full Modbus transaction observed end-to-end on emulated UARTs |
| ESP32 firmware | `idf.py build` in Docker (CI) | Build succeeds |
| ESP32 host-test | `bridge_rx_test.c` Unity tests (Phase 3) | All test cases pass |
| Schematic | KiCad ERC (Phase 4) | Zero errors |
| PCB | KiCad DRC against JLC04161H-7628 (Phase 5) | Zero errors |
| Cloud stack | `docker compose up` + 30 s smoke test (Phase 6) | Live data visible in Grafana |

## 10. Resume bullet drafts

Two bullets in your existing resume format, software-scope:

> • Software-Designed Industrial Gateway: Architected a Modbus-RTU → MQTT gateway as a complete software design package — STM32F103 firmware (bare-metal C, FreeRTOS) compiled in CI, ESP-IDF Wi-Fi bridge, Python firmware twin with 17 pytest tests including 1000-payload CRC fuzz, end-to-end loop verified without hardware.
>
> • Full-Stack Demo: Local docker-compose stack reproduces the production pipeline — Mosquitto with mTLS, Telegraf, InfluxDB 2.7, Grafana — fed by the firmware-twin and visualised on a provisioned dashboard. KiCad 8 schematic + 4-layer PCB layout (ERC/DRC clean, Gerbers exported) complete the design package.

## 11. References

1. [pymodbus 3.13 docs](https://pymodbus.readthedocs.io/en/v3.13.0/)
2. [CMSIS-Core (ARM)](https://github.com/ARM-software/CMSIS_5)
3. [FreeRTOS Kernel](https://github.com/FreeRTOS/FreeRTOS-Kernel)
4. [Modbus over Serial Line v1.02](https://modbus.org/docs/Modbus_over_serial_line_V1_02.pdf)
5. [ST AN3070 — DE signal management](https://www.st.com/resource/en/application_note/an3070-managing-the-driver-enable-signal-for-rs485-and-iolink-communications-with-the-stm32s-usart-stmicroelectronics.pdf)
6. [Renode docs](https://renode.readthedocs.io/)
7. [ESP-IDF v5.4 LTS](https://docs.espressif.com/projects/esp-idf/en/v5.4/get-started/index.html)
8. [Mosquitto 2.x](https://mosquitto.org/documentation/)
9. [InfluxDB 2.7](https://docs.influxdata.com/influxdb/v2.7/)
10. [Grafana 11](https://grafana.com/docs/grafana/latest/)
11. [KiCad 8](https://www.kicad.org/)
12. [RFC 8949 (CBOR)](https://www.rfc-editor.org/rfc/rfc8949.html)
13. [JLCPCB capabilities](https://jlcpcb.com/capabilities/Capabilities)

## 12. Future hardware path (deferred indefinitely)

If you ever decide to fab the board, the Gerbers in `hardware/kicad/exports/gerbers.zip` are submission-ready for JLCPCB's 4-layer JLC04161H-7628 stack-up. Estimated fab cost as of May 2026: ~₹2,800 for qty 5 boards, ~₹4,500 for full assembly with extended-parts library (DRV8323, ADM2587E will be in the extended library and incur a +₹350 setup fee). Total realistic build cost on top of the design package: ~₹15,000 including a Blue Pill, ESP32 dev kit, USB-RS485 dongle, and a Selec MFM384 test target. Not part of this plan's scope.
