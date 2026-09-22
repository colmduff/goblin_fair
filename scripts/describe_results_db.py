"""Write EU-data/RESULTS_DB.md: every table and column in EU-data/results.db.

The descriptions live here, next to the code that checks them. The script reads
the real database and refuses to write the document if any table or column has
no description, so the document can't drift out of step with the data.

Run: make results-doc   (after the walkthrough notebooks 08-10 have run)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "EU-data" / "results.db"
OUTPUT = ROOT / "EU-data" / "RESULTS_DB.md"

RATE = "Steady change in methane per year from the pin year, % (positive = cut, negative = growth)"

# table -> (what it is, which notebook writes it, {column: meaning})
# A column key ending in "*" documents every column starting with that prefix.
TABLES: dict[str, tuple[str, str, dict[str, str]]] = {
    # --- notebook 08: the temperature-neutral (TN) solves -----------------------
    "runs": (
        "One row per TN solve of EU27 biogenic methane.",
        "08",
        {
            "run_id": "Name of the solve: approach, deadline and background, e.g. `A_by2050_ssp119`.",
            "approach": "`A` = biogenic methane's warming held on its own; `B` = all methane's warming held (fossil on the NZ plan).",
            "rule": "The approach in words.",
            "scenario": "The ESABCC scenario used (methane is the same in all three NZ scenarios).",
            "from_year": "Pin year: the warming level to hold, and the first year the TN pathway departs from the NZ plan.",
            "by_year": "Deadline: from this year on, warming must be at or below the pin-year level.",
            "background": "The world the EU sits in (`ssp119` = 1.5 °C world, `ssp245` = middle of the road).",
            "members": "Number of FaIR ensemble members (841 = the full calibrated ensemble).",
            "decline_p5": f"{RATE}, 5th percentile across members.",
            "decline_p50": f"{RATE}, median member (the headline).",
            "decline_p95": f"{RATE}, 95th percentile across members.",
            "cut_by_2050_pct": "How far below the 2020 level the median TN pathway is in 2050, %.",
            "share_neutral": "Share of members for which the median TN pathway really is neutral (0-1).",
            "overshoot_mK": "Median member: highest warming after the deadline minus the pin-year level, mK (≤ 0 = neutral).",
            "pinned_mK": "Median member: methane warming in the pin year, mK.",
            "fair_runs": "How many FaIR runs the search made.",
            "search_hit_limit": "1 if the search reached its limits (20 % growth or 60 % cut a year), else 0.",
            "history": "Which methane history was used.",
            "goblin_fair": "goblin_fair version.",
            "fair": "FaIR version.",
            "run_utc": "When the solve ran (UTC).",
        },
    ),
    "pathways": (
        "Per solve and year: the NZ plan and the TN pathway for EU27 biogenic methane.",
        "08",
        {
            "run_id": "The solve (see `runs`).",
            "year": "Calendar year.",
            "nz_biogenic_kt": "EU27 biogenic methane on the NZ plan, kt/yr.",
            "tn_biogenic_p5_kt": "TN pathway, 5th percentile of emissions (the harshest members), kt/yr.",
            "tn_biogenic_p50_kt": "TN pathway for the median member, kt/yr.",
            "tn_biogenic_p95_kt": "TN pathway, 95th percentile of emissions (the most forgiving members), kt/yr.",
            "fossil_kt": "Fossil methane used (approach B only; empty for A), kt/yr.",
            "allowance_p50_kt": "TN minus NZ for the median member, kt/yr (positive = TN allows more).",
        },
    ),
    "allowance_summary": (
        "Per solve: how much more methane TN allows than the NZ plan.",
        "08",
        {
            "run_id": "The solve (see `runs`).",
            "approach": "`A` or `B` (see `runs`).",
            "by_year": "Deadline.",
            "background": "Background world.",
            "allowance_2030_kt": "TN minus NZ in 2030, kt/yr.",
            "allowance_2050_kt": "TN minus NZ in 2050, kt/yr.",
            "allowance_2100_kt": "TN minus NZ in 2100, kt/yr.",
            "cumulative_2020_2050_Mt": "TN minus NZ added up over 2020-2050, Mt CH4.",
            "cumulative_2020_2100_Mt": "TN minus NZ added up over 2020-2100, Mt CH4.",
        },
    ),
    "approach_difference": (
        "Approach B minus approach A: the extra biogenic methane allowed when the fossil phase-out counts.",
        "08",
        {
            "by_year": "Deadline.",
            "background": "Background world.",
            "year": "Calendar year.",
            "b_minus_a_kt": "B's TN pathway minus A's, kt/yr.",
            "cumulative_b_minus_a_Mt": "The same, added up from 2020 to this year, Mt CH4.",
        },
    ),
    "warming": (
        "Methane warming for the NZ plan and the TN pathways (deadline 2050, ssp119).",
        "08",
        {
            "case": "What was run, e.g. `NZ biogenic (A)` or `TN approach B, by 2050`.",
            "background": "Background world.",
            "year": "Calendar year (warming at the start of the year).",
            "p5_mK": "Warming caused, 5th percentile across members, mK (thousandths of a °C).",
            "p50_mK": "Warming caused, median member, mK.",
            "p95_mK": "Warming caused, 95th percentile, mK.",
        },
    ),
    "member_declines": (
        "The rate each of the 841 members needs, per solve.",
        "08",
        {
            "run_id": "The solve (see `runs`).",
            "member": "FaIR calibrated ensemble member id.",
            "decline_pct": f"{RATE}, for this member.",
        },
    ),
    "inputs_ch4_streams": (
        "Copy of the methane inputs: EU27 methane split into biogenic and fossil, 1750-2100.",
        "08",
        {
            "scenario": "ESABCC NZ scenario.",
            "year": "Calendar year.",
            "biogenic": "Agriculture + land + waste methane, kt/yr.",
            "fossil": "All other methane (energy, industry, unitemised), kt/yr.",
            "total": "biogenic + fossil, kt/yr.",
            "source": "`PRIMAP-hist` (before 2005, scaled) or `ESABCC` (from 2005).",
        },
    ),
    "inputs_ch4_join": (
        "Copy of how the PRIMAP-hist history was scaled to meet ESABCC in 2005.",
        "08",
        {
            "stream": "`biogenic` or `fossil`.",
            "join_year": "Year the two sources meet (2005).",
            "history_kt": "PRIMAP-hist value in the join year, kt.",
            "projection_kt": "ESABCC value in the join year, kt.",
            "factor": "projection / history: every history year of this stream is multiplied by it.",
            "scenario": "ESABCC NZ scenario.",
        },
    ),
    # --- notebook 09: validation -----------------------------------------------
    "validation_q1_history": (
        "Is EU methane warming falling? Three independent estimates, 1960-2023 (history only).",
        "09",
        {
            "year": "Calendar year.",
            "FaIR warming (mK)": "EU27 methane warming from FaIR (median, ssp119, PRIMAP-hist not scaled), mK.",
            "Jones et al. warming (mK)": "EU27 methane warming from Jones et al. (2024) v2024.2, mK.",
            "GWP* (Mt CO2-we/yr)": "GWP* warming-equivalent emissions of EU27 methane, Mt CO2-we/yr (below zero = methane warming falling).",
            "EU27 CH4 (Mt/yr)": "EU27 methane emissions (PRIMAP-hist), Mt/yr.",
        },
    ),
    "validation_q2_breakdown": (
        "Approach B taken apart: warming (mK, median, ssp119) of each piece, 1990-2100.",
        "09",
        {
            "year": "Calendar year.",
            "biogenic held flat": "Biogenic methane held at its 2020 level from 2020, mK.",
            "fossil on NZ plan": "Fossil methane on the NZ plan, mK.",
            "both (approach B at 0 %)": "The two together (approach B with no change), mK.",
            "reference: 11.2 Mt/yr since 1750": "An emitter at the 2020 biogenic level every year since 1750 (no past decline), mK.",
        },
    ),
    "validation_q3_background": (
        "Why the background world changes the answer: world methane and the warming per extra tonne.",
        "09",
        {
            "background": "Background world.",
            "world CH4 2020 (Mt)": "World methane emissions in 2020, Mt/yr (goblin_fair's bundled RCMIP data).",
            "world CH4 2050 (Mt)": "The same in 2050.",
            "world CH4 2100 (Mt)": "The same in 2100.",
            "1 Mt/yr from 2020: warming 2050 (mK)": "Warming in 2050 from an extra 1 Mt/yr of methane from 2020, median, mK.",
            "1 Mt/yr from 2020: warming 2100 (mK)": "The same in 2100.",
        },
    ),
    "validation_q4_sensitivity": (
        "Approaches A and B re-solved with one choice changed at a time (deadline 2050, ssp119).",
        "09",
        {
            "variant": "What was changed (history scaling, history start, pin year).",
            "approach": "`A` or `B`.",
            "rate_p50": f"{RATE}, median.",
            "rate_p5": f"{RATE}, 5th percentile.",
            "rate_p95": f"{RATE}, 95th percentile.",
            "allowance_2020_2050_Mt": "TN minus NZ added up over 2020-2050, Mt CH4.",
        },
    ),
    "validation_q4_method": (
        "Approach B's TN pathway run forward with two attribution methods.",
        "09",
        {
            "method": "`leave_one_out` (world minus EU) or `add` (world plus EU).",
            "level_2020_mK": "Methane warming in 2020, median, mK.",
            "highest_after_2050_mK": "Highest methane warming after 2050, median, mK.",
            "neutral": "1 if the highest after 2050 is at or below the 2020 level.",
        },
    ),
    "validation_q5_rules": (
        "Do the TN pathways pass a stricter rule?",
        "09",
        {
            "approach": "`A` or `B`.",
            "hold rule: share of members neutral by 2100": "Share of members whose warming is back at or below the 2020 level and stays there (0-1).",
            "peak rule: share of members whose warming never rises after 2050": "Share of members whose warming never rises again after 2050 (0-1).",
            "peak rule: median year warming stops rising": "Median year from which warming never rises again (empty = fewer than half get there).",
        },
    ),
    # --- notebook 10: pin year and Ireland ---------------------------------------
    "exp1_pin_year": (
        "Experiment 1: EU27 TN solves pinned at 2020, 2025 and 2030 (deadline 2050, ssp119).",
        "10",
        {
            "case": "Approach and pin year in words.",
            "rate_p50": f"{RATE}, median.",
            "rate_p5": f"{RATE}, 5th percentile.",
            "rate_p95": f"{RATE}, 95th percentile.",
            "share_neutral": "Share of members for which the median pathway is neutral (0-1).",
            "approach": "`A` or `B`.",
            "pin_year": "Pin year.",
            "tn_2050_Mt": "EU27 biogenic methane on the TN pathway in 2050, Mt/yr.",
            "allowance_2020_2050_Mt": "TN minus NZ added up over 2020-2050, Mt CH4 (always from 2020, so pin years compare).",
        },
    ),
    "exp1_pathways": (
        "Experiment 1: the TN pathways by pin year.",
        "10",
        {
            "approach": "`A` or `B`.",
            "pin_year": "Pin year.",
            "year": "Calendar year.",
            "tn_biogenic_kt": "EU27 biogenic methane on the TN pathway (median member), kt/yr.",
            "nz_biogenic_kt": "EU27 biogenic methane on the NZ plan, kt/yr.",
        },
    ),
    "exp2_replication": (
        "Experiment 2a: FaIR against the Irish workbook's MAGICC results ('TN compliant' scenario, ssp126), by gas and history start.",
        "10",
        {
            "gas": "`CH4`, `N2O`, `CO2_FFI` (fossil CO2) or `CO2_AFOLU` (land CO2).",
            "history": "Where the Irish emissions series starts (PRIMAP-hist before 2020).",
            "fair_2020_mK": "FaIR warming from this gas in 2020, median, mK.",
            "magicc_2020_mK": "MAGICC warming from this gas in 2020, mK.",
            "fair_2100_mK": "FaIR in 2100, mK.",
            "magicc_2100_mK": "MAGICC in 2100, mK.",
            "fair_ratio_2100_2020": "FaIR 2100 / 2020 (the shape of the curve).",
            "magicc_ratio_2100_2020": "MAGICC 2100 / 2020.",
        },
    ),
    "exp2_tn_check": (
        "Experiment 2b: is the workbook's 'TN compliant' scenario temperature neutral in FaIR?",
        "10",
        {
            "background": "Background world.",
            "what": "`methane only` or `all gases`.",
            "level_2020_mK": "Irish warming in 2020, median, mK.",
            "highest_after_2050_mK": "Highest Irish warming after 2050, median, mK.",
            "level_2100_mK": "Irish warming in 2100, median, mK.",
            "neutral_hold": "1 if the highest after 2050 is at or below the 2020 level.",
            "share_members_hold": "Share of members that are back at or below the 2020 level by 2100 and stay there (0-1).",
        },
    ),
    "exp2_ireland_pathway": (
        "Experiment 2c: Ireland's own TN methane pathway (pin 2020, deadline 2050, ssp119) next to the workbook scenarios.",
        "10",
        {
            "year": "Calendar year.",
            "tn_p5_kt": "Irish TN pathway, 5th percentile of emissions, kt/yr.",
            "tn_p50_kt": "Irish TN pathway, median member, kt/yr.",
            "tn_p95_kt": "Irish TN pathway, 95th percentile of emissions, kt/yr.",
            "scenario: *": "Irish methane in that workbook scenario, kt/yr.",
        },
    ),
    "exp2_why_steeper": (
        "Experiments 2c and 2d: TN rates for Ireland and for controlled variants that test why Ireland's cut is steeper.",
        "10",
        {
            "case": "Which series was solved (Ireland as is, scaled, reshaped, the EU...).",
            "rate_p50": f"{RATE}, median.",
            "rate_p5": f"{RATE}, 5th percentile.",
            "rate_p95": f"{RATE}, 95th percentile.",
            "share_neutral": "Share of members for which the median pathway is neutral (0-1).",
        },
    ),
    "exp3_national_vs_bloc": (
        "Experiment 3: Irish methane under national TN vs following the EU's rate.",
        "10",
        {
            "rule": "National TN, or one of the EU-bloc versions.",
            "rate_pct_per_yr": f"{RATE} applied to Irish methane.",
            "ch4_2030_kt": "Irish methane in 2030, kt/yr.",
            "ch4_2040_kt": "Irish methane in 2040, kt/yr.",
            "ch4_2050_kt": "Irish methane in 2050, kt/yr.",
            "cut_by_2050_pct": "Cut from 2020 to 2050, %.",
            "cumulative_2020_2050_kt": "Irish methane added up over 2020-2050, kt.",
            "extra_vs_national_2020_2050_kt": "This rule minus national TN, added up over 2020-2050, kt (positive = more methane than national TN).",
        },
    ),
    "exp3_ireland_warming": (
        "Experiment 3 check: Ireland's own methane warming if it follows the EU rate.",
        "10",
        {
            "rule": "Which EU-bloc rate Ireland follows.",
            "ireland_2020_mK": "Irish methane warming in 2020, median, mK.",
            "ireland_2050_mK": "In 2050.",
            "ireland_2100_mK": "In 2100.",
            "ireland_highest_after_2050_mK": "Highest after 2050.",
            "above_2020_level_pct": "How far the highest after 2050 is above the 2020 level, % (positive = Ireland's methane warming rises).",
        },
    ),
}

INTRO = """# `results.db`: tables and columns

