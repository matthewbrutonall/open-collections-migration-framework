import csv
from typing import List, Dict
from ocmf.kernel.models import EntityType, RelationType, DateValue
from ocmf.kernel.graph import KernelGraph

# Canonical AtoM 2.8 information_objects.csv ISAD(G) template order.
# AtoM documents that imports rely on template-compatible column names, and the
# example template order should be maintained for review and compatibility.
ATOM_DESCRIPTION_COLUMNS = [
    'legacyId', 'parentId', 'qubitParentSlug', 'accessionNumber', 'identifier',
    'title', 'levelOfDescription', 'extentAndMedium', 'repository',
    'archivalHistory', 'acquisition', 'scopeAndContent', 'appraisal',
    'accruals', 'arrangement', 'accessConditions', 'reproductionConditions',
    'language', 'script', 'languageNote',
    'physicalCharacteristics', 'findingAids', 'locationOfOriginals',
    'locationOfCopies', 'relatedUnitsOfDescription', 'publicationNote',
    'digitalObjectPath', 'digitalObjectURI', 'generalNote',
    'subjectAccessPoints', 'placeAccessPoints', 'nameAccessPoints',
    'genreAccessPoints', 'descriptionIdentifier', 'institutionIdentifier',
    'rules', 'descriptionStatus', 'levelOfDetail', 'revisionHistory',
    'languageOfDescription', 'scriptOfDescription', 'sources', 'archivistNote',
    'publicationStatus', 'physicalObjectName', 'physicalObjectLocation',
    'physicalObjectType', 'alternativeIdentifiers',
    'alternativeIdentifierLabels',
]

# Event columns the writer actually assembles as aligned parallel arrays.
ATOM_EVENT_COLUMNS = [
    'eventDates', 'eventTypes', 'eventStartDates', 'eventEndDates',
    'eventActors', 'eventActorHistories',
]

# Keys consumed into the event arrays rather than emitted as raw columns.
_CONSUMED_PROPERTY_KEYS = {'dates', 'level_of_description'} | set(ATOM_EVENT_COLUMNS)

# Every legal target for a `fields` mapping. A target outside this set would be
# stored on the graph but never reach the CSV, so it is rejected up front.
DESCRIPTION_TARGET_PROPERTIES = (
    set(ATOM_DESCRIPTION_COLUMNS)
    | set(ATOM_EVENT_COLUMNS)
    | {'identifiers', 'dates', 'level_of_description'}
)
AGENT_TARGET_PROPERTIES = {'identifiers', 'name'}


def validate_targets(engine):
    """Fail fast on any mapped target property the pipeline cannot emit."""
    for f in engine.fields:
        entity_def = engine.entities.get(f.node_name)
        if entity_def is None:
            raise ValueError(
                f"Field mapping references unknown node '{f.node_name}' "
                f"(field '{f.source_field}')."
            )
        if entity_def.entity_type == 'description':
            allowed = DESCRIPTION_TARGET_PROPERTIES
        elif entity_def.entity_type == 'agent':
            allowed = AGENT_TARGET_PROPERTIES
        else:
            allowed = {'identifiers'}

        if f.target_property not in allowed:
            raise ValueError(
                f"Unsupported target property '{f.target_property}' "
                f"(field '{f.source_field}', node '{f.node_name}'). "
                f"It would be silently dropped from the AtoM CSV. "
                f"Use a supported AtoM column or an event field."
            )


def _stringify(value) -> str:
    """Render a graph property value as a CSV cell."""
    if value is None:
        return ""
    if isinstance(value, DateValue):
        return str(value.expression or "")
    if isinstance(value, dict) and 'expression' in value:
        return str(value.get('expression') or "")
    return str(value)


