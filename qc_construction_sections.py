"""
qc_construction_sections.py

Quality-control (QA/QC) script for the Energy Infrastructure Construction
Monitoring geodatabase. Covers two tables:
  - ConstructionSections: attribute, domain, date-order, and geometry checks
  - ConstructionIssues:   Critical-severity issues must have a Responsible_Person

WHAT THIS SCRIPT DOES
----------------------
It opens both feature classes, checks every row against a set of business
rules, and writes a single CSV report listing every problem it finds (which
table it came from, the record's OID/Record_ID, which check failed, and a
human-readable description), plus a short summary printed to the console.
Nothing in the data is changed -- this is a read-only checker, not an
auto-fixer.

HOW TO RUN IT
--------------
This script uses `arcpy`, which is only available inside ArcGIS Pro's own
Python environment. Two ways to run it:

  1. ArcGIS Pro > View > Python window, then:
         exec(open(r"C:\path\to\qc_construction_sections.py", encoding="utf-8").read())

  2. From the "Python Command Prompt" that ships with ArcGIS Pro (Start Menu
     > ArcGIS > Python Command Prompt), run:
         python qc_construction_sections.py

Before running, edit the CONFIGURATION section below so GDB_PATH points at
your file geodatabase.

WHY THIS SHAPE
--------------
Each check is its own small function that takes one row (as a dictionary)
and returns a list of problem strings for that row (empty list = no
problems). That keeps each rule easy to read, easy to test on its own, and
easy to extend later (e.g. add a check for Environmental Constraint overlaps)
without touching the others.
"""

import arcpy
import csv
import os
from datetime import datetime

# ============================================================================
# CONFIGURATION -- edit these lines for your project
# ============================================================================
GDB_PATH = r"C:\Users\hajam\ARCGISProjects\GIS_projects\EnergyInfraMonitoring\EnergyInfraMonitoring.gdb"
FEATURE_CLASS = "ConstructionSections"            # <-- feature class name
ISSUE_FEATURE_CLASS = "ConstructionIssues"        # <-- for the Critical-issue-owner check

# Expected coordinate system for the project (ETRS89 / UTM zone 32N).
# This is the EPSG code, not the name -- arcpy.Describe gives you the code.
EXPECTED_EPSG = 25832

# The valid values for the Status domain. Keep this in sync with the coded
# value domain you defined in the geodatabase (dom_Status).
VALID_STATUSES = {"Not Started", "In Progress", "Delayed", "Completed", "On Hold"}

# Fields that must never be null or empty for a section to be considered valid.
MANDATORY_FIELDS = [
    "Section_ID", "Status", "Contractor_ID", "Planned_Start", "Planned_End",
]

# Where to write the report. Hardcoded rather than derived from __file__,
# because __file__ isn't defined when this script is run via exec() inside
# ArcGIS Pro's interactive Python window (only when run as a standalone .py
# file) -- same category of Pro-vs-standalone difference as the edit-session
# requirement in import_sample_data.py.
OUTPUT_DIR = r"C:\Users\hajam\ARCGISProjects\GIS_projects\EnergyInfraMonitoring\Scripts"
REPORT_PATH = os.path.join(OUTPUT_DIR, "qc_report.csv")

# Column order for the CSV report. "Table" records which feature class the
# problem came from, and "Record_ID" holds whichever ID field applies
# (Section_ID for ConstructionSections rows, Issue_ID for ConstructionIssues
# rows) so both tables' findings can live in one report.
REPORT_FIELDNAMES = ["Table", "OID", "Record_ID", "Check", "Problem"]


# ============================================================================
# INDIVIDUAL CHECKS
# Each function receives one row as a dict of {field_name: value} plus the
# row's OID (ObjectID), and returns a list of problem-description strings.
# An empty list means the row passed that check.
# ============================================================================

def check_mandatory_fields(row, oid):
    problems = []
    for field in MANDATORY_FIELDS:
        value = row.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            problems.append(f"Missing mandatory attribute '{field}'")
    return problems


def check_invalid_status(row, oid):
    status = row.get("Status")
    if status and status not in VALID_STATUSES:
        return [f"Invalid Status value '{status}' (not in the approved domain)"]
    return []


