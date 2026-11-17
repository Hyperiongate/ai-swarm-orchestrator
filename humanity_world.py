"""
The Humanity Index — the World, built from its countries
File: humanity_world.py
Created: November 16, 2026
Last Updated: November 16, 2026 — Initial implementation

PURPOSE:
    Jim (November 16, 2026): a world map coloured by Humanity Index score; click
    any country (Hungary) to see its score; ask "what if Hungary improved by
    10%?" and see the world score move. His choices that day:
      * FREE BULK DATA, AI FILLS GAPS: most measures come for every country at
        once from free official datasets; AI researches only what isn't
        published in bulk, one country at a time, when asked.
      * THE WORLD IS BUILT FROM THE COUNTRIES: the world score is the average of
        the country scores, weighted by population, so any country's change
        flows straight into it.

WHERE EACH OF THE 26 MEASURES COMES FROM (SOURCES below):
    World Bank (api.worldbank.org, World Development Indicators), 13 measures:
        life expectancy, child deaths, hunger, extreme poverty, safe water,
        inequality (Gini), richest 10%'s share, air pollution, young people out
        of work or school, research spending, researchers, murders; plus
        population (for the weighting).
    Our World in Data (ourworldindata.org grapher downloads), 6 measures:
        life satisfaction (Gallup / World Happiness Report), liberal democracy
        (V-Dem), corruption (Transparency International), greenhouse gas
        emissions per person (Jones et al. / Global Carbon Project), years of
        schooling, deaths in armed conflict (UCDP).
    Global, the same for every country, 2 measures: warming and wildlife. Taken
        from the latest World score run (humanity_score.py) when there is one.
    Not published in bulk, 6 measures: freedom to choose, personal freedom,
        modern slavery, helping a stranger, giving, volunteering. Filled in per
        country by AI research when someone asks ("Fill in the missing
        measures", job kind 'country_gap').
    For each country the newest value from 2005 on is used; its year is kept.

HOW IT RUNS:
    'world_refresh' (a job in humanity_runner.py, no AI, no cost) downloads all
    the bulk sources and stores the newest value per country. Scores are worked
    out on request from what is stored, with the same scorecard and rules as
    every other Humanity Index score (humanity_score.SCORECARD, score_run).

DATABASE TABLES (lazy-created; no migration):
    humanity_country          iso3 PK, name, population, updated_at
    humanity_country_values   iso3, measure, value, year, source, url, fetched_at
                              PRIMARY KEY (iso3, measure)

SETTINGS (Render > Environment, optional; used by the tests to point at a stand-in):
    HUMANITY_WORLD_BANK_URL   default https://api.worldbank.org
    HUMANITY_OWID_URL         default https://ourworldindata.org

CHANGELOG:
- November 16, 2026: INITIAL IMPLEMENTATION. New file, used by routes/humanity.py
  and (job kinds 'world_refresh', 'country_gap') humanity_engine.py. No existing
  file changed by it. Rule 1 (do no harm) preserved.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import csv
import io
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

import humanity_score as hs
from db_engine import get_db_connection

logger = logging.getLogger(__name__)

OLDEST_YEAR = 2005
FETCH_TIMEOUT = 60
USER_AGENT = "HumanityIndex/1.0 (Shiftwork Solutions; data refresh)"


def _wb_base():
    return os.environ.get("HUMANITY_WORLD_BANK_URL", "https://api.worldbank.org").rstrip("/")


def _owid_base():
    return os.environ.get("HUMANITY_OWID_URL", "https://ourworldindata.org").rstrip("/")


# measure key -> where it comes from. "page" is the human-readable page shown on the site.
SOURCES = {
    "life_expectancy": {"wb": "SP.DYN.LE00.IN"},
    "child_mortality": {"wb": "SH.DYN.MORT"},
    "hunger": {"wb": "SN.ITK.DEFC.ZS"},
    "extreme_poverty": {"wb": "SI.POV.DDAY"},
    "safe_water": {"wb": "SH.H2O.SMDW.ZS"},
    "gini": {"wb": "SI.POV.GINI"},
    "top10_share": {"wb": "SI.DST.10TH.10"},
    "air": {"wb": "EN.ATM.PM25.MC.M3"},
    "neet": {"wb": "SL.UEM.NEET.ZS"},
    "rd_spending": {"wb": "GB.XPD.RSDV.GD.ZS"},
    "researchers": {"wb": "SP.POP.SCIE.RD.P6"},
    "homicide": {"wb": "VC.IHR.PSRC.P5"},
    "life_satisfaction": {"owid": "happiness-cantril-ladder"},
    "liberal_democracy": {"owid": "liberal-democracy-index"},
    "corruption": {"owid": "ti-corruption-perception-index"},
    "emissions": {"owid": "per-capita-ghg-emissions"},
    "schooling": {"owid": "mean-years-of-schooling-long-run"},
    "conflict_deaths": {"owid": "death-rate-in-armed-conflicts"},
}
POPULATION_CODE = "SP.POP.TOTL"
GLOBAL_MEASURES = ("warming", "wildlife")
GAP_MEASURES = ("freedom_choices", "personal_freedom", "modern_slavery", "helped_stranger", "donated", "volunteered")


def source_page(measure):
    s = SOURCES.get(measure) or {}
    if "wb" in s:
        return "World Bank", f"https://data.worldbank.org/indicator/{s['wb']}"
    if "owid" in s:
        return "Our World in Data", f"https://ourworldindata.org/grapher/{s['owid']}"
    return "", ""


# ============================================================================
# DOWNLOADING
# ============================================================================

def _get(url):
    response = requests.get(url, timeout=FETCH_TIMEOUT, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response


def wb_countries():
    """{iso3: name} for real countries (the World Bank also lists regions and income groups; those are left out)."""
    data = _get(f"{_wb_base()}/v2/country?format=json&per_page=400").json()
    rows = data[1] if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list) else []
    out = {}
    for row in rows:
        region = (row.get("region") or {}).get("id")
        iso3 = str(row.get("id") or "").upper()
        if region and region != "NA" and len(iso3) == 3:
            out[iso3] = row.get("name") or iso3
    return out


def wb_indicator(code):
    """{iso3: (value, year)}: the newest non-empty value per country, from OLDEST_YEAR on."""
    data = _get(f"{_wb_base()}/v2/country/all/indicator/{code}?format=json&per_page=20000&mrnev=1").json()
    rows = data[1] if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list) else []
    out = {}
    for row in rows:
        iso3 = str(row.get("countryiso3code") or "").upper()
        value, year = row.get("value"), str(row.get("date") or "")
        if len(iso3) != 3 or value is None or not year[:4].isdigit() or int(year[:4]) < OLDEST_YEAR:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if iso3 not in out or int(year[:4]) > int(out[iso3][1]):
            out[iso3] = (value, year[:4])
    return out


def owid_chart(slug):
    """{iso3: (value, year)} from an Our World in Data chart download (Entity, Code, Year, value...)."""
    text = _get(f"{_owid_base()}/grapher/{slug}.csv?useColumnShortNames=true&csvType=full").text
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None) or []
    if len(header) < 4 or header[1].strip().lower() != "code":
        raise ValueError(f"unexpected columns in {slug}: {header[:6]}")
    year_col = 2
    data_cols = list(range(3, len(header)))
    out = {}
    for row in reader:
        if len(row) <= max(data_cols, default=3):
            row = row + [""] * (len(header) - len(row))
        code = row[1].strip().upper()
        if len(code) != 3 or not row[year_col].strip().lstrip("-").isdigit():
            continue                                  # regions have OWID_ codes or none
        year = int(row[year_col])
        if year < OLDEST_YEAR:
            continue
        value = None
        for c in data_cols:                           # the first column with a number is the indicator
            try:
                value = float(row[c])
                break
            except (TypeError, ValueError):
                continue
        if value is None:
            continue
        if code not in out or year > int(out[code][1]):
            out[code] = (value, str(year))
    return out


def refresh(payload=None):
    """Job 'world_refresh': download every bulk source and store the newest value per country."""
    ensure_tables()
    started = time.time()
    countries = wb_countries()
    population = wb_indicator(POPULATION_CODE)
    report = {}

    def one(measure):
        spec = SOURCES[measure]
        try:
            values = wb_indicator(spec["wb"]) if "wb" in spec else owid_chart(spec["owid"])
            return measure, values, None
        except Exception as exc:  # noqa: BLE001 - one source failing must not stop the others
            logger.warning("Humanity world refresh: %s failed: %s", measure, exc)
            return measure, {}, f"{type(exc).__name__}: {str(exc)[:160]}"

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(one, SOURCES))

    now = time.time()
    with get_db_connection() as conn:
        cur = conn.cursor()
        for iso3, name in countries.items():
            pop = population.get(iso3, (None, None))[0]
            cur.execute(
                "INSERT INTO humanity_country (iso3, name, population, updated_at) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (iso3) DO UPDATE SET name = EXCLUDED.name, "
                "population = COALESCE(EXCLUDED.population, humanity_country.population), updated_at = EXCLUDED.updated_at",
                (iso3, name, pop, now))
        for measure, values, error in results:
            source, url = source_page(measure)
            stored = 0
            for iso3, (value, year) in values.items():
                if iso3 not in countries:
                    continue
                cur.execute(
                    "INSERT INTO humanity_country_values (iso3, measure, value, year, source, url, fetched_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (iso3, measure) DO UPDATE SET "
                    "value = EXCLUDED.value, year = EXCLUDED.year, source = EXCLUDED.source, url = EXCLUDED.url, "
                    "fetched_at = EXCLUDED.fetched_at",
                    (iso3, measure, value, year, source, url, now))
                stored += 1
            report[measure] = {"countries": stored, "source": source, "error": error}
    return {"countries": len(countries), "measures": report, "seconds": round(time.time() - started, 1),
            "usage": {"model": "none", "input_tokens": 0, "output_tokens": 0, "searches": 0, "cost": 0.0}}


# ============================================================================
# STORAGE
# ============================================================================

_tables_ready = False
_tables_lock = threading.Lock()


def ensure_tables():
    global _tables_ready
    if _tables_ready:
        return
    with _tables_lock:
        if _tables_ready:
            return
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS humanity_country (
                    iso3        TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    population  DOUBLE PRECISION,
                    updated_at  DOUBLE PRECISION NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS humanity_country_values (
                    iso3        TEXT NOT NULL,
                    measure     TEXT NOT NULL,
                    value       DOUBLE PRECISION NOT NULL,
                    year        TEXT NOT NULL DEFAULT '',
                    source      TEXT NOT NULL DEFAULT '',
                    url         TEXT NOT NULL DEFAULT '',
                    fetched_at  DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (iso3, measure)
                )
            """)
        _tables_ready = True


