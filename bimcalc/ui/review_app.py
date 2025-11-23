"""Textual-based review UI for BIMCalc."""

from __future__ import annotations

import asyncio
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Select,
    Static,
)

from bimcalc.config import get_config
from bimcalc.db.connection import get_session
from bimcalc.review import approve_review_record, fetch_pending_reviews
from bimcalc.review.models import ReviewRecord


class ReviewUIApp(App[None]):
    """Interactive review UI built with Textual."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #toolbar {
        padding: 0 1;
        height: auto;
    }

    #content {
        height: 1fr;
    }

    #review-table {
        width: 2fr;
    }

    #detail-panel {
        width: 1fr;
        border: solid $panel 1;
        padding: 1;
    }

    #annotation {
        margin-top: 1;
    }

    #status {
        margin-top: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("a", "accept", "Accept"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, org_id: str, project_id: str, reviewer: str) -> None:
        super().__init__()
        self.org_id = org_id
        self.project_id = project_id
        self.reviewer = reviewer
        self.records: list[ReviewRecord] = []
        self.selected_index: int | None = None
        self.flag_filter: str | None = None
        self.loading = reactive(False)
        self.record_index: dict[str, int] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="toolbar"):
            yield Static(f"Org: {self.org_id} · Project: {self.project_id}")
            yield Select(
                id="flag-filter",
                prompt="Filter by flag",
                options=self._flag_options(),
                value="all",
            )
            yield Button("Refresh", id="refresh-button", variant="primary")

        with Horizontal(id="content"):
            yield DataTable(id="review-table", cursor_type="row")
            with Vertical(id="detail-panel"):
                yield Static("Select an item to inspect details", id="details")
                yield Input(
                    placeholder="Annotation (required for Advisory flags)",
                    id="annotation",
                )
                yield Button("Accept Match", id="accept-button", variant="success")
                yield Static("Ready", id="status")

        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]
        table = self.query_one(DataTable)
        table.zebra_stripes = True
        table.cursor_type = "row"
        table.add_columns("Item", "Confidence", "Flags", "Updated", "Reason")
        await self.load_records()

    async def action_refresh(self) -> None:
        await self.load_records()

    async def action_accept(self) -> None:
        record = self._current_record
        if not record:
            self._set_status("Select an item first", error=True)
            return

        if record.has_critical_flags:
            self._set_status("Critical flags block acceptance", error=True)
            return

        if record.price is None:
            self._set_status("No candidate price to accept", error=True)
            return

        annotation = self.query_one("#annotation", Input).value.strip()
        if record.requires_annotation and not annotation:
            self._set_status("Annotation required for advisory flags", error=True)
            return

        await self._with_session(
            approve_review_record,
            record,
            self.reviewer,
            annotation or None,
        )

        self.query_one("#annotation", Input).value = ""
        self._set_status("Match approved", error=False)
        self._remove_record(str(record.match_result_id))

    async def load_records(self) -> None:
        self.loading = True
        self._set_status("Loading review queue…", error=False)
        records = await self._with_session(
            fetch_pending_reviews,
            self.org_id,
            self.project_id,
            [self.flag_filter] if self.flag_filter else None,
            None,
        )
        self.records = records or []
        self.loading = False
        self._populate_table()
        if not self.records:
            self._set_status("No pending items — you're caught up!", error=False)

    async def _with_session(self, func, *args):
        async with get_session() as session:
            return await func(session, *args)

    def _populate_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear(rows=True, columns=False)
        self.record_index = {}
        for idx, record in enumerate(self.records):
            flags = ", ".join(flag.type for flag in record.flags) if record.flags else "—"
            updated = self._format_ts(record.timestamp)
            reason = record.reason if len(record.reason) < 60 else record.reason[:57] + "…"
            style = "bold red" if record.has_critical_flags else ""
            row_key = str(record.match_result_id)
            self.record_index[row_key] = idx
            table.add_row(
                f"{record.item.family} / {record.item.type_name}",
                f"{record.confidence_score:.0f}%",
                flags,
                updated,
                reason,
                key=row_key,
                style=style,
            )

        if self.records:
            table.cursor_coordinate = (0, 0)
            self._select_record(0)
            table.focus()
        else:
            self.selected_index = None
            self.query_one("#details", Static).update("No pending items.")
            self._toggle_accept_button(disabled=True)

    def _select_record(self, index: int) -> None:
        if index < 0 or index >= len(self.records):
            return
        self.selected_index = index
        record = self.records[index]
        detail = self.query_one("#details", Static)
        detail.update(self._render_detail(record))
        disabled = record.has_critical_flags or record.price is None
        self._toggle_accept_button(disabled=disabled)

    def _render_detail(self, record: ReviewRecord) -> str:
        lines = [
            f"[b]Item[/b]: {record.item.family} / {record.item.type_name}",
            f"[b]Category[/b]: {record.item.category or '—'}",
            f"[b]Quantity[/b]: {record.item.quantity or '—'} {record.item.unit or ''}",
            f"[b]Confidence[/b]: {record.confidence_score:.1f}%",
        ]

        if record.price:
            lines.extend(
                [
                    "",
                    "[b]Candidate Price[/b]",
                    f"SKU: {record.price.sku}",
                    f"Unit Price: {record.price.unit_price} {record.price.currency}",
                    f"VAT: {record.price.vat_rate or '—'}",
                ]
            )
        else:
            lines.append("\n[b]Candidate Price[/b]: None")

        if record.flags:
            lines.append("\n[b]Flags[/b]:")
            for flag in record.flags:
                severity = "Critical" if flag.is_critical else "Advisory"
                lines.append(f"• [{ 'red' if flag.is_critical else 'yellow' }] {severity}: {flag.type}[/] — {flag.message}")
        else:
            lines.append("\n[b]Flags[/b]: None")

        return "\n".join(lines)

    @property
    def _current_record(self) -> ReviewRecord | None:
        if self.selected_index is None:
            return None
        if 0 <= self.selected_index < len(self.records):
            return self.records[self.selected_index]
        return None

    def _toggle_accept_button(self, disabled: bool) -> None:
        button = self.query_one("#accept-button", Button)
        button.disabled = disabled

    def _set_status(self, message: str, *, error: bool) -> None:
        status = self.query_one("#status", Static)
        status.update(("[red]" if error else "") + message + ("[/]" if error else ""))

    def _remove_record(self, key: str) -> None:
        idx = self.record_index.get(key)
        if idx is None:
            return
        self.records.pop(idx)
        self._populate_table()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:  # type: ignore[override]
        key = str(event.row_key.value)
        idx = self.record_index.get(key)
        if idx is not None:
            self._select_record(idx)

    async def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore[override]
        if event.button.id == "refresh-button":
            await self.action_refresh()
        elif event.button.id == "accept-button":
            await self.action_accept()

    async def on_select_changed(self, event: Select.Changed) -> None:  # type: ignore[override]
        if event.select.id == "flag-filter":
            self.flag_filter = None if event.value == "all" else event.value
            await self.load_records()

    def _flag_options(self):
        return [
            ("All Flags", "all"),
            ("Unit Conflict", "Unit Conflict"),
            ("Size Mismatch", "Size Mismatch"),
            ("Angle Mismatch", "Angle Mismatch"),
            ("Material Conflict", "Material Conflict"),
            ("Class Mismatch", "Class Mismatch"),
            ("Stale Price", "StalePrice"),
            ("Currency/VAT", "CurrencyMismatch"),
            ("VAT Unclear", "VATUnclear"),
            ("Vendor Note", "VendorNote"),
        ]

    @staticmethod
    def _format_ts(ts: datetime) -> str:
        return ts.strftime("%Y-%m-%d %H:%M")


def run_review_ui(org_id: str | None, project_id: str | None, reviewer: str | None) -> None:
    config = get_config()
    org_val = org_id or config.org_id
    project_val = project_id or "default"
    reviewer_val = reviewer or "review-ui"

    app = ReviewUIApp(org_val, project_val, reviewer_val)
    asyncio.run(app.run_async())
