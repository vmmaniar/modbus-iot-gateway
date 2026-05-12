# KiCad design specification — Modbus IoT Gateway

> **What this document is.** Every component, every net, every footprint, every clearance — written down so that whoever opens KiCad next can reproduce the design without re-deriving it. Treat this as the contract between the architecture and the CAD file.

> **Target fab:** JLCPCB 4-layer JLC04161H-7628 stack, 1.6 mm FR4, 1 oz/2 oz/0.5 oz/1 oz copper. Standard 35 µm finish copper on outers.

> **Target dimensions:** 80 × 60 mm. DIN-rail-mount footprint with 4 × M3 fixing holes on a 70 × 50 mm rectangle.

## 1. Document conventions

- Net names use `UPPERCASE_SNAKE_CASE`.
- Component refs follow KiCad defaults: U, R, C, D, F, J, T, Y for the obvious classes.
- "TBD" means the design *intends* something specific (see context) but the exact value/footprint should be confirmed at placement time.
- Pin numbers reference the part's datasheet, not the KiCad symbol pin number (they're usually the same, but you should verify against the symbol you ultimately pick).

## 2. Block diagram

```
+---------+                       +---------+
|  24 V   |── F1 ── D1 ── C_BULK ─┤ LM2596  |── 5V ── AMS1117_DIG ── +3V3_DIG ── STM32 + ESP32
|  input  |                       └─────────┘    \                              + bridge UART
+---------+                                       ── AMS1117_ISO ── +3V3_ISO ── (none today: ADM2587E
                                                                                 has its own isoPower
                                                                                 generated from +5V_ISO)
                                                                                 see note in §5

                                                       +--- iso boundary ---+
                                                       ┊                    ┊
                              ESP32 ───── USART2 ───── STM32 ───── USART1 ──┊── ADM2587E ── RS-485 A/B/GND
                                                                            ┊
                                                       ┊                    ┊
```

## 3. Layer stackup (4-layer, JLCPCB JLC04161H-7628)

| Layer | Use | Notes |
|---|---|---|
| F.Cu (Top) | Signal | All ICs, all connectors, fine signal routing |
| In1.Cu | GND plane | Continuous, broken only by the 8 mm iso slot |
| In2.Cu | +3V3_DIG plane | Pour. ISO_GND occupies the isolated half (separated by slot) |
| B.Cu (Bottom) | Signal | Power routing + ground stitching; can also host the LM2596 inductor |

Differential pair impedance with 5 mil trace / 5 mil space over 4.5 mil prepreg ≈ **100 Ω differential** for RS-485 / **90 Ω differential** for USB. KiCad's built-in impedance calculator confirms within ±5 %.

## 4. Hierarchical sheets

Three top-level child sheets feed into the root.

### 4.1 Sheet: `power.kicad_sch`

Components: F1, D1, U_LM2596, L1, D2, C_BULK_IN, C_BULK_OUT, U_LDO_DIG (AMS1117), C_LDO_DIG_IN, C_LDO_DIG_OUT, U_LDO_ISO (AMS1117), C_LDO_ISO_IN, C_LDO_ISO_OUT.

Sheet pins (going up to root): `+24V_IN`, `GND`, `+5V`, `+3V3_DIG`, `+3V3_ISO`.

### 4.2 Sheet: `digital.kicad_sch`

Components: U_STM32 (STM32F103C8T6), U_ESP32 (ESP32-WROOM-32E), Y1 (8 MHz crystal), C_Y1A, C_Y1B, USB-C receptacle, USBLC6-2P6 ESD diode, R_PULLUP × 4 (boot + NRST), JTAG/SWD 10-pin header J_SWD, bridge UART headers, BOOT0 jumper, LED_PWR + LED_STAT + their series resistors, decoupling caps (~16 × 100 nF, 6 × 1 µF, 2 × 10 µF).

