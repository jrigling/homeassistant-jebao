"""Fake MDP-20000 (GizWits LAN protocol) with fault injection. Mirrors python-jebao tests."""
import asyncio

from jebao.protocol import build_frame, split_frame

PASSCODE = b"ABCDEFGHIJ"


def status_frame(state=0x11, speed=70):
    payload = bytes([0x03, state, speed, 0x01, 0x1E]) + bytes(18) + b"\x01\x64"
    payload += b"\xee" * (303 - len(payload) - 1) + b"\x00"
    frame = build_frame(0x0091, payload)
    assert frame[4:6] == b"\xb2\x02"  # matches the real pump's 2-byte varint length
    return frame


class FakePump:
    """Minimal GizWits server. ``faults`` is a list consumed one per connection."""

    def __init__(self):
        self.faults = []
        self.connections = 0
        self.commands = []
        self.writes = []  # attr flags + values of every 0x0093 frame
        self.state = 0x11
        self.speed = 70
        self.server = None
        self.port = None
        self.idle_close = None
        self.passcode_requests = 0
        self.peer_ports = []

    async def start(self):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()

    async def _read(self, reader):
        hdr = await reader.readexactly(4)
        n, shift = 0, 0
        raw = b""
        while True:
            b = (await reader.readexactly(1))[0]
            raw += bytes([b])
            n |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                break
        body = await reader.readexactly(n)
        return split_frame(hdr + raw + body)

    async def _handle(self, reader, writer):
        self.connections += 1
        self.peer_ports.append(writer.get_extra_info("peername")[1])
        fault = self.faults.pop(0) if self.faults else None
        try:
            if fault == "refuse":
                return
            while True:
                if self.idle_close:
                    cmd, payload = await asyncio.wait_for(self._read(reader), self.idle_close)
                else:
                    cmd, payload = await self._read(reader)
                if cmd == 0x0006:
                    self.passcode_requests += 1
                    if fault == "stall_login":
                        await asyncio.sleep(2)
                    writer.write(build_frame(0x0007, b"\x00\x0a" + PASSCODE))
                elif cmd == 0x0008:
                    assert payload == b"\x00\x0a" + PASSCODE
                    writer.write(build_frame(0x0009, b"\x00"))
                elif cmd == 0x0090:
                    if fault == "stall_status":
                        await asyncio.sleep(2)
                    if fault == "half_status":
                        writer.write(status_frame(self.state, self.speed)[:50])
                        await writer.drain()
                        await asyncio.sleep(2)
                    if fault == "unsolicited":
                        # unsolicited report + stray ack before the real answer
                        writer.write(status_frame(0x10, 30))
                        writer.write(build_frame(0x0094, b"\x00"))
                    if fault == "bad_state":
                        writer.write(status_frame(0x00, 0))
                    else:
                        writer.write(status_frame(self.state, self.speed))
                elif cmd == 0x0093:
                    self.commands.append(payload[12:16])
                    self.writes.append(payload[5:])
                    if fault == "drop_ack":
                        return
                    writer.write(build_frame(0x0094, b"\x00"))
                elif cmd == 0x0015:
                    writer.write(build_frame(0x0016))
                await writer.drain()
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError):
            pass
        finally:
            writer.close()
