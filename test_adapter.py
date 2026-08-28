import json
from ocmf.compiler import MappingEngine
from ocmf.adapters.pastperfect import PastPerfectAdapter
from ocmf.hierarchy import HierarchyEngine
from ocmf.preflight import PreflightAudit
from ocmf.writers.atom import AtomISADWriter
from ocmf.audit import AuditPackGenerator

def run():
    print("1. Compiling Mapping Engine...")
    engine = MappingEngine.compile_from_excel('mapping_workbook.xlsx')
    
    print("2. Ingesting CSV via Adapter...")
    adapter = PastPerfectAdapter(engine)
    graph = adapter.ingest_csv('test_data.csv')
    
    print("3. Running Hierarchy Engine...")
    hierarchy = HierarchyEngine(graph, engine.policies)
    graph = hierarchy.run()
    
    print("4. Running Pre-flight Audit...")
    audit = PreflightAudit(graph)
    audit.run()
    print("   -> Audit passed!")
    
    print("5. Outputting final graph snapshot...")
    snapshot = graph.to_dict()
    with open('graph_snapshot_with_hierarchy.json', 'w') as f:
        json.dump(snapshot, f, indent=2)
        
    print("6. Emitting AtoM ISAD(G) CSV...")
    writer = AtomISADWriter(graph)
    writer.write('information_objects.csv')
    print("   -> information_objects.csv created successfully.")
    
    print("7. Generating Audit Pack...")
    audit_gen = AuditPackGenerator(engine, hierarchy, 'test_data.csv')
    audit_gen.generate()
    print("   -> DATA_LOSS_REGISTER.md and LOAD_PLAYBOOK.md created successfully.")

if __name__ == '__main__':
    run()
