from ocmf.kernel.models import EntityType, RelationType
from ocmf.kernel.graph import KernelGraph

class PreflightAudit:
    def __init__(self, graph: KernelGraph):
        self.graph = graph
        
    def run(self) -> bool:
        self.check_nonempty()
        self.check_identifiers()
        self.check_mandatory_fields()
        self.check_cycles()
        return True

    def check_nonempty(self):
        descriptions = [e for e in self.graph.entities.values() if e.type == EntityType.DESCRIPTION]
        if not descriptions:
            raise ValueError(
                "Pre-flight failed: graph contains no description records. "
                "Check the source export, encoding/delimiter, and field mappings."
            )

    def check_cycles(self):
        adj = {e_id: [] for e_id in self.graph.entities.keys()}
        for edge in self.graph.edges:
            if edge.relation == RelationType.CHILD_OF:
                adj[edge.source_id].append(edge.target_id)
                
        visited = set()
        path = set()
        
        def dfs(node):
            visited.add(node)
            path.add(node)
            for neighbor in adj.get(node, []):
                if neighbor in path:
                    raise ValueError(f"Pre-flight failed: Cycle detected involving '{node}' and '{neighbor}'")
                if neighbor not in visited:
                    dfs(neighbor)
            path.remove(node)
        
        for node in self.graph.entities.keys():
            if node not in visited:
                dfs(node)
                
    def check_identifiers(self):
        seen_refs = set()
        for e in self.graph.entities.values():
            if e.type == EntityType.DESCRIPTION:
                if not e.identifiers:
                    raise ValueError(f"Pre-flight failed: Description entity '{e.id}' is missing a mandatory identifier.")
                for ident in e.identifiers:
                    if ident.value in seen_refs:
                        raise ValueError(f"Pre-flight failed: Duplicate identifier detected '{ident.value}'")
                    seen_refs.add(ident.value)

    def check_mandatory_fields(self):
        for e in self.graph.entities.values():
            if e.type == EntityType.DESCRIPTION:
                title = e.properties.get("title", "").strip()
                if not title and not e.id.startswith("synthesized"):
                    raise ValueError(f"Pre-flight failed: Description entity '{e.id}' has an empty title.")
