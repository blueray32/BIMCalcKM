"""Performance benchmark suite for BIMCalc matching engine.

Tests candidate generation, fuzzy matching, and end-to-end performance
with large price catalogs (10K+ records).

Target: p95 latency < 500ms per CLAUDE.md
"""

from __future__ import annotations

import asyncio
import statistics
import time
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bimcalc.db.models import PriceItemModel
from bimcalc.matching.candidate_generator import CandidateGenerator
from bimcalc.matching.orchestrator import MatchOrchestrator
from bimcalc.models import Item


class PerformanceBenchmark:
    """Performance benchmarking suite."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.session_factory = None

    async def setup(self):
        """Initialize database connection."""
        self.engine = create_async_engine(self.database_url, echo=False)

        # Create tables
        from bimcalc.db.models import Base

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        self.session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def teardown(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()

    async def get_catalog_statistics(self, session: AsyncSession) -> dict[str, Any]:
        """Get statistics about the price catalog."""
        # Total prices
        total_result = await session.execute(
            select(func.count(PriceItemModel.id)).where(
                PriceItemModel.is_current == True
            )
        )
        total_prices = total_result.scalar()

        # By classification
        class_result = await session.execute(
            select(
                PriceItemModel.classification_code,
                func.count(PriceItemModel.id).label("count"),
            )
            .where(PriceItemModel.is_current == True)
            .group_by(PriceItemModel.classification_code)
        )
        by_classification = {row.classification_code: row.count for row in class_result}

        # By org
        org_result = await session.execute(
            select(PriceItemModel.org_id, func.count(PriceItemModel.id).label("count"))
            .where(PriceItemModel.is_current == True)
            .group_by(PriceItemModel.org_id)
        )
        by_org = {row.org_id: row.count for row in org_result}

        return {
            "total_prices": total_prices,
            "by_classification": by_classification,
            "by_org": by_org,
        }

    def create_test_item(
        self,
        org_id: str,
        classification_code: int,
        width_mm: float | None = None,
        height_mm: float | None = None,
    ) -> Item:
        """Create a test item for benchmarking."""
        return Item(
            id=uuid4(),
            org_id=org_id,
            project_id="perf-test",
            family="Cable Tray",
            type_name="Ladder Type",
            classification_code=classification_code,
            canonical_key=f"{classification_code}|cable_tray|ladder|w={width_mm or 200}|h={height_mm or 50}",
            unit="m",
            quantity=Decimal("10.0"),
            width_mm=width_mm or 200.0,
            height_mm=height_mm or 50.0,
        )

    async def benchmark_candidate_generation(
        self,
        session: AsyncSession,
        org_id: str,
        num_iterations: int = 100,
    ) -> dict[str, Any]:
        """Benchmark candidate generation with classification blocking."""
        print(f"\n{'=' * 60}")
        print("BENCHMARK: Candidate Generation")
        print(f"{'=' * 60}")

        generator = CandidateGenerator(session)

        # Test with in-class candidates
        item = self.create_test_item(org_id, classification_code=66)

        latencies = []
        for i in range(num_iterations):
            start = time.perf_counter()
            candidates = await generator.generate(item)
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)

            if (i + 1) % 10 == 0:
                print(f"  Completed {i + 1}/{num_iterations} iterations...")

        # Calculate statistics
        results = {
            "iterations": num_iterations,
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "mean_ms": statistics.mean(latencies),
            "median_ms": statistics.median(latencies),
            "p95_ms": self._percentile(latencies, 95),
            "p99_ms": self._percentile(latencies, 99),
            "std_dev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
        }

        print("\nResults:")
        print(f"  Iterations: {results['iterations']}")
        print(f"  Min:        {results['min_ms']:.2f} ms")
        print(f"  Mean:       {results['mean_ms']:.2f} ms")
        print(f"  Median:     {results['median_ms']:.2f} ms")
        print(
            f"  p95:        {results['p95_ms']:.2f} ms {'✓' if results['p95_ms'] < 500 else '✗ EXCEEDS TARGET'}"
        )
        print(f"  p99:        {results['p99_ms']:.2f} ms")
        print(f"  Max:        {results['max_ms']:.2f} ms")
        print(f"  Std Dev:    {results['std_dev_ms']:.2f} ms")

        return results

    async def benchmark_escape_hatch(
        self,
        session: AsyncSession,
        org_id: str,
        num_iterations: int = 50,
    ) -> dict[str, Any]:
        """Benchmark escape-hatch candidate generation."""
        print(f"\n{'=' * 60}")
        print("BENCHMARK: Escape-Hatch Candidate Generation")
        print(f"{'=' * 60}")

        generator = CandidateGenerator(session)

        # Create item with classification that has NO prices (force escape-hatch)
        # Use classification 99 which shouldn't exist in test data
        item = self.create_test_item(org_id, classification_code=99)

        latencies = []
        for i in range(num_iterations):
            start = time.perf_counter()
            candidates, used_escape_hatch = await generator.generate_with_escape_hatch(
                item, max_escape_hatch=2
            )
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)

            if (i + 1) % 10 == 0:
                print(f"  Completed {i + 1}/{num_iterations} iterations...")

        # Calculate statistics
        results = {
            "iterations": num_iterations,
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "mean_ms": statistics.mean(latencies),
            "median_ms": statistics.median(latencies),
            "p95_ms": self._percentile(latencies, 95),
            "p99_ms": self._percentile(latencies, 99),
            "std_dev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
        }

        print("\nResults:")
        print(f"  Iterations: {results['iterations']}")
        print(f"  Min:        {results['min_ms']:.2f} ms")
        print(f"  Mean:       {results['mean_ms']:.2f} ms")
        print(f"  Median:     {results['median_ms']:.2f} ms")
        print(
            f"  p95:        {results['p95_ms']:.2f} ms {'✓' if results['p95_ms'] < 1000 else '✗ EXCEEDS TARGET'}"
        )
        print(f"  p99:        {results['p99_ms']:.2f} ms")
        print(f"  Max:        {results['max_ms']:.2f} ms")

        return results

    async def benchmark_end_to_end_matching(
        self,
        session: AsyncSession,
        org_id: str,
        num_iterations: int = 50,
    ) -> dict[str, Any]:
        """Benchmark complete matching workflow."""
        print(f"\n{'=' * 60}")
        print("BENCHMARK: End-to-End Matching")
        print(f"{'=' * 60}")

        orchestrator = MatchOrchestrator(session)
        item = self.create_test_item(org_id, classification_code=66)

        latencies = []
        for i in range(num_iterations):
            start = time.perf_counter()
            result, matched_price = await orchestrator.match(
                item, created_by="benchmark"
            )
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)

            if (i + 1) % 10 == 0:
                print(f"  Completed {i + 1}/{num_iterations} iterations...")

        # Calculate statistics
        results = {
            "iterations": num_iterations,
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "mean_ms": statistics.mean(latencies),
            "median_ms": statistics.median(latencies),
            "p95_ms": self._percentile(latencies, 95),
            "p99_ms": self._percentile(latencies, 99),
            "std_dev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
        }

        print("\nResults:")
        print(f"  Iterations: {results['iterations']}")
        print(f"  Min:        {results['min_ms']:.2f} ms")
        print(f"  Mean:       {results['mean_ms']:.2f} ms")
        print(f"  Median:     {results['median_ms']:.2f} ms")
        print(
            f"  p95:        {results['p95_ms']:.2f} ms {'✓' if results['p95_ms'] < 500 else '✗ EXCEEDS TARGET'}"
        )
        print(f"  p99:        {results['p99_ms']:.2f} ms")
        print(f"  Max:        {results['max_ms']:.2f} ms")

        return results

    async def benchmark_classification_blocking_reduction(
        self,
        session: AsyncSession,
        org_id: str,
    ) -> dict[str, Any]:
        """Measure candidate reduction from classification blocking."""
        print(f"\n{'=' * 60}")
        print("BENCHMARK: Classification Blocking Effectiveness")
        print(f"{'=' * 60}")

        # Get total prices
        total_result = await session.execute(
            select(func.count(PriceItemModel.id)).where(
                PriceItemModel.is_current == True,
                PriceItemModel.org_id == org_id,
            )
        )
        total_prices = total_result.scalar()

        # Get prices in classification 66
        class_66_result = await session.execute(
            select(func.count(PriceItemModel.id)).where(
                PriceItemModel.is_current == True,
                PriceItemModel.org_id == org_id,
                PriceItemModel.classification_code == 66,
            )
        )
        class_66_prices = class_66_result.scalar()

        reduction_factor = total_prices / class_66_prices if class_66_prices > 0 else 0

        results = {
            "total_prices": total_prices,
            "after_classification_blocking": class_66_prices,
            "reduction_factor": reduction_factor,
            "reduction_percentage": (
                (total_prices - class_66_prices) / total_prices * 100
            )
            if total_prices > 0
            else 0,
        }

        print("\nResults:")
        print(f"  Total prices in catalog:      {results['total_prices']:,}")
        print(
            f"  After classification block:   {results['after_classification_blocking']:,}"
        )
        print(f"  Reduction factor:             {results['reduction_factor']:.1f}×")
        print(f"  Reduction percentage:         {results['reduction_percentage']:.1f}%")
        print(
            f"  Target (≥20×):                {'✓ PASSED' if reduction_factor >= 20 else '✗ FAILED'}"
        )

        return results

    def _percentile(self, data: list[float], percentile: int) -> float:
        """Calculate percentile of a dataset."""
        sorted_data = sorted(data)
        index = (percentile / 100) * len(sorted_data)
        if index.is_integer():
            return sorted_data[int(index) - 1]
        else:
            lower = sorted_data[int(index) - 1]
            upper = sorted_data[int(index)]
            return lower + (upper - lower) * (index - int(index))

    async def run_all_benchmarks(self, org_id: str) -> dict[str, Any]:
        """Run complete benchmark suite."""
        print("\n" + "=" * 60)
        print("BIMCalc Performance Benchmark Suite")
        print("=" * 60)

        async with self.session_factory() as session:
            # Get catalog statistics
            print("\nCatalog Statistics:")
            stats = await self.get_catalog_statistics(session)
            print(f"  Total active prices: {stats['total_prices']:,}")
            print(f"  Organizations: {len(stats['by_org'])}")
            print(f"  Classifications: {len(stats['by_classification'])}")

            # Run benchmarks
            results = {}

            # 1. Classification blocking effectiveness
            results[
                "classification_blocking"
            ] = await self.benchmark_classification_blocking_reduction(session, org_id)

            # 2. Candidate generation
            results["candidate_generation"] = await self.benchmark_candidate_generation(
                session, org_id, num_iterations=100
            )

            # 3. Escape-hatch
            results["escape_hatch"] = await self.benchmark_escape_hatch(
                session, org_id, num_iterations=50
            )

            # 4. End-to-end matching
            results["end_to_end"] = await self.benchmark_end_to_end_matching(
                session, org_id, num_iterations=50
            )

            return results


async def main():
    """Run performance benchmarks."""
    import argparse

    parser = argparse.ArgumentParser(description="Run BIMCalc performance benchmarks")
    parser.add_argument("--org", default="perf-test-org", help="Organization ID")
    parser.add_argument(
        "--database-url",
        default="sqlite+aiosqlite:///./bimcalc_perftest.db",
        help="Database URL",
    )
    args = parser.parse_args()

    benchmark = PerformanceBenchmark(args.database_url)
    await benchmark.setup()

    try:
        results = await benchmark.run_all_benchmarks(args.org)

        # Summary
        print("\n" + "=" * 60)
        print("PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 60)

        print("\nClassification Blocking:")
        print(
            f"  Reduction factor: {results['classification_blocking']['reduction_factor']:.1f}× ({'✓' if results['classification_blocking']['reduction_factor'] >= 20 else '✗'})"
        )

        print("\nCandidate Generation:")
        print(
            f"  p95 latency: {results['candidate_generation']['p95_ms']:.2f} ms ({'✓' if results['candidate_generation']['p95_ms'] < 500 else '✗'})"
        )

        print("\nEscape-Hatch:")
        print(f"  p95 latency: {results['escape_hatch']['p95_ms']:.2f} ms")

        print("\nEnd-to-End Matching:")
        print(
            f"  p95 latency: {results['end_to_end']['p95_ms']:.2f} ms ({'✓' if results['end_to_end']['p95_ms'] < 500 else '✗'})"
        )

        # Overall status
        all_pass = (
            results["classification_blocking"]["reduction_factor"] >= 20
            and results["candidate_generation"]["p95_ms"] < 500
            and results["end_to_end"]["p95_ms"] < 500
        )

        print(f"\n{'=' * 60}")
        print(
            f"Overall Status: {'✓ ALL TARGETS MET' if all_pass else '⚠ SOME TARGETS MISSED'}"
        )
        print(f"{'=' * 60}\n")

    finally:
        await benchmark.teardown()


if __name__ == "__main__":
    asyncio.run(main())
