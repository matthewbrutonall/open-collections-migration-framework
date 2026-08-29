import warnings
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from ocmf.kernel.models import Entity, EntityType, RelationType, Identifier, DateValue
from ocmf.kernel.graph import KernelGraph
from ocmf.compiler import MappingEngine
from ocmf.transforms import apply_transform

class AdlibXMLAdapter:
    def __init__(self, engine: MappingEngine):
        self.engine = engine
        self.graph = KernelGraph()
        self.transformation_notes: List[Dict[str, Any]] = []
        self.seen_source_fields: List[str] = []
        
    def _strip_ns(self, tag: str) -> str:
        return tag.split('}', 1)[-1]
        
    def _process_value_node(self, element: ET.Element, culture: str) -> Optional[str]:
        values = []
        for child in element:
            clean_tag = self._strip_ns(child.tag)
            if clean_tag in ('value', 'text') and child.text and child.text.strip():
                lang = child.get("lang") or child.get("{http://www.w3.org/XML/1998/namespace}lang")
                values.append({"val": child.text.strip(), "lang": lang})
                
        if values:
            for v in values:
                if v["lang"] and v["lang"].startswith(culture):
                    return v["val"]
            return values[0]["val"]
            
        if element.text and element.text.strip():
            return element.text.strip()
        return None

    def _extract_elements(self, element: ET.Element, culture: str, record_data: Dict[str, list] = None) -> Dict[str, list]:
        if record_data is None:
            record_data = {}
            priref = element.get("priref")
            if priref:
                record_data["priref"] = [priref]
                
        clean_tag = self._strip_ns(element.tag)
        has_value_children = any(self._strip_ns(c.tag) in ('value', 'text') for c in element)
        
        if has_value_children:
            val = self._process_value_node(element, culture)
            if val:
                record_data.setdefault(clean_tag, []).append(val)
        else:
            if element.text and element.text.strip() and clean_tag not in ('value', 'text'):
                val = element.text.strip()
                if clean_tag == "priref":
                    if val not in record_data.get("priref", []):
                        record_data.setdefault(clean_tag, []).append(val)
                else:
                    record_data.setdefault(clean_tag, []).append(val)
            
            for child in element:
                self._extract_elements(child, culture, record_data)
                
        return record_data

    def _apply_transform(self, val: str, transform: str, args: Optional[str]) -> Any:
        return apply_transform(val, transform, args)

    def _parse_dates(self, raw_vals: List[str], args: Optional[str], context: str = "") -> DateValue:
        """Parse each repeated date value independently.

        A single value round-trips to its own DateValue. Multiple values are
        collapsed into one spanning DateValue: the parseable coordinates set the
        begin/end range, and the original values are preserved in ``expression``.
        Because collapsing is interpretation, every collapse is recorded as a
        transformation note for the audit pack (and warned at ingest time).
        """
        parsed = [apply_transform(v, 'parse_date', args) for v in raw_vals if v]
        if len(parsed) == 1:
            return parsed[0]

        begins = sorted(p.begin for p in parsed if p.begin)
        ends = sorted(p.end for p in parsed if p.end)
        result = DateValue(
            expression="|".join(raw_vals),
            begin=begins[0] if begins else None,
            end=ends[-1] if ends else None,
        )

        where = f" [{context}]" if context else ""
        note = {
            "action": "collapsed_date_values",
            "context": context,
            "source_values": list(raw_vals),
            "result": {
                "expression": result.expression,
                "begin": result.begin,
                "end": result.end,
            },
        }
        message = (f"Collapsed {len(parsed)} date values{where} "
                   f"({', '.join(raw_vals)}) into span {result.begin or '?'}–{result.end or '?'}.")
        self.transformation_notes.append(note)
        warnings.warn(message)
        return result

    def _pad_parallel_arrays(self, properties: Dict[str, Any]):
        parallel_keys = ['eventActors', 'eventTypes', 'eventStartDates', 'eventEndDates', 'eventDates']
        active_keys = [k for k in parallel_keys if k in properties]
        
        if active_keys:
            def _len(v):
                if isinstance(v, DateValue): return 1
                if not v: return 0
                return len(v.split('|'))
                
            max_len = max(_len(properties[k]) for k in active_keys)
            
            for k in active_keys:
                if isinstance(properties[k], DateValue):
                    pass
                else:
                    arr = properties[k].split('|') if properties[k] else []
                    if len(arr) < max_len:
                        padded = arr + ["NULL"] * (max_len - len(arr))
                        properties[k] = "|".join(padded)

    def ingest_xml(self, filepath: str) -> KernelGraph:
        culture = self.engine.policies.get('culture', 'en')
        encoding = self.engine.policies.get('encoding')
        if not encoding:
            raise ValueError("Strict encoding policy required.")
            
        context = ET.iterparse(filepath, events=("end",))
        
        for event, elem in context:
            if self._strip_ns(elem.tag) == 'record':
                record_data = self._extract_elements(elem, culture)
                row_entities: Dict[str, Entity] = {}
                
                base_id = record_data.get('priref', ['unknown'])[0]

                # Track every tag seen across records so the audit pack can report
                # unmapped source tags and mapped tags absent from the source.
                for tag in record_data.keys():
                    if tag not in self.seen_source_fields:
                        self.seen_source_fields.append(tag)

                for node_name, entity_def in self.engine.entities.items():
                    fields = self.engine.get_fields_for_node(node_name)
                    has_data = False
                    properties = {}
                    identifiers = []
                    
                    for fdef in fields:
                        raw_vals = record_data.get(fdef.source_field, [])
                        if raw_vals:
                            has_data = True
                            if fdef.transform == 'parse_date':
                                # parse_date expects a single date expression; parsing the
                                # pipe-joined string would make individually valid dates
                                # (e.g. "1920|1930") unparseable. Parse each value instead.
                                transformed = self._parse_dates(
                                    raw_vals, fdef.transform_args,
                                    context=f"{node_name}_{base_id}.{fdef.source_field}")
                            else:
                                raw_val = "|".join(raw_vals)
                                transformed = self._apply_transform(raw_val, fdef.transform, fdef.transform_args)

                            if fdef.target_property == 'identifiers':
                                identifiers.append(Identifier(value=transformed, kind="local", source_field=fdef.source_field))
                            else:
                                properties[fdef.target_property] = transformed
                                
                    if has_data:
                        self._pad_parallel_arrays(properties)
                        
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
                    
                elem.clear()
                
        return self.graph
