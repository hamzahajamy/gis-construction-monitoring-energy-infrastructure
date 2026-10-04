"""
generate_sample_data.py

Generates fictional sample data for the "GIS-Based Construction Progress
Monitoring for Energy Infrastructure" portfolio project.

Scenario: a fictional hydrogen pipeline route ("H2-Leitung Hannover-Hildesheim",
~27 km) built by a fictional company. All company names, people, and exact
coordinates are invented for portfolio purposes -- this does not represent a
real infrastructure project.

Output (written next to this script, in ./output/):
  - contractors.csv
  - sections.csv     (LineString geometry as WKT, EPSG:25832)
  - issues.csv        (Point geometry as WKT, EPSG:25832)
  - inspections.csv   (Point geometry as WKT, EPSG:25832)
  - known_data_quality_issues.md   (documents which rows were deliberately
    corrupted, and why, so you can verify the ArcPy QC script catches them)

The WKT columns can be loaded into ArcGIS Pro with:
  Conversion Tools > From WKT > Convert WKT to Geometry (or XY Table To Line
  for the section polylines using start/end points, or simply use the
  "WKT Geometry" field with the "Table To Table" / "XY Table To Point" +
  the WKT parsing option in recent Pro versions). The project plan document
  explains the exact import steps.

No external dependencies -- only the Python standard library, so this runs
anywhere, including outside ArcGIS Pro's Python environment.
"""

import csv
import math
import os
import random
from datetime import date, timedelta

random.seed(42)  # reproducible output

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Route geometry setup
# ---------------------------------------------------------------------------
# Fictional route: starts just south of Hannover and runs ~27 km south
# toward the Hildesheim area, in EPSG:25832 (ETRS89 / UTM zone 32N) meters,
# consistent with the CRS used in the PostGIS/FastAPI portfolio project.
START_X, START_Y = 548000.0, 5800000.0  # roughly south Hannover, UTM32N
TOTAL_LENGTH_KM = 27.0
N_SECTIONS = 25

def route_point(chainage_km):
    """Return an (x, y) point along a gently curving fictional route at the
    given chainage (km from start). The curve is a simple sine wiggle so the
    route looks like a real alignment rather than a straight line."""
    t = chainage_km / TOTAL_LENGTH_KM
    x = START_X + 900 * math.sin(t * math.pi * 2.3)
    y = START_Y - chainage_km * 1000.0  # heading south
    return round(x, 2), round(y, 2)

def wkt_point(x, y):
    return f"POINT ({x} {y})"

def wkt_linestring(points):
    coords = ", ".join(f"{x} {y}" for x, y in points)
    return f"LINESTRING ({coords})"

# ---------------------------------------------------------------------------
# Contractors
# ---------------------------------------------------------------------------
CONTRACTORS = [
    {
        "Contractor_ID": "CTR-01", "Contractor_Name": "Tiefbau Nord GmbH",
        "Contract_Scope": "Open-cut trenching, sections 1-8",
        "Contact_Person": "S. Brandt", "Phone": "+49 511 5551001",
        "Email": "brandt@tiefbaunord.example", "Contract_Start": "2026-02-01",
        "Contract_End": "2026-11-30",
    },
    {
        "Contractor_ID": "CTR-02", "Contractor_Name": "PipelineTech Solutions AG",
        "Contract_Scope": "HDD crossings and specialist works",
        "Contact_Person": "J. Wagner", "Phone": "+49 511 5551002",
        "Email": "wagner@pipelinetech.example", "Contract_Start": "2026-02-15",
        "Contract_End": "2026-12-15",
    },
    {
        "Contractor_ID": "CTR-03", "Contractor_Name": "Erdbau & Kabel AG",
        "Contract_Scope": "Open-cut trenching, sections 9-16",
        "Contact_Person": "M. Keller", "Phone": "+49 511 5551003",
        "Email": "keller@erdbaukabel.example", "Contract_Start": "2026-03-01",
        "Contract_End": "2026-12-01",
    },
    {
        "Contractor_ID": "CTR-04", "Contractor_Name": "Rohrleitungsbau Meyer GmbH",
        "Contract_Scope": "Open-cut trenching, sections 17-25",
        "Contact_Person": "A. Meyer", "Phone": "+49 511 5551004",
        "Email": "meyer@rlb-meyer.example", "Contract_Start": "2026-03-15",
        "Contract_End": "2027-01-15",
    },
    {
        "Contractor_ID": "CTR-05", "Contractor_Name": "InfraGrund Bau GmbH",
        "Contract_Scope": "Access roads and site restoration",
        "Contact_Person": "T. Hoffmann", "Phone": "+49 511 5551005",
        "Email": "hoffmann@infragrund.example", "Contract_Start": "2026-02-01",
        "Contract_End": "2027-02-01",
    },
]

