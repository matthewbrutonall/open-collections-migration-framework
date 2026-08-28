import os
import csv
import json
import chardet
from collections import defaultdict
from typing import Dict, Any

class Phase0Profiler:
    """
    Ingests a PastPerfect CSV/DBF and outputs a health report:
    - Null rates
    - Delimiter candidates
    - Encoding guess
    """
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.report = {
            "file": os.path.basename(file_path),
            "size_bytes": os.path.getsize(file_path),
            "encoding_guess": None,
            "delimiter_guess": None,
            "row_count": 0,
            "null_rates": {}
        }
        
    def profile(self) -> Dict[str, Any]:
        ext = os.path.splitext(self.file_path)[1].lower()
        if ext == '.csv':
            self._profile_csv()
        elif ext == '.dbf':
            self._profile_dbf()
        else:
            raise ValueError(f"Unsupported file extension: {ext}")
            
        return self.report

    def _guess_encoding(self) -> str:
        with open(self.file_path, 'rb') as f:
            raw_data = f.read(100000) # Read first 100kb
        result = chardet.detect(raw_data)
        self.report['encoding_guess'] = result
        return result['encoding'] or 'utf-8'

    def _profile_csv(self):
        enc = self._guess_encoding()
        
        # Delimiter Guessing
        with open(self.file_path, 'r', encoding=enc, errors='replace') as f:
            sample = f.read(4096)
            try:
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample)
                self.report['delimiter_guess'] = dialect.delimiter
            except csv.Error:
                self.report['delimiter_guess'] = ','
                
        # Null rates calculation
        null_counts = defaultdict(int)
        total_rows = 0
        columns = []
        
        with open(self.file_path, 'r', encoding=enc, errors='replace') as f:
            delimiter = self.report['delimiter_guess']
            reader = csv.reader(f, delimiter=delimiter)
            try:
                columns = next(reader)
            except StopIteration:
                return
                
            for row in reader:
                total_rows += 1
                for i, val in enumerate(row):
                    if i < len(columns):
                        # Empty string or just whitespace
                        if not val or not val.strip():
                            null_counts[columns[i]] += 1
                            
        self.report['row_count'] = total_rows
        if total_rows > 0:
            for col in columns:
                self.report['null_rates'][col] = round((null_counts[col] / total_rows) * 100, 2)

    def _profile_dbf(self):
        try:
            from dbfread import DBF
        except ImportError:
            self.report['error'] = "dbfread package is required to profile DBF files. Install with 'pip install dbfread'."
            return
            
        dbf = DBF(self.file_path, load=False, char_decode_errors='replace')
        self.report['encoding_guess'] = {"encoding": dbf.encoding, "confidence": 1.0, "source": "DBF Header"}
        self.report['delimiter_guess'] = "N/A (DBF)"
        
        null_counts = defaultdict(int)
        total_rows = 0
        columns = dbf.field_names
        
        for record in dbf:
            total_rows += 1
            for col in columns:
                val = record.get(col)
                if val is None or str(val).strip() == "":
                    null_counts[col] += 1
                    
        self.report['row_count'] = total_rows
        if total_rows > 0:
            for col in columns:
                self.report['null_rates'][col] = round((null_counts[col] / total_rows) * 100, 2)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 profiler.py <path_to_csv_or_dbf>")
        sys.exit(1)
        
    profiler = Phase0Profiler(sys.argv[1])
    report = profiler.profile()
    print(json.dumps(report, indent=2))
