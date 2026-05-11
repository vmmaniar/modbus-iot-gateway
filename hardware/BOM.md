# Bill of Materials — Modbus IoT Gateway

| Ref          | Part                | Description                                  | Qty |
|--------------|---------------------|----------------------------------------------|-----|
| U1           | STM32F103C8T6       | Cortex-M3 MCU (Modbus master + bridge logic) | 1   |
| U2           | ESP32-WROOM-32E     | Wi-Fi/BLE MCU (MQTT-TLS to AWS)              | 1   |
| U3           | ADM3251E            | Isolated RS-485 transceiver w/ iso-Power     | 1   |
| U4           | LM2596S-5.0         | Switching buck regulator, 24 V → 5 V         | 1   |
| U5           | AMS1117-3V3         | LDO 5 V → 3V3 (digital)                      | 1   |
| U6           | AMS1117-3V3         | LDO 5 V → 3V3 (isolated side)                | 1   |
| D1           | SS34                | Schottky, reverse-polarity protection        | 1   |
| D2, D3       | PESD3V3L5UY         | TVS array on RS-485 A/B differential pair    | 2   |
| F1           | PTC self-reset 250mA| Polyfuse on the 24 V input                   | 1   |
| Y1           | 8 MHz crystal       | STM32 HSE                                    | 1   |
| C_dec        | 100 nF X7R 0603     | Decoupling, one per IC pin pair              | ~30 |
| C_bulk       | 10 µF 25V tantalum  | Bulk on each rail                            | 4   |
| J1           | Phoenix MC 1,5/4    | RS-485 + 24V terminal block                  | 1   |
| J2           | 2x5 1.27 mm SMD     | ARM Cortex-10 SWD/JTAG header                | 1   |
| J3           | USB-C receptacle    | ESP32 USB programming                        | 1   |

## Stack-up

4-layer Altium board, 1.6 mm FR4:

| Layer | Use         |
|-------|-------------|
| 1     | Signal      |
| 2     | GND plane   |
| 3     | +3V3 plane  |
| 4     | Signal      |

The RS-485 isolation boundary cuts across layers 2 and 3 to maintain >3 mm creepage.

## Production notes

* All decoupling capacitors must be placed within 5 mm of their IC pin.
* RS-485 A/B traces are routed as a 100 Ω differential pair (5/5/5 mil) and terminate at the connector with a 120 Ω resistor + 0.01 µF AC termination.
* ESD ground for the TVS array is tied to chassis (frame ground) via a 1 MΩ + 1 nF bleed network — not directly to digital GND.
* Test points TP1..TP6 give scope access to: USART1 TX, USART2 TX, DE/RE, +5V, +3V3, +3V3_ISO.
