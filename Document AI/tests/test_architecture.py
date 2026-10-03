import pytest
from pathlib import Path

def test_architecture_wording():
    arch_file = Path(__file__).parent.parent / "ARCHITECTURE.md"
    content = arch_file.read_text(encoding="utf-8")

    assert "Phase 0" not in content
    assert "implementation on hold" not in content.lower()
    assert "EvidenceBundle" in content
    assert "artifact:" in content
    assert "normalized" in content.lower()
