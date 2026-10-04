"""
qc_construction_sections_tool.py

Script-Tool version of qc_construction_sections.py. Same QA/QC logic, but
configured through arcpy.GetParameterAsText() so it can be wired up to an
ArcGIS Pro Script Tool with a real parameter dialog, instead of requiring
the hardcoded CONFIGURATION block at the top of the original script.

PARAMETERS (in this order -- must match the order you add them in the
Script Tool's Parameters tab):
  0: Input Geodatabase          (Workspace, Required, Input)
  1: Sections Feature Class     (String,    Required, Input)  default: ConstructionSections
  2: Issues Feature Class       (String,    Required, Input)  default: ConstructionIssues
  3: Output Report (CSV)        (File,      Required, Output)

Everything below GetParameterAsText() -- the individual check functions,
SECTION_CHECKS / ISSUE_CHECKS lists, run_section_checks(), run_issue_checks()
-- is identical in logic to qc_construction_sections.py. Only the
configuration source (hardcoded constants -> tool parameters) and the
messaging calls (print -> arcpy.AddMessage/AddWarning) changed.
"""

import arcpy
import csv
import os
from datetime import datetime

# ============================================================================
# CONFIGURATION -- now read from the Script Tool's parameter dialog instead
# of hardcoded constants. Falls back to sensible defaults if run standalone
# with no parameters supplied (e.g. testing from the Python window).
# ============================================================================
GDB_PATH = arcpy.GetParameterAsText(0) or r"C:\Users\hajam\ARCGISProjects\GIS_projects\EnergyInfraMonitoring\EnergyInfraMonitoring.gdb"
FEATURE_CLASS = arcpy.GetParameterAsText(1) or "ConstructionSections"
ISSUE_FEATURE_CLASS = arcpy.GetParameterAsText(2) or "ConstructionIssues"
REPORT_PATH = arcpy.GetParameterAsText(3) or os.path.join(
    r"C:\Users\hajam\ARCGISProjects\GIS_projects\EnergyInfraMonitoring\Scripts", "qc_report.csv"
)

EXPECTED_EPSG = 25832

VALID_STATUSES = {"Not Started", "In Progress", "Delayed", "Completed", "On Hold"}

MANDATORY_FIELDS = [
    "Section_ID", "Status", "Contractor_ID", "Planned_Start", "Planned_End",
]

REPORT_FIELDNAMES = ["Table", "OID", "Record_ID", "Check", "Problem"]


# ============================================================================
# INDIVIDUAL CHECKS -- unchanged from qc_construction_sections.py
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
        return []
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
    severity = row.get("Issue_Severity")
    owner = row.get("Responsible_Person")
    if severity == "Critical" and (owner is None or str(owner).strip() == ""):
        return ["Critical-severity issue has no Responsible_Person assigned"]
    return []


def check_geometry_validity(shape, oid):
    problems = []
    if shape is None:
        problems.append("Geometry is null (no shape stored for this feature)")
        return problems
    if shape.length == 0:
        problems.append("Geometry has zero length (empty or degenerate shape)")
    return problems


SECTION_CHECKS = [
    check_mandatory_fields,
    check_invalid_status,
    check_completion_percent_range,
    check_actual_dates_order,
    check_completed_status_vs_percent,
]

ISSUE_CHECKS = [
    check_critical_issue_has_owner,
]


# ============================================================================
# MAIN LOGIC -- identical structure, print() swapped for arcpy.AddMessage()
# ============================================================================

def check_coordinate_system(fc_path):
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
    seen = {}
    for oid, row in all_rows:
        sid = row.get("Section_ID")
        seen.setdefault(sid, []).append(oid)
    return {sid: oids for sid, oids in seen.items() if len(oids) > 1}


