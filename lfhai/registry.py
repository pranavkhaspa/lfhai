"""Node registry with SQLite backing for the controller."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time

import aiosqlite

from lfhai.models import (
    Heartbeat,
    ModelArtifact,
    NodeCapabilities,
    NodeInfo,
    NodeResources,
    NodeStatus,
    RpcEndpoint,
)

HEARTBEAT_TIMEOUT = 10.0  # seconds before node is considered offline
TOKEN_TTL_DEFAULT_SECONDS = 3600.0  # join tokens expire after 1 hour


def _hash_secret(secret: str) -> str:
    """SHA-256 hash of a join token or node secret (never store plaintext)."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _secrets_equal(a: str, b: str) -> bool:
    """Constant-time comparison of secret hashes."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _serialize_capabilities(caps: NodeCapabilities) -> str:
    return json.dumps(
        {
            "models": caps.models,
            "model_artifacts": [a.model_dump() for a in caps.model_artifacts],
            "backends": caps.backends,
            "rpc_endpoint": caps.rpc_endpoint,
            "rpc_memory_mb": caps.rpc_memory_mb,
            "rpc_endpoints": [e.model_dump() for e in caps.rpc_endpoints],
            "device_class": caps.device_class,
            "fit_target_mib": caps.fit_target_mib,
            "has_gpu": caps.has_gpu,
            "has_cuda": caps.has_cuda,
        }
    )


class NodeRegistry:
    """Manages node registration, heartbeats, and health in SQLite."""

    def __init__(self, db_path: str = "lfhai.db") -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                hostname TEXT NOT NULL,
                ip TEXT DEFAULT '',
                status TEXT DEFAULT 'online',
                cores INTEGER DEFAULT 0,
                memory_total_bytes INTEGER DEFAULT 0,
                memory_used_bytes INTEGER DEFAULT 0,
                memory_available_bytes INTEGER DEFAULT 0,
                disk_free_bytes INTEGER DEFAULT 0,
                gpu_model TEXT DEFAULT '',
                gpu_vram_bytes INTEGER DEFAULT 0,
                gpu_vram_used_bytes INTEGER DEFAULT 0,
                gpu_vram_free_bytes INTEGER DEFAULT 0,
                cuda_version TEXT DEFAULT '',
                has_gpu INTEGER DEFAULT 0,
                capabilities TEXT DEFAULT '[]',
                node_secret_hash TEXT DEFAULT '',
                api_port INTEGER DEFAULT 8002,
                registered_at REAL NOT NULL,
                last_heartbeat REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS join_tokens (
                token_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL,
                expires_at REAL NOT NULL,
                used_at REAL,
                node_id TEXT DEFAULT '',
                node_hostname TEXT DEFAULT '',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                assigned_node TEXT DEFAULT '',
                messages TEXT DEFAULT '[]',
                result TEXT DEFAULT '',
                error TEXT DEFAULT '',
                created_at REAL NOT NULL,
                started_at REAL DEFAULT 0,
                completed_at REAL DEFAULT 0
            );
        """)
        # Migration for databases created before node secrets existed
        cols = await self._db.execute("PRAGMA table_info(nodes)")
        col_names = {row["name"] for row in await cols.fetchall()}
        if "node_secret_hash" not in col_names:
            await self._db.execute(
                "ALTER TABLE nodes ADD COLUMN node_secret_hash TEXT DEFAULT ''"
            )
        if "api_port" not in col_names:
            await self._db.execute(
                "ALTER TABLE nodes ADD COLUMN api_port INTEGER DEFAULT 8002"
            )
        for column, definition in (
            ("memory_used_bytes", "INTEGER DEFAULT 0"),
            ("memory_available_bytes", "INTEGER DEFAULT 0"),
            ("gpu_vram_used_bytes", "INTEGER DEFAULT 0"),
            ("gpu_vram_free_bytes", "INTEGER DEFAULT 0"),
        ):
            if column not in col_names:
                await self._db.execute(
                    f"ALTER TABLE nodes ADD COLUMN {column} {definition}"
                )
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def register(self, node: NodeInfo) -> NodeInfo:
        """Register a new node or update an existing one."""
        now = time.time()
        node.registered_at = now
        node.last_heartbeat = now
        node.status = NodeStatus.ONLINE

        caps_json = _serialize_capabilities(node.capabilities)
        vram_used = node.resources.gpu.vram_used_bytes if node.resources.gpu else 0
        vram_free = node.resources.vram_free_bytes
        if not vram_free and node.resources.gpu:
            vram_free = max(0, node.resources.gpu.vram_total_bytes - vram_used)

        await self._db.execute(
            """INSERT INTO nodes
               (node_id, hostname, ip, status, cores, memory_total_bytes,
                memory_used_bytes, memory_available_bytes, disk_free_bytes,
                gpu_model, gpu_vram_bytes, gpu_vram_used_bytes, gpu_vram_free_bytes,
                cuda_version, has_gpu, capabilities,
                api_port, registered_at, last_heartbeat)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(node_id) DO UPDATE SET
                hostname=excluded.hostname,
                ip=excluded.ip,
                status=excluded.status,
                cores=excluded.cores,
                memory_total_bytes=excluded.memory_total_bytes,
                memory_used_bytes=excluded.memory_used_bytes,
                memory_available_bytes=excluded.memory_available_bytes,
                disk_free_bytes=excluded.disk_free_bytes,
                gpu_model=excluded.gpu_model,
                gpu_vram_bytes=excluded.gpu_vram_bytes,
                gpu_vram_used_bytes=excluded.gpu_vram_used_bytes,
                gpu_vram_free_bytes=excluded.gpu_vram_free_bytes,
                cuda_version=excluded.cuda_version,
                has_gpu=excluded.has_gpu,
                capabilities=excluded.capabilities,
                api_port=excluded.api_port,
                registered_at=excluded.registered_at,
                last_heartbeat=excluded.last_heartbeat""",
            (
                node.node_id,
                node.hostname,
                node.resources.ip,
                node.status.value,
                node.resources.cores,
                node.resources.memory_total_bytes,
                node.resources.memory_used_bytes,
                node.resources.memory_available_bytes,
                node.resources.disk_free_bytes,
                node.resources.gpu.model if node.resources.gpu else "",
                node.resources.gpu.vram_total_bytes if node.resources.gpu else 0,
                vram_used,
                vram_free,
                node.resources.gpu.cuda_version if node.resources.gpu else "",
                int(node.capabilities.has_gpu),
                caps_json,
                node.api_port,
                node.registered_at,
                node.last_heartbeat,
            ),
        )
        await self._db.commit()
        return node

    async def create_join_token(
        self, ttl_seconds: float = TOKEN_TTL_DEFAULT_SECONDS
    ) -> tuple[str, str, float]:
        """Mint a join token.

        Returns (token_id, raw_secret, expires_at). Only the token_id and a
        hash of the raw secret are kept in the database.
        """
        token_id = secrets.token_urlsafe(6)
        raw_secret = secrets.token_urlsafe(24)
        expires_at = time.time() + ttl_seconds
        await self._db.execute(
            """INSERT INTO join_tokens (token_id, token_hash, expires_at, created_at)
               VALUES (?, ?, ?, ?)""",
            (token_id, _hash_secret(raw_secret), expires_at, time.time()),
        )
        await self._db.commit()
        return token_id, raw_secret, expires_at

    async def consume_join_token(self, raw_secret: str) -> str | None:
        """Validate and single-use-consume a join token.

        Returns the token_id on success, or None if the token is missing,
        already used, or expired.
        """
        cursor = await self._db.execute(
            "SELECT token_id, token_hash, expires_at, used_at FROM join_tokens "
            "WHERE token_hash = ?",
            (_hash_secret(raw_secret),),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        if row["used_at"] is not None:
            return None
        if time.time() > row["expires_at"]:
            return None
        await self._db.execute(
            "UPDATE join_tokens SET used_at = ? WHERE token_hash = ?",
            (time.time(), _hash_secret(raw_secret)),
        )
        await self._db.commit()
        return row["token_id"]

    async def list_join_tokens(self) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT token_id, expires_at, used_at, node_id, node_hostname, created_at "
            "FROM join_tokens ORDER BY created_at"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def revoke_join_token(self, token_id: str) -> bool:
        """Permanently disable a token by deleting it."""
        cursor = await self._db.execute(
            "DELETE FROM join_tokens WHERE token_id = ?", (token_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def mark_join_token_used(self, token_id: str, node_id: str, hostname: str) -> None:
        """Record which node joined with a token (for audit visibility)."""
        await self._db.execute(
            "UPDATE join_tokens SET node_id = ?, node_hostname = ? WHERE token_id = ?",
            (node_id, hostname, token_id),
        )
        await self._db.commit()

    async def set_node_secret(self, node_id: str, node_secret: str) -> None:
        """Store the (hashed) per-node credential after a successful join."""
        await self._db.execute(
            "UPDATE nodes SET node_secret_hash = ? WHERE node_id = ?",
            (_hash_secret(node_secret), node_id),
        )
        await self._db.commit()

    async def verify_node(self, node_id: str, node_secret: str) -> bool:
        """Return True if node_secret matches the node's stored credential."""
        cursor = await self._db.execute(
            "SELECT node_secret_hash FROM nodes WHERE node_id = ?", (node_id,)
        )
        row = await cursor.fetchone()
        if not row or not row["node_secret_hash"]:
            return False
        return _secrets_equal(row["node_secret_hash"], _hash_secret(node_secret))

    async def heartbeat(self, hb: Heartbeat) -> bool:
        """Update heartbeat for a node. Returns False if node not found."""
        now = time.time()
        m = hb.metrics
        available = m.memory_available_bytes or max(0, m.memory_total_bytes - m.memory_used_bytes)
        cursor = await self._db.execute(
            """UPDATE nodes SET last_heartbeat = ?, status = 'online',
               cores = COALESCE(NULLIF(cores, 0), cores),
               memory_total_bytes = CASE WHEN ? > 0 THEN ? ELSE memory_total_bytes END,
               memory_used_bytes = CASE WHEN ? > 0 THEN ? ELSE memory_used_bytes END,
               memory_available_bytes = CASE WHEN ? > 0 THEN ? ELSE memory_available_bytes END,
               gpu_vram_used_bytes = CASE WHEN ? > 0 THEN ? ELSE gpu_vram_used_bytes END,
               gpu_vram_free_bytes = CASE WHEN ? > 0 THEN ? ELSE gpu_vram_free_bytes END
               WHERE node_id = ?""",
            (
                now,
                m.memory_total_bytes,
                m.memory_total_bytes,
                m.memory_used_bytes,
                m.memory_used_bytes,
                available,
                available,
                m.gpu_vram_used_bytes,
                m.gpu_vram_used_bytes,
                m.gpu_vram_free_bytes,
                m.gpu_vram_free_bytes,
                hb.node_id,
            ),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def get_node(self, node_id: str) -> NodeInfo | None:
        """Get a single node by ID."""
        cursor = await self._db.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_node(row)

    async def list_nodes(self, include_offline: bool = False) -> list[NodeInfo]:
        """List all registered nodes."""
        if include_offline:
            cursor = await self._db.execute("SELECT * FROM nodes ORDER BY registered_at")
        else:
            cursor = await self._db.execute(
                "SELECT * FROM nodes WHERE status != 'offline' ORDER BY registered_at"
            )
        rows = await cursor.fetchall()
        return [self._row_to_node(row) for row in rows]

    async def find_nodes_for_model(self, model: str) -> list[NodeInfo]:
        """Find online nodes that have the requested model available."""
        now = time.time()
        cursor = await self._db.execute(
            """SELECT * FROM nodes
               WHERE status = 'online'
                 AND (last_heartbeat > ? OR ? - last_heartbeat < ?)
                 AND (capabilities LIKE ? OR gpu_model != '')
               ORDER BY last_heartbeat DESC""",
            (now, now, HEARTBEAT_TIMEOUT, f"%{model}%"),
        )
        rows = await cursor.fetchall()
        return [self._row_to_node(row) for row in rows]

    async def mark_offline_stale_nodes(self) -> list[str]:
        """Mark nodes as offline if heartbeat expired. Returns list of node_ids."""
        now = time.time()
        cursor = await self._db.execute(
            """UPDATE nodes SET status = 'offline'
               WHERE status = 'online' AND (? - last_heartbeat) > ?""",
            (now, HEARTBEAT_TIMEOUT),
        )
        await self._db.commit()
        if cursor.rowcount == 0:
            return []
        # Return the IDs that were just marked offline
        cursor2 = await self._db.execute(
            "SELECT node_id FROM nodes WHERE status = 'offline' AND (? - last_heartbeat) > ?",
            (now, HEARTBEAT_TIMEOUT),
        )
        rows = await cursor2.fetchall()
        return [row["node_id"] for row in rows]

    async def set_node_status(self, node_id: str, status: str) -> bool:
        """Force a node's status (e.g. pending after join, before first heartbeat)."""
        cursor = await self._db.execute(
            "UPDATE nodes SET status = ? WHERE node_id = ?", (status, node_id)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def remove_node(self, node_id: str) -> bool:
        cursor = await self._db.execute("DELETE FROM nodes WHERE node_id = ?", (node_id,))
        await self._db.commit()
        return cursor.rowcount > 0

    def _row_to_node(self, row: aiosqlite.Row) -> NodeInfo:
        from lfhai.models import GPUInfo

        gpu = None
        gpu_model = row["gpu_model"]
        if gpu_model:
            gpu = GPUInfo(
                model=gpu_model,
                vram_total_bytes=row["gpu_vram_bytes"],
                vram_used_bytes=row["gpu_vram_used_bytes"] or 0,
                cuda_version=row["cuda_version"],
            )

        stored_caps = json.loads(row["capabilities"]) if row["capabilities"] else []
        if isinstance(stored_caps, list):
            stored_caps = {"models": stored_caps}
        caps = NodeCapabilities(
            models=stored_caps.get("models", []),
            model_artifacts=[
                ModelArtifact.model_validate(a)
                for a in stored_caps.get("model_artifacts", [])
            ],
            backends=stored_caps.get("backends", []),
            rpc_endpoint=stored_caps.get("rpc_endpoint", ""),
            rpc_memory_mb=stored_caps.get("rpc_memory_mb", 0),
            rpc_endpoints=[
                RpcEndpoint.model_validate(e) for e in stored_caps.get("rpc_endpoints", [])
            ],
            device_class=stored_caps.get("device_class", "auto"),
            fit_target_mib=stored_caps.get("fit_target_mib", 0),
            has_gpu=bool(row["has_gpu"]),
            has_cuda=stored_caps.get("has_cuda", bool(row["has_gpu"])),
        )

        resources = NodeResources(
            hostname=row["hostname"],
            ip=row["ip"],
            cores=row["cores"],
            memory_total_bytes=row["memory_total_bytes"],
            memory_used_bytes=row["memory_used_bytes"] or 0,
            memory_available_bytes=row["memory_available_bytes"] or 0,
            vram_free_bytes=row["gpu_vram_free_bytes"] or 0,
            disk_free_bytes=row["disk_free_bytes"],
            gpu=gpu,
        )

        return NodeInfo(
            node_id=row["node_id"],
            hostname=row["hostname"],
            status=NodeStatus(row["status"]),
            resources=resources,
            capabilities=caps,
            api_port=row["api_port"],
            registered_at=row["registered_at"],
            last_heartbeat=row["last_heartbeat"],
        )


class TaskStore:
    """Simple task tracking in SQLite."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create_task(self, task_id: str, model: str, messages: list[dict]) -> None:
        await self._db.execute(
            """INSERT INTO tasks (task_id, model, messages, created_at)
               VALUES (?, ?, ?, ?)""",
            (task_id, model, json.dumps(messages), time.time()),
        )
        await self._db.commit()

    async def update_task(
        self,
        task_id: str,
        *,
        status: str | None = None,
        assigned_node: str | None = None,
        result: str | None = None,
        error: str | None = None,
        started_at: float | None = None,
        completed_at: float | None = None,
    ) -> None:
        sets = []
        vals = []
        if status is not None:
            sets.append("status = ?")
            vals.append(status)
        if assigned_node is not None:
            sets.append("assigned_node = ?")
            vals.append(assigned_node)
        if result is not None:
            sets.append("result = ?")
            vals.append(result)
        if error is not None:
            sets.append("error = ?")
            vals.append(error)
        if started_at is not None:
            sets.append("started_at = ?")
            vals.append(started_at)
        if completed_at is not None:
            sets.append("completed_at = ?")
            vals.append(completed_at)
        if sets:
            vals.append(task_id)
            await self._db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE task_id = ?", vals)
            await self._db.commit()

    async def get_task(self, task_id: str) -> dict | None:
        cursor = await self._db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)
