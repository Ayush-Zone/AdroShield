import pytest
import os
from pydantic import ValidationError
from datetime import datetime, timezone
from pathlib import Path
from forgerylens.contracts.evidence import EvidenceRecord, Provenance, EvidenceStatus, EvidenceLocation
from forgerylens.utils.hash import calculate_file_sha256
from forgerylens.utils.evidence_log import EvidenceLog

def test_hash_stable():
    test_file = Path("test_hash.txt")
    test_file.write_text("hello world")
    
    hash1 = calculate_file_sha256(test_file)
    hash2 = calculate_file_sha256(test_file)
    
    assert hash1 == hash2
    
    test_file.write_text("hello world2")
    hash3 = calculate_file_sha256(test_file)
    assert hash1 != hash3
    
    test_file.unlink()

def test_evidence_record_serialization_round_trip():
    prov = Provenance(
        source_file_sha256="abcd",
        tool_name="test_tool",
        tool_version="1.0",
        parameters={"threshold": 0.5},
        timestamp=datetime.now(timezone.utc)
    )
    
    record = EvidenceRecord(
        id="test_1",
        type="test_extraction",
        observation="text data",
        location=EvidenceLocation(page_number=1, x=0.1, y=0.1, width=0.5, height=0.5),
        method="ocr",
        confidence=0.95,
        calibrated_confidence=True,
        status=EvidenceStatus.OK,
        limitations="None",
        raw_ref="s3://bucket/obj",
        provenance=prov
    )
    
    json_str = record.model_dump_json()
    deserialized = EvidenceRecord.model_validate_json(json_str)
    
    assert deserialized.id == record.id
    assert deserialized.observation == record.observation
    assert deserialized.provenance.source_file_sha256 == prov.source_file_sha256
    assert deserialized.location.x == record.location.x

def test_invalid_records_rejected():
    prov = Provenance(
        source_file_sha256="abcd",
        tool_name="test_tool",
        tool_version="1.0"
    )
    
    # Missing required fields
    with pytest.raises(ValidationError):
        EvidenceRecord(
            id="test_1",
            type="test",
            observation="obs",
            status=EvidenceStatus.OK
            # missing method, provenance, etc.
        )
        
    # Invalid confidence
    with pytest.raises(ValidationError):
        EvidenceRecord(
            id="test_1",
            type="test",
            observation="obs",
            method="test",
            confidence=1.5, # Out of range
            status=EvidenceStatus.OK,
            provenance=prov
        )

def test_evidence_log(tmp_path):
    log_path = tmp_path / "evidence.log"
    log = EvidenceLog(log_path)
    
    prov = Provenance(
        source_file_sha256="abcd",
        tool_name="test",
        tool_version="1.0"
    )
    record1 = EvidenceRecord(
        id="1", type="t", observation="o", method="m", status=EvidenceStatus.OK, provenance=prov
    )
    record2 = EvidenceRecord(
        id="2", type="t", observation="o2", method="m", status=EvidenceStatus.OK, provenance=prov
    )
    
    log.append(record1)
    
    records = log.read_all()
    assert len(records) == 1
    assert records[0].id == "1"
    
    log.append(record2)
    records = log.read_all()
    assert len(records) == 2
    assert records[0].id == "1"
    assert records[1].id == "2"

def test_null_accepted_where_unknown():
    prov = Provenance(
        source_file_sha256="abcd",
        tool_name="test",
        tool_version="1.0"
    )
    record = EvidenceRecord(
        id="1", type="t", observation="o", method="m", status=EvidenceStatus.OK, provenance=prov,
        confidence=None, location=None, raw_ref=None
    )
    assert record.confidence is None
