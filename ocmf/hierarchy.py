from typing import Dict, List
from ocmf.kernel.models import Entity, EntityType, RelationType, Identifier
from ocmf.kernel.graph import KernelGraph

class HierarchyEngine:
    """
    Applies hierarchy policies (like identifier_dots) to synthesize
    structural CHILD_OF edges between description entities.
    """
    def __init__(self, graph: KernelGraph, policies: Dict[str, str]):
        self.graph = graph
        self.policies = policies
        self.synthesized_nodes: List[str] = []
        
    def run(self) -> KernelGraph:
        strategy = self.policies.get('hierarchy', 'none')
        if strategy == 'identifier_dots':
            self._apply_identifier_dots()
        # Additional strategies (e.g., collection_group, flat_under_root) can be added here
        return self.graph
        
    def _apply_identifier_dots(self):
        # find all description entities and map by their local identifier value
        desc_entities = [e for e in self.graph.entities.values() if e.type == EntityType.DESCRIPTION]

        # Only identifiers from the named source field carry structure. Without
        # this, an accession number or alternate ref that happens to contain a
        # dot would forge a false parent-child edge.
        structure_field = self.policies.get('hierarchy_source_field')

        def structural_idents(entity):
            if structure_field is None:
                return entity.identifiers
            return [i for i in entity.identifiers if i.source_field == structure_field]

        # build lookup map; reject collisions so we never silently mis-link a
        # child to whichever duplicate happened to be indexed last.
        id_map = {}
        for e in desc_entities:
            for ident in structural_idents(e):
                if ident.value in id_map and id_map[ident.value].id != e.id:
                    raise ValueError(
                        f"Duplicate identifier '{ident.value}' on entities "
                        f"'{id_map[ident.value].id}' and '{e.id}'; cannot build hierarchy."
                    )
                id_map[ident.value] = e

        orphan_policy = self.policies.get('orphans', 'abort')

        for e in desc_entities:
            for ident in structural_idents(e):
                val = ident.value
                if '.' in val:
                    parent_val = val.rsplit('.', 1)[0]
                    if parent_val in id_map:
                        self.graph.add_edge(e.id, id_map[parent_val].id, RelationType.CHILD_OF)
                    else:
                        if orphan_policy == 'synthesize_parents':
                            self._synthesize_parent_chain(parent_val, id_map)
                            self.graph.add_edge(e.id, id_map[parent_val].id, RelationType.CHILD_OF)
                        elif orphan_policy == 'abort':
                            raise ValueError(f"Orphan detected: {val} has no parent {parent_val}")

    def _synthesize_parent_chain(self, parent_val: str, id_map: dict):
        """Recursively synthesize parents if they do not exist."""
        if parent_val in id_map:
            return
            
        # Check if parent itself has a parent based on the dots policy
        if '.' in parent_val:
            grandparent_val = parent_val.rsplit('.', 1)[0]
            self._synthesize_parent_chain(grandparent_val, id_map)
            
        phantom_id = f"synthesized_{parent_val}"
        phantom = Entity(
            id=phantom_id,
            type=EntityType.DESCRIPTION,
            identifiers=[Identifier(value=parent_val, kind="local", source_field="synthesized")],
            properties={"title": f"[Synthesized] {parent_val}", "level_of_description": "series"}
        )
        self.graph.add_entity(phantom)
        id_map[parent_val] = phantom
        self.synthesized_nodes.append(phantom_id)
        
        # If we synthesized a grandparent, link the phantom parent to it
        if '.' in parent_val:
            grandparent_val = parent_val.rsplit('.', 1)[0]
            self.graph.add_edge(phantom_id, id_map[grandparent_val].id, RelationType.CHILD_OF)
