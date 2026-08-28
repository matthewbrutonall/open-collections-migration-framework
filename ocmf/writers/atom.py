import csv
from typing import List, Dict
from ocmf.kernel.models import EntityType, RelationType, DateValue
from ocmf.kernel.graph import KernelGraph

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
                        
        fieldnames = [
            'legacyId', 'parentId', 'identifier', 'title', 'levelOfDescription', 
            'eventActors', 'eventTypes', 'eventDates', 'eventStartDates', 'eventEndDates'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
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

                max_events = max(len(all_actors), len(mapped_dates), 1 if (all_actors or mapped_dates) else 0)
                
                if max_events > 0:
                    actors_str = "|".join(all_actors + ["NULL"] * (max_events - len(all_actors)))
                    dates_str = "|".join(mapped_dates + ["NULL"] * (max_events - len(mapped_dates)))
                    sdates_str = "|".join(mapped_sdates + ["NULL"] * (max_events - len(mapped_sdates)))
                    edates_str = "|".join(mapped_edates + ["NULL"] * (max_events - len(mapped_edates)))
                    types_str = "|".join(["Creation"] * max_events)
                else:
                    actors_str = types_str = dates_str = sdates_str = edates_str = ""

                row = {
                    'legacyId': e_id,
                    'parentId': parent_id,
                    'identifier': identifier,
                    'title': ent.properties.get('title', ''),
                    'levelOfDescription': level,
                    'eventActors': actors_str,
                    'eventTypes': types_str,
                    'eventDates': dates_str,
                    'eventStartDates': sdates_str,
                    'eventEndDates': edates_str
                }
                writer.writerow(row)
