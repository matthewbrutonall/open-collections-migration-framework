import os
import pytest

from ocmf.compiler import MappingEngine, EntityDef, FieldDef
from ocmf.adapters.pastperfect import PastPerfectAdapter
from ocmf.adapters.adlib import AdlibXMLAdapter
from ocmf.hierarchy import HierarchyEngine
from ocmf.preflight import PreflightAudit
from ocmf.kernel.graph import KernelGraph
from ocmf.kernel.models import Entity, EntityType, Identifier, RelationType

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(TEST_DIR, 'golden')

def test_missing_encoding():
    with pytest.raises(ValueError, match="Strict encoding policy required"):
        engine = MappingEngine()
        PastPerfectAdapter(engine).ingest_csv("dummy.csv")

def test_invalid_transform(tmp_path):
    wb_path = os.path.join(tmp_path, "bad.xlsx")
    import openpyxl
    wb = openpyxl.Workbook()
    wb.create_sheet("policies").append(["encoding", "utf-8"])
    ws = wb.create_sheet("fields")
    ws.append(["node_name", "source_field", "target_property", "transform"])
    ws.append(["item", "f1", "prop", "unknown_magic"])
    wb.save(wb_path)
    
    with pytest.raises(ValueError, match="Invalid transform 'unknown_magic'"):
        MappingEngine.compile_from_excel(wb_path)

def test_preflight_duplicate_identifiers():
    graph = KernelGraph()
    e1 = Entity(id="1", type=EntityType.DESCRIPTION, identifiers=[Identifier(value="A", kind="local")], properties={"title": "T1"})
    e2 = Entity(id="2", type=EntityType.DESCRIPTION, identifiers=[Identifier(value="A", kind="local")])
    graph.add_entity(e1)
    graph.add_entity(e2)
    audit = PreflightAudit(graph)
    with pytest.raises(ValueError, match="Duplicate identifier"):
        audit.run()

def test_preflight_empty_title():
    graph = KernelGraph()
    e1 = Entity(id="1", type=EntityType.DESCRIPTION, identifiers=[Identifier(value="A", kind="local")], properties={"title": ""})
    graph.add_entity(e1)
    audit = PreflightAudit(graph)
    with pytest.raises(ValueError, match="empty title"):
        audit.run()

def test_bom_detection(tmp_path):
    csv_path = os.path.join(tmp_path, "bom.csv")
    with open(csv_path, "w", encoding="utf-8-sig") as f:
        f.write("ref_code,title\n1,Test")
        
    engine = MappingEngine()
    engine.policies['encoding'] = 'utf-8'
    adapter = PastPerfectAdapter(engine)
    with pytest.raises(ValueError, match="BOM detected"):
        adapter.ingest_csv(csv_path)

def test_unimplemented_transform(tmp_path):
    engine = MappingEngine()
    engine.policies['encoding'] = 'utf-8'
    engine.entities['item'] = EntityDef('item', 'test.csv', 'description')
    engine.fields.append(FieldDef('item', 'title', 'title', 'split'))
    
    csv_path = os.path.join(tmp_path, "test.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("ref_code,title\n1,Test")
        
    adapter = PastPerfectAdapter(engine)
    with pytest.raises(NotImplementedError, match="is not implemented"):
        adapter.ingest_csv(csv_path)

def test_orphan_abort():
    graph = KernelGraph()
    e1 = Entity(id="1", type=EntityType.DESCRIPTION, identifiers=[Identifier(value="A.01", kind="local")])
    graph.add_entity(e1)
    hierarchy = HierarchyEngine(graph, {"hierarchy": "identifier_dots", "orphans": "abort"})
    with pytest.raises(ValueError, match="Orphan detected"):
        hierarchy.run()

def test_cycle_detection():
    graph = KernelGraph()
    e1 = Entity(id="1", type=EntityType.DESCRIPTION, identifiers=[Identifier(value="A", kind="local")], properties={"title": "T1"})
    e2 = Entity(id="2", type=EntityType.DESCRIPTION, identifiers=[Identifier(value="B", kind="local")], properties={"title": "T2"})
    graph.add_entity(e1)
    graph.add_entity(e2)
    graph.add_edge("1", "2", RelationType.CHILD_OF)
    graph.add_edge("2", "1", RelationType.CHILD_OF)
    
    audit = PreflightAudit(graph)
    with pytest.raises(ValueError, match="Cycle detected"):
        audit.run()

def test_date_parsing_edge_cases():
    from ocmf.compiler import MappingEngine
    from ocmf.adapters.pastperfect import PastPerfectAdapter
    engine = MappingEngine()
    adapter = PastPerfectAdapter(engine)
    
    dv1 = adapter._apply_transform("1920-01-01", "parse_date", None)
    assert dv1.expression == "1920-01-01" and dv1.begin is None and dv1.end is None
    
    dv2 = adapter._apply_transform("1914–1918", "parse_date", None)
    assert dv2.expression == "1914–1918" and dv2.begin is None and dv2.end is None
    
    dv3 = adapter._apply_transform("c. 1920", "parse_date", None)
    assert dv3.expression == "c. 1920" and dv3.begin is None and dv3.end is None

