# Build Plan — Industrial Modbus-RTU → MQTT IoT Gateway

> **Owner:** Vansh Mehul Maniar — Electronics & Instrumentation, BITS Pilani Goa
> **Location:** Pune / Goa, India
> **Timeline:** 4–6 weeks (~120–180 focused hours)
> **Status:** Code scaffold complete (see `firmware-stm32/`, `firmware-esp32/`, `simulator/`); hardware unbuilt.
> **Plan revision:** 2026-05-12

---

## 1. Executive summary

This project converts an existing software scaffold (FreeRTOS Modbus-RTU master on STM32, MQTT-TLS bridge on ESP32, pymodbus slave simulator, Altium 4-layer board outline) into a fully working, deployable hardware artefact: a DIN-rail-mountable industrial IoT gateway that polls Modbus-RTU slaves on an isolated RS-485 bus, encodes their registers as CBOR, and forwards them to AWS IoT Core over MQTT-TLS.

**Elevator pitch.** A dual-MCU industrial gateway that lifts data from legacy Modbus-RTU field devices (energy meters, PLCs, flow meters) into AWS IoT Core. The STM32F103 handles deterministic Modbus timing and the ESP32 carries the Wi-Fi / TLS / cloud burden — a clean security and real-time separation, packaged as a 4-layer Altium PCB with 2.5 kV galvanic isolation on the RS-485 port and TVS protection on every exposed pin.

**Success criteria ("done" looks like).**

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | One assembled 4-layer PCB powers up cleanly from 24 V industrial supply | Bench DMM; current draw < 200 mA idle |
| 2 | STM32 polls 3 simulated slaves (`fake_slave.py`) at 9600-8N1 with zero CRC errors over a 1-hour soak | Serial log + counter |
| 3 | ESP32 publishes at least 500 CBOR messages to AWS IoT Core, all decoded server-side | AWS IoT MQTT test client + Lambda CBOR-decode rule |
| 4 | Gateway survives a 1-hour Wi-Fi-down → Wi-Fi-up cycle with store-and-forward buffering | Drop access point, watch ESP32 reconnect; verify no message loss |
| 5 | Gateway successfully polls **one real** Modbus device (Selec MFM384 or equivalent) | Live energy values appear in AWS IoT Console |
| 6 | DFM pass: Altium output package accepted without queries by chosen fab | Fab quote email |
| 7 | Two strong resume bullets backed by repo + photos + scope traces | Resume review |

**Top-line numbers.**

| Bucket | Estimate (INR) |
|--------|----------------|
| BOM (incl. 15% spare buffer) | ~₹6,200 |
| PCB fabrication (5 boards, 4-layer, JLCPCB to India incl. shipping) | ~₹2,800 |
| Real industrial test target (Selec MFM384-R-C) | ~₹3,000 |
| Tools you don't already own (ST-Link clone, USB-RS485, scope probes if needed) | ~₹2,500 |
| AWS IoT Core for the 6-week build window | ₹0 (well inside Free Tier) |
| **Total cash outlay** | **~₹14,500** |

Time estimate: **6 calendar weeks at ~25 hours/week**, single builder, sequenced phases below.

---

## 2. Phase-by-phase breakdown

> All phases assume sequential execution by one person. Where two phases can be parallelised (e.g. waiting on PCBs while writing tests), that is called out.

### Phase 1 — Research + Simulation (Week 0–1, ~25 hrs)

**Deliverable.** Running pymodbus simulator on host, talking to the STM32 firmware compiled in a known-good state. End-to-end software path verified before any solder is melted.

