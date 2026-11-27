import Foundation
#if canImport(Darwin)
import Darwin
#elseif canImport(Glibc)
import Glibc
#endif

public protocol RpcProviding {
    func start(host: String, port: Int, memoryMB: Int) -> String?
}

public struct NoopRpcProvider: RpcProviding {
    public init() {}

    public func start(host: String, port: Int, memoryMB: Int) -> String? {
        nil
    }
}

public struct DynamicRpcProvider: RpcProviding {
    public init() {}

    public func start(host: String, port: Int, memoryMB: Int) -> String? {
        let endpoint = "\(host):\(port)"
        typealias StartFunction = @convention(c) (UnsafePointer<CChar>, Int32) -> Int32
        guard let handle = dlopen(nil, RTLD_NOW), let symbol = dlsym(handle, "lfhai_rpc_start") else {
            return nil
        }
        defer { dlclose(handle) }
        let start = unsafeBitCast(symbol, to: StartFunction.self)
        return endpoint.withCString { pointer in
            start(pointer, 1) == 1 ? endpoint : nil
        }
    }
}

public struct JoinToken: Sendable {
    public let host: String
    public let port: Int
    public let secret: String

    public init?(raw: String) {
        let value = raw.split(separator: "://").last.map(String.init) ?? raw
        let parts = value.split(separator: ":", omittingEmptySubsequences: false)
        guard parts.count == 3, let port = Int(parts[1]) else { return nil }
        host = String(parts[0])
        self.port = port
        secret = String(parts[2])
    }
}

public actor NodeClient {
    private let session: URLSession
    private let rpcProvider: RpcProviding
    private var controller: String = ""
    private var nodeId: String = ""
    private var nodeSecret: String = ""
    private var rpcEndpoint: String = ""

    public init(session: URLSession = .shared, rpcProvider: RpcProviding = DynamicRpcProvider()) {
        self.session = session
        self.rpcProvider = rpcProvider
    }

    public func join(token raw: String) async throws {
        guard let token = JoinToken(raw: raw) else {
            throw NodeClientError.invalidToken
        }
        controller = "http://\(token.host):\(token.port)"
        let started = rpcProvider.start(host: "0.0.0.0", port: 50053, memoryMB: 1536) ?? ""
        rpcEndpoint = started.replacingOccurrences(
            of: "0.0.0.0",
            with: ProcessInfo.processInfo.hostName
        )

        let body: [String: Any] = [
            "token": token.secret,
            "node": nodeInfo()
        ]
        let response = try await post("/api/v1/nodes/join", body: body, authorization: nil)
        guard
            let id = response["node_id"] as? String,
            let secret = response["node_secret"] as? String
        else {
            throw NodeClientError.invalidResponse
        }
        nodeId = id
        nodeSecret = secret
    }

    public func heartbeat() async throws {
        guard !nodeId.isEmpty else { throw NodeClientError.notJoined }
        let metrics: [String: Any] = [
            "cpu_usage_pct": 0.0,
            "memory_total_bytes": Int(ProcessInfo.processInfo.physicalMemory)
        ]
        _ = try await post(
            "/api/v1/nodes/heartbeat",
            body: ["node_id": nodeId, "metrics": metrics],
            authorization: nodeSecret
        )
    }

    public var status: String {
        nodeId.isEmpty ? "not joined" : "online \(nodeId)"
    }

    private func nodeInfo() -> [String: Any] {
        var endpoints: [[String: Any]] = []
        if !rpcEndpoint.isEmpty {
            endpoints.append([
                "endpoint": rpcEndpoint,
                "backend": "cpu",
                "memory_mb": 1536
            ])
        }
        return [
            "hostname": ProcessInfo.processInfo.hostName,
            "resources": [
                "ip": "127.0.0.1",
                "cores": ProcessInfo.processInfo.activeProcessorCount,
                "memory_total_bytes": Int(ProcessInfo.processInfo.physicalMemory)
            ],
            "capabilities": [
                "models": [String](),
                "backends": ["llamacpp_rpc"],
                "rpc_endpoints": endpoints
            ]
        ]
    }

    private func post(
        _ path: String,
        body: [String: Any],
        authorization: String?
    ) async throws -> [String: Any] {
        guard let url = URL(string: controller + path) else {
            throw NodeClientError.invalidToken
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let authorization {
            request.setValue("Bearer \(authorization)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await session.dataTask(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw NodeClientError.requestFailed
        }
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw NodeClientError.invalidResponse
        }
        return json
    }
}

public enum NodeClientError: Error {
    case invalidToken
    case invalidResponse
    case notJoined
    case requestFailed
}
