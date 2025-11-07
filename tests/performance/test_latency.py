"""Performance tests for matching latency.

Tests that p95 latency < 0.5s per item.
"""

from __future__ import annotations

import pytest


class TestMatchingLatency:
    """Test end-to-end matching latency."""

    @pytest.mark.skip(reason="Requires full matching pipeline with database")
    def test_p95_latency_under_500ms(self):
        """Test p95 matching latency < 0.5s per item.

        PRP-001 Requirement:
        - Latency: p95 < 0.5s/item on benchmark (N=500 × M=5000)

        Implementation:
        1. Load 500 test items
        2. Load 5000 price catalog
        3. For each item:
           a. Start timer
           b. Run full pipeline: classify → canonical key → lookup → fuzzy → flags
           c. Record elapsed time
        4. Calculate p50, p95, p99 percentiles
        5. Assert: p95 < 0.5s

        Success Criteria:
        - p50 < 0.2s
        - p95 < 0.5s
        - p99 < 1.0s
        """
        pass

    @pytest.mark.skip(reason="Requires database implementation")
    def test_canonical_key_lookup_latency(self):
        """Test canonical key lookup is O(1).

        Measures:
        - Mapping memory lookup time
        - Hash table performance

        Success Criteria:
        - Average lookup < 1ms
        - p99 lookup < 5ms
        """
        pass

    @pytest.mark.skip(reason="Requires fuzzy matcher implementation")
    def test_fuzzy_matching_latency(self):
        """Test fuzzy matching within class is fast.

        Measures:
        - Fuzzy ranking time for filtered candidates
        - RapidFuzz performance

        Success Criteria:
        - Average fuzzy rank < 0.1s for 20-50 candidates
        - p95 < 0.2s
        """
        pass

    @pytest.mark.skip(reason="Requires flags engine integration")
    def test_flags_evaluation_latency(self):
        """Test flag evaluation is negligible.

        Measures:
        - Time to evaluate all flags for one item-price pair

        Success Criteria:
        - Average < 1ms per evaluation
        - p99 < 5ms
        """
        pass


class TestScalability:
    """Test scalability with larger datasets."""

    @pytest.mark.skip(reason="Requires large test dataset")
    def test_latency_scales_linearly_with_catalog_size(self):
        """Test latency scales linearly with price catalog size.

        Validates:
        - Classification blocking prevents O(N) explosion
        - Latency grows slowly as catalog expands

        Test with catalogs:
        - 1000 items
        - 5000 items
        - 10000 items
        - 20000 items

        Success Criteria:
        - Latency increases < 2× when catalog size doubles
        """
        pass

    @pytest.mark.skip(reason="Requires batch processing implementation")
    def test_batch_matching_throughput(self):
        """Test batch matching throughput.

        Measures:
        - Items per second for batch processing
        - Parallelization effectiveness

        Success Criteria:
        - Throughput ≥ 10 items/second (single-threaded)
        - Throughput ≥ 50 items/second (parallel)
        """
        pass
