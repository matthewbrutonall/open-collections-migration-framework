import os
import json
import pytest

from ocmf.compiler import MappingEngine
from ocmf.adapters.pastperfect import PastPerfectAdapter
from ocmf.hierarchy import HierarchyEngine
from ocmf.preflight import PreflightAudit
from ocmf.writers.atom import AtomISADWriter

# Determine paths relative to this test file
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(TEST_DIR, 'golden')

def test_full_migration_pipeline(tmp_path):
    """
    Tests the full pipeline from synthetic PastPerfect CSV to golden graph JSON
    and golden AtoM CSV.
    """
    input_csv = os.path.join(GOLDEN_DIR, 'input_data.csv')
    mapping_xlsx = os.path.join(GOLDEN_DIR, 'input_mapping.xlsx')
    golden_graph_path = os.path.join(GOLDEN_DIR, 'golden_graph.json')
    golden_atom_path = os.path.join(GOLDEN_DIR, 'golden_information_objects.csv')
    
    # Outputs to temporary directory
    output_atom_path = os.path.join(tmp_path, 'information_objects.csv')
    
    # 1. Compile engine
    engine = MappingEngine.compile_from_excel(mapping_xlsx)
    
    # 2. Adapter ingest
    adapter = PastPerfectAdapter(engine)
    graph = adapter.ingest_csv(input_csv)
    
    # 3. Hierarchy engine
    hierarchy = HierarchyEngine(graph, engine.policies)
    graph = hierarchy.run()
    
    # 4. Preflight
    audit = PreflightAudit(graph)
    assert audit.run() is True, "Preflight audit should pass on golden data."
    
    # 5. Compare graph to golden graph
    # Roundtrip through JSON to handle Enum stringification
    generated_graph_dict = json.loads(json.dumps(graph.to_dict()))
    with open(golden_graph_path, 'r', encoding='utf-8') as f:
        golden_graph_dict = json.load(f)
        
    assert generated_graph_dict == golden_graph_dict, "Graph snapshot does not match golden JSON."
    
    # 6. Emit AtoM CSV and compare
    writer = AtomISADWriter(graph)
    writer.write(output_atom_path)
    
    with open(output_atom_path, 'r', encoding='utf-8') as f_out:
        generated_csv = f_out.read()
        
    with open(golden_atom_path, 'r', encoding='utf-8') as f_gold:
        golden_csv = f_gold.read()
        
    assert generated_csv == golden_csv, "AtoM CSV output does not match golden CSV."
