from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import openpyxl

from ocmf.transforms import VALID_TRANSFORMS

@dataclass
class EntityDef:
    node_name: str
    source_table: str
    entity_type: str

@dataclass
class FieldDef:
    node_name: str
    source_field: str
    target_property: str
    transform: str
    transform_args: Optional[str] = None

@dataclass
class MappingEngine:
    entities: Dict[str, EntityDef] = field(default_factory=dict)
    fields: List[FieldDef] = field(default_factory=list)
    policies: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def compile_from_excel(cls, filepath: str) -> 'MappingEngine':
        wb = openpyxl.load_workbook(filepath, data_only=True)
        engine = cls()
        
        if 'entities' in wb.sheetnames:
            ws = wb['entities']
            headers = [cell.value for cell in ws[1]] if ws.max_row > 0 else []
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]: continue
                data = dict(zip(headers, row))
                engine.entities[data['node_name']] = EntityDef(
                    node_name=data.get('node_name'),
                    source_table=data.get('source_table'),
                    entity_type=data.get('entity_type')
                )
                
        if 'fields' in wb.sheetnames:
            ws = wb['fields']
            headers = [cell.value for cell in ws[1]] if ws.max_row > 0 else []
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]: continue
                data = dict(zip(headers, row))
                transform = data.get('transform') or 'identity'
                if transform not in VALID_TRANSFORMS:
                    raise ValueError(f"Invalid transform '{transform}'. Must be one of {VALID_TRANSFORMS}")
                engine.fields.append(FieldDef(
                    node_name=data.get('node_name'),
                    source_field=data.get('source_field'),
                    target_property=data.get('target_property'),
                    transform=transform,
                    transform_args=data.get('transform_args')
                ))
                
        if 'policies' in wb.sheetnames:
            ws = wb['policies']
            headers = [cell.value for cell in ws[1]] if ws.max_row > 0 else []
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]: continue
                data = dict(zip(headers, row))
                engine.policies[data.get('policy_name')] = data.get('policy_value')
                
        if 'encoding' not in engine.policies:
            raise ValueError("An explicit 'encoding' policy is mandatory in the workbook.")

        # Fatal-by-default: an empty or unusable workbook must not pass as a
        # valid mapping, or a typo could yield an empty CSV and "success".
        if not engine.entities:
            raise ValueError("Workbook defines no entities. The 'entities' sheet must declare at least one node.")
        if not engine.fields:
            raise ValueError("Workbook defines no field mappings. The 'fields' sheet must declare at least one mapping.")

        from ocmf.writers.atom import validate_targets
        validate_targets(engine)

        return engine

    def get_fields_for_node(self, node_name: str) -> List[FieldDef]:
        return [f for f in self.fields if f.node_name == node_name]

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return {
            "entities": {k: asdict(v) for k, v in self.entities.items()},
            "fields": [asdict(f) for f in self.fields],
            "policies": self.policies
        }
