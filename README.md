# Open Collections Migration Framework (OCMF)

OCMF is a rigorous, graph-based data migration pipeline designed to extract archival data from legacy systems (like PastPerfect and Axiell Adlib), strictly enforce typing and hierarchy constraints, and emit cleanly formatted, validation-ready CSVs for AtoM (Access to Memory).

## Architecture

Unlike simple row-by-row scripts, OCMF translates unstructured or deeply nested data into a strict, strongly-typed **Kernel Graph** before writing output. The pipeline operates in distinct stages:

1. **Mapping Engine:** Consumes an Excel-based mapping workbook (`entities`, `fields`, `policies`) that defines how source fields map to the Kernel Graph, applying strict, closed-vocabulary transforms (e.g., `parse_date`, `identity`).
2. **Adapters:** 
   - `PastPerfectAdapter`: Ingests flat CSV dumps, actively detecting and rejecting silent corruption (e.g., unexpected BOMs via strict encoding policies).
   - `AdlibXMLAdapter`: Streams large XML exports using `iterparse`, efficiently flattening grouped metadata, deduplicating `priref` attributes, and filtering multilingual tags.
3. **Hierarchy Engine:** Reconstructs archival hierarchies (e.g., Fonds -> Series -> Item) based on dotted reference codes and synthesizes missing intermediate parent nodes (orphans) depending on strict policies.
4. **Preflight Audit:** Scans the fully loaded graph in memory, enforcing uniqueness across identifiers, ensuring mandatory fields (like ISAD(G) titles) are present, and detecting structural cycles (e.g., via Depth-First Search).
5. **AtoM ISAD Writer:** Flattens the graph back into AtoM's `information_objects.csv` using a topological sort. Event-based data (creators, dates) are explicitly constructed into parallel, pipe-delimited arrays (`eventActors`, `eventStartDates`, etc.) padded flawlessly with `NULL`.
6. **Audit Pack Generator:** Produces a `DATA_LOSS_REGISTER.md` for archivist review and a `LOAD_PLAYBOOK.md` with explicit Qubit CLI ingestion commands.

## Strict Typing & Date Handling

OCMF operates on a strict `DateValue` schema. The `parse_date` transform evaluates inputs carefully:
- Standard point dates (`1921`) and ranges (`1920-1925`) are split into `begin` and `end` values.
- Non-standard expressions (ISO strings, circa dates, en-dashes) are safely retained in the `expression` field while omitting `begin` / `end` coordinates. This prevents malformed data from silently breaking AtoM's event date ingestion.

## Development & Testing

OCMF is configured as a native Python package.

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -e .
pip install pytest

# Run the test suite
pytest tests
```

The test suite aggressively validates the failure paths, actively ensuring that cyclic hierarchies, missing encoding schemas, and duplicate identifiers immediately halt the pipeline.
