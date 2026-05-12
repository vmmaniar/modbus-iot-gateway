"""TCP-mode Modbus slave simulator (pymodbus 3.13 SimData/SimDevice API).

The serial-mode `fake_slave.py` requires a real or virtual COM port, which
isn't always available during early development. This TCP variant exposes the
same simulated register map on a local TCP port so the Python firmware-twin
(or any Modbus TCP master) can exercise the protocol without cables.

  python tcp_slave.py --port 5020

The register map is identical to fake_slave.py:
  - Slave 0x01 holding-regs 0x0000..0x0001 : tank pressure (Pa, u32 BE)
  - Slave 0x01 holding-reg  0x0010         : ambient temp  (centi-degC)
  - Slave 0x02 holding-regs 0x0020..0x0023 : flow + totalizer (u32 each)
"""

from __future__ import annotations

import argparse
import asyncio
import math
import threading
import time

from pymodbus.server import StartAsyncTcpServer
from pymodbus.simulator import SimData, SimDevice, DataType


def build_devices() -> list[SimDevice]:
    # Each SimData backs a contiguous block of holding registers. We allocate
    # generously sized blocks so the firmware can point its `register_count`
    # at any address inside without an out-of-range fault.
    slave1 = SimDevice(1, simdata=[
        SimData(0x0000, values=[0] * 64, datatype=DataType.UINT16),
    ])
    slave2 = SimDevice(2, simdata=[
        SimData(0x0000, values=[0] * 64, datatype=DataType.UINT16),
    ])
    return [slave1, slave2]


def update_loop(devices: list[SimDevice], stop: threading.Event) -> None:
    """Background updater — keeps the simulated register values cycling."""
    block_s1 = devices[0].simdata[0].values
    block_s2 = devices[1].simdata[0].values
    t0 = time.monotonic()
    while not stop.is_set():
        t = time.monotonic() - t0
        pressure_pa = int(101325 + 200 * math.sin(t / 5))
        temp_centi  = int(2500 + 50 * math.sin(t / 30))
        flow_m3h    = int(120 + 10 * math.sin(t / 7))
        totalizer   = int(t * 0.0333)

        # Slave 1: holding regs at 0x0000 (u32 BE pressure) and 0x0010 (temp)
        block_s1[0x0000] = (pressure_pa >> 16) & 0xFFFF
        block_s1[0x0001] = pressure_pa & 0xFFFF
        block_s1[0x0010] = temp_centi & 0xFFFF
        # Slave 2: holding regs at 0x0020..0x0023 (u32 flow, u32 totalizer)
        block_s2[0x0020] = (flow_m3h >> 16) & 0xFFFF
        block_s2[0x0021] = flow_m3h & 0xFFFF
        block_s2[0x0022] = (totalizer >> 16) & 0xFFFF
        block_s2[0x0023] = totalizer & 0xFFFF
        time.sleep(0.1)


async def serve(host: str, port: int, stop: threading.Event,
                ready: threading.Event | None = None):
    devices = build_devices()
    updater = threading.Thread(target=update_loop, args=(devices, stop), daemon=True)
    updater.start()
    if ready is not None:
        ready.set()
    await StartAsyncTcpServer(context=devices, address=(host, port))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5020)
    args = parser.parse_args()
    print(f"Modbus TCP slave on {args.host}:{args.port} — Ctrl+C to stop")
    stop = threading.Event()
    try:
        asyncio.run(serve(args.host, args.port, stop))
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
