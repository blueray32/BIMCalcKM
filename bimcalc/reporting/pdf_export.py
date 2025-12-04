"""PDF export functionality for BIMCalc executive reports.

Generates professional PDF reports using ReportLab, including:
- Executive Summary
- Cost Breakdown
- Risk Analysis
"""

from __future__ import annotations

from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from bimcalc.reporting.dashboard_metrics import compute_dashboard_metrics
from bimcalc.db.models import ProjectModel

# Styles
styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    "CustomTitle",
    parent=styles["Heading1"],
    fontSize=24,
    spaceAfter=30,
    textColor=colors.HexColor("#2d3748"),
)
subtitle_style = ParagraphStyle(
    "CustomSubtitle",
    parent=styles["Heading2"],
    fontSize=18,
    spaceAfter=20,
    textColor=colors.HexColor("#4a5568"),
)
normal_style = ParagraphStyle(
    "CustomNormal",
    parent=styles["Normal"],
    fontSize=10,
    leading=14,
    textColor=colors.HexColor("#2d3748"),
)


async def generate_project_pdf_report(
    session: AsyncSession, org_id: str, project_id: str
) -> BytesIO:
    """Generate a comprehensive PDF report for the project."""

    # Fetch data
    metrics = await compute_dashboard_metrics(session, org_id, project_id)
    project_query = select(ProjectModel).where(
        ProjectModel.org_id == org_id, ProjectModel.project_id == project_id
    )
    result = await session.execute(project_query)
    project = result.scalar_one()

    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    story = []

    # --- Title Page ---
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph("Project Cost Report", title_style))
    story.append(
        Paragraph(f"{project.display_name or project.project_id}", subtitle_style)
    )
    story.append(Spacer(1, 0.5 * inch))
    story.append(
        Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", normal_style
        )
    )
    story.append(Paragraph(f"Organization: {org_id}", normal_style))
    story.append(PageBreak())

    # --- Executive Summary ---
    story.append(Paragraph("Executive Summary", title_style))

    # Key Metrics Table
    data = [
        ["Metric", "Value"],
        ["Total Cost (Net)", f"{metrics.currency} {metrics.total_cost_net:,.2f}"],
        ["Total Cost (Gross)", f"{metrics.currency} {metrics.total_cost_gross:,.2f}"],
        [
            "Matched Items",
            f"{metrics.matched_items} / {metrics.total_items} ({metrics.match_percentage:.1f}%)",
        ],
        ["High Risk Cost", f"{metrics.currency} {metrics.high_risk_cost:,.2f}"],
    ]

    t = Table(data, colWidths=[3 * inch, 3 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#edf2f7")),
                ("TEXTCOLOR", (0, 0), (1, 0), colors.HexColor("#2d3748")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                ("PADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 0.5 * inch))

    # --- Cost Breakdown ---
    story.append(Paragraph("Cost Breakdown by Category", subtitle_style))

    # Fetch category breakdown
    category_query = text("""
        SELECT 
            COALESCE(i.category, 'Uncategorized') as category,
            SUM(i.quantity * pi.unit_price) as total_cost
        FROM items i
        JOIN match_results mr ON mr.item_id = i.id
        JOIN price_items pi ON pi.id = mr.price_item_id
        WHERE i.org_id = :org_id 
          AND i.project_id = :project_id
          AND mr.decision IN ('auto-accepted', 'accepted', 'pending-review')
          AND mr.timestamp = (
              SELECT MAX(timestamp) 
              FROM match_results 
              WHERE item_id = i.id
          )
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 10
    """)

    cat_result = await session.execute(
        category_query, {"org_id": org_id, "project_id": project_id}
    )
    categories = cat_result.fetchall()

    if categories:
        # Prepare data for chart and table
        cat_data = [["Category", "Cost"]]
        chart_data = []
        chart_labels = []

        for cat in categories:
            cost = float(cat.total_cost) if cat.total_cost else 0
            cat_data.append([cat.category, f"{metrics.currency} {cost:,.2f}"])
            if cost > 0:
                chart_data.append(cost)
                chart_labels.append(cat.category[:15])  # Truncate for chart

        # Table
        t_cat = Table(cat_data, colWidths=[3 * inch, 3 * inch])
        t_cat.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#edf2f7")),
                    ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                    ("PADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(t_cat)
        story.append(Spacer(1, 0.5 * inch))

        # Pie Chart
        if chart_data:
            d = Drawing(400, 200)
            pc = Pie()
            pc.x = 100
            pc.y = 0
            pc.width = 150
            pc.height = 150
            pc.data = chart_data
            pc.labels = chart_labels
            pc.slices.strokeWidth = 0.5
            d.add(pc)
            story.append(d)

    else:
        story.append(Paragraph("No cost data available yet.", normal_style))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer
