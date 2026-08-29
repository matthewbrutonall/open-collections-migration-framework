import csv
from typing import Optional, Dict, Any

from ocmf.kernel.models import Entity, EntityType, RelationType, Identifier, DateValue
from ocmf.kernel.graph import KernelGraph
from ocmf.compiler import MappingEngine
from ocmf.transforms import apply_transform

class PastPerfectAdapter:
    def __init__(self, engine: MappingEngine):
        self.engine = engine
        self.graph = KernelGraph()
        self.transformation_notes: list = []
        self.seen_source_fields: list = []

    def _apply_transform(self, val: str, transform: str, args: Optional[str]) -> Any:
        return apply_transform(val, transform, args)

    def ingest_csv(self, filepath: str) -> KernelGraph:
        encoding = self.engine.policies.get('encoding')
        if not encoding:
            raise ValueError("Strict encoding policy required.")
            
        with open(filepath, 'r', encoding=encoding, errors='strict') as f:
            sample = f.read(1)
            if sample == '\ufeff':
                raise ValueError("BOM detected. Use 'utf-8-sig' as the encoding policy to parse this file safely.")
            f.seek(0)
            
            reader = csv.DictReader(f)
            self.seen_source_fields = list(reader.fieldnames or [])

            for row_idx, row in enumerate(reader):
                row_entities: Dict[str, Entity] = {}
                base_id = row.get("ref_code", f"row_{row_idx}").replace(".", "_").replace("-", "_")
                
                for node_name, entity_def in self.engine.entities.items():
                    fields = self.engine.get_fields_for_node(node_name)
                    has_data = False
                    properties = {}
                    identifiers = []
                    
                    for fdef in fields:
                        raw_val = row.get(fdef.source_field, "")
                        if raw_val:
                            has_data = True
                            transformed = self._apply_transform(raw_val, fdef.transform, fdef.transform_args)
                            
                            if fdef.target_property == 'identifiers':
                                identifiers.append(Identifier(value=transformed, kind="local", source_field=fdef.source_field))
                            else:
                                properties[fdef.target_property] = transformed
                                
                    if has_data:
                        ent_id = f"{node_name}_{base_id}"
                        ent = Entity(
                            id=ent_id,
                            type=EntityType(entity_def.entity_type),
                            identifiers=identifiers,
                            properties=properties
                        )
                        self.graph.add_entity(ent)
                        row_entities[node_name] = ent

                desc_nodes = [e for e in row_entities.values() if e.type == EntityType.DESCRIPTION]
                agent_nodes = [e for e in row_entities.values() if e.type == EntityType.AGENT]
                
                for d in desc_nodes:
                    for a in agent_nodes:
                        self.graph.add_edge(d.id, a.id, RelationType.CREATED_BY)
                        
        return self.graph