def run_section_checks():
    fc_path = os.path.join(GDB_PATH, FEATURE_CLASS)
    arcpy.AddMessage(f"Running QA/QC checks on: {fc_path}")

    report_rows = []

    for problem in check_coordinate_system(fc_path):
        report_rows.append({
            "Table": FEATURE_CLASS, "OID": "N/A", "Record_ID": "N/A",
            "Check": "Coordinate System", "Problem": problem,
        })

    fields = MANDATORY_FIELDS + [
        "Completion_Percent", "Actual_Start", "Actual_End", "SHAPE@",
    ]
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

    arcpy.AddMessage(f"Loaded {len(all_rows)} rows from {FEATURE_CLASS}")

    for oid, row in all_rows:
        section_id = row.get("Section_ID", "N/A")
        for check_fn in SECTION_CHECKS:
            for problem in check_fn(row, oid):
                report_rows.append({
                    "Table": FEATURE_CLASS, "OID": oid, "Record_ID": section_id,
                    "Check": check_fn.__name__, "Problem": problem,
                })

    for oid, row in all_rows:
        shape = row.get("SHAPE@")
        section_id = row.get("Section_ID", "N/A")
        for problem in check_geometry_validity(shape, oid):
            report_rows.append({
                "Table": FEATURE_CLASS, "OID": oid, "Record_ID": section_id,
                "Check": "check_geometry_validity", "Problem": problem,
            })

    duplicates = check_duplicate_section_ids(all_rows)
    for sid, oids in duplicates.items():
        report_rows.append({
            "Table": FEATURE_CLASS, "OID": ", ".join(str(o) for o in oids),
            "Record_ID": sid, "Check": "check_duplicate_section_ids",
            "Problem": f"Section_ID '{sid}' is used by {len(oids)} rows (OIDs: {oids})",
        })

    return report_rows, len(all_rows)


def run_issue_checks():
    fc_path = os.path.join(GDB_PATH, ISSUE_FEATURE_CLASS)
    arcpy.AddMessage(f"Running QA/QC checks on: {fc_path}")

    fields = ["Issue_ID", "Issue_Severity", "Responsible_Person"]
    all_rows = []
    with arcpy.da.SearchCursor(fc_path, ["OID@"] + fields) as cursor:
        for record in cursor:
            oid = record[0]
            row = dict(zip(fields, record[1:]))
            all_rows.append((oid, row))

    arcpy.AddMessage(f"Loaded {len(all_rows)} rows from {ISSUE_FEATURE_CLASS}")

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

    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(report_rows)

    arcpy.AddMessage("\n" + "=" * 60)
    arcpy.AddMessage("QA/QC SUMMARY")
    arcpy.AddMessage("=" * 60)
    arcpy.AddMessage(f"ConstructionSections rows checked:  {section_row_count}")
    arcpy.AddMessage(f"ConstructionIssues rows checked:    {issue_row_count}")

    # Use AddWarning (shows as a yellow warning in the tool dialog, not just
    # a plain message) when problems were found, so the result is visually
    # distinct from a clean run -- a nice bit of tool UX polish.
    if report_rows:
        arcpy.AddWarning(f"Total problems found:               {len(report_rows)}")
    else:
        arcpy.AddMessage("Total problems found:               0")

    problems_by_check = {}
    for r in report_rows:
        key = f"{r['Table']} / {r['Check']}"
        problems_by_check[key] = problems_by_check.get(key, 0) + 1
    for check_name, count in sorted(problems_by_check.items()):
        arcpy.AddMessage(f"  - {check_name}: {count}")

    arcpy.AddMessage(f"\nFull report written to: {REPORT_PATH}")
    arcpy.AddMessage(f"Run completed at: {datetime.now().isoformat(timespec='seconds')}")

    if not report_rows:
        arcpy.AddMessage("\nNo problems found -- data passed all QC checks.")

    # Set the output parameter explicitly so ArcGIS Pro's GP pane recognizes
    # the CSV as this tool's derived output (e.g. for adding it to a model).
    arcpy.SetParameterAsText(3, REPORT_PATH)


if __name__ == "__main__":
    run()
