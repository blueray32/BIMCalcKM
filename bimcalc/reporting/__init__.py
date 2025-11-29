"""Reporting module for BIMCalc.

Generates deterministic cost reports using SCD2 as-of queries and EU formatting.
"""

from bimcalc.reporting.builder import ReportBuilder

__all__ = ["ReportBuilder", "generate_report"]
