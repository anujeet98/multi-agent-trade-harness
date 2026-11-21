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


@app.command()
def flow(
    coin: str = typer.Argument(..., help="coin or symbol, e.g. BLESS or BLESSUSDT"),
    big: float = typer.Option(0, help="big-print threshold in $ (0 = adaptive)"),
    fps: float = typer.Option(4, help="screen refreshes per second"),
) -> None:
    """Live buyers-vs-sellers dashboard for one Binance perp (Ctrl+C to quit)."""
    import asyncio

    from rich.live import Live

    from mats.flow import live as flow_live
    from mats.flow.engine import FlowState
    from mats.flow.view import render

    sym = coin.upper()
    sym = sym if sym.endswith("USDT") else sym + "USDT"
    state = FlowState(sym, big_print_usd=big or None)

    async def main() -> None:
        stop = asyncio.Event()
        runner = asyncio.create_task(flow_live.run(state, stop))
        with Live(render(state), console=console, screen=True, auto_refresh=False) as view:
            try:
                while not runner.done():
                    view.update(render(state), refresh=True)
                    await asyncio.sleep(1 / fps)
            finally:
                stop.set()
        await runner  # surfaces errors such as an unknown symbol

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    app()
