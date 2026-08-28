import csv
import re
from typing import Optional, Dict

from ocmf.kernel.models import Entity, EntityType, RelationType, Identifier, DateValue
from ocmf.kernel.graph import KernelGraph
from ocmf.compiler import MappingEngine

class PastPerfectAdapter:
    def __init__(self, engine: MappingEngine):
        self.engine = engine
        self.graph = KernelGraph()
        
    def _apply_transform(self, val: str, transform: str, args: Optional[str]) -> any:
        if not val:
            return ""
        val = str(val).strip()
        if transform == 'identity':
            return val
        elif transform == 'parse_date':
            m_year = re.match(r'^\s*(\d{4})\s*$', val)
            if m_year:
                return DateValue(expression=val, begin=m_year.group(1), end=m_year.group(1))
            
            m_range = re.match(r'^\s*(\d{4})\s*-\s*(\d{4})\s*$', val)
            if m_range:
                return DateValue(expression=val, begin=m_range.group(1), end=m_range.group(2))
                
            return DateValue(expression=val, begin=None, end=None)
        else:
            raise NotImplementedError(f"Transform '{transform}' is not implemented.")

    def ingest_csv(self, filepath: str) -> KernelGraph:
        encoding = self.engine.policies.get('encoding')
        if not encoding:
            raise ValueError("Strict encoding policy required.")
            
        with open(filepath, 'r', encoding=encoding, errors='strict') as f:
            sample = f.read(1)
            if sample == '\ufeff':
                raise ValueError("BOM detected. Use 'utf-8-sig' as the encoding policy to parse this file safely.")
            f.seek(0)
            
            reader = csv.DictReader(f, escapechar='\\')
            
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
