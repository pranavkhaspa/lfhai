"""Task routing logic - decides which node handles which task."""

from __future__ import annotations

from lfhai.models import NodeInfo
from lfhai.registry import NodeRegistry


class TaskRouter:
    """Routes tasks to the best available node based on capabilities and load."""

    def __init__(self, registry: NodeRegistry) -> None:
        self.registry = registry

    async def route(self, model: str) -> NodeInfo | None:
        """Find the best node for a given model.

        Priority:
        1. Nodes that explicitly list the model in their capabilities
        2. Nodes with a GPU (can run any model via Ollama)
        3. Any online node as fallback
        """
        # Clean up stale nodes first
        await self.registry.mark_offline_stale_nodes()

        # Try exact model match first
        nodes = await self.registry.find_nodes_for_model(model)
        if nodes:
            return self._pick_best(nodes)

        # Fall back: any node with a GPU
        all_nodes = await self.registry.list_nodes()
        gpu_nodes = [n for n in all_nodes if n.capabilities.has_gpu]
        if gpu_nodes:
            return self._pick_best(gpu_nodes)

        # Last resort: any online node
        if all_nodes:
            return self._pick_best(all_nodes)

        return None

    def _pick_best(self, nodes: list[NodeInfo]) -> NodeInfo:
        """Pick the best node from a list. Simple heuristic: prefer GPU, then most free memory."""
        def score(n: NodeInfo) -> tuple:
            return (
                0 if n.capabilities.has_gpu else 1,  # prefer GPU
                -n.resources.memory_total_bytes,      # more memory = better
                -n.resources.disk_free_bytes,          # more disk = better
            )
        return sorted(nodes, key=score)[0]
