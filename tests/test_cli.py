import os
import sys
import subprocess
import pytest

def test_cli_template(tmp_path):
    out_file = tmp_path / "my_template.xlsx"
    res = subprocess.run([sys.executable, "-m", "ocmf.cli", "template", "--outfile", str(out_file)], capture_output=True, text=True)
    assert res.returncode == 0
    assert "successfully generated" in res.stdout
    assert os.path.exists(out_file)

def test_cli_migrate(tmp_path):
    engine = "tests/golden/input_mapping.xlsx"
    source = "tests/golden/input_data.csv"
    out_dir = tmp_path / "output"
    
    res = subprocess.run(
        [sys.executable, "-m", "ocmf.cli", "migrate", "--engine", engine, "--source", source, "--outdir", str(out_dir)], 
        capture_output=True, text=True
    )
    
    assert res.returncode == 0
    assert "Audit passed" in res.stdout
    assert "Migration complete" in res.stdout
    
    # Assert artifacts are emitted
    assert os.path.exists(out_dir / "information_objects.csv")
    assert os.path.exists(out_dir / "DATA_LOSS_REGISTER.md")
    assert os.path.exists(out_dir / "LOAD_PLAYBOOK.md")
    assert os.path.exists(out_dir / "graph_snapshot.json")