Every table in `EU-data/results.db`, and what each column means. This file is
generated by `scripts/describe_results_db.py` (`make results-doc`) from the database
itself. The script refuses to write it if any table or column is undescribed, so what you
read here matches the data.

## Terms used throughout

- **TN (temperature neutral):** methane's warming never goes above its level in the
  **pin year** (`from_year` / `pin_year`) from the **deadline** (`by_year`) on.
- **Approach A:** biogenic methane's own warming is held. **Approach B:** the warming of all
  methane is held, with fossil methane on the NZ plan. In both, only biogenic methane is
  adjusted.
- **NZ plan:** the ESABCC net-zero scenario (`NZero_withICEPhOP`, REMIND 3.2; methane is the
  same in all three NZ scenarios).
- **Rate:** the steady % change per year from the pin year. **Positive = cut, negative =
  growth.**
- **Members:** FaIR's 841 calibrated climate versions. **p5 / p50 / p95** are the 5th
  percentile, median and 95th percentile across them. For *emissions pathways*, p5 is the
  lowest path, i.e. the harshest cut.
- **Background:** the world around the emitter. `ssp119` is a 1.5 °C world (the headline),
  `ssp126` well below 2 °C, `ssp245` middle of the road.
- **Units:** kt = thousand tonnes of CH4; Mt = million tonnes; mK = thousandths of a degree
  Celsius of global warming.
