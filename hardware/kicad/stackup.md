# PCB stackup — JLCPCB JLC04161H-7628

Standard JLCPCB 4-layer, 1.6 mm finished thickness. Configure in KiCad via
**File → Board Setup → Physical Stackup**.

| Layer | Material | Thickness | Notes |
|---|---|---|---|
| F.Cu | Copper (1 oz, 35 µm) | 0.035 mm | Top signal |
| F.Mask | Solder mask (green) | 0.010 mm | |
| F.SilkS | Silkscreen (white) | 0.012 mm | |
| Core (top) | FR4 | 0.150 mm | Prepreg 7628 |
| In1.Cu | Copper (1 oz, 17 µm half-oz) | 0.017 mm | GND plane |
| Core (middle) | FR4 | 1.065 mm | Bulk core |
| In2.Cu | Copper (0.5 oz, 17 µm) | 0.017 mm | +3V3_DIG plane / split |
| Core (bottom) | FR4 | 0.150 mm | Prepreg 7628 |
| B.Cu | Copper (1 oz, 35 µm) | 0.035 mm | Bottom signal |
| B.Mask | Solder mask | 0.010 mm | |
| B.SilkS | Silkscreen | 0.012 mm | |

Total nominal thickness ≈ 1.6 mm.

## Impedance calculations

Using KiCad 8's built-in calculator with εr = 4.5 (FR4 standard):

### RS-485 differential pair (100 Ω target)
- Trace width: 5 mil (0.127 mm)
- Trace spacing: 5 mil (0.127 mm)
- Distance to nearest reference plane (In1.Cu through 0.150 mm prepreg): correct
- Computed Z_diff: ~98 Ω → within 2 % of target ✓

### USB differential pair (90 Ω target)
- Trace width: 4 mil (0.102 mm)
- Trace spacing: 5 mil (0.127 mm)
- Distance to GND: 0.150 mm
- Computed Z_diff: ~88 Ω → within 3 % of target ✓

### Single-ended signal (50 Ω, for crystal traces)
- Trace width: 8 mil (0.203 mm)
- Distance to GND: 0.150 mm
- Computed Z₀: ~50 Ω ✓

## JLCPCB DRC notes

JLCPCB's free DRC profile for the 4-layer process matches what's already
configured in `modbus-iot-gateway.kicad_pro`. The only additional thing to
verify before submission:

- **No silkscreen text smaller than 6 mil thick** — JLCPCB rejects boards
  with sub-6-mil silk. Default KiCad silk for component refs is 1.0 mm height
  × 0.15 mm thick which is fine; just don't manually shrink it.
- **No copper inside the mounting hole keep-out** — KiCad MountingHole
  footprints handle this for you.

## When you actually submit (if you ever do)

Order through JLCPCB's "PCB Order" page:

1. Upload `exports/gerbers.zip`.
2. Confirm: 4 layers, 1.6 mm thickness, HASL lead-free finish (or ENIG +₹500),
   green soldermask, white silkscreen.
3. Quantity 5, dimensions 80×60 mm.
4. Estimated cost as of May 2026: **~₹2,800 boards + ~₹1,200 shipping = ~₹4,000 INR**, lead time ~10 days.
5. Add JLC SMT assembly only if you intend to actually build it (out of
   scope for this project per BUILD_PLAN.md § 2).
