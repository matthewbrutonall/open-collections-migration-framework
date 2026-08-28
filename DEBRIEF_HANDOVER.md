# DEBRIEF & HANDOVER: Open Collections Migration Framework (OCMF)

**To the Next Agent:** You are picking up where a highly iterative, architecturally rigorous session left off. This document contains the context, the pivot, and the exact architectural blueprint approved by senior LLMs (Codex and Grok) for building a professional GLAM (Galleries, Libraries, Archives, Museums) ETL migration toolkit.

## 1. How We Got Here
We started by writing a simple Python CLI tool (`pastperfect-to-atom`). Through rigorous auditing by Grok and Codex, we realized that bespoke migration scripts are a trap. The goal is a professional, open-source ETL Toolkit designed for consulting engagements.

## 2. The Target Architecture (The Grok/Codex Blueprint)

The core insight is that **the internal representation cannot be a flat dictionary.** Flattening data on ingest destroys structural integrity. The engine must use a **Typed Entity-Relation Graph**. 

### A. The Kernel Graph (v0.1)
The intermediate representation is a closed-vocabulary graph of typed entities and directed edges.

**Entities (6 types):**
1. `description` (Intellectual unit: Fonds, Series, Item)
2. `agent` (Person, family, corporate body)
3. `repository` (Holding institution)
4. `term` (Taxonomy concept)
5. `accession` (Acquisition transaction)
6. `instantiation` (Digital file or URI)

**Value Objects:**
*   `Identifier`: value, kind, source_field.
*   `DateValue`: expression, begin, end, schema, certainty, inferred. (Preserve uncertainty, never coerce to ISO blindly).

**Named Relations (Directed Edges):**
`child_of`, `held_by`, `created_by`, `accumulated_by`, `subject_agent`, `acquired_from`, `accessioned_as`, `has_subject`, `has_place`, `has_genre`, `has_object_name`, `has_instantiation`.

### B. The Mapping Workbook
Archivists map in Excel, not JSON. The framework ingests a workbook with three sheets:
1.  **entities:** Declares which source tables produce which nodes.
2.  **fields:** Maps `source_field` -> `target` via a closed list of transforms (`identity`, `split`, `parse_date`, `lookup`, `concat`). *No arbitrary Python eval.*
3.  **policies:** Defines `encoding` (explicit, no silent fallback), `hierarchy` (`identifier_dots`, `collection_group`, `flat_under_root`), `orphans` (`abort`, `synthesize_parents`), `root_level`, `item_level`, etc.

### C. The Target Profiles
The core graph is domain-agnostic. To emit data, it applies a domain profile (e.g., `ISAD`) which attaches properties like `extent_and_medium` or `scope_and_content` to the `description` entities. The target writer (AtoM CSV) then flattens the graph into the required format.

## 3. Your Mission: Ruthless Phase 1 Scope

You are to build **one vertical slice**: PastPerfect → ISAD(G) AtoM.
*Do not build Minisis, Heratio, EAD, or ISAAR/Actors CSVs yet.*

### The Build Order (Do not skip):
1.  **Kernel dataclasses:** Build the typed Graph and Entity classes. Output a JSON snapshot of a mocked graph (no adapters yet).
2.  **Phase 0 Profiler:** Write a tool that ingests a PastPerfect CSV/DBF and outputs a health report (null rates, delimiter candidates, encoding guess).
3.  **Workbook Compiler:** Read the `.xlsx` mapping workbook and compile it into an internal mapping engine.
4.  **PastPerfect Adapter:** Read the dump and generate the Graph entities/edges (no hierarchy yet).
5.  **Hierarchy Engine & Pre-flight:** Apply the hierarchy policies and run the fatal-by-default pre-flight audit (unique IDs, no cycles, mandatory fields).
6.  **AtoM ISAD Writer:** Emit the `information_objects.csv` ensuring parents are sorted before children.
7.  **Audit Pack:** Generate the Data-Loss Register (unmapped fields, synthesized nodes) and the Markdown Load Playbook for the archivist.
8.  **Pytest:** Test synthetic PastPerfect CSVs against golden graph JSONs and golden AtoM CSVs.

**Definition of Done:** 
A declared-encoding PastPerfect dump + filled mapping workbook produces a Profiler Report, Graph Snapshot, AtoM ISAD CSV, Data-Loss Register, and Load Playbook, and refuses to emit if the pre-flight fails.

Proceed strictly with **Step 1: Kernel Dataclasses**.

## 4. Note on Axiell Adlib (Phase 2 Scouting)
We just completed a quick "scouting mission" by writing a standalone `adlib-to-atom` script (located in `../adlib-to-atom/`). 
*   **Finding:** Axiell Adlib exports highly structured XML (`AdlibXML`) that is extremely easy to parse using Python's `xml.etree.ElementTree.iterparse()`.
*   **Critical Gotchas (from Grok's Review):** 
    1. **Grouped XML:** Adlib exports often use "Grouped XML" (tags nested under group wrappers like `<production><date><start>`). You must deeply traverse the tree using `.iter()`, not just check direct children.
    2. **Attributes:** Identifiers like `priref` are often *attributes* on the `<record>` node (e.g., `priref="123"`), not just child elements. Deduplicate them carefully if they appear as both.
    3. **Parallel Arrays:** When extracting multiple actors or dates, they MUST be perfectly padded with literal `"NULL"` strings to satisfy AtoM's strict event import rules.
    4. **Multilingual Tags:** For WebAPI exports, you must explicitly filter `<value lang="en">` tags to match the target culture, falling back to the first translation if missing.
*   **Strategy:** Do NOT integrate Adlib yet. Stick to the Ruthless Phase 1 Scope (PastPerfect). Once Phase 1 is done, building the `AdlibXMLAdapter` for Phase 2 will be trivial because you can just reference the logic we already perfected in the scouting script.