| # | Subtask | Hours | Risk |
|---|---------|-------|------|
| 1.1 | Sanity-check the scaffold compiles: `cd firmware-stm32 && make -j` on Linux/WSL toolchain (arm-none-eabi-gcc 10.x+). | 2 | Missing CMSIS headers — vendor them locally if so. |
| 1.2 | Install ESP-IDF v5.4 LTS via the official installer ([Espressif docs](https://docs.espressif.com/projects/esp-idf/en/v5.4/get-started/index.html)). Confirm `idf.py --version` and `idf.py build` of the `hello_world` sample on a spare ESP32-DevKitC. | 3 | ESP-IDF v6 has corePKCS11 incompatibility for the AWS IoT SDK — pin to v5.4 LTS. |
| 1.3 | Run `simulator/fake_slave.py` against a USB-RS485 dongle on the host. Verify with a generic Modbus master (e.g. `mbpoll` or QModMaster) that registers update as expected. | 4 | pymodbus 3.x has multiple breaking API changes vs. 2.x — `requirements.txt` must pin a version. |
| 1.4 | Read the [esp-modbus library](https://github.com/espressif/esp-modbus) and write a one-page decision memo on dual-MCU vs single-ESP32 (see §5). Keep the dual-MCU choice but document the rationale. | 4 | None — this is reading. |
| 1.5 | Set up an AWS account, claim the 12-month Free Tier, create a Thing `gateway-001` and a test certificate. Verify MQTT publish from a desktop `mosquitto_pub --cert ... --key ...`. | 4 | Region choice: pick `ap-south-1` (Mumbai) for latency; confirm Free Tier applies (it does for all regions except GovCloud — see [AWS IoT pricing](https://aws.amazon.com/iot-core/pricing/)). |
| 1.6 | Read [ST AN3070](https://www.st.com/resource/en/application_note/an3070-managing-the-driver-enable-signal-for-rs485-and-iolink-communications-with-the-stm32s-usart-stmicroelectronics.pdf) (DE signal management) and the [Modbus RTU spec](https://modbus.org/docs/Modbus_over_serial_line_V1_02.pdf) — particularly §2.5 on the 3.5-character silence rule. | 4 | The existing `rs485_uart.c` hard-codes 4 ms silence — verify this is correct for 9600 baud (it is: 3.5 × 1.04 ms ≈ 3.65 ms, but per spec, at >19200 baud the silence is **fixed at 1.75 ms** rather than scaled per character — keep this in mind if you ever raise the baud rate). |
| 1.7 | Order long-lead parts: ADM3251E (or recommended swap, see §3), STM32 Blue Pill, ESP32-DevKitC, MFM384 test target, USB-RS485. | 1 | Robu.in next-day in metros; Mouser India 5–7 days; meter from Indiamart 3–5 days. |
| 1.8 | Write a brief test plan for §7 before any firmware bring-up. | 3 | None. |

**Verification.** `fake_slave.py` running → simulator reachable from QModMaster on the host → AWS Console shows test message from a desktop publisher.

### Phase 2 — STM32 firmware bring-up on Blue Pill (Week 1–2, ~30 hrs)

**Deliverable.** Blue Pill running the scaffold firmware, USART1 connected to a MAX485 module wired to the host's USB-RS485 dongle running `fake_slave.py`. Bridge UART (USART2) emits framed CBOR observable on a USB-TTL converter.

| # | Subtask | Hours | Risk |
|---|---------|-------|------|
| 2.1 | Verify Blue Pill is genuine STM32F103, not CKS/CS32/GD32 clone. Use `st-info --probe` and check Device ID = `0x410`. [Detection guide](https://hackmd.io/@ampheo/how-you-can-identify-a-fake-stm32f103c8t6). | 1 | ~60% of cheap Blue Pills on Indian retailers are CKS32 clones — they mostly work but USB enumeration & some peripherals differ. Buy 2–3 boards so you have a known-good one. |
| 2.2 | Flash a blink test via ST-Link V2 clone + OpenOCD to confirm toolchain. | 1 | Cheap ST-Link clones occasionally have outdated firmware — reflash with `STLinkUpgrade.jar` if `openocd` complains. |
| 2.3 | Flash scaffold `main.c` with the Modbus master + bridge tasks running. Connect USART1 (PA9/PA10) to a 3.3 V MAX485 breakout. Tie DE/RE to PA8 per existing pinout. | 3 | The Blue Pill's PA9/PA10 are 5 V-tolerant, but the MAX485 IC is 5 V — confirm the breakout has a 3.3 V LDO or use a level shifter. The cheap Robu.in MAX485 module is 5V-only; the "Auto-Direction" variant with on-board 5V→3.3V is better for dev. |
| 2.4 | Bring up `fake_slave.py` on host side using a USB-RS485 dongle (FT232RL-based recommended over CH340 for less Linux-driver pain). Wire A-A, B-B, common GND. | 2 | RS-485 with both ends on the same desk requires no termination at 9600 baud over <1 m, but adding 120 Ω at each end is harmless and reduces ringing. |
| 2.5 | Capture USART1 traffic with a logic analyzer (Saleae clone, Pulseview decoder) — confirm 8N1, 9600 baud, valid CRC-16, 3.5-char silence between frames. | 4 | The bare-metal `rs485_uart.c` polls `RXNE`/`TC` in a loop — at 72 MHz this is fine, but watch for FreeRTOS tick (1 kHz default) inserting jitter at higher baud rates. Stay at 9600 for the first bring-up. |
| 2.6 | Capture USART2 (bridge) traffic on a USB-TTL adapter at 115200. Decode the framed CBOR with a quick Python script (use the `cbor2` library) and confirm the JSON-equivalent matches the simulator's register values. | 3 | XOR checksum in `bridge_uart.c` is weak but adequate; sanity-check it now so you catch corruption before MQTT gets involved. |
| 2.7 | Add CRC error / timeout counters into `modbus_rtu.c` and expose them over the bridge as a separate periodic CBOR record. Trivial code, high diagnostic value. | 3 | Watch stack depth — FreeRTOS task stacks are sized 512 words; the CBOR encoder uses ~300 B on stack. Increase to 1024 if you add features. |
| 2.8 | Soak test: 1 hour, 3 polled slave tables, no errors. Save the log. | 8 | If clones in the network drop frames the master must retry — implement a simple 1-retry-then-skip in `modbus_poll`. |
| 2.9 | Tag this firmware version in git: `stm32-phase2-v1`. | 1 | None. |

**Verification.** Logic-analyzer screenshot of one clean Modbus transaction (request + response + CRC OK), and a Python-decoded CBOR record matching the simulator's expected output.

### Phase 3 — ESP32 firmware bring-up (Week 2–3, ~25 hrs)

**Deliverable.** ESP32-DevKitC running the scaffold ESP-IDF project, receiving CBOR from the STM32 over UART, and publishing each record to AWS IoT Core on `iot/gateway-001/telemetry`.

| # | Subtask | Hours | Risk |
|---|---------|-------|------|
| 3.1 | `idf.py set-target esp32 && idf.py menuconfig` — set Wi-Fi creds + AWS IoT endpoint (use the `ap-south-1` ATS endpoint, format `xxx-ats.iot.ap-south-1.amazonaws.com`). | 2 | Use the ATS endpoint, not legacy Verisign — AWS deprecated the latter. |
| 3.2 | Provision device certificate via NVS partition per `docs/aws_iot_provisioning.md`. Hand-provisioning is fine for week 3; revisit JITP if you push for the stretch goal of fleet provisioning (see §9). | 3 | NVS partition generator needs absolute paths to the PEM files. Watch line endings (CRLF on Windows breaks PEM parse — convert to LF). |
| 3.3 | Confirm Wi-Fi STA connects to BITS / home network. **Note** for BITS-Pilani: the campus enterprise Wi-Fi uses WPA2-Enterprise (PEAP-MSCHAPv2). ESP-IDF supports this via `esp_wifi_sta_wpa2_ent_set_*` APIs — non-trivial. **Recommend developing on home / mobile-hotspot Wi-Fi**, demo on either. | 4 | This is the single biggest schedule risk if you try to use campus Wi-Fi. Mitigation: own mobile hotspot. |
| 3.4 | Connect ESP32 GPIO16 (RX) and GPIO17 (TX) to STM32 USART2 (PA2/PA3). Cross over TX↔RX. Share GND. | 1 | None. |
| 3.5 | Verify `bridge_rx.c` state machine assembles framed CBOR correctly. Trigger XOR-mismatch path by deliberately corrupting a byte to check error handling. | 2 | The state machine resets on `0x7E` — confirm that an aborted partial frame doesn't lock state. |
| 3.6 | First successful MQTT publish. Watch the AWS IoT MQTT test client subscribed to `iot/gateway-001/telemetry`. Payloads will be base64-encoded in the console — copy/paste into a CBOR decoder to verify. | 3 | TLS handshake can fail with cryptic `MBEDTLS_ERR_SSL_FATAL_ALERT_MESSAGE` if the certificate has the wrong policy attached — re-attach with explicit Resource ARNs (see `docs/aws_iot_provisioning.md` IAM section). |
| 3.7 | Add a store-and-forward queue: enqueue CBOR records in `bridge_task` and drain only when `s_connected == true`. Use a FreeRTOS queue with `xQueueSendToBack` + a separate "publisher" task. | 5 | Bounded queue (256 entries × 512 B = 128 KB) won't fit in ESP32 SRAM — cap depth at 32 records for now, evaluate PSRAM later. |
| 3.8 | Wi-Fi disconnect test: drop the AP, watch the queue fill, restore AP, watch publish drain. | 3 | The default `esp_mqtt` client reconnects on its own — verify the queue drains in FIFO order. |
| 3.9 | Tag this firmware version: `esp32-phase3-v1`. | 1 | None. |
| 3.10 | Write an AWS IoT Rule that base64-decodes the binary payload and republishes JSON to `decoded/+/telemetry`. This makes the demo legible to non-CBOR audiences. | 1 | The IoT Rule SQL engine has a `decode(payload, 'base64')` function — combine with a Lambda for CBOR→JSON if needed. |

**Verification.** Subscribe to `decoded/gateway-001/telemetry` in the AWS Console → values appear matching the simulator's sine-wave.

### Phase 4 — End-to-end integration on breadboard (Week 3, ~15 hrs)

**Deliverable.** Blue Pill + ESP32-DevKitC + ADM3251E (or selected alternative) on a perfboard, polling the pymodbus simulator over a real RS-485 link, publishing to AWS IoT.

| # | Subtask | Hours | Risk |
|---|---------|-------|------|
| 4.1 | Wire the ADM3251E (or ADM2587E swap, see §3) on perfboard with all decoupling caps and a 120 Ω termination + AC bias network. | 4 | ADM3251E is the **RS-232** variant — see §3 for why this should be swapped to ADM2587E (isolated RS-485 with isoPower) **before perfboard assembly**. |
| 4.2 | Power the perfboard from 24 V bench supply through the LM2596 module → AMS1117-3.3 chain. Verify rails with DMM. | 1 | 24 V on LM2596 is well inside its 40 V max, but inrush at power-on can spike — add a 10 µF tantalum on input. |
| 4.3 | Replace `fake_slave.py` running on the host with the **real** Selec MFM384 powered from mains (be careful — this device sees line voltage on its current/voltage inputs). | 2 | Bench test the MFM384 first with no mains connected, using only its RS-485 port; the registers will read zero but the protocol will respond. **Do not** connect mains until you've isolated the meter in a proper test enclosure. For first-pass tests just keep using the simulator. |
| 4.4 | Run end-to-end for 2 hours. Log into a CSV from AWS IoT → S3 (use an IoT Rule with the `s3` action). | 3 | S3 action requires a separate IAM role on the Rule. |
| 4.5 | Capture three scope shots: power-on inrush, one full Modbus transaction on the A/B differential pair, the ESP32 TLS handshake on the bridge UART. Save for the resume / portfolio. | 3 | None. |
| 4.6 | Freeze firmware: `firmware-v1.0.0` tag. | 1 | None. |
| 4.7 | Lock the BOM revision before ordering the PCB. | 1 | None. |

**Verification.** Two-hour clean run, scope shots saved, BOM frozen.

### Phase 5 — PCB design in Altium (Week 3–4, ~25 hrs, partially in parallel with Phase 4 soak)

**Deliverable.** Altium project producing fab-ready Gerbers + drill + pick-and-place + BOM + IPC-2581 (optional) outputs, passing the DFM checklist in `hardware/schematic_notes.md`.

| # | Subtask | Hours | Risk |
|---|---------|-------|------|
| 5.1 | Apply for the [Altium Student license](https://www.altium.com/education/students) using BITS Pilani email — annual free renewal, full feature set. | 1 | License approval is automatic for `.edu`-domain emails; BITS uses `bits-pilani.ac.in` which is recognised. |
| 5.2 | Capture the schematic in three sheets: (a) Power input + protection + buck/LDO chain, (b) STM32 + ESP32 + bridge UART, (c) Isolated RS-485 frontend + connectors. | 6 | None. |
| 5.3 | Place components per `schematic_notes.md` isolation plan: ADM2587E (assumed swap) straddles the iso-barrier; keep 8 mm creepage to the digital side. | 4 | Easy to accidentally route a digital trace under the iso-IC — mark the barrier as a keep-out zone in Altium. |
| 5.4 | 4-layer stackup per BOM.md: Top signal / GND / 3V3 / Bottom signal. Confirm impedance: 5 mil trace + 5 mil space + 5 mil over GND ≈ 100 Ω differential. | 2 | Use Altium's built-in impedance calculator with FR4 εr = 4.3 at 1 MHz. JLCPCB JLC04161H-7628 stack is the cheap 4-layer default. |
| 5.5 | Route in this order: (1) iso barrier + RS-485 diff pair, (2) 24 V & 5 V power, (3) crystal traces for STM32, (4) bridge UART, (5) everything else. | 8 | Watch the bridge UART — it crosses several power planes if you're not careful. Keep it short, on top layer. |
| 5.6 | Generate outputs via OutJob: Gerber X2 (RS-274X), Excellon drill, IPC-2581 (optional, JLCPCB accepts), assembly drawings, P&P CSV, BOM CSV. | 2 | JLCPCB has occasional issues with IPC-2581 — Gerber X2 is the safest universal format. |
| 5.7 | DFM self-check against the table in `hardware/schematic_notes.md` plus JLCPCB's [DFM rule set](https://jlcpcb.com/capabilities/Capabilities). | 2 | Watch annular-ring minimums and silkscreen widths — JLCPCB defaults are 3 mil and 5 mil respectively. |

**Verification.** Altium project tag `pcb-v1.0`. Gerbers uploaded to JLCPCB's online viewer with zero DFM warnings.

### Phase 6 — PCB fabrication + assembly (Week 4–5, ~15 hrs build + waiting time)

**Deliverable.** 5× assembled boards, 1× fully populated and powered.

| # | Subtask | Hours | Risk |
|---|---------|-------|------|
| 6.1 | Place JLCPCB order: 5 pieces, 4-layer, 1.6 mm FR4, HASL or ENIG (ENIG +30%, worth it for the iso-IC's fine-pitch SOIC if going ADM2587E), black solder mask. Choose Global Standard Direct Line shipping ($3–8, 7–14 days to India). [Customs reference](https://jlcpcb.com/help/article/customs,-duties-and-taxes). | 1 | At ≤$30 declared value (~₹2,500), most India customs lets it clear without BCD. The ₹1,000 statutory de minimis is small but in practice low-value PCB orders pass [per multiple maker accounts](https://www.diyaudio.com/community/threads/jlcpcb-india-custom-duty.379223/). Budget +18% IGST mentally. |
| 6.2 | Place a parallel BOM order at Robu.in for the populate list (see §3) — same-day dispatch from Pune means parts often arrive before PCBs. | 1 | If a Robu.in line item is OOS at order time, switch to TomsonElectronics or Quartz before placing the order — back-orders on these distributors can be 4+ weeks. |
| 6.3 | Place a Mouser India order for the parts Robu.in doesn't carry (ADM2587E, precision passives, Phoenix connectors). Flat ~₹1,400 shipping — consolidate orders. | 1 | Add 18% IGST mentally to the Mouser invoice; it's billed at delivery. |
| 6.4 | Hand-assembly day: stencil-free reflow on a skillet (~190 °C) or hot-plate. Solder ADM2587E first (it has the smallest pitch), then STM32 LQFP-48, then 0603 passives. ESP32-WROOM goes on last as a hot-air rework job. | 8 | 0402 caps are listed in BOM.md but consider switching to 0603 for hand-assembly. The cost delta is negligible. |
| 6.5 | Continuity-check every rail before applying power. Use isolation-tester (or DMM in resistance mode) across the 2.5 kV barrier to confirm >10 MΩ. | 1 | Solder bridges across the iso-barrier kill the whole point of the design — test before powering. |
| 6.6 | Smoke-test: 24 V at 100 mA current-limit. Walk it up. Verify each rail in order: 24V → 5V → 3V3_DIG → 3V3_ISO. | 1 | Current limit your supply. The LM2596 has a soft-start but the ESP32 inrush during Wi-Fi association can briefly spike to 600 mA. |
| 6.7 | Flash the STM32 and ESP32 via the on-board SWD and USB-C headers. | 2 | If USB-C enumeration fails, check D+/D- swap and CC pull-down resistors (5.1 kΩ each to GND for device mode). |

**Verification.** Powered board, LEDs blinking, both MCUs flashed and producing serial output.

### Phase 7 — Final bring-up + DFM verification (Week 5–6, ~20 hrs)

**Deliverable.** All seven success criteria from §1 met. Resume bullets drafted. Demo video recorded.

| # | Subtask | Hours | Risk |
|---|---------|-------|------|
| 7.1 | Reproduce the Phase 4 soak test on the PCB, not the perfboard. Run for 4 hours. | 4 | New PCB might have a layout issue not present on perfboard — common ones: clock load caps wrong, RX/TX swapped, DE polarity inverted. |
| 7.2 | Real Modbus device test: bring up the Selec MFM384 in a small enclosure with a 230 V mains feed through a single-phase miniature breaker. Connect A/B to the gateway. Confirm voltage / current / power values appear in AWS. | 4 | **Live mains work — be careful.** Use a residual-current device (RCBO). Better still: borrow a low-voltage demo from a friend's project. |
| 7.3 | EMI spot-check: with a near-field probe + scope, look for radiated emissions above 30 MHz around the LM2596 inductor and the antenna keepout. Document. | 3 | Don't expect to pass formal CE/FCC; goal is to identify obvious problems (e.g. unfiltered 150 kHz harmonics making it onto the RS-485 lines). |
| 7.4 | Thermal soak: 30 minutes at 40 °C ambient (heat gun on low, or a cardboard enclosure on a sunny window). Check no rail droops, no MCU reset. | 2 | LM2596 thermal pad is on the underside of the SOIC-8; if it gets near 100 °C, add a copper pour or heatsink. |
| 7.5 | Photo session: top, bottom, with the meter, scope traces. Use a phone with a tripod and side lighting. These shots **are** half of the resume value. | 2 | None. |
| 7.6 | Write two resume bullets (see §10). Iterate with mentors / classmates. | 2 | None. |
| 7.7 | Update README.md to point to the BUILD_PLAN, photos, and demo video. | 1 | None. |
| 7.8 | DFM verification report: list every component that needed substitution, every wire-mod / blue-wire / rework. Tag `pcb-v1.0-asbuilt`. | 2 | This is the institutional knowledge that distinguishes a portfolio project from a one-off. |

**Verification.** All 7 success criteria ticked, repo tagged `v1.0`.

---

## 3. Detailed BOM with India sourcing

> **Pricing baseline:** May 2026, sourced from Robu.in / Mouser.in / Quartz / Indiamart product pages and recent web research. Where a current INR figure was not located, the entry is annotated "est." with a reasoning trail. Add ~18 % IGST mentally to Mouser line items; Indian retailers' prices already include GST.
>
> **Recommended swap:** the existing BOM lists **ADM3251E** which is a 2.5 kV isolated **RS-232** transceiver, not RS-485 ([Analog Devices product page](https://www.analog.com/en/products/adm3251e.html)). For Modbus-RTU over RS-485 the correct sibling is the **ADM2587E** — same iCoupler architecture, same isoPower DC-to-DC, 500 kbps, full/half-duplex RS-485 ([datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/adm2582e-2587e.pdf)). **This is an existing-design bug. Fix before ordering PCB.** The schematic notes already describe the part as the "isolated RS-485 transceiver" — so the BOM line and `README.md` mention are the only places to change. Cost delta is ~₹50 in favour of ADM2587E.

### 3.1 Active components

| Ref | Part | Description | Supplier | Supplier P/N | INR (incl GST) | Availability (May 2026) | Datasheet |
|-----|------|-------------|----------|--------------|----------------|--------------------------|-----------|
| U1  | STM32F103C8T6 (or pin-compatible STM32C031C6T6 — see swap note) | Cortex-M3 MCU, 64 KB flash, LQFP-48 | Robu.in / Quartz | "STM32F103C8T6 Blue Pill" board if going DIP-style for week-2 bring-up; SMT IC also stocked | ₹240 for the chip alone (Robu.in), ₹220–280 for full Blue Pill board ([Quartz listing](https://quartzcomponents.com/products/stm32f103c8t6-development-board-stm32-arm-core-module)) | In stock at multiple Indian distributors; F1-family is **not yet EOL** but has been long-life noticed by ST. Mitigation: secondary BOM listing for **STM32C031C6T6** as a future-proofing footprint-compatible replacement (see [ST product longevity](https://www.st.com/content/st_com/en/about/quality-and-reliability/product-longevity.html)). | [DS5319](https://www.st.com/resource/en/datasheet/stm32f103c8.pdf) |
| U2  | ESP32-WROOM-32E (8 MB flash) | Wi-Fi + BT5 module | Robu.in | "Espressif ESP32-WROOM-32E 8M" — multiple flash variants listed at [robu.in](https://robu.in/product/espressif-esp32-wroom-32e-8m-64mbit-flash-wifi-bluetooth-module) | ~₹350–450 (8 MB) / ~₹400–500 (16 MB N16); confirm at order time | In stock. -32E and -32UE (with U.FL antenna pad) both available. | [ESP32 datasheet](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf) |
| U3  | **ADM2587EBRWZ** (swap from ADM3251E) | 2.5 kV signal+power isolated RS-485 transceiver, 500 kbps, SOIC-W-20 | Mouser India | ADM2587EBRWZ | ~₹950–1,150 + 18 % IGST = ~₹1,300 | Mouser/DigiKey in-stock typically 1,000+ units; lead time short. [Mouser product page](https://www.mouser.in/new/analog-devices/adi-adm2587e-rs485-transceiver/) | [ADM2587E DS](https://www.analog.com/media/en/technical-documentation/data-sheets/adm2582e-2587e.pdf) |
| U4  | LM2596S-5.0 | 3 A buck, 24 V → 5 V, TO-263 (or pick the module if hand-assembling) | Robu.in | LM2596 module ₹80 / bare IC ₹40 | ₹40–100 | In stock | [TI LM2596 DS](https://www.ti.com/lit/ds/symlink/lm2596.pdf) |
| U5  | AMS1117-3.3 | 5 V → 3.3 V LDO, 1 A, SOT-223 (digital side) | Robu.in | AMS1117-3.3 | ₹15–25 | In stock | [AMS1117 DS](http://www.advanced-monolithic.com/pdf/ds1117.pdf) |
| U6  | (none — the isoPower built into ADM2587E provides the iso-side 5 V rail, then an MCP1700-3302 or AMS1117 generates 3V3_ISO) Use **MCP1700-3302E/TO** (40 µA quiescent, much better than AMS1117 for the iso side which only powers an op-amp / status LED) | Mouser | MCP1700-3302E/TO | ~₹35 + GST | In stock | [MCP1700 DS](https://www.microchip.com/en-us/product/MCP1700) |

### 3.2 Protection / RS-485 front-end

| Ref | Part | Description | Supplier | INR | Notes |
|-----|------|-------------|----------|-----|-------|
| D1  | SS34 | Schottky reverse-polarity, 3 A 40 V | Robu.in | ₹6/ea (pack of 10 ₹50) | In stock |
| D2,D3 | PESD3V3L5UY | TVS array, 3.3 V working, SOT-23-3 | Mouser | ~₹25 each | In stock |
| F1  | Bourns MF-R025 PTC | 250 mA polyfuse, 30 V | Mouser | ~₹35 | In stock |
| RT1 | 120 Ω 1% 0805 (RS-485 termination) | Yageo | Robu.in / Mouser | ₹1 | Standard |
| RB1,RB2 | 680 Ω 1% (fail-safe bias divider on A/B) | Yageo | Robu.in | ₹1 | See §5 below — must be present for receiver determinism |
| C_term | 10 nF X7R 0805 (AC termination cap in series with RT1) | Yageo | Robu.in | ₹1 | See [Analog Devices RS-485 guide](https://www.analog.com/en/resources/technical-articles/rs485-cable-specification-guide--maxim-integrated.html) |

### 3.3 Clock + reset + decoupling

| Ref | Part | Description | Supplier | INR | Notes |
|-----|------|-------------|----------|-----|-------|
| Y1 | 8 MHz HC-49S SMD crystal | ABM3B-8.000MHz-B2T or equivalent | Robu.in | ₹15 | 18 pF load |
| C_cl1, C_cl2 | 18 pF NP0 0603 | crystal load caps | Robu.in | ₹0.5/ea | |
| C_dec | 100 nF X7R 0603 ×30 | Decoupling, one per IC pin pair | Robu.in (strip of 100) | ₹50 for 100 | Standard |
| C_bulk | 10 µF 25 V tantalum (or X5R 1206) ×4 | One per rail | Robu.in | ₹8/ea | Industrial-grade X5R ceramic preferred over tantalum to avoid solder-reflow tantalum failures |
| C_iso | 2.2 µF 0805 X7R ×2 | ADM2587E V_ISO bypass per datasheet | Mouser | ₹3/ea | Critical — undersized here causes isoPower DC/DC instability |

### 3.4 Connectors + headers

| Ref | Part | Description | Supplier | INR | Notes |
|-----|------|-------------|----------|-----|-------|
| J1  | Phoenix MKDS 1,5/4 or MC 1,5/4-G-3,5 | 4-pos screw-terminal (24 V + GND + A + B) | Mouser | ~₹120 | The Phoenix MKDS is the cheaper variant; both have 5 mm pitch |
| J2  | 2x5 1.27 mm Cortex-10 SWD/JTAG | Pinheader, SMD | Robu.in / Mouser | ₹15 | Pin-compatible with ST-Link V2 cable adapter |
| J3  | USB-C receptacle (16-pin SMD) | Programming + power | Robu.in | ~₹40 | |
| LED1..3 | 0603 green/yellow/red | Power / Wi-Fi / Modbus-activity | Robu.in | ₹1/ea | |
| R_led | 1 kΩ 0603 ×3 | LED current limit | Robu.in | ₹0.5/ea | |
| TP1..TP6 | Keystone 5015 (1 mm) test points | Loop test points | Mouser | ₹6/ea | Optional — pads suffice |

### 3.5 PCB and consumables

| Item | Description | Supplier | INR |
|------|-------------|----------|-----|
| PCB | 4-layer 80×60 mm, qty 5, HASL, 1.6 mm | JLCPCB Global Standard to India | ~$28 PCB + $8 shipping = ~₹3,000 (no duty if assessed value <₹2,500, else +35%) — see §8 |
| Solder paste | Sn63/Pb37 No-clean, 100 g jar | Robu.in | ₹600 |
| Solder wire | 0.6 mm leaded, 50 g | Robu.in | ₹250 |
| Flux pen | Kingbo RMA-218 | Robu.in | ₹150 |
| Isopropanol | 99% 500 ml | Local pharmacy | ₹250 |

### 3.6 Spare-parts buffer (10–15% rule)

Order **2×** each of: STM32 (or Blue Pill board), ESP32-WROOM module, ADM2587E (highest-risk part), LM2596 module, AMS1117, USB-C connector. Order **3×** each of: 100 nF caps, 10 µF caps, 0805 resistors. Cost overhead ~₹600.

### 3.7 BOM cost roll-up

| Bucket | INR |
|--------|-----|
| Active ICs (incl. spare ADM2587E) | ~₹3,200 |
| Protection + RS-485 frontend | ~₹250 |
| Passives + crystal + decoupling | ~₹400 |
| Connectors + LEDs + test points | ~₹400 |
| Spare-parts buffer | ~₹600 |
| Solder paste + flux + IPA + wire | ~₹1,250 |
| **Sub-total (parts only)** | **~₹6,100** |

---

## 4. Tools you need

### 4.1 Hardware (one-time)

| Tool | Why | Source / cost |
|------|-----|----------------|
| **Multimeter** | rails, continuity, isolation | UNI-T UT139C — ~₹2,500, Robu.in (or already owned) |
| **Soldering iron, 60 W temperature-controlled** | Hand-assembly | T12-style station — ~₹2,500 |
| **Hot-air rework station** | ESP32-WROOM, ADM2587E | 858D clone — ~₹3,000 (consider borrowing from BITS embedded lab) |
| **ST-Link V2 clone** | STM32 SWD flash + debug | Robu.in / Robokits ~₹120 ([listing](https://robokits.co.in/programmers/stm32-stm08/st-link-v2)) — buy 2; lifespan is short |
| **USB-TTL serial (FT232RL)** | ESP32 serial console + bridge-UART tap | Robu.in ~₹250 |
| **USB-RS485 (FT232 + MAX485)** | Host-side Modbus master test, simulator | Robu.in ~₹350 |
| **Logic analyzer (Saleae clone, 8 ch, 24 MHz)** | UART + DE/RE timing, CRC verification | Robu.in / Amazon ~₹700 |
| **Bench supply 0–30 V, current-limit** | smoke-testing rails | If not already owned: Mastech HY3005 clone ~₹4,500. BITS lab will have one. |
| **Oscilloscope, 50 MHz, 2 ch** | RS-485 differential signal, EMI spot-check | Use BITS lab scope — Rigol DS1054Z or similar |

### 4.2 Software (free)

| Tool | Notes |
|------|-------|
| **STM32CubeIDE 1.15+** | [Download from ST](https://www.st.com/en/development-tools/stm32cubeide.html). Free. Includes CubeMX. Pin-mux & clock-tree GUI is the fastest way to sanity-check `rs485_uart.c` |
| **ESP-IDF v5.4 LTS** | Use the official installer ([Windows](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32/get-started/windows-setup.html) / [Linux](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32/get-started/linux-macos-setup.html)). **Pin to v5.4, not v6.0** because esp-aws-iot doesn't yet support mbedTLS v4 / corePKCS11 on v6 ([readme](https://github.com/espressif/esp-aws-iot)). |
| **Altium Designer (Student)** | Free with BITS email ([apply here](https://www.altium.com/education/students)). Full features, annual renewal. |
| **KiCad 8** | Free backup if Altium proves heavy. KiCad output is also accepted by JLCPCB, PCBPower, PCBWay. |
| **MQTT Explorer** | [mqtt-explorer.com](http://mqtt-explorer.com/) — free GUI. Supports cert-based AWS IoT auth for desktop testing. |
| **QModMaster / mbpoll** | Modbus master client for host-side testing without the gateway. `mbpoll` is the CLI workhorse on Linux/macOS. |
| **Saleae Logic 2** | Free for clone hardware. Decoders for Modbus RTU + async serial built-in. |
| **AWS CLI v2** | Free. Used for the provisioning commands in `docs/aws_iot_provisioning.md`. |
| **`cbor2` Python package** | Decode bridge frames offline for verification. |
| **OpenOCD 0.12** | Alternative STM32 flash + debug. Already in the scaffold's `make flash` target. |

### 4.3 Test fixtures

* A Modbus slave simulator running on a laptop — already provided by `simulator/fake_slave.py`.
* A real Modbus slave for final acceptance — Selec MFM384-R-C (DIN-rail, ~₹3,000 — see §6 of research notes; [Selec product page](https://www.selec.com/product-details/multifunction-meter-384-r-c)).
* Isolation tester (or a 1500 V flyback transformer rig) if you want to claim the 2.5 kV isolation as verified. Otherwise, document this as datasheet-trusted.

---

## 4.5 Modbus protocol nuances — implementation gotchas

The scaffold already gets the protocol fundamentals right (CRC-16-Modbus polynomial `0xA001` reflected, 3.5-char silence, function-code mask `0x80` for exceptions). The areas where real-world slaves bite implementers are below — read these **before** Phase 2.

### Inter-frame timing (the 3.5 / 1.5 char rule)

Per [Modbus.org spec V1.02](https://modbus.org/docs/Modbus_over_serial_line_V1_02.pdf) §2.5.1.1:

| Symbol | Definition | At 9600 baud (11 bits/char ≈ 1.146 ms/char) | At 19200 baud (≈573 µs/char) | At ≥38400 baud |
|--------|------------|--------------------------------------------|------------------------------|-----------------|
| t1.5 | Max gap **within** a frame | 1.72 ms | 0.86 ms | **fixed 750 µs** |
| t3.5 | Min silence **between** frames | 4.01 ms | 2.01 ms | **fixed 1.75 ms** |

The existing `rs485_uart.c` uses `pdMS_TO_TICKS(4)` which is correct for 9600 baud. **If you ever raise the baud rate above 19200**, switch to the fixed 1.75 ms rule, not the scaled-by-character one. Most commercial slaves implement the fixed rule for everything ≥19200, so a master that scales below this can cause subtle interop bugs.

### Common slave-side quirks

| Quirk | What you'll see | Fix |
|-------|------------------|-----|
| **Register numbering off-by-one** (1-based human-readable vs 0-based on-wire) | Reading register "1" in the slave manual returns garbage; you actually want address `0x0000` | Always check the manual: Schneider PM5110 uses 1-based docs, on-wire 0-based; Selec MFM384 uses 0-based docs and on-wire — read the protocol annex of the actual device. |
| **Word order in 32-bit values** (big-endian vs little-endian within the pair) | Pressure reads as 2.4 MPa instead of 71 kPa | Most slaves are big-endian word order (high word first) but Schneider's older devices are word-swapped little-endian. Make this configurable per-register in `s_poll_table`. |
| **Float32 packed across two registers** | Returns 0.0 or NaN if you assume integer | IEEE 754 float, again with word-order ambiguity. Test against a known reading first. |
| **Slave needs >50 ms turnaround time after a write** | Subsequent reads time out | Add a `post_write_delay_ms` field to `modbus_poll_entry_t` for write-then-read patterns. |
| **Some slaves answer to broadcast (slave-ID 0)** even though they shouldn't | Garbled reply on bus | Never poll slave-ID 0. |
| **Slave clock drift slowly desyncs framing** at long-running deployment | CRC errors creep in after hours | Treat any CRC error as recoverable; just retry the next poll cycle. Existing code already does this. |
| **Wrong start register on multi-register read** | Function-code `0x83` exception with code `0x02` (illegal data address) | This is good — your master gets a clean error and you fix the table. |

### RS-485 termination in industrial deployments

Per [Opto22's reference](https://blog.opto22.com/optoblog/rs-485-to-terminate-bias-or-both) and AN1690:

1. **Termination resistor** at *each physical end* of the bus only, never on intermediate nodes. Value matches cable Zc, typically 120 Ω. AC termination (R in series with 10 nF cap) draws less idle current — adopt this for battery-powered slaves.
2. **Fail-safe bias** at *exactly one* node, typically the master. For 3.3 V supply: 680 Ω pull-up on A, 680 Ω pull-down on B against a 120 Ω terminator gives ~250 mV idle differential, comfortably above the −200 mV receiver threshold.
3. **Stub length** to each slave ≤ λ/10 of the rise time. At 9600 baud and 1 µs edges, stubs up to ~30 m are tolerable, but in practice keep them <1 m.
4. **Daisy-chain topology**, never star. Each slave connects through, with screw terminals so the loop continues.
5. **Cable**: 120 Ω twisted pair, shielded for industrial. Belden 3105A or generic CAT5e UTP both work; CAT5e at long runs (>100 m) needs careful bias.
6. **Common-mode return**: connect all device 0 V together via the third terminal or shield. RS-485 is **not** a 2-wire bus — it's 3-wire (A, B, common). Skipping common ground is the #1 cause of intermittent industrial failures.

### Capturing & decoding for debug

* Saleae Logic 2 has a native **Modbus RTU** analyzer plugin — feed it the USART1 TX or RX line and it decodes addresses, function codes, register data, and CRC validity in real time.
* For free-tier Saleae captures, the [`sigrok` / `pulseview`](https://sigrok.org/) project has equivalent Modbus decoding.
* For network-level introspection on a future Modbus-TCP stretch goal, Wireshark has built-in Modbus dissection.

---

## 5. Reference designs to study

> Time-to-value: read these **before** Phase 2 starts. Each link below is annotated with what to take from it.

### 5.1 GitHub repositories

| Repo | Stars / Activity (May 2026) | What's useful |
|------|------------------------------|----------------|
| [**alejoseb/Modbus-STM32-HAL-FreeRTOS**](https://github.com/alejoseb/Modbus-STM32-HAL-FreeRTOS) | ~692★ / 215 forks, active commits March 2025 | Drop-in Modbus TCP+RTU master/slave library using STM32 HAL + FreeRTOS — the closest commercial-grade reference to what this project does. Read the master example; consider replacing the bare-metal `modbus_rtu.c` with this if `Phase 2.6` reveals fundamental bugs. |
| [**eziya/STM32_HAL_FREEMODBUS_RTU**](https://github.com/eziya/STM32_HAL_FREEMODBUS_RTU) | smaller / lightly maintained | A clean FreeMODBUS port — good for understanding the canonical FreeMODBUS state machine. |
| [**ADElectronics/STM32-FreeModbus-Example**](https://github.com/ADElectronics/STM32-FreeModbus-Example) | reference examples | Both master & slave on F401 — adaptation notes for F103 in the issues. |
| [**armink/FreeModbus_Slave-Master-RTT-STM32**](https://github.com/armink/FreeModbus_Slave-Master-RTT-STM32) | older but cited often | The first community port of FreeMODBUS that added master mode. Worth scanning for the state-machine diagrams. |
| [**espressif/esp-modbus**](https://github.com/espressif/esp-modbus) | official, v2.1.0 component | The official ESP-IDF Modbus library. **This is the basis for the "should we drop the STM32?" question discussed below.** |
| [**zivillian/esp32-modbus-gateway**](https://github.com/zivillian/esp32-modbus-gateway) | small but recent (2025) | Single-MCU ESP32 Modbus-RTU↔TCP gateway. Read this and articulate **why you didn't go single-MCU** for the resume. |
| [**espressif/esp-aws-iot**](https://github.com/espressif/esp-aws-iot) | official | AWS-IoT C SDK + mbedTLS adaptation. Use the `mqtt_mutual_auth` example as the literal template for `mqtt_aws.c`. |

### 5.2 ST application notes

| AN | Title | Link |
|----|-------|------|
| AN3070 | Managing the Driver Enable signal for RS-485 and IO-Link communications with the STM32's USART | [ST PDF](https://www.st.com/resource/en/application_note/an3070-managing-the-driver-enable-signal-for-rs485-and-iolink-communications-with-the-stm32s-usart-stmicroelectronics.pdf) |
| AN3155 | USART protocol used in the STM32 bootloader | Useful for the OTA-via-bridge stretch goal |
| AN4904 | Migration from STM32F1 → STM32F4 access lines | [ST PDF](https://www.st.com/resource/en/application_note/an4904-migration-of-microcontroller-applications-from-stm32f1-series-to-stm32f4-access-lines-stmicroelectronics.pdf) — read if you decide to swap U1 in the future |
| AN5969 | Migrating between STM32G0 and STM32C0 MCUs | [ST PDF](https://www.st.com/resource/en/application_note/an5969-migrating-between-stm32g0-and-stm32c0-mcus-stmicroelectronics.pdf) |
| AN1690 | Fail-safe biasing for ST485EB | [ST PDF](https://www.st.com/resource/en/application_note/an1690-failsafe-biasing-for-st485eb-stmicroelectronics.pdf) — the canonical reference for the RB1/RB2 bias divider |

### 5.3 Blog posts / tutorials

* [Feaser blog: STM32 Modbus RTU server tutorial](https://www.feaser.com/en/blog/2023/04/stm32-modbus-rtu-server-tutorial/) — slave side, complements your master.
* [AgileVision.io: ESP32 + AWS IoT tutorial](https://agilevision.io/blog/esp32-and-aws-iot-tutorial/) — covers the mutual-TLS handshake setup gotchas.
* [Hackaday: Test your Blue Pill for genuine STM32F103](https://hackaday.com/2021/06/23/test-your-blue-pill-board-for-a-genuine-stm32f103c8-mcu/) — critical for Phase 2.1.
* [Industrial Monitor Direct: Modbus RTU timeouts with increased message length](https://industrialmonitordirect.com/blogs/knowledgebase/modbus-rtu-timeouts-with-increased-message-length-specifications-and-solutions) — useful when debugging your master against real slaves.
* [Opto22 OptoBlog: RS-485 — to terminate, bias, or both?](https://blog.opto22.com/optoblog/rs-485-to-terminate-bias-or-both) — settled, canonical RS-485 termination guide.

### 5.4 Books

* **"Industrial Communication Technology Handbook"** (CRC Press, Zurawski) — Modbus chapter is the go-to spec interpretation.
* **"Mastering STM32"** (Carmine Noviello) — bare-metal & HAL coverage, good for `rs485_uart.c` understanding.
* **"Designing Embedded Hardware"** (John Catsoulis, 2nd ed.) — for the analog/protection side.

### 5.5 Commercial gateways to benchmark against

| Product | Price tier (USD/INR) | What to copy / not copy |
|---------|----------------------|--------------------------|
| **Moxa MGate MB3170 / MB3170-G2** | ~$400 list / ~₹35,000 ([Moxa](https://www.moxa.com/en/products/industrial-edge-connectivity/protocol-gateways/modbus-tcp-gateways/mgate-mb3170-mb3270-series)) | DIN-rail form factor, isolation rating, web config UI — copy the form factor and connector layout. |
| **Advantech ADAM-4572** | ~$225 / ~₹19,000 ([Advantech](https://www.advantech.com/en-us/products/db72f61c-801b-4e61-8863-5d418f01b6e9/adam-4572/mod_1e01192d-95a1-42a4-b199-79343134f4ca)) | 50 bps–921.6 kbps range, 15 kV ESD spec — benchmark your own ESD claim against this. |
| **Norvi ENET / Norvi IoT** (Indian/Sri Lankan) | ~$110 / ~₹9,000 ([Norvi](https://norvi.io/modbus-devices-with-esp32/)) | ESP32-based **single MCU** gateway — read their architecture pages carefully so you can articulate why dual-MCU is your design choice. |

### 5.6 Architecture decision record — Dual MCU vs single ESP32

**The question.** Espressif's [esp-modbus](https://github.com/espressif/esp-modbus) library is mature and the ESP32 has hardware UART, plenty of FreeRTOS muscle, and direct Wi-Fi. Could you just delete the STM32 and ship a single-ESP32 gateway? Yes, you could — and most cheap commercial gateways do exactly that ([Norvi](https://norvi.io/modbus-devices-with-esp32/), [zivillian/esp32-modbus-gateway](https://github.com/zivillian/esp32-modbus-gateway), the August-2025 [CNX gateway](https://www.cnx-software.com/2025/08/19/esp32-modbus-gateway-handles-rtu-tcp-ip-and-mqtt-for-industrial-iot/)).

**Why dual-MCU here.** Four arguments hold for this project:

1. **Real-time determinism.** Modbus-RTU requires 3.5-char inter-frame silence. The Wi-Fi stack on ESP32 can preempt for up to tens of ms during association events, easily breaking the silence rule and causing slaves to misframe. Pinning the Modbus task to ESP32 core 0 partially mitigates but doesn't eliminate the issue. (See [community discussion](https://esp32.com/viewtopic.php?t=23806).)
2. **Security boundary.** An ESP32 is internet-facing and has had a steady stream of CVEs (e.g. Espressif's BLE stack issues in 2023). Keeping the Modbus side on a stack that has no IP routing means a compromised ESP32 cannot trivially become a pivot onto the factory floor.
3. **Field serviceability.** OTA-updating the ESP32 over MQTT (stretch goal §9) leaves the STM32 firmware untouched — the protocol-critical code is frozen the day the device ships.
4. **Resume narrative.** Demonstrates explicit architectural reasoning. Easier to defend in an interview than "I used the obvious ESP32-only path."

**Trade-off acknowledged.** Costs an extra ~₹450 in silicon (the F103 IC + a UART crystal + extra decoupling), board area, and ~10 hours of bring-up time vs. a single-MCU design. The trade is worth it for the security and timing arguments. Document this ADR explicitly in `docs/`.

---

## 6. Risk register

| # | Risk | Probability | Impact | Mitigation |
|---|------|-------------|--------|------------|
| R1 | STM32F103 long-term-availability notice / EOL during product life | Medium | High (replan U1) | Footprint-compatible second source: **STM32C031C6T6** (LQFP-48 same pinout for power/clock — most peripherals on different pins, requires firmware re-port but not PCB respin). ST's [longevity programme](https://www.st.com/content/st_com/en/about/quality-and-reliability/product-longevity.html) commits to 10+ years notice. F103 is not formally EOL as of May 2026 but is "Mature" status. |
| R2 | ADM2587E lead time from Mouser India spikes | Medium | High (build slips ≥4 weeks) | Pre-order at Phase 1.7. Backup: ADM2682E (more bandwidth, similar pinout). Last-resort: discrete NVE IL3085 + Murata MEU1S0505SC isolated DC/DC. |
| R3 | Counterfeit Blue Pill chip (CKS/CS32/GD32) — silently different USB and clock behaviour | High (60–70% of cheap boards per [Hackaday](https://hackaday.com/2020/10/22/stm32-clones-the-good-the-bad-and-the-ugly/)) | Medium | Verify Device ID `0x410` and reported flash size in Phase 2.1. Buy 3 boards from 2 different sellers. |
| R4 | BITS-Pilani enterprise Wi-Fi (WPA2-Enterprise/PEAP) breaks the ESP32 connect path | High if attempted | Medium | Develop & demo on home/mobile hotspot. Document the limitation rather than try to fix it. |
| R5 | RS-485 fail-safe biasing missing → receiver outputs garbage when bus is idle | Medium | Medium (corrupts CRC, looks like a software bug) | Add 680 Ω pull-up on A and pull-down on B per [AN1690](https://www.st.com/resource/en/application_note/an1690-failsafe-biasing-for-st485eb-stmicroelectronics.pdf). Existing BOM omitted these — add in Phase 5.2. |
| R6 | 0402 hand-assembly without stencil → bridging, tombstoning | Medium | Low (tedious to rework, doesn't kill schedule) | Switch passives to 0603 in Phase 5.2 (small area penalty, much easier hand-soldering). |
| R7 | India customs charges 35%+ on JLCPCB shipment | Low if <₹2,500 declared / High if ₹5,000+ | Medium (~₹1,000 extra) | Keep PCB order <₹2,500 declared. If parts also ordered abroad, separate the PCB shipment. |
| R8 | LM2596 EMI radiates onto the RS-485 differential pair | Medium | Medium (intermittent CRC errors at high baud) | Use shielded inductor on LM2596 module, keep traces away from RS-485 lines. Consider MP1584 (1.5 MHz vs 150 kHz) for v1.1 — but harder to source as a module in India. |
| R9 | Live-mains test of Selec MFM384 → personal safety + firmware lockup | Low if RCBO used | Catastrophic | Do **not** energise the meter's voltage/current inputs until everything else works. RCBO required. Better: arrange a controlled test at a lab with a qualified supervisor. |
| R10 | AWS IoT Free Tier exhausted before project end | Very low (12-month tier covers 500 k messages + 2.25 M conn-minutes — see [AWS pricing](https://aws.amazon.com/iot-core/pricing/)) | Low | Telemetry rate at 1 msg/sec × 86,400 s/day × 42 days = 3.6 M msgs — **exceeds Free Tier**. Mitigation: throttle to 1 msg/5 s during dev, or use a fresh Free Tier account if available. Worst case: ~$3 over-tier in dev. |
| R11 | ESP-IDF / esp-aws-iot version mismatch (v6 vs v5 breakage) | Medium | Low | Pin to ESP-IDF v5.4 LTS, esp-aws-iot release tag `release/202412.00-LTS`. Commit the exact tag in `firmware-esp32/CMakeLists.txt` comments. |
| R12 | Altium student license rejection (rare with `.ac.in` domain) | Low | Low | Backup to KiCad 8. Re-do schematic, ~6 hours lost. |
| R13 | Modbus slave at address `0x01` collides with the simulator default → bus contention if both connected | Low | Low | Set the MFM384 to slave-ID `0x05` (DIP / config) before connecting both. |
| R14 | Phoenix screw terminal not available in 5 mm pitch from Robu.in at order time | Medium | Low | Backup: KF301-5.08 cheap clone terminals — same footprint, ₹15 vs ₹120. |
| R15 | Solder reflow on hot plate scorches the FR4 silkscreen | Low | Low | Keep skillet max temp ≤200 °C, use IR thermometer to verify. |

---

## 7. Test and verification plan

### 7.1 Unit tests (host-side, before any hardware)

| Test | Code | Pass criterion |
|------|------|----------------|
| CRC-16-Modbus correctness | `simulator/test_crc16.py` (already in repo); add a fuzzer comparing to `crcmod` library | Every random byte string matches reference |
| CBOR encoder round-trip | New test: feed known `modbus_response_t` through `cbor_encode_modbus_reading()` on a host build of the encoder, decode with Python `cbor2`, assert equality | Decoded dict matches input |
| Bridge frame state machine | New test: drive `bridge_rx.c` state machine with a synthetic byte stream including a corrupted frame; assert the state resets and the next-good frame is accepted | Recovery works |
| Modbus response parser corner cases | Add tests for: short frame (<5 B), wrong CRC, exception response (function | 0x80), slave-ID mismatch | All return the documented error code |

Run all under CI (GitHub Actions, `pytest`) — sets the project apart from typical student work.

### 7.2 Integration tests (gateway-side, against simulator)

| Test | Setup | Pass criterion |
|------|-------|----------------|
| **End-to-end happy path** | `fake_slave.py` on PC; gateway connected via USB-RS485 dongle | ≥99.9% of polls return MB_OK over 1 hour |
| **CRC error injection** | Inject random bit flips on the RX line (use a 3.3 V buffer with a tied pin) | All flipped frames are rejected; counter increments; no firmware crash |
| **Slave timeout** | Power off the simulator mid-poll | `MB_ERR_TIMEOUT` reported; next poll round picks back up |
| **Exception response** | Configure simulator to return illegal-data-address for one register | `MB_ERR_EXCEPTION` reported with exception code = 0x02 |
| **Wi-Fi outage** | Disable AP for 5 min | Queue fills to cap, no firmware crash; on reconnect, queued messages drain to AWS within 30 s |
| **AWS IoT outage** | Detach IoT policy (forces broker reject) | Reconnect-with-backoff is observed; no infinite TLS handshake loop |

### 7.3 Hardware tests (on the PCB)

| Test | Equipment | Pass criterion |
|------|-----------|----------------|
| **Power-rail sanity** | DMM | 24 V ±5 %, 5 V ±5 %, 3V3_DIG ±3 %, 3V3_ISO ±3 % all within spec at no-load and at full Wi-Fi-TX load |
| **Isolation continuity** | DMM in resistance mode (or insulation tester) | >10 MΩ across the iso-barrier (datasheet says >10⁹ Ω at 5 V; rough DMM check OK) |
| **RS-485 differential at AB** | Scope, differential probe | Mark/space swing 1.5–5 V differential per [EIA-485 spec](https://www.ti.com/lit/an/slla272d/slla272d.pdf), no ringing >15% |
| **DE/RE timing** | Logic analyzer | DE asserts ≥3.5 char times before first start bit; deasserts ≥3.5 char times after last stop bit. Matches AN3070. |
| **Bus loading** | Multimeter on idle bus voltage | Idle differential >200 mV (proves fail-safe biasing works) |
| **EMI spot check** | Near-field probe + scope, FFT mode | No emissions >40 dBµV at 30 MHz–1 GHz near the antenna keepout. Don't expect to pass CE; just spot obvious problems. |
| **Thermal soak** | Hand-held IR thermometer | LM2596 case <85 °C, MCUs <60 °C at 25 °C ambient, full load |
| **Reverse-polarity** | Bench supply | Apply −24 V to J1: SS34 conducts, no damage. DMM shows 0.3 V across diode. |

### 7.4 Acceptance criteria (gating release as v1.0)

* All §1 success criteria met.
* 4-hour soak with zero unexplained errors.
* One live demo recorded (phone video, <3 min) showing the gateway publishing real meter data.
* `BUILD_PLAN.md` updated with as-built notes from §7.8.

---

## 7.5 PCB fabrication comparison (India context)

For a 4-layer ~80×60 mm board in qty 5, here's how the four candidate fabs compare for a builder in India:

| Vendor | Board cost (5 pcs, 4-layer, 1.6 mm, HASL) | Shipping to India | Lead time | Total INR | Customs / duty | Notes |
|--------|--------------------------------------------|--------------------|-----------|------------|-----------------|-------|
| **JLCPCB** (HK/CN) | ~$22 base + $5 4-layer surcharge | $3–8 Global Standard / ~$18 DHL | 5 days fab + 7–14 days ship (standard) | ~₹2,800 standard / ~₹3,800 DHL | Per [their docs](https://jlcpcb.com/help/article/customs,-duties-and-taxes): India BCD applies if assessed value >₹2,500; in practice $30 shipments clear about half the time without BCD per [community reports](https://www.diyaudio.com/community/threads/jlcpcb-india-custom-duty.379223/). Worst case +35% = +₹1,000. | Recommended default. Excellent DFM tooling, free SMT assembly (one side) for first orders. |
| **PCBWay** (CN) | ~$30 base for 4-layer 80×60 mm × 5 | ~$10 standard / ~$25 DHL | 4 days fab + 7–14 days ship | ~₹3,400 / ~₹4,500 DHL | Same as JLCPCB customs rules | Slightly better silkscreen quality, marginally pricier. Free up to 5 pieces of standard 2-layer; 4-layer always paid. |
| **PCBPower** (Gandhinagar, India) | ~₹2,500–4,000 for 5 pcs 4-layer prototype (no exact 80×60 published; estimate from [Zbotic comparison](https://zbotic.in/indian-pcb-manufacturers-compared-2026-price-quality-lead-time/)) | included | 7–10 days fab + 1–2 days courier | ~₹3,000–4,500 | **None — domestic manufacture, just 18% GST included.** | Best for production-rep builds in India, no customs uncertainty. Sometimes pricier than JLCPCB on small qty. |
| **Sierra Circuits** (USA) | $200+ for prototype 4-layer | ~$50 international ship | 2 days fab + 5 days ship | ~₹22,000+ | Definitively triggers customs at ~35% | **Not viable** for student budget. Quality is top-tier but irrelevant overhead here. |

**Recommendation: JLCPCB standard shipping.** Best price/quality. If a parts customs duty has already been paid this month and you want zero further customs touch, fall back to PCBPower.

**Order specification cheat-sheet for JLCPCB:**

* Layers: 4
* Dimensions: 80 × 60 mm (or as designed)
* Quantity: 5
* PCB thickness: 1.6 mm
* PCB color: green (cheapest); black is +$0 on most prototype tiers
* Surface finish: **ENIG** (gold) recommended for fine-pitch ADM2587E pads; HASL OK if you've kept everything ≥0.5 mm pitch
* Outer copper weight: 1 oz
* Inner copper weight: 0.5 oz (default; 1 oz is +$0 sometimes)
* Min via hole size: 0.3 mm
* Stackup: **JLC04161H-7628** (cheapest standard 4-layer stack)
* Confirm differential-impedance calculation outputs 100 Ω with 5/5/5 mil rules on this stack

## 7.6 AWS IoT Core — provisioning, costs, and pitfalls

### Free Tier (as of May 2026)

Per [aws.amazon.com/iot-core/pricing](https://aws.amazon.com/iot-core/pricing/), 12 months from account creation:

| Component | Free Tier | Beyond |
|-----------|-----------|--------|
| Connection minutes | 2,250,000 / month | $0.08 / 1M minutes |
| Messages (5 KB increments) | 500,000 / month | $1 / 1M messages |
| Registry / Shadow operations | 225,000 / month | $1.25 / 1M ops |
| Rules triggered / actions | 250,000 / 250,000 | $0.15 each / 1M |

For this project, 1 message every 5 seconds = 17,280 msg/day. 500 k / 17,280 = ~29 days. Throttling dev publishing to 1 msg/30 s gets you well clear of the limit through the full 6-week dev cycle.

### JITR vs JITP — which one to choose

| Approach | Best for | This project |
|----------|----------|---------------|
| **JITR (Just-in-time Registration)** — older. Device first connects, AWS publishes to `$aws/events/certificates/registered/<caID>`, a Lambda fires to attach policy + create Thing. Costs Lambda + custom Lambda code. | When you need bespoke onboarding logic (custom validation, third-party integrations) | Overkill |
| **JITP (Just-in-time Provisioning)** — newer (and now mature). Provisioning template + IAM role attached to a registered CA; AWS does the Thing creation + policy attachment server-side on first connect. No Lambda needed. | Standard fleets with a clear provisioning template | **Recommended.** Single template covers all gateways. |
| **Manual** (current scaffold) | Single-device proof-of-concept | Use for the 6-week dev; switch to JITP only if you pursue the §9 stretch. |

For the first build, the scaffolded approach (`aws iot create-keys-and-certificate` + manual NVS flash) is correct. For a stretch goal, follow [AWS's JITP setup guide](https://aws.amazon.com/blogs/iot/setting-up-just-in-time-provisioning-with-aws-iot-core/) and adapt the `aws-samples/aws-iot-jitp-sample-scripts` repo.

### Greengrass — should you use it?

**No** for this project. AWS IoT Greengrass V2 is the edge runtime for fleets that need local compute when offline (e.g. local ML inference, local Lambdas). The gateway here has a clearly defined uplink-only function with a small store-and-forward queue handling brief outages. Bringing in Greengrass would require a Linux-class processor (Pi, BeagleBone), bloating cost, complexity, and the security surface. Document the decision; don't implement Greengrass.

### Common provisioning pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `MBEDTLS_ERR_SSL_FATAL_ALERT_MESSAGE` on connect | Policy missing or scoped to wrong client ID | Re-issue policy with `iot:Connect` resource = exactly the `client-id`; this scaffold uses `gateway-001` |
| Connect succeeds but publish silently dropped | Policy missing `iot:Publish` on the topic ARN | Verify `iot:Publish` on `arn:aws:iot:ap-south-1:<acct>:topic/iot/gateway-001/telemetry` |
| Cert validates OK but Thing not auto-created | Using JITR without Lambda implementation | Either implement the Lambda or move to JITP |
| Region mismatch | endpoint URI region ≠ cert registration region | Always use `xxx-ats.iot.<region>.amazonaws.com`; recommend `ap-south-1` (Mumbai) for India latency |
| Time-of-day issues with TLS handshake | Device clock is 1970-01-01 | After Wi-Fi up, run SNTP sync before MQTT connect. esp-aws-iot examples do this. |

## 8. Cost summary table

| Item | INR | Source / note |
|------|-----|----------------|
| BOM (parts incl. spares) | 6,100 | §3.7 |
| Solder paste / wire / flux / IPA | 1,250 | §3.5 |
| PCB fabrication (JLCPCB, 5 boards, 4-layer, ENIG, shipping) | 2,800 | [JLCPCB shipping article](https://jlcpcb.com/help/article/customs,-duties-and-taxes) — ~$28 PCB + $8 shipping; allow ₹500 contingency for customs |
| Real-Modbus test target (Selec MFM384-R-C) | 3,000 | [Indiamart listings](https://www.indiamart.com/proddetail/selec-mfm-384-digital-multifunction-meter-16946019230.html) ₹2,999–4,347; assume mid-range with GST |
| Tools delta (ST-Link clone, USB-RS485, logic analyzer if not owned) | 1,500 | §4.1 minus assumed-owned bench gear |
| AWS IoT Core (6-week dev window) | 0 | Free Tier covers it if you throttle dev publishes to 1/5 s. Worst case ₹250 if over-tier. |
| Mouser shipping (one consolidated order) | 1,400 | Mouser India flat-rate |
| **Sub-total** | **~₹16,050** | |
| Contingency (15%) | 2,400 | |
| **Grand total** | **~₹18,450** | But if you already own a soldering iron, bench supply, scope, this drops to ~**₹14,500** as in §1 |

---

## 9. Stretch goals (only if time permits)

| Goal | Effort | Why it's worth it |
|------|--------|--------------------|
| **Modbus-TCP gateway mode** on the ESP32 | ~8 hrs | Bidirectional translation: a SCADA over Wi-Fi sends Modbus-TCP frames, gateway translates to RTU on the wire. Killer feature for industrial roles. Use `mongoose` or `esp-modbus` slave-TCP. |
| **Master + slave on the same gateway** | ~6 hrs | Gateway exposes its CBOR cache as readable Modbus registers — a SCADA can poll the gateway itself. Tiny addition to the STM32 firmware. |
| **OTA updates over MQTT for the ESP32** | ~10 hrs | Use [esp_https_ota](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/esp_https_ota.html) triggered by an MQTT command on `iot/<id>/cmd`. Industrial gold standard. |
| **OTA for the STM32 via the bridge UART** | ~12 hrs | ESP32 receives a firmware blob over MQTT, ferries it byte-by-byte over USART to the STM32 in bootloader mode via AN3155. Hard but very impressive. |
| **Web UI for slave-table config** | ~8 hrs | ESP32 hosts a `httpd` on the LAN before AWS connect; user enters slave IDs, registers, poll rates; saved to NVS, pushed to STM32 over the bridge. |
| **AWS IoT JITP fleet provisioning** | ~10 hrs | Replace the hand-NVS-flash workflow with [JITP](https://docs.aws.amazon.com/iot/latest/developerguide/jit-provisioning.html) — devices self-register on first connect using a registered CA. Real production approach. AWS recommends JITP over JITR for new designs ([Foundries blog](https://foundries.io/insights/blog/aws-iot-jitp/)). |
| **Greengrass V2 edge** | ~16 hrs | Likely too much for 6 weeks but mention as a vNext: install Greengrass on a small SBC alongside the gateway for local rules processing. Out of scope here. |

Pick **one** stretch goal. Recommend "Modbus-TCP gateway mode" — biggest resume impact for least effort, demonstrable in the demo video.

---

## 10. Resume bullet drafts

Two formats — pick the one that fits the existing resume's voice. Both deliberately quantify and reference the artefacts.

**Draft A — concise (1.5 lines each).**

> * Designed and built a dual-MCU industrial IoT gateway (STM32F103 FreeRTOS Modbus-RTU master + ESP32 MQTT-TLS bridge to AWS IoT Core) on a 4-layer Altium PCB with 2.5 kV galvanic isolation, TVS protection, and CBOR-framed UART bridge — taken from blank schematic to assembled DFM-verified board and live energy-meter demo in 6 weeks.
> * Implemented Modbus-RTU master from scratch on STM32F103 with FreeRTOS, achieving ≥99.9% CRC integrity at 9600-8N1 across a 1-hour soak against a Selec MFM384 energy meter; data published as CBOR over MQTT-TLS to AWS IoT Core with a store-and-forward queue surviving 5-minute Wi-Fi outages without message loss.

**Draft B — slightly punchier (single line each).**

> * Built a 4-layer DIN-rail-mountable Modbus-RTU → MQTT IoT gateway (STM32F103 + ESP32-WROOM-32E, ADM2587E 2.5 kV iso, Altium DFM-clean) shipping CBOR telemetry to AWS IoT Core; verified end-to-end against live energy meter.
> * Wrote bare-metal STM32 Modbus-RTU master in C/FreeRTOS (3.5-char timing, CRC-16, exception parsing) and a 300-byte CBOR encoder; integrated with an ESP32 MQTT-TLS bridge using AWS IoT mutual auth.

After Phase 7.6, iterate these against feedback from a friend / mentor and the BITS placement cell. Don't lock in copy until you have photos and scope traces to back up the claims.

---

## 11. References

1. [STM32F103C8 datasheet (ST DS5319)](https://www.st.com/resource/en/datasheet/stm32f103c8.pdf)
2. [STMicroelectronics product longevity policy](https://www.st.com/content/st_com/en/about/quality-and-reliability/product-longevity.html)
3. [STM32F103 longevity / EOL community thread](https://community.st.com/t5/stm32-mcus-products/stm32f103-longterm-availability-and-eol/td-p/195370)
4. [STM32 clones: CKS, GD32, CS32 — Hackaday](https://hackaday.com/2020/10/22/stm32-clones-the-good-the-bad-and-the-ugly/)
5. [How you can identify a fake STM32F103C8T6](https://hackmd.io/@ampheo/how-you-can-identify-a-fake-stm32f103c8t6)
6. [STM32G0B1CB product page](https://www.st.com/en/microcontrollers-microprocessors/stm32g0b1cb.html)
7. [STM32G0B1CBT6 on DigiKey](https://www.digikey.com/en/products/detail/stmicroelectronics/STM32G0B1CBT6/18086231)
8. [AN3070 — Managing the DE signal on STM32 USART (RS-485)](https://www.st.com/resource/en/application_note/an3070-managing-the-driver-enable-signal-for-rs485-and-iolink-communications-with-the-stm32s-usart-stmicroelectronics.pdf)
9. [AN1690 — Fail-safe biasing for ST485EB](https://www.st.com/resource/en/application_note/an1690-failsafe-biasing-for-st485eb-stmicroelectronics.pdf)
10. [AN4904 — STM32F1 → STM32F4 migration](https://www.st.com/resource/en/application_note/an4904-migration-of-microcontroller-applications-from-stm32f1-series-to-stm32f4-access-lines-stmicroelectronics.pdf)
11. [AN5969 — STM32G0 ↔ STM32C0 migration](https://www.st.com/resource/en/application_note/an5969-migrating-between-stm32g0-and-stm32c0-mcus-stmicroelectronics.pdf)
12. [ADM2587E datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/adm2582e-2587e.pdf)
13. [ADM2587E Mouser India product page](https://www.mouser.in/new/analog-devices/adi-adm2587e-rs485-transceiver/)
14. [ADM3251E datasheet (RS-232, original BOM entry)](https://www.analog.com/media/en/technical-documentation/data-sheets/adm3251e.pdf)
15. [MAX13487E / MAX13488E datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/max13487e-max13488e.pdf)
16. [TI LM2596 datasheet](https://www.ti.com/lit/ds/symlink/lm2596.pdf)
17. [Espressif ESP-IDF GitHub](https://github.com/espressif/esp-idf)
18. [ESP-IDF v5.4 getting started](https://docs.espressif.com/projects/esp-idf/en/v5.4/get-started/index.html)
19. [Espressif esp-modbus library](https://github.com/espressif/esp-modbus)
20. [esp-modbus on Espressif Component Registry](https://components.espressif.com/components/espressif/esp-modbus)
21. [Espressif esp-aws-iot SDK](https://github.com/espressif/esp-aws-iot)
22. [Espressif LTS release blog](https://developer.espressif.com/blog/support-for-lts-release-of-aws-iot-device-sdk-for-embedded-c-on-esp3/)
23. [AWS IoT Core pricing](https://aws.amazon.com/iot-core/pricing/)
24. [AWS IoT Core developer guide pricing](https://docs.aws.amazon.com/iot/latest/developerguide/iot-price.html)
25. [AWS IoT just-in-time provisioning docs](https://docs.aws.amazon.com/iot/latest/developerguide/jit-provisioning.html)
26. [AWS IoT JIT registration blog](https://aws.amazon.com/blogs/iot/just-in-time-registration-of-device-certificates-on-aws-iot/)
27. [AWS IoT JITP setup blog](https://aws.amazon.com/blogs/iot/setting-up-just-in-time-provisioning-with-aws-iot-core/)
28. [Foundries.io — Integrating with AWS IoT using JITP](https://foundries.io/insights/blog/aws-iot-jitp/)
29. [alejoseb/Modbus-STM32-HAL-FreeRTOS](https://github.com/alejoseb/Modbus-STM32-HAL-FreeRTOS)
30. [eziya/STM32_HAL_FREEMODBUS_RTU](https://github.com/eziya/STM32_HAL_FREEMODBUS_RTU)
31. [armink/FreeModbus_Slave-Master-RTT-STM32](https://github.com/armink/FreeModbus_Slave-Master-RTT-STM32)
32. [ADElectronics/STM32-FreeModbus-Example](https://github.com/ADElectronics/STM32-FreeModbus-Example)
33. [zivillian/esp32-modbus-gateway](https://github.com/zivillian/esp32-modbus-gateway)
34. [CNX Software — ESP32 Modbus gateway (Aug 2025)](https://www.cnx-software.com/2025/08/19/esp32-modbus-gateway-handles-rtu-tcp-ip-and-mqtt-for-industrial-iot/)
35. [Norvi — Modbus with ESP32](https://norvi.io/modbus-devices-with-esp32/)
36. [Moxa MGate MB3170 series](https://www.moxa.com/en/products/industrial-edge-connectivity/protocol-gateways/modbus-tcp-gateways/mgate-mb3170-mb3270-series)
37. [Advantech ADAM-4572](https://www.advantech.com/en-us/products/db72f61c-801b-4e61-8863-5d418f01b6e9/adam-4572/mod_1e01192d-95a1-42a4-b199-79343134f4ca)
38. [Modbus.org — Modbus over Serial Line V1.02](https://modbus.org/docs/Modbus_over_serial_line_V1_02.pdf)
39. [Industrial Monitor Direct — Modbus RTU timing](https://industrialmonitordirect.com/blogs/knowledgebase/modbus-rtu-timeouts-with-increased-message-length-specifications-and-solutions)
40. [Modbus Frame Timing Calculator (RFTools)](https://rftools.io/calculators/protocol/modbus-frame-timing)
41. [Opto22 — RS-485: Terminate, Bias, or Both?](https://blog.opto22.com/optoblog/rs-485-to-terminate-bias-or-both)
42. [Analog Devices — RS-485 cable spec guide](https://www.analog.com/en/resources/technical-articles/rs485-cable-specification-guide--maxim-integrated.html)
43. [JLCPCB customs, duties and taxes](https://jlcpcb.com/help/article/customs,-duties-and-taxes)
44. [JLCPCB capabilities & DFM rules](https://jlcpcb.com/capabilities/Capabilities)
45. [DIY Audio — JLCPCB India customs duty thread](https://www.diyaudio.com/community/threads/jlcpcb-india-custom-duty.379223/)
46. [PCBPower India](https://www.pcbpower.com/)
47. [Robu.in — ESP32-WROOM-32E 8M](https://robu.in/product/espressif-esp32-wroom-32e-8m-64mbit-flash-wifi-bluetooth-module)
48. [Robu.in — MAX485 TTL to RS485](https://robu.in/product/max485-ttl-rs485/)
49. [Robokits India — ST-Link V2 clone](https://robokits.co.in/programmers/stm32-stm08/st-link-v2)
50. [Quartz Components — STM32F103C8T6 Blue Pill board](https://quartzcomponents.com/products/stm32f103c8t6-development-board-stm32-arm-core-module)
51. [Selec — MFM384-R-C product page](https://www.selec.com/product-details/multifunction-meter-384-r-c)
52. [Indiamart — Selec MFM384 listing](https://www.indiamart.com/proddetail/selec-mfm-384-digital-multifunction-meter-16946019230.html)
53. [Schneider — PowerLogic PM5110 (India)](https://www.se.com/in/en/product/METSEPM5110/power-meter-powerlogic-pm5110-modbus-up-to-15th-harmonic-1do-33-alarms/)
54. [Altium Student Lab](https://www.altium.com/education/students)
55. [Feaser — STM32 Modbus RTU server tutorial](https://www.feaser.com/en/blog/2023/04/stm32-modbus-rtu-server-tutorial/)
56. [Hackaday — Test your Blue Pill for genuine STM32F103](https://hackaday.com/2021/06/23/test-your-blue-pill-board-for-a-genuine-stm32f103c8-mcu/)
57. [Espressif esp-aws-iot mqtt mutual auth example](https://github.com/espressif/esp-aws-iot/tree/master/examples/mqtt/tls_mutual_auth)
58. [AWS IoT — provisioning identity / device manufacturing whitepaper](https://docs.aws.amazon.com/whitepapers/latest/device-manufacturing-provisioning/provisioning-identity-in-aws-iot-core-for-device-connections.html)
59. [AgileVision.io — ESP32 and AWS IoT tutorial](https://agilevision.io/blog/esp32-and-aws-iot-tutorial/)
60. [Simply Explained — ESP-IDF storing AWS IoT certs in NVS](https://simplyexplained.com/blog/esp-idf-store-aws-iot-certificates-in-nvs-partition/)

---

*Generated 2026-05-12. Re-issue after each phase with as-built notes.*
