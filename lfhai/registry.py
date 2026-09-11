"""Node registry with SQLite backing for the controller."""

from __future__ import annotations

import json
import time

import aiosqlite

from lfhai.models import (
    Heartbeat,
    NodeCapabilities,
    NodeInfo,
    NodeResources,
    NodeStatus,
)

HEARTBEAT_TIMEOUT = 10.0  # seconds before node is considered offline


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
                disk_free_bytes INTEGER DEFAULT 0,
                gpu_model TEXT DEFAULT '',
                gpu_vram_bytes INTEGER DEFAULT 0,
                cuda_version TEXT DEFAULT '',
                has_gpu INTEGER DEFAULT 0,
                capabilities TEXT DEFAULT '[]',
                registered_at REAL NOT NULL,
                last_heartbeat REAL NOT NULL
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

        caps_json = json.dumps(node.capabilities.models)

        await self._db.execute(
            """INSERT OR REPLACE INTO nodes
               (node_id, hostname, ip, status, cores, memory_total_bytes, disk_free_bytes,
                gpu_model, gpu_vram_bytes, cuda_version, has_gpu, capabilities,
                registered_at, last_heartbeat)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                node.node_id,
                node.hostname,
                node.resources.ip,
                node.status.value,
                node.resources.cores,
                node.resources.memory_total_bytes,
                node.resources.disk_free_bytes,
                node.resources.gpu.model if node.resources.gpu else "",
                node.resources.gpu.vram_total_bytes if node.resources.gpu else 0,
                node.resources.gpu.cuda_version if node.resources.gpu else "",
                int(node.capabilities.has_gpu),
                caps_json,
                node.registered_at,
                node.last_heartbeat,
            ),
        )
        await self._db.commit()
        return node

    async def heartbeat(self, hb: Heartbeat) -> bool:
        """Update heartbeat for a node. Returns False if node not found."""
        now = time.time()
        cursor = await self._db.execute(
            """UPDATE nodes SET last_heartbeat = ?, status = 'online',
               cores = COALESCE(NULLIF(cores, 0), cores),
               memory_total_bytes = CASE WHEN ? > 0 THEN ? ELSE memory_total_bytes END
               WHERE node_id = ?""",
            (now, hb.metrics.memory_total_bytes, hb.metrics.memory_total_bytes, hb.node_id),
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

    async def remove_node(self, node_id: str) -> bool:
        cursor = await self._db.execute("DELETE FROM nodes WHERE node_id = ?", (node_id,))
        await self._db.commit()
        return cursor.rowcount > 0

    def _row_to_node(self, row: aiosqlite.Row) -> NodeInfo:
        gpu = None
        gpu_model = row["gpu_model"]
        if gpu_model:
            from lfhai.models import GPUInfo
            gpu = GPUInfo(
                model=gpu_model,
                vram_total_bytes=row["gpu_vram_bytes"],
                cuda_version=row["cuda_version"],
            )

        caps = NodeCapabilities(
            models=json.loads(row["capabilities"]) if row["capabilities"] else [],
            has_gpu=bool(row["has_gpu"]),
        )

        resources = NodeResources(
            hostname=row["hostname"],
            ip=row["ip"],
            cores=row["cores"],
            memory_total_bytes=row["memory_total_bytes"],
            disk_free_bytes=row["disk_free_bytes"],
            gpu=gpu,
        )

        return NodeInfo(
            node_id=row["node_id"],
            hostname=row["hostname"],
            status=NodeStatus(row["status"]),
            resources=resources,
            capabilities=caps,
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
