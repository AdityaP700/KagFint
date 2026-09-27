"""Terminal report (Layer 8, pipeline view).

Renders the pipeline's current state — validation summary, forecast metrics,
risk tiers, recommendation actions — as a rich terminal report. This is the
run manifest made visible: what you'd check in production to see whether the
pipeline is healthy before trusting any dashboard built on top of it.

Usage: PYTHONPATH=src python -m demandops.report
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from demandops import config

console = Console()


def _latest(pattern: str) -> Path | None:
    files = sorted(config.REPORTS_DIR.glob(pattern))
    return files[-1] if files else None


def _load_json(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def render_validation() -> None:
    report = _load_json(_latest("validation_report_*.json"))
    if report is None:
        console.print("[yellow]No validation report found.[/yellow]")
        return
    s = report["summary"]
    color = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}[s["overall"]]
    table = Table(title="1. Validation gate (latest run)", show_lines=False)
    table.add_column("check")
    table.add_column("status")
    table.add_column("evidence")
    for check in report["checks"]:
        if check["status"] != "PASS":
            detail = json.dumps(check["details"], default=str)
            table.add_row(f"{check['table']}:{check['name']}",
                          f"[{color}]{check['status']}[/{color}]",
                          detail[:90])
    table.add_row("...all other checks", "PASS", "")
    console.print(Panel(table, subtitle=f"overall: [{color}]{s['overall']}[/{color}] "
                        f"({s['PASS']} passed, {s['WARN']} warn, {s['FAIL']} fail)"))


def render_forecasts() -> None:
    baselines = _load_json(config.EXPERIMENTS_DIR / "baseline_results.json")
    gbm = _load_json(config.EXPERIMENTS_DIR / "gbm_results.json")
    if baselines is None or gbm is None:
        console.print("[yellow]Forecast experiment results not found.[/yellow]")
        return
    table = Table(title="2. Forecast quality (28-day temporal holdout)")
    for col in ("model", "WMAPE", "weighted WMAPE", "MAE", "RMSE"):
        table.add_column(col)
    for name, r in baselines["results"].items():
        o = r["overall"]
        table.add_row(name, f"{o['wmape']:.1%}", f"{o['wmape_weighted']:.1%}",
                      f"{o['mae']:.2f}", f"{o['rmse']:.1f}")
    o = gbm["results"]["overall"]
    table.add_row(f"{gbm['model']} (GPU)", f"[bold green]{o['wmape']:.1%}"
                  f"[/bold green]", f"{o['wmape_weighted']:.1%}",
                  f"{o['mae']:.2f}", f"{o['rmse']:.1f}")
    console.print(Panel(table))


def render_risk() -> None:
    risk_path = config.PROCESSED_DATA_DIR / "risk" / "risk_scores.csv"
    rec_path = config.PROCESSED_DATA_DIR / "recommendations" / "recommendations.csv"
    if not risk_path.exists():
        console.print("[yellow]Risk scores not found.[/yellow]")
        return
    risk = pd.read_csv(risk_path)
    counts = risk["risk_tier"].value_counts().to_dict()
    console.print(Panel(
        f"series scored: {len(risk)}   [red]HIGH {counts.get('HIGH', 0)}[/red]   "
        f"[yellow]MEDIUM {counts.get('MEDIUM', 0)}[/yellow]   "
        f"[green]LOW {counts.get('LOW', 0)}[/green]   "
        f"data gaps: {int(risk['availability_data_gap'].fillna(False).sum())}",
        title="3. Stockout risk (28-day horizon)"))

    top = risk[risk["risk_tier"] == "HIGH"].head(8)
    table = Table(title="Top HIGH-risk series")
    for col in ("name", "warehouse", "forecast_units", "recent_availability",
                "estimated_unmet_units"):
        table.add_column(col)
    for _, r in top.iterrows():
        table.add_row(str(r["name"]), str(r["warehouse"]),
                      f"{r['forecast_units']:,.0f}", f"{r['recent_availability']:.0%}",
                      f"{r['estimated_unmet_units']:,.0f}")
    console.print(Panel(table))

    if rec_path.exists():
        recs = pd.read_csv(rec_path)
        actions = recs["action"].value_counts().to_dict()
        console.print(Panel(
            "   ".join(f"{k}: {v}" for k, v in sorted(actions.items())),
            title=f"4. Recommendations (engine v{recs['engine_version'].iloc[0]})"))


def main() -> int:
    console.print(Panel("[bold]DemandOps — pipeline status[/bold]",
                        subtitle=config.PROJECT_ROOT.name))
    render_validation()
    render_forecasts()
    render_risk()
    return 0


if __name__ == "__main__":
    sys.exit(main())
