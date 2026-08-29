import openpyxl

def create_template(filepath: str):
    wb = openpyxl.Workbook()
    
    ws_entities = wb.active
    ws_entities.title = "entities"
    ws_entities.append(["node_name", "source_table", "entity_type"])
    ws_entities.append(["item_node", "pastperfect_export.csv", "description"])
    ws_entities.append(["creator_node", "pastperfect_export.csv", "agent"])
    
    ws_fields = wb.create_sheet("fields")
    ws_fields.append(["node_name", "source_field", "target_property", "transform", "transform_args"])
    ws_fields.append(["item_node", "ref_code", "identifiers", "identity", None])
    ws_fields.append(["item_node", "title", "title", "identity", None])
    ws_fields.append(["item_node", "dates", "dates", "parse_date", None])
    ws_fields.append(["creator_node", "creator", "name", "identity", None])
    
    ws_policies = wb.create_sheet("policies")
    ws_policies.append(["policy_name", "policy_value"])
    ws_policies.append(["encoding", "utf-8"])
    ws_policies.append(["hierarchy", "identifier_dots"])
    ws_policies.append(["hierarchy_source_field", "ref_code"])
    ws_policies.append(["orphans", "synthesize_parents"])
    ws_policies.append(["missing_mapped_fields", "warn"])
    
    wb.save(filepath)

if __name__ == "__main__":
    import sys
    create_template(sys.argv[1] if len(sys.argv) > 1 else "mapping_workbook.xlsx")
