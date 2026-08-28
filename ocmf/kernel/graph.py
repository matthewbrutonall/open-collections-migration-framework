from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from .models import Entity, Edge, RelationType

@dataclass
class KernelGraph:
    entities: Dict[str, Entity] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)

    def add_entity(self, entity: Entity):
        if entity.id in self.entities:
            raise ValueError(f"Entity ID conflict: {entity.id} already exists.")
        self.entities[entity.id] = entity
        
    def add_edge(self, source_id: str, target_id: str, relation: RelationType, properties: Optional[Dict] = None):
        if source_id not in self.entities:
            raise ValueError(f"Source entity {source_id} not in graph")
        if target_id not in self.entities:
            raise ValueError(f"Target entity {target_id} not in graph")
        
        edge = Edge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            properties=properties or {}
        )
        if edge not in self.edges:
            self.edges.append(edge)

    def to_dict(self) -> Dict:
        return {
            "entities": {k: asdict(v) for k, v in self.entities.items()},
            "edges": [asdict(e) for e in self.edges]
        }
