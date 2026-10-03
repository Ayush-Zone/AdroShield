"""Tests for the similarity calculation layer."""
import pytest
from src.similarity import compare_embeddings, calculate_cosine_distance

def test_cosine_distance_identical():
    emb = [1.0, 0.0, 0.0]
    dist = calculate_cosine_distance(emb, emb)
    assert dist == pytest.approx(0.0)

def test_cosine_distance_orthogonal():
    emb1 = [1.0, 0.0, 0.0]
    emb2 = [0.0, 1.0, 0.0]
    dist = calculate_cosine_distance(emb1, emb2)
    assert dist == pytest.approx(1.0)

def test_compare_embeddings_match():
    emb1 = [1.0, 1.0, 1.0]
    emb2 = [0.9, 1.0, 1.1]
    res = compare_embeddings(emb1, emb2, threshold=0.1)
    assert res.status == "ok"
    # Should be close, check if is_match evaluates correctly
    assert res.distance < 0.1
    assert res.is_match is True

def test_compare_embeddings_mismatch():
    emb1 = [1.0, 0.0, 0.0]
    emb2 = [0.0, 1.0, 0.0]
    res = compare_embeddings(emb1, emb2, threshold=0.4)
    assert res.status == "ok"
    assert res.is_match is False

def test_compare_embeddings_dimension_error():
    res = compare_embeddings([1.0], [1.0, 2.0])
    assert res.status == "error"
    assert res.indicator == "DIMENSION_MISMATCH"

def test_compare_embeddings_zero_vector():
    res = compare_embeddings([0.0], [0.0])
    assert res.status == "error"
    assert res.indicator == "CALCULATION_ERROR"
