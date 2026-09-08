"""MATS entrypoint. Wires config + agents + broker and runs the event loop.

Only paper mode is implemented at this stage; live mode is intentionally a hard stop.
"""

from __future__ import annotations

import typer
from rich.console import Console

from mats.config import Mode, Settings

app = typer.Typer(add_completion=False, help="Multi-Agent Trade Harness")
console = Console()


@app.command()
def run(mode: str = typer.Option("paper", help="paper | live")) -> None:
    settings = Settings(mode=Mode(mode))
    settings.guard_live()
    console.print(f"[bold green]MATS[/] starting in [cyan]{settings.mode.value}[/] mode")
    console.print(f"paper capital: ₹{settings.paper_start_capital_inr:,.0f}")
    # TODO(#3): construct feeds  (issue: CoinDCX feed layer)
    # TODO(#4): construct scanner/observer/risk/coordinator agents
    # TODO(#5): run asyncio event loop
    console.print("[yellow]scaffold only — agent wiring lands with issues #3-#6[/]")


if __name__ == "__main__":
    app()
