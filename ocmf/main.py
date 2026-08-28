import json
from uuid import uuid4
from ocmf.kernel.models import Entity, EntityType, Identifier, DateValue, RelationType
from ocmf.kernel.graph import KernelGraph

def build_mock_graph() -> KernelGraph:
    graph = KernelGraph()
    repo_id = "repo_main"
    repo = Entity(id=repo_id, type=EntityType.REPOSITORY, properties={"name": "State Archives"})
    graph.add_entity(repo)
    
    fonds_id = "desc_fonds_1"
    fonds = Entity(
        id=fonds_id, type=EntityType.DESCRIPTION,
        identifiers=[Identifier(value="F001", kind="reference_code", source_field="ref_code")],
        properties={"title": "Smith Family Papers", "level_of_description": "fonds", "dates": DateValue(expression="1920-1980", begin="1920-01-01", end="1980-12-31", inferred=False).__dict__}
    )
    graph.add_entity(fonds)
    
    item_id = "desc_item_1"
    item = Entity(
        id=item_id, type=EntityType.DESCRIPTION,
        identifiers=[Identifier(value="F001-01", kind="reference_code", source_field="ref_code")],
        properties={"title": "Letter from John to Mary", "level_of_description": "item"}
    )
    graph.add_entity(item)
    
    agent_id = "agent_smith_j"
    agent = Entity(id=agent_id, type=EntityType.AGENT, properties={"name": "Smith, John", "agent_type": "person"})
    graph.add_entity(agent)
    
    graph.add_edge(fonds_id, repo_id, RelationType.HELD_BY)
    graph.add_edge(item_id, fonds_id, RelationType.CHILD_OF)
    graph.add_edge(item_id, agent_id, RelationType.CREATED_BY)
    return graph

def main():
    graph = build_mock_graph()
    snapshot = graph.to_dict()
    print(json.dumps(snapshot, indent=2))
    with open("mock_graph_snapshot.json", "w") as f:
        json.dump(snapshot, f, indent=2)

if __name__ == "__main__":
    main()
