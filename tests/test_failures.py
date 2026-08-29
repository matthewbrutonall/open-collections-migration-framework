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

def test_split_transform(tmp_path):
    engine = MappingEngine()
    engine.policies['encoding'] = 'utf-8'
    engine.entities['item'] = EntityDef('item', 'test.csv', 'description')
    engine.fields.append(FieldDef('item', 'ref_code', 'identifiers', 'identity'))
    engine.fields.append(FieldDef('item', 'subjects', 'subjects', 'split', ';'))

    csv_path = os.path.join(tmp_path, "test.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("ref_code,subjects\n1,War ; Peace ;Diaries\n")

    adapter = PastPerfectAdapter(engine)
    graph = adapter.ingest_csv(csv_path)
    ent = graph.entities['item_1']
    assert ent.properties['subjects'] == "War|Peace|Diaries"

def test_lookup_transform():
    from ocmf.adapters.pastperfect import PastPerfectAdapter
    engine = MappingEngine()
    adapter = PastPerfectAdapter(engine)
    assert adapter._apply_transform("M", "lookup", "M=Male;F=Female") == "Male"
    # Unmatched keys pass through unchanged.
    assert adapter._apply_transform("X", "lookup", "M=Male;F=Female") == "X"

def test_empty_workbook_rejected(tmp_path):
    import openpyxl
    wb_path = os.path.join(tmp_path, "empty.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.create_sheet("policies")
    ws.append(["policy_name", "policy_value"])
    ws.append(["encoding", "utf-8"])
    # entities and fields sheets absent
    wb.save(wb_path)
    with pytest.raises(ValueError, match="no entities"):
        MappingEngine.compile_from_excel(wb_path)

def test_preflight_empty_graph_rejected():
    graph = KernelGraph()
    with pytest.raises(ValueError, match="no description records"):
        PreflightAudit(graph).run()

def test_mapped_event_type_preserved(tmp_path):
    from ocmf.writers.atom import AtomISADWriter
    graph = KernelGraph()
    e = Entity(id="1", type=EntityType.DESCRIPTION,
               identifiers=[Identifier(value="A", kind="local")],
               properties={"title": "T", "eventActors": "Custodian X", "eventTypes": "Accumulation"})
    graph.add_entity(e)
    out = os.path.join(tmp_path, "io.csv")
    AtomISADWriter(graph).write(out)
    with open(out) as f:
        content = f.read()
    assert "Accumulation" in content
    assert "Creation" not in content

def test_hierarchy_source_field_scopes_structure():
    # An accession identifier containing a dot must not forge a parent link.
    graph = KernelGraph()
    e = Entity(id="1", type=EntityType.DESCRIPTION,
               identifiers=[Identifier(value="A", kind="local", source_field="ref_code"),
                            Identifier(value="ACC.99", kind="local", source_field="accession")],
               properties={"title": "T"})
    graph.add_entity(e)
    hierarchy = HierarchyEngine(graph, {"hierarchy": "identifier_dots",
                                        "orphans": "abort",
                                        "hierarchy_source_field": "ref_code"})
    hierarchy.run()  # would raise "Orphan detected" for ACC.99 if not scoped
    assert not any(edge.relation == RelationType.CHILD_OF for edge in graph.edges)

def test_adlib_multiple_dates_span():
    from ocmf.adapters.adlib import AdlibXMLAdapter
    from ocmf.compiler import MappingEngine
    adapter = AdlibXMLAdapter(MappingEngine())
    dv = adapter._parse_dates(["1920", "1930"], None, context="item_1.creator_date")
    assert dv.begin == "1920" and dv.end == "1930"
    assert dv.expression == "1920|1930"
    # The collapse must be recorded as an interpretive transformation, not silent.
    assert len(adapter.transformation_notes) == 1
    assert adapter.transformation_notes[0]["action"] == "collapsed_date_values"
    assert adapter.transformation_notes[0]["source_values"] == ["1920", "1930"]

def test_mapped_description_field_emitted(tmp_path):
    from ocmf.writers.atom import AtomISADWriter
    graph = KernelGraph()
    e = Entity(id="1", type=EntityType.DESCRIPTION,
               identifiers=[Identifier(value="A", kind="local")],
               properties={"title": "T", "scopeAndContent": "The full story", "extentAndMedium": "3 boxes"})
    graph.add_entity(e)
    out = os.path.join(tmp_path, "io.csv")
    AtomISADWriter(graph).write(out)
    with open(out) as f:
        header, row = f.read().splitlines()[:2]
    assert "scopeAndContent" in header and "extentAndMedium" in header
    assert "The full story" in row and "3 boxes" in row

def test_unsupported_target_rejected():
    from ocmf.writers.atom import validate_targets
    engine = MappingEngine()
    engine.entities['item'] = EntityDef('item', 'test.csv', 'description')
    engine.fields.append(FieldDef('item', 'notes', 'scopeAndContnt', 'identity'))  # typo
    with pytest.raises(ValueError, match="Unsupported target property"):
        validate_targets(engine)

def test_agent_only_target_rejected_on_description():
    from ocmf.writers.atom import validate_targets
    engine = MappingEngine()
    engine.entities['item'] = EntityDef('item', 'test.csv', 'description')
    engine.fields.append(FieldDef('item', 'creator', 'name', 'identity'))
    with pytest.raises(ValueError, match="Unsupported target property"):
        validate_targets(engine)

def test_event_arrays_align_from_coordinates_only(tmp_path):
    from ocmf.writers.atom import AtomISADWriter
    graph = KernelGraph()
    # Only structured coordinates mapped — must still emit an aligned event row.
    e = Entity(id="1", type=EntityType.DESCRIPTION,
               identifiers=[Identifier(value="A", kind="local")],
               properties={"title": "T", "eventStartDates": "1900", "eventEndDates": "1901"})
    graph.add_entity(e)
    out = os.path.join(tmp_path, "io.csv")
    AtomISADWriter(graph).write(out)
    import csv as _csv
    with open(out) as f:
        row = list(_csv.DictReader(f))[0]
    assert row["eventStartDates"] == "1900"
    assert row["eventEndDates"] == "1901"
    # All parallel arrays are length 1 (no misalignment).
    assert row["eventActors"] == "NULL"
    assert row["eventTypes"] == "Creation"
    assert row["eventDates"] == "NULL"

def test_audit_reports_missing_mapped_field(tmp_path):
    from ocmf.audit import AuditPackGenerator
    from ocmf.hierarchy import HierarchyEngine
    engine = MappingEngine()
    engine.fields.append(FieldDef('item', 'title', 'title', 'identity'))
    engine.fields.append(FieldDef('item', 'nonexistent', 'scopeAndContent', 'identity'))
    hierarchy = HierarchyEngine(KernelGraph(), {})
    gen = AuditPackGenerator(engine, hierarchy, "source.xml",
                             source_fields=["title", "descrip"])
    gen.generate(str(tmp_path))
    register = open(os.path.join(tmp_path, "DATA_LOSS_REGISTER.md")).read()
    assert "Mapped Fields Missing From Source" in register
    assert "`nonexistent`" in register       # mapped but absent from source
    assert "`descrip`" in register           # present in source but unmapped

def test_missing_mapped_field_can_be_fatal():
    from ocmf.audit import AuditPackGenerator
    from ocmf.hierarchy import HierarchyEngine
    engine = MappingEngine()
    engine.policies["missing_mapped_fields"] = "abort"
    engine.fields.append(FieldDef('item', 'title', 'title', 'identity'))
    engine.fields.append(FieldDef('item', 'nonexistent', 'scopeAndContent', 'identity'))
    gen = AuditPackGenerator(
        engine,
        HierarchyEngine(KernelGraph(), {}),
        "source.xml",
        source_fields=["title"],
    )
    with pytest.raises(ValueError, match="Mapped fields missing from source"):
        gen.enforce_missing_mapped_policy()

def test_load_playbook_uses_atom_28_safe_cli_guidance(tmp_path):
    from ocmf.audit import AuditPackGenerator
    from ocmf.hierarchy import HierarchyEngine
    engine = MappingEngine()
    gen = AuditPackGenerator(engine, HierarchyEngine(KernelGraph(), {}), "source.csv", source_fields=[])
    gen.generate(str(tmp_path))
    playbook = open(os.path.join(tmp_path, "LOAD_PLAYBOOK.md")).read()
    assert "csv:check-import --verbose" in playbook
    assert "csv:import /path/to/information_objects.csv" in playbook
    assert "csv:import --application" not in playbook
    assert "csv:import --env" not in playbook

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
