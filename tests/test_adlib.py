import os
import openpyxl
from ocmf.compiler import MappingEngine
from ocmf.adapters.adlib import AdlibXMLAdapter

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(TEST_DIR, 'golden')

def test_adlib_adapter_produces_correct_graph(tmp_path):
    wb_path = os.path.join(tmp_path, "adlib_mapping_workbook.xlsx")
    wb = openpyxl.Workbook()
    
    ws_entities = wb.active
    ws_entities.title = "entities"
    ws_entities.append(["node_name", "source_table", "entity_type"])
    ws_entities.append(["item_node", "adlib.xml", "description"])
    
    ws_fields = wb.create_sheet("fields")
    ws_fields.append(["node_name", "source_field", "target_property", "transform", "transform_args"])
    ws_fields.append(["item_node", "reference_number", "identifiers", "identity", None])
    ws_fields.append(["item_node", "title", "title", "identity", None])
    ws_fields.append(["item_node", "creator", "eventActors", "identity", None])
    # Mapping dates using parse_date
    ws_fields.append(["item_node", "creator_date", "dates", "parse_date", None])
    
    ws_policies = wb.create_sheet("policies")
    ws_policies.append(["policy_name", "policy_value"])
    ws_policies.append(["encoding", "utf-8"])
    ws_policies.append(["culture", "en"])
    ws_policies.append(["hierarchy", "identifier_dots"])
    ws_policies.append(["orphans", "abort"])
    
    wb.save(wb_path)
    
    engine = MappingEngine.compile_from_excel(wb_path)
    adapter = AdlibXMLAdapter(engine)
    
    input_xml = os.path.join(GOLDEN_DIR, 'input_adlib.xml')
    graph = adapter.ingest_xml(input_xml)
    
    assert len(graph.entities) == 1
    assert "item_node_1001" in graph.entities
    assert graph.entities["item_node_1001"].identifiers[0].value == "REF-001"
    assert graph.entities["item_node_1001"].properties.get("title") == "The Adlib Migration Test"
    ent = graph.entities["item_node_1001"]
    
    assert ent.properties["eventActors"] == "Smith, John|Doe, Jane"
    
    # Check that DateValue object was properly populated for single-year format
    date_val = ent.properties["dates"]
    assert date_val.expression == "1920"
    assert date_val.begin == "1920"
    assert date_val.end == "1920"
