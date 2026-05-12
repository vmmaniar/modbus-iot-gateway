# KiCad design package

Open `modbus-iot-gateway.kicad_pro` in **KiCad 8.0 or later**.

## Project status

This directory contains the KiCad **project skeleton** with all design rules,
net classes, and design constraints pre-configured. The schematic itself is
authored interactively in the KiCad GUI per the comprehensive specification
in [`design_spec.md`](design_spec.md) — capturing schematic geometry in plain
text would be enormous and error-prone, so the design spec is the source of
truth and the `.kicad_sch` files are produced from it.

## Sub-paths

```
modbus-iot-gateway.kicad_pro    Project file with all design rules + net classes
design_spec.md                  Complete schematic + layout specification (the build instructions)
stackup.md                      4-layer board stackup definition for JLCPCB JLC04161H-7628
libraries/                      Custom symbols + footprints for non-stdlib parts (ADM2587E, ESP32-WROOM-32E)
sheets/                         Hierarchical schematic sheets (start here once you open the project)
exports/                        Generated artefacts: PDF schematic, Gerbers, drill, BOM CSV, pick-and-place
```

## Pre-configured design constraints

The project file already has the right design rules wired up — you don't need
to fiddle with KiCad's preferences for the basics:

| Setting | Value | Why |
|---|---|---|
| Min track width | 0.127 mm (5 mil) | JLCPCB 4-layer default capability |
| Min clearance | 0.127 mm | Same |
| Min via | 0.45 mm / 0.3 mm drill | JLCPCB 4-layer default |
| Min hole-to-hole | 0.25 mm | JLCPCB minimum |
| Min copper-edge clearance | 0.5 mm | Industry standard, generous |

## Net classes

Already defined and pattern-assigned by net-name regex:

| Net class | Track width | Use |
|---|---|---|
| `Default` | 0.25 mm | All signal traces |
| `Power` | 0.60 mm | `+24V`, `+5V`, `+3V3*`, `GND`, `ISO_GND` |
| `RS485` | 0.25 mm, 0.18 mm diff pair | `RS485_A`, `RS485_B` (100 Ω differential) |
| `USB` | 0.20 mm, 0.15 mm diff pair | `USB_D+`, `USB_D-` (90 Ω differential) |

When you start routing, drop traces with their net name and KiCad applies the
class automatically.

## Workflow for whoever finishes the schematic

1. Open project in KiCad 8.
2. Read [`design_spec.md`](design_spec.md) end to end — it lists every
   component, every pin assignment, every interconnect.
3. Open the schematic editor. Create three hierarchical sheets per
   `design_spec.md` § 4 (power, digital, isolated RS-485).
4. Place components per the BOM table in `design_spec.md` § 5. Footprints are
   pre-specified.
5. Wire per the net table in `design_spec.md` § 6.
6. Run **ERC** → fix until clean.
7. Switch to PCB editor.
8. Set board outline (80 × 60 mm) per `design_spec.md` § 7.
9. Place components in the zones called out in § 8.
10. Route in the order specified in § 9 of the design spec.
11. Pour copper polygons per § 10.
12. Run **DRC** → fix until clean.
13. Plot Gerbers + drill + position files → `exports/`.

## CI

The repo's `.github/workflows/kicad-checks.yml` (added in Phase 4) runs ERC
and DRC headlessly via the `kiauto` Docker image on every push. It will fail
loudly if anything regresses.
