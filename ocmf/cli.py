import argparse
import sys
import os
import json

from ocmf.compiler import MappingEngine
from ocmf.adapters.pastperfect import PastPerfectAdapter
from ocmf.adapters.adlib import AdlibXMLAdapter
from ocmf.hierarchy import HierarchyEngine
from ocmf.preflight import PreflightAudit
from ocmf.writers.atom import AtomISADWriter
from ocmf.audit import AuditPackGenerator
from ocmf.tools.create_template import create_template

def run_migrate(args):
    if not os.path.exists(args.engine):
        print(f"Error: Mapping engine workbook '{args.engine}' not found.")
        sys.exit(1)
    if not os.path.exists(args.source):
        print(f"Error: Source data file '{args.source}' not found.")
        sys.exit(1)
        
    print("1. Compiling Mapping Engine...")
    try:
        engine = MappingEngine.compile_from_excel(args.engine)
    except Exception as e:
        print(f"Compile Error: {e}")
        sys.exit(1)
        
    print("2. Ingesting Data...")
    try:
        if args.source.lower().endswith('.xml'):
            adapter = AdlibXMLAdapter(engine)
            graph = adapter.ingest_xml(args.source)
        else:
            adapter = PastPerfectAdapter(engine)
            graph = adapter.ingest_csv(args.source)
    except Exception as e:
        print(f"Ingest Error: {e}")
        sys.exit(1)
        
    print("3. Running Hierarchy Engine...")
    try:
        hierarchy = HierarchyEngine(graph, engine.policies)
        graph = hierarchy.run()
    except Exception as e:
        print(f"Hierarchy Error: {e}")
        sys.exit(1)
        
    print("4. Running Pre-flight Audit...")
    audit = PreflightAudit(graph)
    try:
        audit.run()
        print("   -> Audit passed!")
    except Exception as e:
        print(f"Pre-flight Error: {e}")
        sys.exit(1)
        
    os.makedirs(args.outdir, exist_ok=True)
    
    print("4.5 Emitting Graph Snapshot...")
    snapshot_path = os.path.join(args.outdir, 'graph_snapshot.json')
    class EnumEncoder(json.JSONEncoder):
        def default(self, obj):
            if hasattr(obj, 'value'): return obj.value
            return super().default(obj)
    try:
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(graph.to_dict(), f, indent=2, cls=EnumEncoder)
        print(f"   -> {snapshot_path} created successfully.")
    except Exception as e:
        print(f"Snapshot Error: {e}")
        sys.exit(1)
    
    print("5. Emitting AtoM ISAD(G) CSV...")
    out_csv = os.path.join(args.outdir, 'information_objects.csv')
    try:
        writer = AtomISADWriter(graph)
        writer.write(out_csv)
        print(f"   -> {out_csv} created successfully.")
    except Exception as e:
        print(f"Writer Error: {e}")
        sys.exit(1)
    
    print("6. Generating Audit Pack...")
    try:
        pack_gen = AuditPackGenerator(engine, hierarchy, args.source)
        pack_gen.generate(args.outdir)
        print("   -> DATA_LOSS_REGISTER.md and LOAD_PLAYBOOK.md created successfully.")
    except Exception as e:
        print(f"Audit Pack Error: {e}")
        sys.exit(1)
        
    print("\nMigration complete! Review your LOAD_PLAYBOOK.md for the next steps.")

def run_template(args):
    try:
        create_template(args.outfile)
        print(f"Template workbook successfully generated at '{args.outfile}'")
    except Exception as e:
        print(f"Error generating template: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Open Collections Migration Framework (OCMF) CLI")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")
    
    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Run a full migration pipeline (Source -> Graph -> AtoM CSV)")
    migrate_parser.add_argument("--engine", required=True, help="Path to the Excel mapping workbook (e.g., mapping.xlsx)")
    migrate_parser.add_argument("--source", required=True, help="Path to the source data export (CSV or XML)")
    migrate_parser.add_argument("--outdir", default=".", help="Output directory for the AtoM CSV and Audit Pack (default: current directory)")
    
    # Template command
    template_parser = subparsers.add_parser("template", help="Generate a blank mapping workbook template")
    template_parser.add_argument("--outfile", default="mapping_workbook.xlsx", help="Output path for the new workbook template")
    
    args = parser.parse_args()
    
    if args.command == "migrate":
        run_migrate(args)
    elif args.command == "template":
        run_template(args)

if __name__ == "__main__":
    main()
