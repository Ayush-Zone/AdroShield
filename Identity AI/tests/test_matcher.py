"""Tests for the identity matcher orchestrator."""
import pytest
from src.matcher import IdentityMatcher, MatchResult
from src.embedder import BaseFaceEmbedder

class MockEmbedder(BaseFaceEmbedder):
    def get_embedding_raw(self, image, bounding_box):
        return [0.5, 0.5, 0.5]

def test_matcher_missing_files(tmp_path):
    embedder = MockEmbedder()
    matcher = IdentityMatcher(embedder=embedder)
    doc_path = str(tmp_path / "nonexistent.jpg")
    selfie_path = str(tmp_path / "also_missing.jpg")
    
    result = matcher.match_identity(doc_path, selfie_path)
    assert result.status == "error"
    assert result.indicator == "VALIDATION_FAILED"
