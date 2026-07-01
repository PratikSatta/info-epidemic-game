import heapq
from model.region import Region


def bfs_reachable(start: Region) -> set[Region]:
    visited = {start}
    queue = [start]
    while queue:
        current = queue.pop(0)
        for neighbor in current.connections:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return visited


def dfs_reachable(start: Region) -> set[Region]:
    visited = set()

    def _dfs(node: Region):
        visited.add(node)
        for neighbor in node.connections:
            if neighbor not in visited:
                _dfs(neighbor)

    _dfs(start)
    return visited


def dijkstra_shortest(start: Region) -> dict[Region, float]:
    """
    Returns a dict mapping each reachable Region -> minimum cumulative cost
    from `start`, where edge cost = 1 - connection_weight. Lower total cost
    means the strain can reach that region more easily (a "fastest spread"
    path), which the controller can use to highlight likely next targets.
    """
    distances: dict[Region, float] = {start: 0.0}
    visited: set[Region] = set()
    pq: list[tuple[float, Region]] = [(0.0, start)]

    while pq:
        current_dist, current = heapq.heappop(pq)
        if current in visited:
            continue
        visited.add(current)

        for neighbor, weight in current.connections.items():
            edge_cost = max(0.01, 1.0 - weight)   # avoid zero-cost edges
            new_dist = current_dist + edge_cost
            if neighbor not in distances or new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                heapq.heappush(pq, (new_dist, neighbor))

    return distances