class AtomISADWriter:
    def __init__(self, graph: KernelGraph):
        self.graph = graph
        
    def write(self, output_path: str):
        descriptions = {e_id: e for e_id, e in self.graph.entities.items() if e.type == EntityType.DESCRIPTION}
        parent_map = {}
        children_map = {e_id: [] for e_id in descriptions.keys()}
        
        for edge in self.graph.edges:
            if edge.relation == RelationType.CHILD_OF:
                if edge.source_id in descriptions and edge.target_id in descriptions:
                    parent_map[edge.source_id] = edge.target_id
                    if edge.source_id not in children_map[edge.target_id]:
                        children_map[edge.target_id].append(edge.source_id)
                    
        roots = [e_id for e_id in descriptions.keys() if e_id not in parent_map]
        ordered_ids = []
        visited = set()
        
        def dfs(node_id):
            if node_id in visited: return
            visited.add(node_id)
            ordered_ids.append(node_id)
            children = sorted(
                children_map[node_id], 
                key=lambda cid: descriptions[cid].identifiers[0].value if descriptions[cid].identifiers else ""
            )
            for child_id in children:
                dfs(child_id)
                
        sorted_roots = sorted(roots, key=lambda rid: descriptions[rid].identifiers[0].value if descriptions[rid].identifiers else "")
        for root_id in sorted_roots:
            dfs(root_id)
            
        creators_map = {e_id: [] for e_id in descriptions.keys()}
        for edge in self.graph.edges:
            if edge.relation == RelationType.CREATED_BY:
                if edge.source_id in descriptions and edge.target_id in self.graph.entities:
                    agent = self.graph.entities[edge.target_id]
                    name = agent.properties.get("name", "")
                    if name and name not in creators_map[edge.source_id]:
                        creators_map[edge.source_id].append(name)
                        
        # Emit any mapped, supported descriptive column that actually carries
        # data, so mapped fields (scopeAndContent, extentAndMedium, ...) are
        # never silently dropped. Identity/level columns always lead.
        present_keys = set()
        for ent in descriptions.values():
            present_keys.update(ent.properties.keys())

        required_columns = ['legacyId', 'parentId', 'identifier', 'title', 'levelOfDescription']
        fieldnames = []
        for column in ATOM_DESCRIPTION_COLUMNS + ATOM_EVENT_COLUMNS + ['culture']:
            if column in required_columns or column in present_keys or column in ATOM_EVENT_COLUMNS:
                fieldnames.append(column)

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator='\n')
            writer.writeheader()
            
            for e_id in ordered_ids:
                ent = descriptions[e_id]
                identifier = ent.identifiers[0].value if ent.identifiers else ""
                parent_id = parent_map.get(e_id, "")
                
                level = ent.properties.get('level_of_description')
                if not level:
                    level = 'series' if children_map.get(e_id) else 'item'
                
                edge_creators = creators_map.get(e_id, [])
                mapped_actors = ent.properties.get('eventActors', '').split('|') if ent.properties.get('eventActors') else []
                all_actors = mapped_actors + edge_creators
                mapped_types = ent.properties.get('eventTypes', '').split('|') if ent.properties.get('eventTypes') else []
                mapped_histories = ent.properties.get('eventActorHistories', '').split('|') if ent.properties.get('eventActorHistories') else []

                mapped_sdates = ent.properties.get('eventStartDates', '').split('|') if ent.properties.get('eventStartDates') else []
                mapped_edates = ent.properties.get('eventEndDates', '').split('|') if ent.properties.get('eventEndDates') else []
                mapped_dates = ent.properties.get('eventDates', '').split('|') if ent.properties.get('eventDates') else []
                
                dates_prop = ent.properties.get('dates')
                if dates_prop:
                    if isinstance(dates_prop, DateValue):
                        mapped_dates = [str(dates_prop.expression or '')]
                        mapped_sdates = [str(dates_prop.begin or '')]
                        mapped_edates = [str(dates_prop.end or '')]
                    elif isinstance(dates_prop, dict):
                        mapped_dates = [str(dates_prop.get('expression') or '')]
                        mapped_sdates = [str(dates_prop.get('begin') or '')]
                        mapped_edates = [str(dates_prop.get('end') or '')]
                    else:
                        mapped_dates = [str(dates_prop)]
                        mapped_sdates = [str(dates_prop)]
                        mapped_edates = [""]

                # All parallel event arrays must drive length, or a record with
                # only start/end coordinates would emit blank event columns, and
                # mismatched lengths would misalign AtoM's parallel event fields.
                has_events = bool(all_actors or mapped_dates or mapped_types or mapped_sdates or mapped_edates or mapped_histories)
                max_events = max(
                    len(all_actors), len(mapped_dates), len(mapped_types),
                    len(mapped_sdates), len(mapped_edates), len(mapped_histories),
                    1 if has_events else 0,
                )

                if max_events > 0:
                    actors_str = "|".join(all_actors + ["NULL"] * (max_events - len(all_actors)))
                    histories_str = "|".join(mapped_histories + ["NULL"] * (max_events - len(mapped_histories)))
                    dates_str = "|".join(mapped_dates + ["NULL"] * (max_events - len(mapped_dates)))
                    sdates_str = "|".join(mapped_sdates + ["NULL"] * (max_events - len(mapped_sdates)))
                    edates_str = "|".join(mapped_edates + ["NULL"] * (max_events - len(mapped_edates)))
                    # Preserve mapped event types; only default to "Creation" where none was supplied.
                    types_str = "|".join(mapped_types + ["Creation"] * (max_events - len(mapped_types)))
                else:
                    actors_str = histories_str = types_str = dates_str = sdates_str = edates_str = ""

                row = {col: "" for col in fieldnames}
                row.update({
                    'legacyId': e_id,
                    'parentId': parent_id,
                    'identifier': identifier,
                    'title': ent.properties.get('title', ''),
                    'levelOfDescription': level,
                    'eventActors': actors_str,
                    'eventTypes': types_str,
                    'eventDates': dates_str,
                    'eventStartDates': sdates_str,
                    'eventEndDates': edates_str,
                    'eventActorHistories': histories_str,
                })
                for col in fieldnames:
                    if col in row and row[col]:
                        continue
                    if col in ent.properties and col not in _CONSUMED_PROPERTY_KEYS:
                        row[col] = _stringify(ent.properties.get(col, ""))
                writer.writerow(row)
