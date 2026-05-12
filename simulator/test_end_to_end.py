"""End-to-end Phase 0 integration test.

Spawns the TCP simulator in a background thread, runs the Python firmware-twin
against it (Modbus master → CBOR encode → frame), pipes the framed bytes
through the host decoder, and verifies that the simulated register values
arrive intact on the other end.

This proves the full software path is correct without any hardware:

  tcp_slave.py ──► firmware_twin.run_master ──► frame_payload bytes
        │                                              │
        └─────────────  registers updated   ◄──────── host_decoder.FrameDecoder
                                                              │
                                                              ▼
                                                       decoded record dict
                                                       (label, slave, regs)

If this test passes on a fresh checkout, Phase 0 of BUILD_PLAN.md is green.
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time
import unittest
from contextlib import closing

from firmware_twin import (
    DEFAULT_POLL_TABLE, TcpTransport, run_master,
)
from host_decoder import FrameDecoder, decode_cbor_record
from tcp_slave import serve


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _SimulatorThread(threading.Thread):
    """Run tcp_slave.py's serve() in its own asyncio loop on a dedicated thread."""

    def __init__(self, host: str, port: int) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.stop_evt = threading.Event()
        self.ready_evt = threading.Event()
        self.loop: asyncio.AbstractEventLoop | None = None

    def run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(
                serve(self.host, self.port, self.stop_evt, self.ready_evt)
            )
        except Exception:
            self.ready_evt.set()   # unblock waiters on failure
            raise

    def shutdown(self) -> None:
        self.stop_evt.set()
        if self.loop is not None and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)


class TestEndToEnd(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.port = _find_free_port()
        cls.sim = _SimulatorThread("127.0.0.1", cls.port)
        cls.sim.start()
        # Wait for the simulator's TCP server to actually accept connections.
        # `ready_evt.set()` only signals the context-builder ran; we still need
        # the asyncio TCP server to be listening. A short retry loop is fine.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            cls.sim.ready_evt.wait(timeout=0.1)
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("simulator failed to start within 5s")

        # Give the update_loop a moment to write non-zero values into the
        # register map (it starts at t=0 with sin(0)=0 offsets, which are
        # still non-zero baselines, but a quick wait makes the test less
        # sensitive to startup race conditions).
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.sim.shutdown()

    def test_one_cycle_through_decoder(self):
        """Poll each entry once, decode each framed record, verify values."""
        transport = TcpTransport("127.0.0.1", self.port)
        decoder = FrameDecoder()
        records = []

        readings = list(run_master(transport,
                                   poll_table=DEFAULT_POLL_TABLE,
                                   max_readings=len(DEFAULT_POLL_TABLE)))
        transport.close()

        self.assertEqual(len(readings), len(DEFAULT_POLL_TABLE),
                         "every entry in the poll table should produce a reading")

        for r in readings:
            framed = r.to_framed_cbor()
            frames = decoder.feed(framed)
            self.assertEqual(len(frames), 1, "exactly one frame per reading")
            records.append(decode_cbor_record(frames[0]))

        # Verify each record matches the poll-table entry that produced it
        for entry, record in zip(DEFAULT_POLL_TABLE, records):
            self.assertEqual(record.label, entry.label)
            self.assertEqual(record.slave, entry.slave_id)
            self.assertEqual(len(record.registers), entry.register_count)

        # The pressure record's two registers form a u32 BE near 101325 Pa
        pressure_rec = next(r for r in records if r.label == "tank_pressure")
        u32 = (pressure_rec.registers[0] << 16) | pressure_rec.registers[1]
        self.assertGreater(u32, 100_000, "pressure should be in pascals near atmospheric")
        self.assertLess(u32, 102_000)

        # decoder accounting
        self.assertEqual(decoder.frames_seen, len(records))
        self.assertEqual(decoder.xor_errors, 0)
        self.assertEqual(decoder.framing_errors, 0)

    def test_burst_of_readings_remains_intact(self):
        """Run for ~3 seconds of real time, decode everything, verify no losses."""
        transport = TcpTransport("127.0.0.1", self.port)
        decoder = FrameDecoder()
        record_count = 0

        # Time-bounded loop: 3 seconds is enough to hit every entry
        # at least once at their poll intervals (500/1000/2000 ms).
        start = time.monotonic()
        for reading in run_master(transport, poll_table=DEFAULT_POLL_TABLE):
            frames = decoder.feed(reading.to_framed_cbor())
            for f in frames:
                _ = decode_cbor_record(f)
                record_count += 1
            if time.monotonic() - start > 3.0:
                break

        transport.close()
        self.assertGreaterEqual(record_count, 4,
            "should see at least 4 readings in 3s across the poll-table")
        self.assertEqual(decoder.xor_errors, 0)
        self.assertEqual(decoder.framing_errors, 0)


if __name__ == "__main__":
    unittest.main()
