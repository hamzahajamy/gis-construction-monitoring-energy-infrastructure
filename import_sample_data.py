"""
import_sample_data.py

Loads the sample CSV data (contractors, sections, issues, inspections) into
the EnergyInfraMonitoring geodatabase, converting each row's WKT_Geometry
column into a real ArcGIS geometry.

WHY A SCRIPT INSTEAD OF A GUI IMPORT
--------------------------------------
ArcGIS Pro doesn't have a clean built-in wizard for turning a WKT text
column into line/point features on import. Rather than fight that, this
script does it directly with arcpy.FromWKT() and an insert cursor -- which
is also a more realistic example of how a GIS data engineer actually loads
external data than a one-off manual import would be.

HOW TO RUN IT
--------------
Same as the QC script: ArcGIS Pro's Python window, or the Python Command
Prompt that ships with Pro. Before running, edit the two paths in the
CONFIGURATION section below.

WHAT IT DOES
-------------
For each of the 4 CSVs, it reads every row and inserts it into the matching
table/feature class, doing three kinds of conversion the geodatabase needs
that the raw CSV strings don't provide on their own:
  - date strings ("2026-03-01") -> Python datetime objects
  - empty strings ("") -> None (so nullable fields stay properly null,
    instead of being stored as the literal text "")
  - the WKT_Geometry column -> an arcpy Geometry object, via arcpy.FromWKT()

It does NOT delete existing rows first -- if you run it twice you'll get
duplicate rows. If you need to re-run it, truncate the tables first
(right-click each feature class/table -> Manage -> Truncate Table), which
mirrors a real "reload" data pipeline step.
"""

import arcpy
import csv
import os
from datetime import datetime

# ============================================================================
# CONFIGURATION -- edit these two lines for your machine
# ============================================================================
GDB_PATH = r"C:\Users\hajam\ARCGISProjects\GIS_projects\EnergyInfraMonitoring\EnergyInfraMonitoring.gdb"
CSV_DIR = r"C:\Users\hajam\ARCGISProjects\GIS_projects\EnergyInfraMonitoring\SampleData"

FEATURE_DATASET = "ConstructionMonitoring"
SPATIAL_REFERENCE = arcpy.SpatialReference(25832)  # ETRS89 / UTM zone 32N


# ============================================================================
# HELPERS
# ============================================================================

def parse_date(value):
    """Converts a 'YYYY-MM-DD' string to a datetime object, or returns None
    for blank/missing values so the field stays properly null."""
    if value is None or str(value).strip() == "":
        return None
    return datetime.strptime(value.strip(), "%Y-%m-%d")


def parse_int(value):
    if value is None or str(value).strip() == "":
        return None
    return int(float(value))  # float() first in case it's like "20.0"


def parse_float(value):
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def clean_text(value):
    """Empty string -> None, otherwise the trimmed string."""
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()


