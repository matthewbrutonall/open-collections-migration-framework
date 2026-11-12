# Open Collections Migration Framework (OCMF)

![Legacy collection exports passing through a graph and checks into an archival import and audit report](assets/open-collections-migration-framework.png)

OCMF is a rigorous, graph-based data migration pipeline that processes archival exports from legacy collections systems (like PastPerfect and Axiell Adlib), strictly enforces typing and hierarchy constraints, and emits cleanly formatted, validation-ready CSVs for AtoM (Access to Memory).

OCMF operates on *exported* data files, not live databases — the export is the operational boundary. Migration accepts PastPerfect CSV and Adlib XML; DBF files are supported for profiling only (`ocmf profile`) and should be exported to CSV before migration.

## Install with your AI agent

Copy and paste this into your agent:

```text
Install Open Collections Migration Framework from https://github.com/matthewbrutonall/open-collections-migration-framework on my computer. Check that Python 3.9 or later is available, create a virtual environment, install the normal package from the repository, and verify that `ocmf --help` works. Tell me how to run it. Do not profile or migrate any collection data yet.
```

## In plain English

OCMF helps move catalogue data out of old collections databases and into AtoM.

It takes an exported file, such as a CSV from PastPerfect or XML from Adlib, reads it according to a mapping spreadsheet, checks for common migration problems, rebuilds parent-child hierarchies, and produces an AtoM-ready import CSV.

It also produces an audit pack showing what was mapped, what was missing, what was changed by interpretation, and what should be checked before import.

## Who this is for

OCMF is for archivists, consultants, and GLAM technologists preparing legacy collection data for audited import into AtoM.

## Architecture

Unlike simple row-by-row scripts, OCMF translates unstructured or deeply nested data into a strict, strongly-typed **Kernel Graph** before writing output. The pipeline operates in distinct stages:

1. **Mapping Engine:** Consumes an Excel-based mapping workbook (`entities`, `fields`, `policies`) that defines how source fields map to the Kernel Graph, applying strict, closed-vocabulary transforms — no arbitrary Python `eval`. The supported transforms are:
   - `identity` — trimmed value, unchanged.
   - `parse_date` — build a typed `DateValue`, preserving uncertainty (see below).
   - `split` — split one field into a normalised multi-value field; `transform_args` sets the delimiter (default `;`), re-joined with `|`.
   - `lookup` — remap values via `transform_args` (`"M=Male;F=Female"`); unmatched values pass through unchanged.
2. **Adapters:** 
   - `PastPerfectAdapter`: Ingests flat CSV dumps, actively detecting and rejecting silent corruption (e.g., unexpected BOMs via strict encoding policies).
   - `AdlibXMLAdapter`: Streams large XML exports using `iterparse`, efficiently flattening grouped metadata, deduplicating `priref` attributes, and filtering multilingual tags.
3. **Hierarchy Engine:** Reconstructs archival hierarchies (e.g., Fonds -> Series -> Item) based on dotted reference codes. It detects orphaned records (children whose parent is absent from the export) and, according to policy, either aborts or synthesizes the missing intermediate parent nodes.
4. **Preflight Audit:** Scans the fully loaded graph in memory, enforcing uniqueness across identifiers, ensuring mandatory fields (like ISAD(G) titles) are present, and detecting structural cycles (e.g., via Depth-First Search).
5. **AtoM ISAD Writer:** Flattens the graph back into AtoM's `information_objects.csv` using a topological sort. Supported columns are validated against the AtoM 2.8 ISAD(G) CSV template vocabulary and emitted in template order. Event-based data (creators, dates) are explicitly constructed into parallel, pipe-delimited arrays (`eventActors`, `eventStartDates`, etc.) padded flawlessly with `NULL`.
6. **Audit Pack Generator:** Produces a `DATA_LOSS_REGISTER.md` audit register (unmapped source fields, mapped fields missing from the source, synthesized nodes, and interpretive transformations) for archivist review, plus a `LOAD_PLAYBOOK.md` with explicit Qubit CLI ingestion commands.

### What a record becomes internally

A single source row is normalized into a typed `description` entity with structured identifiers and values, plus directed edges to its parent and creator. For example, the PastPerfect row `PP001.01.01, "Diary 1", "Smith, John", 1921` becomes:

```json
{
  "entities": {
    "item_node_PP001_01_01": {
      "type": "description",
      "identifiers": [{ "value": "PP001.01.01", "kind": "local", "source_field": "ref_code" }],
      "properties": {
        "title": "Diary 1",
        "dates": { "expression": "1921", "begin": "1921", "end": "1921", "inferred": false }
      }
    }
  },
  "edges": [
    { "source_id": "item_node_PP001_01_01", "target_id": "creator_node_PP001_01_01", "relation": "created_by" },
    { "source_id": "item_node_PP001_01_01", "target_id": "item_node_PP001_01", "relation": "child_of" }
  ]
}
```

The full snapshot is emitted as `graph_snapshot.json` on every run.

## Strict Typing & Date Handling

OCMF operates on a strict `DateValue` schema. The `parse_date` transform evaluates inputs carefully:
- Standard point dates (`1921`) and ranges (`1920-1925`) are split into `begin` and `end` values.
- Non-standard expressions (ISO strings, circa dates, en-dashes) are safely retained in the `expression` field while omitting `begin` / `end` coordinates. This prevents malformed data from silently breaking AtoM's event date ingestion.

## Mapping Policies

The generated workbook includes conservative defaults:
- `hierarchy_source_field=ref_code` means only the reference-code identifier drives parent/child reconstruction.
- `missing_mapped_fields=warn` records mapped source fields that never appear in the export. Set it to `abort` for stricter client migrations where optional-field typos should halt the run.
- Unsupported AtoM target properties are rejected during workbook compilation rather than stored in the graph and silently omitted from CSV output.

The generated `LOAD_PLAYBOOK.md` follows AtoM 2.8 command-line guidance: validate with `php symfony csv:check-import --verbose` before importing with `php symfony csv:import`, and do not pass Symfony `--application`, `--env`, or `--connection` overrides.

## Installation

OCMF is configured as a native Python package.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## CLI Usage

The package installs the `ocmf` unified CLI tool natively into your environment.

### 1. Profile the Source (Phase 0)
Before mapping, inspect a raw export for encoding, delimiter, and per-column null rates:
```bash
ocmf profile --source input_data.csv          # prints JSON to stdout
ocmf profile --source export.dbf --outfile health_report.json
```
CSV and DBF are supported (DBF requires the optional `dbfread` dependency: `pip install ocmf[dbf]`).

### 2. Generate a Mapping Template
To start a new migration project, generate a blank mapping workbook:
```bash
ocmf template --outfile my_mapping.xlsx
```

### 3. Run the Migration Pipeline
Once your workbook is mapped against your source data (CSV or XML), execute the full pipeline:
```bash
ocmf migrate --engine my_mapping.xlsx --source input_data.csv --outdir ./output
```
This will ingest the data, evaluate hierarchies, run the pre-flight audits, and generate:
- `information_objects.csv` (AtoM ready)
- `graph_snapshot.json` (Internal typed memory graph)
- `DATA_LOSS_REGISTER.md` (Audit register: unmapped source fields, mapped fields missing from source, synthesized nodes, and interpretive transformations)
- `LOAD_PLAYBOOK.md` (AtoM server import instructions)

## Testing

```bash
pip install pytest
pytest tests
```

The test suite aggressively validates the failure paths, actively ensuring that cyclic hierarchies, missing encoding schemas, and duplicate identifiers immediately halt the pipeline.
