# Migration Load Playbook

## 1. Review Data Loss
Review the Data-Loss Register.

## 2. Ingest Commands
Transfer the generated `information_objects.csv` to the AtoM server. From the AtoM root directory, run the following CLI command:

```bash
php symfony csv:import --application=qubit --env=prod information_objects.csv
```

## 3. Post-Ingest Verification
- Rebuild the search index: `php symfony search:populate`