Sheet pins (going up to root): `+3V3_DIG`, `GND`, `+5V`, `RS485_TX_FROM_MCU` (3.3 V TTL going to ADM2587E primary side via the iso barrier? No — see §5 note: the ADM2587E sits next to the STM32, and the iso barrier is *internal to the chip*. So this net stays on the digital side as TTL UART), `RS485_RX_TO_MCU`, `RS485_DE_RE_FROM_MCU`.

### 4.3 Sheet: `rs485.kicad_sch`

Components: U_RS485 (ADM2587E), TVS_A (PESD3V3L5UY on A line), TVS_B (PESD3V3L5UY on B line), R_TERM (120 Ω across A/B), R_BIAS_HIGH (680 Ω from +3V3_ISO to A), R_BIAS_LOW (680 Ω from B to ISO_GND), C_AC_TERM (10 nF AC-couple termination, optional), J_BUS (Phoenix MC1.5/4 screw terminal), decoupling caps (4 × 100 nF, 2 × 4.7 µF, 2 × 10 µF on isoPower side).

Sheet pins (going up to root): `+5V` (note: ADM2587E generates its own isoPower from primary +5V), `GND`, `RS485_TX_FROM_MCU`, `RS485_RX_TO_MCU`, `RS485_DE_RE_FROM_MCU`, `RS485_A`, `RS485_B`, `RS485_GND` (terminal pin to the cable shield).

## 5. Bill of components (KiCad library + footprint table)

| Ref | Part | KiCad symbol | KiCad footprint | Notes |
|---|---|---|---|---|
| U_STM32 | STM32F103C8T6 | `MCU_ST_STM32F1:STM32F103C8Tx` | `Package_QFP:LQFP-48_7x7mm_P0.5mm` | |
| U_ESP32 | ESP32-WROOM-32E | `RF_Module:ESP32-WROOM-32` | `RF_Module:ESP32-WROOM-32` | |
| U_RS485 | ADM2587EBRWZ | `Interface_UART:ADM2587E` (in custom lib) | `Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm` | Width 7.5 mm (W body); confirm datasheet |
| U_LM2596 | LM2596S-5.0 | `Regulator_Switching:LM2596S-5` | `Package_TO_SOT_SMD:TO-263-5_TabPin3` | TO-263 surface mount, gnd via thermal pad |
| U_LDO_DIG | AMS1117-3.3 | `Regulator_Linear:AMS1117-3.3` | `Package_TO_SOT_SMD:SOT-223-3_TabPin2` | |
| U_LDO_ISO | AMS1117-3.3 | (same) | (same) | Only needed if you want a separate `+3V3_ISO` rail beyond the ADM2587E's internal isoPower — see §5 note. |
| Y1 | 8 MHz crystal | `Device:Crystal_GND24_Small` | `Crystal:Crystal_SMD_HC49-SD` | Two GND mount tabs |
| D1 | SS34 Schottky | `Diode:SS34` | `Diode_SMD:D_SMA` | Reverse-polarity protection |
| TVS_A/B | PESD3V3L5UY | `Diode:PESD3V3L5UY` | `Package_TO_SOT_SMD:SOT-323_SC-70` | Bidirectional TVS |
| F1 | PolyFuse 250 mA | `Device:Polyfuse` | `Resistor_SMD:R_1812_4532Metric` | Wickmann ZEN056V230A24LS or equivalent |
| L1 | LM2596 inductor 33 µH 3A | `Device:L` | `Inductor_SMD:L_Wuerth_WE-PD-Typ-S` | 12×12 mm shielded SMD inductor |
| C_BULK_IN | 47 µF 50 V electrolytic | `Device:C_Polarized` | `Capacitor_THT:CP_Radial_D6.3mm_P2.50mm` | Through-hole, mount upright |
| C_BULK_OUT | 220 µF 16 V electrolytic | `Device:C_Polarized` | `Capacitor_THT:CP_Radial_D6.3mm_P2.50mm` | LM2596 output ripple cap |
| C_LDO_*_OUT | 22 µF 6.3 V tantalum | `Device:C_Polarized_Small` | `Capacitor_SMD:CP_Elec_3x5.4` | |
| C_DEC (×18) | 100 nF X7R 0603 | `Device:C` | `Capacitor_SMD:C_0603_1608Metric` | One per IC supply pin |
| C_BULK_3V3 (×3) | 10 µF X5R 0805 | `Device:C` | `Capacitor_SMD:C_0805_2012Metric` | |
| C_Y1A/B | 22 pF C0G 0603 | `Device:C` | `Capacitor_SMD:C_0603_1608Metric` | Crystal load caps |
| C_AC_TERM | 10 nF X7R 0603 | `Device:C` | `Capacitor_SMD:C_0603_1608Metric` | RS-485 AC termination |
| R_TERM | 120 Ω 1 % 0805 | `Device:R` | `Resistor_SMD:R_0805_2012Metric` | RS-485 bus termination |
| R_BIAS_HIGH/LOW | 680 Ω 1 % 0805 | `Device:R` | `Resistor_SMD:R_0805_2012Metric` | Fail-safe bias per ST AN1690 |
| R_PULLUP (×4) | 10 kΩ 1 % 0603 | `Device:R` | `Resistor_SMD:R_0603_1608Metric` | NRST, BOOT0, etc. |
| R_LED (×2) | 1 kΩ 0603 | `Device:R` | `Resistor_SMD:R_0603_1608Metric` | |
| LED_PWR/STAT | 0603 green/yellow | `Device:LED` | `LED_SMD:LED_0603_1608Metric` | |
| J_BUS | Phoenix MC1.5/4-G-3.5 | `Connector:Conn_01x04_Pin` | `Connector_PhoenixContact:PhoenixContact_MC_1,5_4-G-3.5_1x04_P3.50mm_Horizontal` | RS-485 + 24V + GND |
| J_USB | USB-C receptacle | `Connector:USB_C_Receptacle` | `Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12` | ESP32 programming |
| J_SWD | 2×5 1.27 mm SMD | `Connector_Generic:Conn_02x05_Odd_Even` | `Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD` | ARM Cortex 10-pin |
| TP1..TP6 | Test points | `Connector:TestPoint` | `TestPoint:TestPoint_Pad_D1.5mm` | +5V, +3V3_DIG, UART_TX, UART_RX, DE/RE, GND |
| H1..H4 | M3 mounting hole | `Mechanical:MountingHole` | `MountingHole:MountingHole_3.2mm_M3` | Non-plated |

