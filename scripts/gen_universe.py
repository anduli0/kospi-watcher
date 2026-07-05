"""Dev-time generator: snapshot the top-N KOSPI/KOSDAQ common shares by market
cap into a committed Python data module (domain/stocks/_universe_data.py).

Run once (or to refresh) with the venv python after `pip install finance-datareader`.
The runtime imports the generated module — it does NOT depend on FDR/pandas.
"""

from __future__ import annotations

import math

import FinanceDataReader as fdr  # noqa: N813  (the library's conventional alias)

TOP_N = 300
OUT = "src/kospi_watcher/domain/stocks/_universe_data.py"


def _is_preferred(name: str) -> bool:
    n = name.strip()
    return n.endswith("우") or n.endswith("우B") or "우B" in n


def _skip(name: str) -> bool:
    n = name.strip()
    if not n:
        return True
    if _is_preferred(n):
        return True
    return any(x in n for x in ("스팩", "ETF", "ETN", " ETN", "리츠"))


def main() -> None:
    df = fdr.StockListing("KRX")
    rows: list[tuple[str, str, str, str, int]] = []
    for r in df.itertuples():
        market = str(getattr(r, "Market", "") or "")
        if market not in ("KOSPI", "KOSDAQ"):
            continue
        code = str(getattr(r, "Code", "") or "").strip()
        if len(code) != 6 or not code.isdigit():
            continue
        name = str(getattr(r, "Name", "") or "").strip()
        if _skip(name):
            continue
        marcap = getattr(r, "Marcap", None)
        if marcap is None or (isinstance(marcap, float) and math.isnan(marcap)) or marcap <= 0:
            continue
        dept = getattr(r, "Dept", None)
        is_nan = dept is None or (isinstance(dept, float) and math.isnan(dept))
        sector = "" if is_nan else str(dept).strip()
        rows.append((code, name, market, sector, int(marcap)))

    rows.sort(key=lambda x: x[4], reverse=True)
    top = rows[:TOP_N]

    lines = [
        '"""Auto-generated KRX universe snapshot — DO NOT EDIT BY HAND.',
        "",
        f"Top {TOP_N} KOSPI/KOSDAQ common shares by market cap (FinanceDataReader),",
        "the broad candidate pool the stock recommender selects from (ADR-026).",
        "Regenerate with `scripts/gen_universe.py`.",
        'Tuple = (code, name, market, sector, marcap)."""',
        "",
        "from __future__ import annotations",
        "",
        "RAW_UNIVERSE: tuple[tuple[str, str, str, str, int], ...] = (",
    ]
    for code, name, market, sector, marcap in top:
        nm = name.replace('"', '\\"')
        sec = sector.replace('"', '\\"')
        lines.append(f'    ("{code}", "{nm}", "{market}", "{sec}", {marcap}),')
    lines.append(")")
    content = "\n".join(lines) + "\n"

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(content)

    kospi = sum(1 for x in top if x[2] == "KOSPI")
    kosdaq = sum(1 for x in top if x[2] == "KOSDAQ")
    with_sector = sum(1 for x in top if x[3])
    print(f"wrote {OUT}")
    print(f"  {len(top)} names: KOSPI {kospi}, KOSDAQ {kosdaq}; sector on {with_sector}")
    print(f"  smallest: {top[-1][1]} {top[-1][4] / 1e12:.2f}T won")
    print(f"  sample: {[(x[0], x[1]) for x in top[:5]]}")


if __name__ == "__main__":
    main()