def _load():
    """(countries {iso3: {name, population}}, values {iso3: {measure: row}}, last update time)."""
    ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT iso3, name, population, updated_at FROM humanity_country")
        countries = {r["iso3"]: {"name": r["name"], "population": r["population"]} for r in cur.fetchall()}
        cur.execute("SELECT MAX(updated_at) AS t FROM humanity_country")
        row = cur.fetchone()
        updated = float(row["t"]) if row and row["t"] else None
        cur.execute("SELECT iso3, measure, value, year, source, url FROM humanity_country_values")
        values = {}
        for r in cur.fetchall():
            values.setdefault(r["iso3"], {})[r["measure"]] = {
                "value": float(r["value"]), "year": r["year"], "source": r["source"], "url": r["url"]}
    return countries, values, updated


def _globals():
    """Warming and wildlife from the latest complete World score run, if there is one."""
    try:
        run = hs.latest_run(hs.WORLD)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Humanity world: could not read the World run: %s", exc)
        return {}
    if not run:
        return {}
    out = {}
    for cat in run["score"]["categories"]:
        for m in cat["measures"]:
            if m["key"] in GLOBAL_MEASURES and m.get("value") is not None:
                out[m["key"]] = {"value": m["value"], "year": m.get("year", ""), "source": "World score run",
                                 "url": (m.get("source") or {}).get("url", "")}
    return out


