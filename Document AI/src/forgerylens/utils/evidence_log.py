from pathlib import Path
from forgerylens.contracts.evidence import EvidenceRecord

class EvidenceLog:
    """A simple append-only file-based log for evidence records."""
    
    def __init__(self, filepath: str | Path):
        self.filepath = Path(filepath)
        
    def append(self, record: EvidenceRecord) -> None:
        """Append a JSON-serialized evidence record to the log."""
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")
            
    def read_all(self) -> list[EvidenceRecord]:
        """Read all records from the log."""
        if not self.filepath.exists():
            return []
            
        records = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(EvidenceRecord.model_validate_json(line))
        return records