**Notes on the ADM2587E:**

- The ADM2587E has an integrated isoPower DC-to-DC that takes the **primary-side 5 V** input and generates the isolated-side 5 V it needs internally. You do **not** need an external `+3V3_ISO` LDO unless you have additional isolated-side components (we don't). So `U_LDO_ISO` and the `+3V3_ISO` net are technically optional. Keep them in the schematic as DNP / "future" components.
- The DE and ~RE pins on the ADM2587E are typically tied together so a single GPIO drives both (active high enables driver, active low enables receiver). Make sure the schematic ties them.

## 6. Net table (every named connection)

Power:

| Net | From | To |
|---|---|---|
| `+24V_IN` | J_BUS pin 4 | F1 pin 1 |
| `+24V` (post-fuse) | F1 pin 2 | D1 anode |
| `+24V_PROT` | D1 cathode | C_BULK_IN+, LM2596 Vin |
| `+5V` | LM2596 Vout, ADM2587E VCC1, U_LDO_DIG Vin, U_LDO_ISO Vin (DNP), C_BULK_OUT+ | |
| `+3V3_DIG` | U_LDO_DIG Vout, STM32 VDD pins, ESP32 3V3 pin, all 100 nF decoupling caps on digital side | |
| `+3V3_ISO` (DNP) | U_LDO_ISO Vout — unused in v1 | |
| `GND` | LM2596 GND, all digital-side decoupling, ADM2587E GND1, J_USB shell, mounting holes | |
| `ISO_GND` | ADM2587E GND2 (pin 13), TVS_A/B cathodes (yes really — TVS-to-iso-GND), J_BUS pin 3 (cable shield) | |

STM32 ↔ ADM2587E (digital-side TTL UART):

| Net | From | To |
|---|---|---|
| `RS485_TX_FROM_MCU` | STM32 PA9 (USART1_TX) | ADM2587E pin 6 (DI) |
| `RS485_RX_TO_MCU` | STM32 PA10 (USART1_RX) | ADM2587E pin 8 (RO) |
| `RS485_DE_RE_FROM_MCU` | STM32 PA8 | ADM2587E pin 4 (DE) + pin 5 (~RE) tied |

ADM2587E ↔ field bus:

| Net | From | To |
|---|---|---|
| `RS485_A` | ADM2587E pin 14 (A) | R_TERM pin 1, R_BIAS_HIGH pin 1, TVS_A pin 1, J_BUS pin 1 |
| `RS485_B` | ADM2587E pin 15 (B) | R_TERM pin 2, R_BIAS_LOW pin 1, TVS_B pin 1, J_BUS pin 2 |

STM32 ↔ ESP32 (bridge UART):

| Net | From | To |
|---|---|---|
| `BRIDGE_TX` | STM32 PA2 (USART2_TX) | ESP32 GPIO16 (RX of UART1) |
| `BRIDGE_RX` | STM32 PA3 (USART2_RX) | ESP32 GPIO17 (TX of UART1) |

STM32 clocking and reset:

| Net | From | To |
|---|---|---|
| `HSE_IN` | STM32 PD0/OSC_IN | Y1 pin 1, C_Y1A pin 1 |
| `HSE_OUT` | STM32 PD1/OSC_OUT | Y1 pin 3, C_Y1B pin 1 |
| `Y1_GND` | Y1 pins 2 and 4 | GND |
| `C_Y1A` pin 2, `C_Y1B` pin 2 | | GND |
| `NRST` | STM32 NRST | R_PULLUP × 10 kΩ to +3V3_DIG, J_SWD pin 10 |
| `BOOT0` | STM32 BOOT0 | R_PULLUP × 10 kΩ to GND (run from flash) |

ESP32 strapping pins:

| Pin | Connection | Reason |
|---|---|---|
| EN | 10 kΩ pull-up to +3V3_DIG + 1 µF cap to GND | Power-on delay |
| GPIO0 | 10 kΩ pull-up to +3V3_DIG, exposed as test point | Hold low at reset for download mode |
| GPIO2 | NC (with internal pull-down) | Strapping pin — leave alone |
| GPIO12 | NC (with internal pull-down) | Strapping pin — leave alone |
| GPIO15 | NC | |

USB-C (ESP32 programming):

| Net | From | To |
|---|---|---|
| `USB_VBUS` | J_USB pins A4, B4, A9, B9 | C_BULK_IN+, ferrite bead → +5V (or directly to LM2596 Vin via a Schottky OR-ing diode) |
| `USB_D+` | J_USB pins A6, B6 | USBLC6-2P6 pin 4, ESP32 GPIO19 (or whatever U0TXD/U0RXD bridge you've decided) |
| `USB_D-` | J_USB pins A7, B7 | USBLC6-2P6 pin 1, ESP32 partner pin |
| `USB_CC1` | J_USB pin A5 | 5.1 kΩ to GND (config for "device, 5V default") |
| `USB_CC2` | J_USB pin B5 | 5.1 kΩ to GND |

SWD/JTAG (STM32):

| Pin | Net |
|---|---|
| J_SWD pin 1 | +3V3_DIG |
| J_SWD pin 2 | SWDIO (STM32 PA13) |
| J_SWD pin 3, 5, 9 | GND |
| J_SWD pin 4 | SWCLK (STM32 PA14) |
| J_SWD pin 6 | SWO (STM32 PB3) |
| J_SWD pin 7 | KEY (no connect) |
| J_SWD pin 8 | NC |
| J_SWD pin 10 | NRST |

LEDs:

| Net | From | To |
|---|---|---|
| `LED_PWR` | +3V3_DIG | R_LED_PWR 1 kΩ → LED anode → cathode to GND |
| `LED_STAT` | STM32 PC13 | R_LED_STAT 1 kΩ → LED anode → cathode to GND |

## 7. PCB board outline

- 80 × 60 mm rectangle.
- 4 × M3 mounting holes at coordinates (5, 5), (75, 5), (5, 55), (75, 55).
- 8 mm × 35 mm routed slot for galvanic isolation, running vertically from (52, 10) to (52, 50). The slot crosses *all four layers* (KiCad: User_Drawings + Edge.Cuts) and the GND/3V3 planes are broken by it.

## 8. Component placement zones

```
+----+ J_BUS (right edge)
|    |
|  R + ADM2587E + termination + biasing + TVS  ─── isolated zone ───  iso slot ───
|    +─────────────────────────────────────────                     ─── digital zone
|  R |                                                                |
|    |                                                                |  STM32 (centre-left)
|    |                                                                |  ESP32 (top-left)
|  R |                                                                |
|    | LM2596 + LDOs (lower-right of digital zone)                    |
|    +─── USB-C (top edge)
+----+ SWD (bottom edge)
```

- ADM2587E pins 9-16 are on the iso side, pins 1-8 on the primary side; physically straddle the slot.
- LM2596 thermal pad needs ~50 mm² of copper pour for thermal dissipation; route it on Layer 4 (B.Cu) and stitch with vias to GND plane.
- The 8 MHz crystal must be < 10 mm from the STM32, with the load caps tied directly to the STM32's VSSA pin, not bulk GND.
- ESP32 antenna corner gets a copper keepout 5 mm into the board from the edge — no copper, no plane.

## 9. Routing order

1. **RS-485 differential pair** (`RS485_A` / `RS485_B`) — 100 Ω diff, top layer, 5/5/5 mil, short and length-matched to within 2 mm.
2. **USB diff pair** (`USB_D+` / `USB_D-`) — 90 Ω diff, top layer, 4/5/4 mil, length-matched.
3. **+24V → LM2596 power input loop** — short, wide (40 mil), keep the loop small.
4. **+5V → ADM2587E VCC1** — wide trace, decoupling caps within 2 mm.
5. **HSE crystal** — shortest possible trace, 20 mil ground guard rings around HSE_IN and HSE_OUT.
6. **Bridge UART** — top layer, 8 mil, short.
7. **Everything else** — auto-route or finish manually.

## 10. Copper pours

- **In1.Cu (GND plane)**: continuous pour, only broken by the iso slot. Stitch vias every 5 mm around the slot edge.
- **In2.Cu (+3V3_DIG plane)**: pour on the digital half only; iso half is unused in v1 (would be `+3V3_ISO` if populated).
- **F.Cu (Top)**: ground pour to fill empty space, especially under the ESP32 module to reduce loop area.
- **B.Cu (Bottom)**: ground pour for thermal dissipation under LM2596.

## 11. Silkscreen / fabrication

- Project name and revision on top silk near J_BUS.
- Pin 1 indicators on all polarised components.
- TP1-TP6 labels (test point names).
- 3 fiducials on top + 3 on bottom, 1 mm copper, 2 mm mask aperture, asymmetric pattern.
- Reference designators all visible (no IC ref hidden under the IC body).
- Pin direction arrow on J_BUS (A / B / +24V / GND from top to bottom).

## 12. Production outputs (saved to `exports/`)

Per Phase 5 in `BUILD_PLAN.md`:

- Schematic PDF (one page per hierarchical sheet + the root, 4 pages total).
- Gerbers (RS-274X, 8 layers: 4 copper + 2 solder mask + 2 silkscreen).
- Excellon drill file.
- Pick-and-place CSV (centroid file).
- BOM CSV (refdes, qty, value, footprint, manufacturer, MPN, supplier P/N).
- Board top + bottom render PDFs.
- DRC report (zero violations).
- ERC report (zero violations).

These are all produced via KiCad's "Plot" + "Fabrication Outputs" menus, or
scripted via `kicad-cli` (KiCad 8.0+) for the CI job in
`.github/workflows/kicad-checks.yml`.