def check_completion_percent_range(row, oid):
    value = row.get("Completion_Percent")
    if value is None:
        return []  # already caught by the mandatory-field check if required
    if not (0 <= value <= 100):
        return [f"Completion_Percent = {value} is outside the valid 0-100 range"]
    return []


def check_actual_dates_order(row, oid):
    start = row.get("Actual_Start")
    end = row.get("Actual_End")
    if start and end and end < start:
        return [f"Actual_End ({end}) is earlier than Actual_Start ({start})"]
    return []


def check_completed_status_vs_percent(row, oid):
    status = row.get("Status")
    completion = row.get("Completion_Percent")
    if status == "Completed" and completion is not None and completion < 100:
        return [f"Status is 'Completed' but Completion_Percent = {completion} (should be 100)"]
    return []


def check_critical_issue_has_owner(row, oid):
    """Applies to the ConstructionIssues table, not sections -- called
    separately in run_issue_checks() below."""
    severity = row.get("Issue_Severity")
    owner = row.get("Responsible_Person")
    if severity == "Critical" and (owner is None or str(owner).strip() == ""):
        return ["Critical-severity issue has no Responsible_Person assigned"]
    return []


def check_geometry_validity(shape, oid):
    """Flags null, empty, or self-intersecting/invalid geometries."""
    problems = []
    if shape is None:
        problems.append("Geometry is null (no shape stored for this feature)")
        return problems
    if shape.length == 0:
        problems.append("Geometry has zero length (empty or degenerate shape)")
    # arcpy geometry objects can report basic validity issues themselves;
    # for a more thorough check you can also run the "Check Geometry" tool
    # (arcpy.management.CheckGeometry) over the whole feature class, which
    # is more complete than a per-row check for things like self-intersections.
    return problems


# Rules that apply to every row of ConstructionSections, in the order we
# want them reported.
SECTION_CHECKS = [
    check_mandatory_fields,
    check_invalid_status,
    check_completion_percent_range,
    check_actual_dates_order,
    check_completed_status_vs_percent,
]

# Rules that apply to every row of ConstructionIssues.
ISSUE_CHECKS = [
    check_critical_issue_has_owner,
]


# ============================================================================
# MAIN LOGIC
# ============================================================================

def check_coordinate_system(fc_path):
    """Returns a list with one problem string if the feature class isn't in
    the expected coordinate system, otherwise an empty list."""
    desc = arcpy.Describe(fc_path)
    sr = desc.spatialReference
    if sr is None or sr.factoryCode != EXPECTED_EPSG:
        actual = sr.name if sr else "Unknown/undefined"
        actual_code = sr.factoryCode if sr else "N/A"
        return [(
            f"Feature class coordinate system is '{actual}' (EPSG:{actual_code}), "
            f"expected EPSG:{EXPECTED_EPSG} (ETRS89 / UTM zone 32N)"
        )]
    return []


def check_duplicate_section_ids(all_rows):
    """Returns a dict of {Section_ID: [oids]} for every Section_ID that
    appears more than once."""
    seen = {}
    for oid, row in all_rows:
        sid = row.get("Section_ID")
        seen.setdefault(sid, []).append(oid)
    return {sid: oids for sid, oids in seen.items() if len(oids) > 1}