with open(os.path.join(OUT_DIR, "contractors.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(CONTRACTORS[0].keys()))
    writer.writeheader()
    writer.writerows(CONTRACTORS)

# ---------------------------------------------------------------------------
# Construction sections
# ---------------------------------------------------------------------------
STATUS_PLAN = (
    ["Completed"] * 10 + ["In Progress"] * 8 + ["Delayed"] * 4 + ["Not Started"] * 3
)
random.shuffle(STATUS_PLAN)

METHODS = ["Open Cut", "HDD", "Trenchless (Pipe Jacking)"]
PROJECT_START = date(2026, 3, 1)

sections = []
for i in range(N_SECTIONS):
    section_id = f"SEC-{i+1:03d}"
    chain_start = round(i * (TOTAL_LENGTH_KM / N_SECTIONS), 3)
    chain_end = round((i + 1) * (TOTAL_LENGTH_KM / N_SECTIONS), 3)
    length_m = round((chain_end - chain_start) * 1000, 1)

    p_start = route_point(chain_start)
    p_mid = route_point((chain_start + chain_end) / 2)
    p_end = route_point(chain_end)
    geom = wkt_linestring([p_start, p_mid, p_end])

    status = STATUS_PLAN[i]
    contractor = CONTRACTORS[i // 7 % len(CONTRACTORS)]["Contractor_ID"] if i < 20 else CONTRACTORS[4]["Contractor_ID"]

    planned_start = PROJECT_START + timedelta(days=i * 10)
    planned_end = planned_start + timedelta(days=45)

    actual_start = ""
    actual_end = ""
    completion = 0

    if status == "Completed":
        actual_start = (planned_start + timedelta(days=random.randint(-3, 5))).isoformat()
        actual_end = (planned_end + timedelta(days=random.randint(-5, 10))).isoformat()
        completion = 100
    elif status == "In Progress":
        actual_start = (planned_start + timedelta(days=random.randint(-3, 5))).isoformat()
        completion = random.randint(20, 85)
    elif status == "Delayed":
        actual_start = (planned_start + timedelta(days=random.randint(5, 20))).isoformat()
        completion = random.randint(5, 40)
    # Not Started: leave actual_start/end blank, completion 0

    section = {
        "Section_ID": section_id,
        "Route_ID": "ROUTE-01",
        "Section_Name": f"Section {i+1:02d}",
        "Chainage_Start_km": chain_start,
        "Chainage_End_km": chain_end,
        "Length_m": length_m,
        "Status": status,
        "Contractor_ID": contractor,
        "Planned_Start": planned_start.isoformat(),
        "Planned_End": planned_end.isoformat(),
        "Actual_Start": actual_start,
        "Actual_End": actual_end,
        "Completion_Percent": completion,
        "Construction_Method": random.choice(METHODS),
        "Responsible_Person": random.choice(
            ["L. Ahrens", "F. Nowak", "D. Krause", "R. Schmitt"]
        ),
        "Last_Update": (planned_start + timedelta(days=random.randint(1, 60))).isoformat(),
        "WKT_Geometry": geom,
    }
    sections.append(section)

# --- Deliberately introduce controlled data-quality problems -----------------
# These mirror the "corrupted copy" approach used in the other portfolio
# project, so the ArcPy QC script has real, documented issues to catch.
quality_notes = []

# 1) Duplicate Section_ID
sections[24]["Section_ID"] = sections[10]["Section_ID"]
quality_notes.append(
    "Row 25 (originally SEC-025) was given a duplicate Section_ID (same as "
    "row 11, SEC-011) to test duplicate-ID detection."
)

# 2) Completion_Percent out of range
sections[3]["Completion_Percent"] = 130
quality_notes.append(
    "Row 4 (SEC-004) has Completion_Percent = 130 (invalid, must be 0-100) "
    "to test the range check."
)

# 3) Actual_End earlier than Actual_Start
completed_idx = next(i for i, s in enumerate(sections) if s["Status"] == "Completed" and i not in (3, 24))
sections[completed_idx]["Actual_End"] = (
    date.fromisoformat(sections[completed_idx]["Actual_Start"]) - timedelta(days=10)
).isoformat()
quality_notes.append(
    f"Row {completed_idx+1} ({sections[completed_idx]['Section_ID']}) has "
    "Actual_End set before Actual_Start to test the date-order check."
)

# 4) Completed section with Completion_Percent below 100
other_completed_idx = next(
    i for i, s in enumerate(sections)
    if s["Status"] == "Completed" and i not in (3, 24, completed_idx)
)
sections[other_completed_idx]["Completion_Percent"] = 85
quality_notes.append(
    f"Row {other_completed_idx+1} ({sections[other_completed_idx]['Section_ID']}) "
    "is marked Completed but Completion_Percent = 85, to test the "
    "status-vs-completion business rule."
)

# 5) Missing mandatory attribute (Contractor_ID blank)
sections[7]["Contractor_ID"] = ""
quality_notes.append(
    f"Row 8 ({sections[7]['Section_ID']}) has a blank Contractor_ID to test "
    "the mandatory-field check."
)

# 6) Invalid Status value (not in the domain)
sections[15]["Status"] = "Paused"
quality_notes.append(
    f"Row 16 ({sections[15]['Section_ID']}) has Status = 'Paused', which is "
    "not a valid domain value (valid values: Not Started, In Progress, "
    "Delayed, Completed, On Hold), to test domain validation."
)

with open(os.path.join(OUT_DIR, "sections.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(sections[0].keys()))
    writer.writeheader()
    writer.writerows(sections)

# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------
ISSUE_TYPES = [
    "Utility Clash", "Environmental", "Safety", "Design Conflict",
    "Quality Defect", "Access", "Delay",
]
SEVERITIES = ["Low", "Medium", "High", "Critical"]
ISSUE_STATUSES = ["Open", "In Progress", "Resolved", "Closed"]

issues = []
N_ISSUES = 15
issue_section_sample = random.sample(range(N_SECTIONS), k=N_ISSUES)
for n, sec_idx in enumerate(issue_section_sample):
    sec = sections[sec_idx]
    chain = random.uniform(float(sec["Chainage_Start_km"]), float(sec["Chainage_End_km"]))
    x, y = route_point(chain)
    reported = date.fromisoformat(sec["Planned_Start"]) + timedelta(days=random.randint(5, 80))
    status = random.choice(ISSUE_STATUSES)
    resolved = ""
    if status in ("Resolved", "Closed"):
        resolved = (reported + timedelta(days=random.randint(2, 20))).isoformat()

    severity = random.choices(SEVERITIES, weights=[4, 4, 2, 1])[0]

    issue = {
        "Issue_ID": f"ISS-{n+1:03d}",
        "Section_ID": sec["Section_ID"] if sec_idx not in (24,) else f"SEC-{sec_idx+1:03d}",
        "Issue_Type": random.choice(ISSUE_TYPES),
        "Issue_Severity": severity,
        "Description": f"{random.choice(ISSUE_TYPES)} issue identified during routine works.",
        "Date_Reported": reported.isoformat(),
        "Responsible_Person": random.choice(
            ["L. Ahrens", "F. Nowak", "D. Krause", "R. Schmitt"]
        ),
        "Status": status,
        "Date_Resolved": resolved,
        "WKT_Geometry": wkt_point(x, y),
    }
    issues.append(issue)

# Deliberate error: a Critical issue with no Responsible_Person (business rule
# used later for the Power Automate trigger, and a good QC check to add).
issues[0]["Issue_Severity"] = "Critical"
issues[0]["Responsible_Person"] = ""
quality_notes.append(
    f"Issue {issues[0]['Issue_ID']} is Critical severity but has a blank "
    "Responsible_Person, to test that business rule."
)

with open(os.path.join(OUT_DIR, "issues.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(issues[0].keys()))
    writer.writeheader()
    writer.writerows(issues)

# ---------------------------------------------------------------------------
# Inspections
# ---------------------------------------------------------------------------
INSPECTION_TYPES = ["Pre-Construction", "Progress", "Final", "Environmental", "Safety"]
INSPECTION_STATUSES = ["Passed", "Failed", "Passed with Comments", "Pending"]

inspections = []
n = 0
for i, sec in enumerate(sections):
    if sec["Status"] == "Not Started":
        continue  # nothing to inspect yet
    n_inspections_here = 1 if sec["Status"] in ("In Progress", "Delayed") else random.randint(1, 2)
    for _ in range(n_inspections_here):
        n += 1
        chain = random.uniform(float(sec["Chainage_Start_km"]), float(sec["Chainage_End_km"]))
        x, y = route_point(chain)
        insp_date = date.fromisoformat(sec["Planned_Start"]) + timedelta(days=random.randint(10, 90))
        status = random.choices(INSPECTION_STATUSES, weights=[6, 1, 2, 1])[0]
        inspections.append({
            "Inspection_ID": f"INS-{n:03d}",
            "Section_ID": sec["Section_ID"],
            "Inspection_Date": insp_date.isoformat(),
            "Inspection_Type": random.choice(INSPECTION_TYPES),
            "Inspector_Name": random.choice(["K. Fischer", "P. Lange", "N. Becker"]),
            "Inspection_Status": status,
            "Findings": "No issues noted." if status == "Passed" else "See comments / follow-up required.",
            "Follow_Up_Required": "Yes" if status in ("Failed", "Passed with Comments") else "No",
            "WKT_Geometry": wkt_point(x, y),
        })

with open(os.path.join(OUT_DIR, "inspections.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(inspections[0].keys()))
    writer.writeheader()
    writer.writerows(inspections)

# ---------------------------------------------------------------------------
# Documentation of deliberate errors
# ---------------------------------------------------------------------------
with open(os.path.join(OUT_DIR, "known_data_quality_issues.md"), "w", encoding="utf-8") as f:
    f.write("# Deliberately introduced data-quality issues\n\n")
    f.write(
        "These rows were corrupted on purpose so the ArcPy QC script has "
        "real problems to catch. Use this list to verify the script's "
        "output matches what's actually wrong in the data.\n\n"
    )
    for note in quality_notes:
        f.write(f"- {note}\n")

print(f"Wrote {len(CONTRACTORS)} contractors, {len(sections)} sections, "
      f"{len(issues)} issues, {len(inspections)} inspections to {OUT_DIR}")
