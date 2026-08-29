import os
import csv
from typing import Any, List

from ocmf.compiler import MappingEngine
from ocmf.hierarchy import HierarchyEngine

class AuditPackGenerator:
    def __init__(self, engine: MappingEngine, hierarchy: HierarchyEngine, source_filepath: str,
                 transformation_notes: List[Any] = None, source_fields: List[str] = None):
        self.engine = engine
        self.hierarchy = hierarchy
        self.source_filepath = source_filepath
        self.transformation_notes = transformation_notes or []
        # Ordered list of source fields/tags actually present in the source,
        # supplied by the adapter (works for both CSV and XML).
        self.source_fields = source_fields

    def generate(self, output_dir: str = "."):
        unmapped = self._get_unmapped_fields()
        missing = self._get_missing_mapped_fields()
        synthesized = self.hierarchy.synthesized_nodes
        self._write_dataloss_register(unmapped, missing, synthesized, output_dir)
        self._write_load_playbook(unmapped, synthesized, output_dir)

    def _source_fields(self) -> List[str]:
        """Ordered source fields/tags present in the source.

        Prefers what the adapter actually observed (covers CSV and XML); falls
        back to reading the CSV header if no adapter data was supplied.
        """
        if self.source_fields is not None:
            return self.source_fields
        if not self.source_filepath.endswith('.csv'):
            return []
        encoding = self.engine.policies.get('encoding', 'utf-8')
        with open(self.source_filepath, 'r', encoding=encoding, errors='strict') as f:
            reader = csv.reader(f)
            try:
                return next(reader)
            except StopIteration:
                return []

    def _get_unmapped_fields(self) -> List[str]:
        mapped_fields = {f.source_field for f in self.engine.fields}
        return [h for h in self._source_fields() if h not in mapped_fields]

    def _get_missing_mapped_fields(self) -> List[str]:
        """Mapped source fields that never appeared in the source (likely typos)."""
        return self.missing_mapped_fields()

    def missing_mapped_fields(self) -> List[str]:
        """Mapped source fields that never appeared in the source (likely typos)."""
        present = set(self._source_fields())
        if not present:
            return []
        missing = []
        for f in self.engine.fields:
            if f.source_field not in present and f.source_field not in missing:
                missing.append(f.source_field)
        return missing

    def enforce_missing_mapped_policy(self):
        policy = self.engine.policies.get('missing_mapped_fields', 'warn')
        if policy not in ('warn', 'abort'):
            raise ValueError(
                "Policy 'missing_mapped_fields' must be either 'warn' or 'abort'."
            )
        missing = self.missing_mapped_fields()
        if policy == 'abort' and missing:
            raise ValueError(
                "Mapped fields missing from source: " + ", ".join(missing)
            )

    def _render_transformation_note(self, note: Any) -> str:
        if isinstance(note, dict):
            action = note.get('action', 'Transformation')
            context = note.get('context')
            source_values = note.get('source_values')
            result = note.get('result', {})
            pieces = [str(action)]
            if context:
                pieces.append(f"[{context}]")
            if source_values:
                pieces.append(f"source={source_values}")
            if result:
                pieces.append(f"result={result}")
            return " ".join(pieces)
        return str(note)

    def _write_dataloss_register(self, unmapped: List[str], missing: List[str],
                                 synthesized: List[str], out_dir: str):
        path = os.path.join(out_dir, "DATA_LOSS_REGISTER.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# Data-Loss Register\n\n")
            f.write("## Unmapped Source Fields\n")
            for field in unmapped:
                if field.strip(): f.write(f"- `{field}`\n")
            if not unmapped: f.write("*None. All fields were successfully mapped.*\n")

            f.write("\n## Mapped Fields Missing From Source\n")
            f.write("*Mapped fields not found in the source — likely typos or an unexpected export.*\n\n")
            for field in missing: f.write(f"- `{field}`\n")
            if not missing: f.write("*None. Every mapped field was present in the source.*\n")

            f.write("\n## Synthesized Nodes\n")
            for node in synthesized: f.write(f"- `{node}`\n")
            if not synthesized: f.write("*None. No orphans detected.*\n")

            f.write("\n## Interpretive Transformations\n")
            f.write("*Values altered by policy beyond a direct 1:1 mapping. Review for fidelity.*\n\n")
            for note in self.transformation_notes:
                f.write(f"- {self._render_transformation_note(note)}\n")
            if not self.transformation_notes: f.write("*None. All values mapped without interpretation.*\n")

    def _write_load_playbook(self, unmapped: List[str], synthesized: List[str], out_dir: str):
        path = os.path.join(out_dir, "LOAD_PLAYBOOK.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# Migration Load Playbook\n\n")
            f.write("## 1. Review the Audit Register\n")
            f.write("Review `DATA_LOSS_REGISTER.md` before touching an AtoM instance.\n\n")
            f.write("## 2. Use a Test Instance First\n")
            f.write("AtoM recommends testing imports outside production. Restore a recent production backup into a staging/test instance, run the import there, and review the resulting descriptions before production import.\n\n")
            f.write("## 3. Transfer the CSV\n")
            f.write("Copy `information_objects.csv` to a working directory readable from the AtoM root.\n\n")
            f.write("## 4. Validate the CSV\n")
            f.write("From the AtoM root directory, run AtoM's CSV validator. The `--verbose` flag gives row-level detail for many failures:\n\n")
            f.write("```bash\n")
            f.write("php symfony csv:check-import --verbose /path/to/information_objects.csv\n")
            f.write("```\n\n")
            f.write("Do not import until validation errors are resolved and warnings have been reviewed.\n\n")
            f.write("## 5. Import the CSV\n")
            f.write("Run the import from the AtoM root directory. Do not add `--application`, `--env`, or `--connection`; AtoM expects the Symfony defaults for this task.\n\n")
            f.write("```bash\n")
            f.write("php symfony csv:import /path/to/information_objects.csv --source-name=\"OCMF_IMPORT_NAME\"\n")
            f.write("```\n\n")
            f.write("Use a stable `--source-name` for related chunks from the same migration so AtoM keymap rows stay grouped.\n\n")
            f.write("## 6. Post-Import Verification\n")
            f.write("- Clear cache: `php symfony cc`\n")
            f.write("- Rebuild the search index if the import did not index as it ran: `php symfony search:populate`\n")
            f.write("- Spot-check hierarchy, titles, identifiers, repository links, event actors, and any synthesized nodes.\n")
