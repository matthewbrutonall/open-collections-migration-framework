import os
import csv
from typing import List

from ocmf.compiler import MappingEngine
from ocmf.hierarchy import HierarchyEngine

class AuditPackGenerator:
    def __init__(self, engine: MappingEngine, hierarchy: HierarchyEngine, source_filepath: str):
        self.engine = engine
        self.hierarchy = hierarchy
        self.source_filepath = source_filepath
        
    def generate(self, output_dir: str = "."):
        unmapped = self._get_unmapped_fields()
        synthesized = self.hierarchy.synthesized_nodes
        self._write_dataloss_register(unmapped, synthesized, output_dir)
        self._write_load_playbook(unmapped, synthesized, output_dir)
        
    def _get_unmapped_fields(self) -> List[str]:
        if not self.source_filepath.endswith('.csv'):
            return ["(Source is not CSV - structural check bypassed)"]
            
        encoding = self.engine.policies.get('encoding', 'utf-8')
        with open(self.source_filepath, 'r', encoding=encoding, errors='strict') as f:
            reader = csv.reader(f, escapechar='\\')
            try:
                headers = next(reader)
            except StopIteration:
                headers = []
                
        mapped_fields = {f.source_field for f in self.engine.fields}
        return [h for h in headers if h not in mapped_fields]
        
    def _write_dataloss_register(self, unmapped: List[str], synthesized: List[str], out_dir: str):
        path = os.path.join(out_dir, "DATA_LOSS_REGISTER.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# Data-Loss Register\n\n")
            f.write("## Unmapped Source Fields\n")
            for field in unmapped:
                if field.strip(): f.write(f"- `{field}`\n")
            if not unmapped: f.write("*None. All fields were successfully mapped.*\n")
                
            f.write("\n## Synthesized Nodes\n")
            for node in synthesized: f.write(f"- `{node}`\n")
            if not synthesized: f.write("*None. No orphans detected.*\n")

    def _write_load_playbook(self, unmapped: List[str], synthesized: List[str], out_dir: str):
        path = os.path.join(out_dir, "LOAD_PLAYBOOK.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# Migration Load Playbook\n\n")
            f.write("## 1. Review Data Loss\n")
            f.write(f"Review the Data-Loss Register.\n\n")
            f.write("## 2. Ingest Commands\n")
            f.write("Transfer the generated `information_objects.csv` to the AtoM server. From the AtoM root directory, run the following CLI command:\n\n")
            f.write("```bash\n")
            f.write("php symfony csv:import --application=qubit --env=prod information_objects.csv\n")
            f.write("```\n\n")
            f.write("## 3. Post-Ingest Verification\n")
            f.write("- Rebuild the search index: `php symfony search:populate`\n")