- **Allowance:** TN pathway minus the reference plan. Positive means TN allows more methane.

## Tables by notebook

| Notebook | Tables |
|---|---|
"""


def _meaning(column: str, columns: dict[str, str]) -> str | None:
    if column in columns:
        return columns[column]
    for key, text in columns.items():
        if key.endswith("*") and column.startswith(key[:-1]):
            return text
    return None


def render(database: Path, tables: dict = TABLES) -> str:
    """The markdown document, or ValueError listing whatever is undescribed."""
    with sqlite3.connect(database) as con:
        names = [r[0] for r in con.execute(
            "select name from sqlite_master where type='table' order by name")]  # fmt: skip
        schema = {
            n: [(r[1], r[2]) for r in con.execute(f'pragma table_info("{n}")')]
            for n in names
        }
        rows = {
            n: con.execute(f'select count(*) from "{n}"').fetchone()[0] for n in names
        }
    missing = [n for n in names if n not in tables]
    missing += [f"{n}.{c}" for n in names if n in tables for c, _ in schema[n]
                if _meaning(c, tables[n][2]) is None]  # fmt: skip
    if missing:
        raise ValueError(f"undescribed in results.db: {missing}")

    order = [n for n in tables if n in names]
    by_notebook: dict[str, list[str]] = {}
    for n in order:
        by_notebook.setdefault(tables[n][1], []).append(n)
    lines = [INTRO.rstrip("\n")]
    for notebook, group in by_notebook.items():
        links = ", ".join(f"[`{n}`](#{n})" for n in group)
        lines.append(f"| {notebook} | {links} |")
    for n in order:
        description, notebook, columns = tables[n]
        lines += ["", f"## `{n}`", "", description, "",
                  f"Written by notebook {notebook}. {rows[n]:,} rows.", "",
                  "| Column | Type | Meaning |", "|---|---|---|"]  # fmt: skip
        for column, kind in schema[n]:
            lines.append(f"| `{column}` | {kind} | {_meaning(column, columns)} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT.write_text(render(DATABASE))
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
