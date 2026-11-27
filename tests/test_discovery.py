from lfhai.discovery import DiscoveryBeacon, decode_packet
from lfhai.models import RpcEndpoint


def test_discovery_packet_round_trip():
    beacon = DiscoveryBeacon(
        node_id="node-1",
        hostname="phone",
        address="10.0.0.8",
        api_port=8002,
        rpc_endpoints=[
            RpcEndpoint(endpoint="10.0.0.8:50053", backend="cpu", memory_mb=1536)
        ],
        model_names=["tiny.gguf"],
        fit_target_mib=2048,
    )

    kind, decoded = decode_packet(beacon.to_packet())

    assert kind == "beacon"
    assert decoded is not None
    assert decoded.node_id == "node-1"
    assert decoded.rpc_endpoints[0].backend == "cpu"
    assert decoded.fit_target_mib == 2048


def test_discovery_ignores_unknown_packets():
    assert decode_packet(b"not json") == ("", None)