def _as_categories(rows, globals_, population=None):
    """Stored values in the shape humanity_score.score_run expects."""
    by_cat = {}
    for cat in hs.SCORECARD:
        vals = []
        for m in cat["measures"]:
            row = rows.get(m["key"]) or globals_.get(m["key"])
            if m["key"] == "population" and population:
                row = {"value": population, "year": "", "source": "World Bank", "url": ""}
            if not row:
                continue
            vals.append({"key": m["key"], "value": row["value"], "year": row["year"],
                         "level": "world" if m["key"] in GLOBAL_MEASURES else "country", "where": "",
                         "note": "Same for every country." if m["key"] in GLOBAL_MEASURES else "",
                         "source": {"url": row["url"], "title": row["source"]} if row.get("url") else None})
        by_cat[cat["key"]] = {"values": vals, "status": "done"}
    return by_cat


def summary():
    """Every country's score, and the world built from them (population-weighted)."""
    countries, values, updated = _load()
    globals_ = _globals()
    out = []
    measure_values = {}                 # measure -> [(value, population)] for the world's averages
    for iso3, c in countries.items():
        scored = hs.score_run(_as_categories(values.get(iso3, {}), globals_, c["population"]))
        out.append({"iso3": iso3, "name": c["name"], "population": c["population"], "overall": scored["overall"],
                    "measured": scored["measured"], "of": scored["of"],
                    "categories": {cat["key"]: cat["score"] for cat in scored["categories"]}})
        if c["population"]:
            for cat in scored["categories"]:
                for m in cat["measures"]:
                    if m.get("value") is not None and not m.get("info"):
                        measure_values.setdefault(m["key"], []).append((m["value"], c["population"]))
    world = world_from(out)
    # The world's value of each measure: the average over countries, weighted by population.
    # Used to show how a change by some number of people moves the world (an approximation).
    world["measures"] = {k: round(sum(v * p for v, p in rows) / sum(p for _v, p in rows), 4)
                         for k, rows in measure_values.items()}
    return {"updated_at": updated, "countries": sorted(out, key=lambda x: x["name"]),
            "world": world, "globals_available": sorted(globals_)}