def run_section_checks():
    """Runs all ConstructionSections checks and returns (report_rows, row_count)."""
    fc_path = os.path.join(GDB_PATH, FEATURE_CLASS)
    print(f"Running QA/QC checks on: {fc_path}")

    report_rows = []

    # --- 1) Coordinate system check (once, for the whole feature class) ----
    for problem in check_coordinate_system(fc_path):
        report_rows.append({
            "Table": FEATURE_CLASS, "OID": "N/A", "Record_ID": "N/A",
            "Check": "Coordinate System", "Problem": problem,
        })

    # --- 2) Read every row once into memory (fine for a few hundred to a
    #        few thousand rows -- for very large datasets you would stream
    #        with the cursor instead of collecting a list). ------------------
    fields = MANDATORY_FIELDS + [
        "Completion_Percent", "Actual_Start", "Actual_End", "SHAPE@",
    ]
    # de-duplicate field list while keeping order
    seen_fields = []
    for f in fields:
        if f not in seen_fields:
            seen_fields.append(f)
    fields = seen_fields

    all_rows = []
    with arcpy.da.SearchCursor(fc_path, ["OID@"] + fields) as cursor:
        for record in cursor:
            oid = record[0]
            row = dict(zip(fields, record[1:]))
            all_rows.append((oid, row))

    print(f"Loaded {len(all_rows)} rows from {FEATURE_CLASS}")

    # --- 3) Per-row attribute checks ---------------------------------------
    for oid, row in all_rows:
        section_id = row.get("Section_ID", "N/A")
        for check_fn in SECTION_CHECKS:
            for problem in check_fn(row, oid):
                report_rows.append({
                    "Table": FEATURE_CLASS, "OID": oid, "Record_ID": section_id,
                    "Check": check_fn.__name__, "Problem": problem,
                })

    # --- 4) Per-row geometry checks -----------------------------------------
    for oid, row in all_rows:
        shape = row.get("SHAPE@")
        section_id = row.get("Section_ID", "N/A")
        for problem in check_geometry_validity(shape, oid):
            report_rows.append({
                "Table": FEATURE_CLASS, "OID": oid, "Record_ID": section_id,
                "Check": "check_geometry_validity", "Problem": problem,
            })

    # --- 5) Duplicate Section_ID check (needs all rows at once) ------------
    duplicates = check_duplicate_section_ids(all_rows)
    for sid, oids in duplicates.items():
        report_rows.append({
            "Table": FEATURE_CLASS, "OID": ", ".join(str(o) for o in oids),
            "Record_ID": sid, "Check": "check_duplicate_section_ids",
            "Problem": f"Section_ID '{sid}' is used by {len(oids)} rows (OIDs: {oids})",
        })

    return report_rows, len(all_rows)


def run_issue_checks():
    """Runs all ConstructionIssues checks and returns (report_rows, row_count)."""
    fc_path = os.path.join(GDB_PATH, ISSUE_FEATURE_CLASS)
    print(f"Running QA/QC checks on: {fc_path}")

    fields = ["Issue_ID", "Issue_Severity", "Responsible_Person"]
    all_rows = []
    with arcpy.da.SearchCursor(fc_path, ["OID@"] + fields) as cursor:
        for record in cursor:
            oid = record[0]
            row = dict(zip(fields, record[1:]))
            all_rows.append((oid, row))

    print(f"Loaded {len(all_rows)} rows from {ISSUE_FEATURE_CLASS}")

    report_rows = []
    for oid, row in all_rows:
        issue_id = row.get("Issue_ID", "N/A")
        for check_fn in ISSUE_CHECKS:
            for problem in check_fn(row, oid):
                report_rows.append({
                    "Table": ISSUE_FEATURE_CLASS, "OID": oid, "Record_ID": issue_id,
                    "Check": check_fn.__name__, "Problem": problem,
                })

    return report_rows, len(all_rows)


def run():
    section_report, section_row_count = run_section_checks()
    issue_report, issue_row_count = run_issue_checks()
    report_rows = section_report + issue_report

    # --- Write the combined CSV report --------------------------------------
    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(report_rows)

    # --- Print a summary to the console ----------------------------------
    print("\n" + "=" * 60)
    print("QA/QC SUMMARY")
    print("=" * 60)
    print(f"ConstructionSections rows checked:  {section_row_count}")
    print(f"ConstructionIssues rows checked:    {issue_row_count}")
    print(f"Total problems found:               {len(report_rows)}")

    problems_by_check = {}
    for r in report_rows:
        key = f"{r['Table']} / {r['Check']}"
        problems_by_check[key] = problems_by_check.get(key, 0) + 1
    for check_name, count in sorted(problems_by_check.items()):
        print(f"  - {check_name}: {count}")

    print(f"\nFull report written to: {REPORT_PATH}")
    print(f"Run completed at: {datetime.now().isoformat(timespec='seconds')}")

    if not report_rows:
        print("\nNo problems found -- data passed all QC checks.")


if __name__ == "__main__":
    run()
