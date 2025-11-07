"""Reporting module for BIMCalc.

Generates deterministic cost reports using SCD2 as-of queries and EU formatting.
"""

from bimcalc.reporting.builder import ReportBuilder, generate_report

__all__ = ["ReportBuilder", "generate_report"]