def load_csv(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ============================================================================
# ONE LOADER FUNCTION PER TABLE
# Each one lists exactly which CSV columns go to which geodatabase fields,
# and how each value needs to be converted. Keeping them separate (rather
# than one generic "smart" loader) makes it obvious what's happening for
# each table, at the cost of a little repetition -- worth it for a script
# this size.
# ============================================================================

def load_contractors():
    rows = load_csv(os.path.join(CSV_DIR, "contractors.csv"))
    target = os.path.join(GDB_PATH, "Contractors")
    fields = [
        "Contractor_ID", "Contractor_Name", "Contract_Scope",
        "Contact_Person", "Phone", "Email", "Contract_Start", "Contract_End",
    ]
    with arcpy.da.InsertCursor(target, fields) as cursor:
        for row in rows:
            cursor.insertRow((
                clean_text(row["Contractor_ID"]),
                clean_text(row["Contractor_Name"]),
                clean_text(row["Contract_Scope"]),
                clean_text(row["Contact_Person"]),
                clean_text(row["Phone"]),
                clean_text(row["Email"]),
                parse_date(row["Contract_Start"]),
                parse_date(row["Contract_End"]),
            ))
    print(f"Loaded {len(rows)} rows into Contractors")


def load_sections():
    rows = load_csv(os.path.join(CSV_DIR, "sections.csv"))
    target = os.path.join(GDB_PATH, FEATURE_DATASET, "ConstructionSections")
    fields = [
        "Section_ID", "Route_ID", "Section_Name", "Chainage_Start_km",
        "Chainage_End_km", "Length_m", "Status", "Contractor_ID",
        "Planned_Start", "Planned_End", "Actual_Start", "Actual_End",
        "Completion_Percent", "Construction_Method", "Responsible_Person",
        "Last_Update", "SHAPE@",
    ]
    with arcpy.da.InsertCursor(target, fields) as cursor:
        for row in rows:
            geom = arcpy.FromWKT(row["WKT_Geometry"], SPATIAL_REFERENCE)
            cursor.insertRow((
                clean_text(row["Section_ID"]),
                clean_text(row["Route_ID"]),
                clean_text(row["Section_Name"]),
                parse_float(row["Chainage_Start_km"]),
                parse_float(row["Chainage_End_km"]),
                parse_float(row["Length_m"]),
                clean_text(row["Status"]),
                clean_text(row["Contractor_ID"]),
                parse_date(row["Planned_Start"]),
                parse_date(row["Planned_End"]),
                parse_date(row["Actual_Start"]),
                parse_date(row["Actual_End"]),
                parse_int(row["Completion_Percent"]),
                clean_text(row["Construction_Method"]),
                clean_text(row["Responsible_Person"]),
                parse_date(row["Last_Update"]),
                geom,
            ))
    print(f"Loaded {len(rows)} rows into ConstructionSections")


def load_issues():
    rows = load_csv(os.path.join(CSV_DIR, "issues.csv"))
    target = os.path.join(GDB_PATH, FEATURE_DATASET, "ConstructionIssues")
    fields = [
        "Issue_ID", "Section_ID", "Issue_Type", "Issue_Severity",
        "Description", "Date_Reported", "Responsible_Person", "Status",
        "Date_Resolved", "SHAPE@",
    ]
    with arcpy.da.InsertCursor(target, fields) as cursor:
        for row in rows:
            geom = arcpy.FromWKT(row["WKT_Geometry"], SPATIAL_REFERENCE)
            cursor.insertRow((
                clean_text(row["Issue_ID"]),
                clean_text(row["Section_ID"]),
                clean_text(row["Issue_Type"]),
                clean_text(row["Issue_Severity"]),
                clean_text(row["Description"]),
                parse_date(row["Date_Reported"]),
                clean_text(row["Responsible_Person"]),
                clean_text(row["Status"]),
                parse_date(row["Date_Resolved"]),
                geom,
            ))
    print(f"Loaded {len(rows)} rows into ConstructionIssues")


def load_inspections():
    rows = load_csv(os.path.join(CSV_DIR, "inspections.csv"))
    target = os.path.join(GDB_PATH, FEATURE_DATASET, "Inspections")
    fields = [
        "Inspection_ID", "Section_ID", "Inspection_Date", "Inspection_Type",
        "Inspector_Name", "Inspection_Status", "Findings",
        "Follow_Up_Required", "SHAPE@",
    ]
    with arcpy.da.InsertCursor(target, fields) as cursor:
        for row in rows:
            geom = arcpy.FromWKT(row["WKT_Geometry"], SPATIAL_REFERENCE)
            cursor.insertRow((
                clean_text(row["Inspection_ID"]),
                clean_text(row["Section_ID"]),
                parse_date(row["Inspection_Date"]),
                clean_text(row["Inspection_Type"]),
                clean_text(row["Inspector_Name"]),
                clean_text(row["Inspection_Status"]),
                clean_text(row["Findings"]),
                clean_text(row["Follow_Up_Required"]),
                geom,
            ))
    print(f"Loaded {len(rows)} rows into Inspections")


# ============================================================================
# MAIN
# ============================================================================

def run():
    print(f"Loading sample data from {CSV_DIR}")
    print(f"Into geodatabase: {GDB_PATH}\n")

    # Running this inside ArcGIS Pro's own Python window (as opposed to a
    # standalone script run outside Pro) means the geodatabase is already
    # "open" via the current project/map. Any edits made through da cursors
    # in that situation must happen inside an explicit edit session, or
    # ArcGIS Pro raises "Objects in this class cannot be updated outside an
    # edit session." Wrapping everything in one arcpy.da.Editor session also
    # makes the whole load one atomic transaction: if any table fails
    # partway through, stopEditing(False) discards everything rather than
    # leaving the geodatabase in a half-loaded state.
    edit = arcpy.da.Editor(GDB_PATH)
    edit.startEditing(False, True)
    edit.startOperation()
    try:
        # Order matters a little here: Contractors first, since sections
        # reference Contractor_ID (not enforced by the database unless
        # you've built the relationship class yet, but it's the logical
        # order either way -- load the thing being referenced before the
        # thing referencing it).
        load_contractors()
        load_sections()
        load_issues()
        load_inspections()
    except Exception:
        edit.abortOperation()
        edit.stopEditing(False)  # False = discard changes made so far
        raise
    else:
        edit.stopOperation()
        edit.stopEditing(True)  # True = save changes

    print("\nDone. Open each layer's attribute table in ArcGIS Pro to spot-check.")


if __name__ == "__main__":
    run()
