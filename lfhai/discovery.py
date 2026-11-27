"""Lightweight LAN discovery for lfhai workers."""

from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass, field

from lfhai.models import RpcEndpoint

DISCOVERY_PORT = 45831
DISCOVERY_MAGIC = "lfhai-discovery-1"


@dataclass
class DiscoveryBeacon:
    node_id: str
    hostname: str
    address: str
    api_port: int
    rpc_endpoints: list[RpcEndpoint] = field(default_factory=list)
    model_names: list[str] = field(default_factory=list)
    fit_target_mib: int = 0

    def to_packet(self, kind: str = "beacon") -> bytes:
        data = {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "address": self.address,
            "api_port": self.api_port,
            "rpc_endpoints": [endpoint.model_dump() for endpoint in self.rpc_endpoints],
            "model_names": self.model_names,
            "fit_target_mib": self.fit_target_mib,
        }
        payload = {"kind": kind, "magic": DISCOVERY_MAGIC, "beacon": data}
        return json.dumps(payload).encode("utf-8")


def decode_packet(data: bytes) -> tuple[str, DiscoveryBeacon | None]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "", None
    if payload.get("magic") != DISCOVERY_MAGIC:
        return "", None
    beacon_data = payload.get("beacon")
    if not isinstance(beacon_data, dict):
        return "", None
    endpoints = [
        RpcEndpoint.model_validate(endpoint)
        for endpoint in beacon_data.get("rpc_endpoints", [])
    ]
    beacon = DiscoveryBeacon(
        node_id=str(beacon_data.get("node_id", "")),
        hostname=str(beacon_data.get("hostname", "")),
        address=str(beacon_data.get("address", "")),
        api_port=int(beacon_data.get("api_port", 8002)),
        rpc_endpoints=endpoints,
        model_names=[str(name) for name in beacon_data.get("model_names", [])],
        fit_target_mib=int(beacon_data.get("fit_target_mib", 0)),
    )
    return str(payload.get("kind", "")), beacon


def _broadcast(data: bytes) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(data, ("255.255.255.255", DISCOVERY_PORT))


class DiscoveryService:
    def __init__(self, beacon: DiscoveryBeacon, interval: float = 5.0) -> None:
        self.beacon = beacon
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", DISCOVERY_PORT))
            sock.settimeout(0.5)
            next_beacon = 0.0
            while not self._stop.is_set():
                now = time.monotonic()
                if now >= next_beacon:
                    _broadcast(self.beacon.to_packet())
                    next_beacon = now + self.interval
                try:
                    data, _ = sock.recvfrom(65535)
                    kind, _ = decode_packet(data)
                    if kind == "query":
                        _broadcast(self.beacon.to_packet())
                except socket.timeout:
                    pass
                except OSError:
                    pass


def discover_nodes(timeout: float = 3.0) -> list[DiscoveryBeacon]:
    found: dict[str, DiscoveryBeacon] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", DISCOVERY_PORT))
        sock.settimeout(0.3)
        _broadcast(DiscoveryBeacon("", "", "", 0).to_packet("query"))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            kind, beacon = decode_packet(data)
            if kind == "beacon" and beacon and beacon.node_id:
                found[beacon.node_id] = beacon
    return list(found.values())
