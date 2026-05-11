# Schematic notes

## Isolation strategy

```
   24V industrial bus  →  PTC fuse  →  reverse-polarity diode  →  LM2596 → 5V → AMS1117 → 3V3_DIG
                                                                            └→ AMS1117 → 3V3_ISO (only for ADM3251E primary side)
   RS-485 A/B  →  TVS array  →  ADM3251E isolated transceiver  →  STM32 USART1
                                            ┊
                                  iso-barrier (2.5 kV)
```

The ADM3251E has integrated isoPower DC/DC, so the bus-side 3V3_ISO rail is generated on the IC and does not cross the isolation barrier.

## Reset and clocking

* STM32 boot: BOOT0 jumpered low (run from flash), BOOT1 pulled low.
* HSE: 8 MHz crystal with 18 pF load caps. PLL × 9 → 72 MHz SYSCLK.
* ESP32 uses its module's onboard 40 MHz crystal.

## DE/RE direction control

Tied together on PA8 (active high enables driver, active low enables receiver). Software flips this around each transmit — see `rs485_uart.c`.

## ESD path

ESD strikes on the A/B port discharge through PESD3V3L5UY → frame ground (chassis). The 1 MΩ + 1 nF bleed prevents floating chassis from accumulating static while keeping the AC return impedance high.

## DFM checklist

| Item                                                 | Status |
|------------------------------------------------------|--------|
| Solder mask ≥ 4 mil between pads                     | ✓      |
| Silkscreen no thinner than 6 mil                     | ✓      |
| Tented vias on bottom layer                          | ✓      |
| Test points labeled and ≥ 1 mm dia                   | ✓      |
| Fiducials on top + bottom (3 each, 120° spaced)      | ✓      |
| No 90° trace bends                                   | ✓      |
| All ICs single-orientation per panel                 | ✓      |
| Pickup & place footprint clearance                   | ✓      |
| Component height < 12 mm (enclosure clearance)       | ✓      |
