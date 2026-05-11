"""Modbus RTU slave simulator that mimics a small industrial site:
  - Slave 0x01 holding-regs 0x0000..0x0001: tank pressure (Pa, u32 big-endian)
  - Slave 0x01 holding-reg  0x0010:         ambient temp (centi-degC, s16)
  - Slave 0x02 holding-regs 0x0020..0x0023: flow meter (m3/h, totalizer)

Use this to bring up the STM32 firmware without a real PLC.

  pip install -r requirements.txt
  python fake_slave.py --port COM5            # Windows
  python fake_slave.py --port /dev/ttyUSB0    # Linux
"""

from __future__ import annotations

import argparse
import math
import time

from pymodbus.server import StartSerialServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import (
    ModbusServerContext, ModbusSlaveContext, ModbusSequentialDataBlock,
)


def make_context() -> ModbusServerContext:
    slave1 = ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, [0] * 256),
        zero_mode=True,
    )
    slave2 = ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, [0] * 256),
        zero_mode=True,
    )
    return ModbusServerContext(slaves={1: slave1, 2: slave2}, single=False)


def update_loop(ctx: ModbusServerContext) -> None:
    """Update register values in a background-friendly tight loop."""
    t0 = time.monotonic()
    while True:
        t = time.monotonic() - t0
        pressure_pa = int(101325 + 200 * math.sin(t / 5))
        temp_centi  = int(2500 + 50 * math.sin(t / 30))     # 25.00 °C ± 0.5
        flow_m3h    = int(120 + 10 * math.sin(t / 7))
        totalizer   = int(t * 0.0333)

        ctx[1].setValues(3, 0x0000, [(pressure_pa >> 16) & 0xFFFF, pressure_pa & 0xFFFF])
        ctx[1].setValues(3, 0x0010, [temp_centi & 0xFFFF])
        ctx[2].setValues(3, 0x0020, [
            (flow_m3h >> 16) & 0xFFFF, flow_m3h & 0xFFFF,
            (totalizer >> 16) & 0xFFFF, totalizer & 0xFFFF,
        ])
        time.sleep(0.1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=9600)
    args = parser.parse_args()

    ctx = make_context()

    import threading
    t = threading.Thread(target=update_loop, args=(ctx,), daemon=True)
    t.start()

    identity = ModbusDeviceIdentification(
        info_name={"VendorName": "Maniar Industries", "ProductCode": "FAKE-PLC",
                   "VendorUrl": "https://github.com/vmmaniar", "ProductName": "FakeSlave"}
    )

    print(f"Modbus RTU slave on {args.port} @ {args.baud} 8N1 — Ctrl+C to stop")
    StartSerialServer(
        context=ctx,
        identity=identity,
        port=args.port,
        baudrate=args.baud,
        stopbits=1,
        bytesize=8,
        parity="N",
        framer="rtu",
    )


if __name__ == "__main__":
    main()