def world_from(countries):
    """The world: each country's score weighted by its population."""
    def weighted(get):
        total = weight = 0.0
        for c in countries:
            v, p = get(c), c.get("population")
            if v is None or not p:
                continue
            total += v * p
            weight += p
        return (round(total / weight, 2) if weight else None), weight
    overall, people = weighted(lambda c: c["overall"])
    cats = {}
    for cat in hs.SCORECARD:
        cats[cat["key"]] = weighted(lambda c, k=cat["key"]: c["categories"].get(k))[0]
    counted = sum(1 for c in countries if c["overall"] is not None and c.get("population"))
    return {"overall": overall, "categories": cats, "population": people, "countries_counted": counted}


def country(iso3):
    """One country in full: every measure, its value, year, source and score; and what is missing."""
    countries, values, updated = _load()
    c = countries.get(str(iso3 or "").upper())
    if not c:
        return None
    iso3 = str(iso3).upper()
    scored = hs.score_run(_as_categories(values.get(iso3, {}), _globals(), c["population"]))
    missing = {}
    for cat in scored["categories"]:
        gaps = [m["key"] for m in cat["measures"] if m.get("value") is None and not m.get("info")]
        if gaps:
            missing[cat["key"]] = gaps
    return {"iso3": iso3, "name": c["name"], "population": c["population"], "updated_at": updated,
            "score": scored, "missing": missing}


# ============================================================================
# FILLING THE GAPS FOR ONE COUNTRY (job 'country_gap')
# ============================================================================

def fill_gap(payload):
    """Research one category for one country with AI, and keep only the values that were missing."""
    iso3 = str(payload.get("iso3") or "").upper()
    detail = country(iso3)
    if detail is None:
        raise ValueError("That country is not in the world data. Refresh the world data first.")
    result = hs.research_category({"category": payload.get("category"), "place": detail["name"]})
    missing = set(detail["missing"].get(payload.get("category"), []))
    stored = []
    now = time.time()
    with get_db_connection() as conn:
        cur = conn.cursor()
        for v in result.get("values", []):
            if v["key"] not in missing or v.get("value") is None:
                continue
            src = v.get("source") or {}
            cur.execute(
                "INSERT INTO humanity_country_values (iso3, measure, value, year, source, url, fetched_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (iso3, measure) DO NOTHING",
                (iso3, v["key"], v["value"], v.get("year") or "", "AI research" + (f": {src.get('title')}" if src.get("title") else ""),
                 src.get("url") or "", now))
            stored.append(v["key"])
    return {"iso3": iso3, "category": payload.get("category"), "stored": stored, "usage": result.get("usage")}


def start_fill(iso3):
    """Queue one AI job per category that has missing measures. Returns {category: job_id}."""
    import humanity_engine
    detail = country(iso3)
    if detail is None:
        raise LookupError("That country is not in the world data.")
    jobs = {}
    for category in detail["missing"]:
        jobs[category] = humanity_engine.submit_job(
            "country_gap", {"iso3": detail["iso3"], "category": category}, start_helper=False)
    if jobs:
        humanity_engine.ensure_runner()
    return jobs

# I did no harm and this file is not truncated
