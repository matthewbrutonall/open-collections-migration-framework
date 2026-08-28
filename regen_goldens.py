import json
from ocmf.compiler import MappingEngine
from ocmf.adapters.pastperfect import PastPerfectAdapter
from ocmf.hierarchy import HierarchyEngine
from ocmf.preflight import PreflightAudit
from ocmf.writers.atom import AtomISADWriter

def run():
    engine = MappingEngine.compile_from_excel('tests/golden/input_mapping.xlsx')
    adapter = PastPerfectAdapter(engine)
    graph = adapter.ingest_csv('tests/golden/input_data.csv')
    hierarchy = HierarchyEngine(graph, engine.policies)
    graph = hierarchy.run()
    audit = PreflightAudit(graph)
    audit.run()
    
    # Custom encoder for Enums
    class EnumEncoder(json.JSONEncoder):
        def default(self, obj):
            if hasattr(obj, 'value'): return obj.value
            return super().default(obj)
            
    snapshot = json.loads(json.dumps(graph.to_dict(), cls=EnumEncoder))
    with open('tests/golden/golden_graph.json', 'w') as f:
        json.dump(snapshot, f, indent=2)
        
    writer = AtomISADWriter(graph)
    writer.write('tests/golden/golden_information_objects.csv')

if __name__ == '__main__':
    run()
