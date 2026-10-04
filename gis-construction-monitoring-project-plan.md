# GIS-Based Construction Progress Monitoring for Energy Infrastructure

Portfolio project plan — targeting GIS / geodata management roles in energy infrastructure (Germany)

**Fictional scenario:** NordEnergie Infrastruktur GmbH is building a ~27 km hydrogen pipeline ("H2-Leitung Hannover–Hildesheim") south of Hannover. The GIS supports construction managers, GIS specialists, field engineers, and project managers tracking progress, quality, and issues along the route. All company names, people, and exact coordinates in the sample data are invented — this does not represent a real infrastructure project.

This is a second, separate portfolio piece from your PostGIS/FastAPI project. Where that one demonstrates open-source geospatial engineering, this one demonstrates the Esri/ArcGIS ecosystem — the two together cover most of what German GIS job postings ask for.

**Assumption flagged:** everything below assumes ArcGIS Pro access (university Esri license or trial) and a personal/trial ArcGIS Online account for the Dashboard and Field Maps sections. Full ArcGIS Enterprise Server is not something we'll actually install — Section 10 is a deployment plan you can discuss in an interview, not a running server.

---

## Phasing

Build in this order — each phase produces something demonstrable on its own, so if time runs short you stop with a complete, working artifact rather than a pile of half-finished features.

- **Phase 1 (core, do this first):** geodatabase + domains + relationships, import sample data, build the status-symbolized progress map, run the ArcPy QC script and fix what it finds.
- **Phase 2:** publish hosted feature layers to ArcGIS Online, build the Dashboard, package the QC script as a Script Tool.
- **Phase 3:** design the Field Maps form, design the Power Automate workflow.
- **Phase 4:** write the Enterprise deployment plan, then package everything into the portfolio (README, diagram, CV bullets, LinkedIn, interview prep).

---

## 1. Data model

Coordinate system: **EPSG:25832 (ETRS89 / UTM zone 32N)** — the correct projected CRS for this part of Germany, and the same one used in your other portfolio project (a small but real consistency point across both).

### Feature classes / tables

**ProjectRoute** (Polyline) — one record, the overall alignment
| Field | Type | Notes |
|---|---|---|
| Route_ID | Text(10) | PK |
| Route_Name | Text(100) | |
| Infrastructure_Type | Text, domain `dom_InfraType` | Power Cable / Gas Pipeline / Hydrogen Pipeline / District Heating |
| Total_Length_km | Double | |
| Owner_Company | Text(100) | |
| Created_Date, Last_Update | Date | |

**ConstructionSections** (Polyline) — the main progress-tracking unit, ~25 records
| Field | Type | Notes |
|---|---|---|
| Section_ID | Text(10) | PK, unique, e.g. `SEC-001` |
| Route_ID | Text(10) | FK → ProjectRoute |
| Section_Name | Text(50) | |
| Chainage_Start_km, Chainage_End_km | Double | |
| Length_m | Double | |
| Status | Text, domain `dom_Status` | Not Started / In Progress / Delayed / Completed / On Hold |
| Contractor_ID | Text(10) | FK → Contractors |
| Planned_Start, Planned_End | Date | mandatory |
| Actual_Start, Actual_End | Date | nullable until work begins |
| Completion_Percent | Short Integer | 0–100 |
| Construction_Method | Text, domain `dom_ConstructionMethod` | Open Cut / HDD / Trenchless |
| Responsible_Person | Text(50) | |
| Last_Update | Date | |

**ConstructionSites** (Point) — joint bays, valve stations, laydown yards
Site_ID (PK), Section_ID (FK), Site_Type (domain: Joint Bay / Valve Station / Laydown Yard / Compound), Status, Area_m2, Contractor_ID, Last_Update

**AccessRoads** (Polyline)
Road_ID (PK), Section_ID (FK), Road_Type (domain: Existing / Temporary / To Be Restored), Surface_Type, Status (domain: Open / Restored / Closed), Last_Update

**Crossings** (Point)
Crossing_ID (PK), Section_ID (FK), Crossing_Type (domain: Road / Rail / River / Existing Pipeline / Existing Cable), Crossing_Method (domain: Open Cut / HDD / Bore), Permit_Status (domain: Not Applied / Applied / Approved / Rejected), Status, Last_Update

**Inspections** (Point) — ~27 sample records
Inspection_ID (PK), Section_ID (FK), Inspection_Date, Inspection_Type (domain: Pre-Construction / Progress / Final / Environmental / Safety), Inspector_Name, Inspection_Status (domain: Passed / Failed / Passed with Comments / Pending), Findings, Follow_Up_Required (domain: Yes/No)

**ConstructionIssues** (Point) — ~15 sample records
Issue_ID (PK), Section_ID (FK), Issue_Type (domain: Design Conflict / Environmental / Safety / Delay / Utility Clash / Quality Defect / Access), Issue_Severity (domain: Low / Medium / High / Critical), Description, Date_Reported, Responsible_Person, Status (domain: Open / In Progress / Resolved / Closed), Date_Resolved, and an **attachment** enabled for photos

**EnvironmentalConstraints** (Polygon)
Constraint_ID (PK), Constraint_Type (domain: Nature Reserve / Water Protection / Noise-Sensitive / Archaeological / Species Protection Buffer), Restriction_Description, Season_Restriction, Last_Update

**Parcels** (Polygon)
Parcel_ID (PK), Owner_Ref (a generic reference, not a real name — this is fictional data), Parcel_Area_m2, Easement_Status (domain: Not Started / Negotiation / Agreed / Compensated)

**Contractors** (standalone Table, not spatial) — 5 sample records
Contractor_ID (PK), Contractor_Name, Contract_Scope, Contact_Person, Phone, Email, Contract_Start, Contract_End

### Relationship classes
- `Route_Has_Sections`: ProjectRoute 1—∞ ConstructionSections (Route_ID)
- `Sections_Use_Contractor`: Contractors 1—∞ ConstructionSections (Contractor_ID) — this is the one to enforce as a relationship class rather than a free-text field, since it's a real referential-integrity constraint
- `Section_Has_Inspections`: ConstructionSections 1—∞ Inspections (Section_ID)
- `Section_Has_Issues`: ConstructionSections 1—∞ ConstructionIssues (Section_ID)
- `Section_Has_Sites`, `Section_Has_AccessRoads`, `Section_Has_Crossings`: same pattern

### Coded value domains
`dom_Status`, `dom_InfraType`, `dom_ConstructionMethod`, `dom_SiteType`, `dom_RoadType`, `dom_CrossingType`, `dom_CrossingMethod`, `dom_PermitStatus`, `dom_InspectionType`, `dom_InspectionStatus`, `dom_IssueType`, `dom_IssueSeverity`, `dom_IssueStatus`, `dom_EasementStatus`, `dom_YesNo` — each as a Coded Value Domain assigned to its field, not a free-text field. This is the single most "shows you understand geodata management" detail in the whole schema — free-text status fields are exactly what makes real infrastructure GIS data unreliable.

### Validation / business rules
These become both **Attribute Rules** in the geodatabase (where practical) and checks in the ArcPy QC script (which catches what attribute rules can't, and gives you something to run and show):
- Section_ID unique (no duplicates)
- Completion_Percent between 0–100
- If Status = "Completed" then Completion_Percent must = 100
- Actual_End ≥ Actual_Start when both are populated
- Mandatory fields (Section_ID, Status, Contractor_ID, Planned_Start, Planned_End) never null
- Status must be one of the domain's valid values
- Critical-severity issues must have a Responsible_Person assigned
- Feature class coordinate system must be EPSG:25832

---

## 2. Sample data

Provided as ready-to-use CSV files (generated with a dependency-free Python script, `generate_sample_data.py`, included so you can regenerate or extend it):
- `contractors.csv` — 5 contractors
- `sections.csv` — 25 sections, with a `WKT_Geometry` column (LineString, EPSG:25832)
- `issues.csv` — 15 issues, with a `WKT_Geometry` column (Point)
- `inspections.csv` — 27 inspections, with a `WKT_Geometry` column (Point)
- `known_data_quality_issues.md` — documents 6 deliberately corrupted rows (duplicate Section_ID, out-of-range completion %, reversed dates, a "Completed" section under 100%, a missing mandatory field, an invalid status value, plus a Critical issue with no owner) so you can verify the QC script actually catches real problems, not just run cleanly against clean data

**Importing into ArcGIS Pro:** the WKT columns import cleanly via **Analysis Tools → XY Table To Point** for the point layers (parse the WKT with **Table To Ellipse/Convert WKT to Geometry**, or simpler: use **XY Table To Point** after splitting WKT into X/Y columns — the plan below uses the more direct route). For the section polylines, use **Data Management → Features → XY To Line**, or the more general **Table To Geodatabase** followed by pasting the WKT into ArcGIS Pro's "Convert WKT to Geometry" geoprocessing tool (available in current Pro versions under Data Management Tools → Features). We'll pin down the exact click-path together once you're in Pro and can tell me your version — this varies slightly release to release.

Sites, access roads, crossings, environmental constraints, and parcels are schema-only for now — add a handful of sample rows for those in Phase 2 once the core workflow is proven; they don't carry new skills to demonstrate on their own.

---

## 3. ArcGIS Pro workflow (Phase 1)

1. **Create the file geodatabase**: Catalog pane → right-click a folder → New → File Geodatabase. Name it something like `EnergyInfraMonitoring.gdb`.
2. **Set the coordinate system** at the geodatabase feature dataset level: create a Feature Dataset inside the gdb, set its spatial reference to ETRS89 / UTM zone 32N (EPSG:25832), and put all the spatial feature classes inside it — this guarantees they all share one CRS, which matters for the spatial joins later.
3. **Create the domains** first (Catalog → right-click the geodatabase → Properties → Domains tab), since feature classes reference them at creation time.
4. **Create the feature classes** (polyline/point/polygon per the table above) inside the feature dataset, table by table, assigning field types and domains as you go. Create `Contractors` as a standalone table (not in the feature dataset, since it's non-spatial).
5. **Import the sample data**: bring in the CSVs, convert the WKT to geometry, and field-map into the feature classes you just created (Append or Table To Table, matching schema).
6. **Create relationship classes** (Catalog → right-click geodatabase → New → Relationship Class) for each FK pair listed above — set cardinality (1:M), and for `Sections_Use_Contractor` specifically, this is a good place to demonstrate you understand composite vs. simple relationships (use simple, since deleting a contractor shouldn't cascade-delete sections).
7. **Symbology**: symbolize ConstructionSections by the Status field (unique values renderer) — colors specified in Section 4 below.
8. **Labeling**: label sections with Section_ID at small scale, switch to Section_Name + Completion_Percent at larger scale (use a label class with a scale range, or an Arcade label expression that concatenates the two).
9. **Definition queries**: build a couple of demo definition queries on a duplicated layer, e.g. `Status = 'Delayed'` or `Issue_Severity = 'Critical' AND Status <> 'Closed'` — useful both as a map layer and to show you know definition queries aren't the same thing as filters applied client-side.
10. **Editing workflow**: practice the actual edit session workflow (Edit tab → Create Features, attribute inspector, Save edits) on at least a couple of records — this is what you'd describe if asked "how would a GIS specialist maintain this data day to day."
11. **QC checks**: run `qc_construction_sections.py` (Section 7 below) against the imported data and confirm it catches the deliberately corrupted rows documented in `known_data_quality_issues.md`. Fix the real ones, keep a "before/after" QC report — a genuinely strong thing to screenshot for the portfolio.

---

## 4. Construction progress map

Symbolize **ConstructionSections** by Status with a sequential-feeling but distinct palette that reads clearly against an OSM/topographic basemap:
- Not Started — light grey (`#B0B0B0`)
- In Progress — amber/orange (`#F2A93B`)
- Delayed — red (`#D64545`)
- Completed — green (`#3F9142`)

Use a moderately thick line width (e.g. 3pt) so sections are legible at route scale, with a thin dark outline/casing if the basemap is busy. Overlay:
- **ConstructionIssues** as point markers, sized or colored by Issue_Severity (small circles for Low/Medium, a larger red triangle or exclamation icon for Critical) — severity should be the dominant visual signal, not issue type.
- **Inspections** as a smaller, muted point symbol (e.g. a checkmark for Passed, an X for Failed), toggleable as its own layer so the map isn't cluttered by default.

Add a scale bar and north arrow (standard for any construction/engineering map), a legend, and — since this is a linear project — consider a chainage-referenced inset or a simple "profile strip" layout if you want a second, more advanced map later. Keep the base map muted (light gray canvas or a simplified topo) so the status colors stay the visual focus; this is the single cartographic choice that most separates a "looks professional" map from a "looks like a GIS class exercise" map.

---

## 5. ArcGIS Dashboard (Phase 2)

Build this against the hosted feature layers once published to ArcGIS Online.

**KPI indicators (top row):**
- Total route length (sum of Length_m across all sections, converted to km) — Indicator widget, statistic = Sum
- Completed route length — Indicator with a filter `Status = 'Completed'`
- Overall completion % — Indicator using an Arcade expression: `Sum(Length_m × Completion_Percent/100) / Sum(Length_m)` (length-weighted, more honest than a simple average of percentages)
- Sections in progress / Delayed sections / Open issues / Critical issues / Overdue inspections — each an Indicator with the matching definition query

**Map widget:** the ConstructionSections layer symbolized by Status (same palette as Section 4), with ConstructionIssues and Inspections as toggle-able layers; set this as the dashboard's primary interactive element so clicking a section filters everything else.

**Charts:**
- A bar or column chart of section count by Status
- A bar chart of open issues by Issue_Severity
- Optionally a line/area chart of cumulative completion % over time if you add a simple progress-history table later (stretch goal, not needed for MVP)

**Filters / selectors:** a category selector for Contractor (so a PM can see "just this contractor's sections"), and a date range selector on Planned_Start/Planned_End for schedule review.

**Configuration notes:** every widget should point at the same hosted feature layer view rather than separate copies, and use the map widget's selection to drive the other widgets (Dashboard's "Map actions" → filter) — this is the detail that turns a set of static widgets into an actual operational dashboard, and it's a strong thing to explain in an interview.

---

## 6. Field Maps workflow (Phase 3)

**Scenario:** a site engineer in the field selects their section, updates progress, logs an inspection, or raises an issue — all offline-capable.

Configure in **Field Maps Designer** (or the Map Viewer's form designer, depending on your Online version):
1. **Section selection + progress update form**: expose ConstructionSections with an editable form limited to the fields a field engineer should touch (Status, Completion_Percent, Actual_Start, Actual_End, Last_Update) — not Section_ID or Contractor_ID, which shouldn't be field-editable. Use a dropdown (domain-backed) for Status so it can't go out of domain from the field, which is exactly the kind of "invalid status value" problem the QC script checks for at the desktop — the form is the first line of defense, the script is the backstop.
2. **Inspection form**: a related-record form on Inspections, linked via the Section_Has_Inspections relationship, so an inspection is always tied to the section the engineer is standing on. Fields: Inspection_Type, Inspection_Status, Findings (text), Follow_Up_Required.
3. **Issue creation form**: a related-record form on ConstructionIssues — Issue_Type and Issue_Severity as dropdowns, Description as text, Responsible_Person, Status defaulting to "Open". Enable **attachments** on this layer so the engineer can attach a photo directly.
4. **Issue status update**: allow the engineer to re-open the same feature later to change Status (e.g. Open → In Progress → Resolved) and add Date_Resolved when closing it.

Smart forms in current Field Maps/Field Maps Designer let you set field visibility/read-only rules by expression (e.g., hide Date_Resolved unless Status is Resolved/Closed) — worth configuring at least once as a concrete example of "conditional form logic" for an interview answer.

---

## 7. Python / ArcPy automation

Provided as `qc_construction_sections.py`, run inside ArcGIS Pro's Python environment (it uses `arcpy`, which isn't available outside Pro). It checks, per row: missing mandatory attributes, duplicate Section_ID, invalid Status values, Completion_Percent outside 0–100, Actual_End earlier than Actual_Start, "Completed" sections under 100%, and — once, for the whole feature class — the coordinate system. It also does a basic null/zero-length geometry check (for a more thorough geometry validity sweep, pair it with ArcGIS Pro's built-in **Check Geometry** tool, which is better at catching self-intersections than a hand-rolled check).

Output: a `qc_report.csv` (one row per problem, with OID/Section_ID/Check name/Problem description) and a console summary with counts per check type. It's structured as small, separately-testable check functions rather than one long procedural script — worth understanding why (easier to explain, easier to extend, easier to unit-test later) since "how is this script organized and why" is a natural interview question.

Run it against your imported sample data — it should surface all 6 deliberately corrupted rows documented in `known_data_quality_issues.md`. If it finds more (or fewer) than expected, that's the debugging exercise: paste me the `qc_report.csv` output and we'll work through it.

---

## 8. Turning it into an ArcGIS Pro Script Tool

So a non-programmer (a PM, say) can run the QC check without opening Python:
1. In your project's Catalog pane, right-click your Toolbox (or create one: right-click a folder → New → Toolbox) → New → Script.
2. Point it at `qc_construction_sections.py`, give it a name/label like "Run Construction Data QC".
3. Add **parameters** in the Script Tool's Parameters tab: an input Feature Class parameter (so the user browses to their gdb/feature class instead of it being hardcoded), and an output File parameter for the report location.
4. In the script, swap the hardcoded `GDB_PATH`/`FEATURE_CLASS`/`REPORT_PATH` constants for `arcpy.GetParameterAsText(0)`, `(1)`, `(2)` reads at the top of `run()` — this is the one real code change needed to go from "script I run" to "tool anyone on the team can run."
5. Set "Run Python script" (not "Run in background") while testing, so print() output shows in the Pro geoprocessing pane; check "Show as Result" if you want the output report to auto-add as a table.
6. Document the tool's parameters in the tool's own Item Description (Metadata) — this, plus the tool itself, is exactly the kind of artifact a GIS team lead would want a junior GIS specialist to be able to produce.

---

## 9. Power Automate concept

**Trigger:** ConstructionIssues.Issue_Severity changes to "Critical" (via ArcGIS Online's "When a feature is created or updated" trigger connector, watching the hosted ConstructionIssues layer).

**Flow steps:**
1. Trigger fires on the update.
2. Condition: `Issue_Severity = 'Critical'`.
3. If true: create an item in a SharePoint list ("Critical Issue Register") with columns for Section_ID, Location (lat/long or chainage), Issue Description, Severity, Responsible_Person, Date_Reported.
4. Send an email (or post an adaptive card to a Teams channel) to the responsible person and the project manager, with the same fields plus a deep link back to the feature in the web map.

**Architecture note:** since we won't have a full ArcGIS Enterprise + Power Automate premium connector environment, document this as an architecture diagram + a written flow description rather than a running flow — that's a completely normal, honest way to present it ("designed, not deployed due to licensing constraints" is a fine sentence in an interview). If you do have access to a personal Microsoft 365 + ArcGIS Online trial, it's genuinely buildable with the standard ArcGIS Online connector, and worth doing for real if you have the time — a working automation is stronger than a diagram of one.

---

## 10. ArcGIS Enterprise deployment concept

Written as a deployment/permissions plan — the artifact itself, not a running server:

- **Hosted feature layers**: the file geodatabase feature classes get published as hosted feature layers (via ArcGIS Pro's "Share as Web Layer") once the schema is stable, becoming the single source of truth that Field Maps, Dashboards, and web maps all read/write against.
- **Web maps**: one operational web map (all layers, full editing) for GIS specialists; one lighter, filtered web map for the Dashboard; one purpose-built map (progress-update fields only) for Field Maps.
- **Groups**: `GIS-Admins`, `Project-Managers`, `Field-Engineers`, each owning/sharing the layers and maps relevant to their role.
- **User roles / permissions**: GIS Administrator (full schema/admin rights, publishes layers, manages domains), Project Manager (read + limited edit — e.g., can update Status/Contractor but not geometry, via item-level or layer-level editing permissions), Field Engineer (edit access scoped via Field Maps forms to just the fields defined in Section 6), read-only stakeholder role (e.g. a Viewer license for anyone who just needs the Dashboard).
- **Editing rights**: enforced at two levels — the hosted feature layer's own editor tracking + field-level "editable" flags, and the form-level field visibility in Field Maps — worth being explicit in an interview that these are two different mechanisms doing complementary jobs.
- **Editor tracking**: enable it on every editable layer (who/when created and last edited) — this alone answers a lot of "how do you know who changed what" questions without extra design work.

---

## 11–13. Portfolio output, CV, and interview prep

We'll finalize these in Phase 4, once the project actually exists to describe — drafting them now, before anything is built, risks writing claims you can't back up in an interview, which runs against the whole point of doing this hands-on. What follows are **working drafts to build toward**, not text to use yet.

**README structure (draft):** Problem → Scenario → Data model (with a diagram) → ArcGIS Pro build (screenshots: geodatabase schema, domains, relationships) → Progress map (screenshot) → QC script + before/after report (screenshot of the CSV or a summary table) → Dashboard (screenshot/GIF) → Field Maps form (screenshots) → Power Automate flow (diagram) → Enterprise deployment plan → Limitations & future improvements.

**Screenshots to capture as you go** (don't try to do this retroactively at the end): geodatabase schema in Catalog, a domain's coded values, a relationship class diagram, the symbolized progress map, the QC script's console output and CSV report, the Dashboard in use, the Field Maps form on a phone/simulator, the Power Automate flow designer canvas.

**CV bullets (draft — revise once built, and only claim what you actually did):**
- Designed and built a geodatabase data model (10+ feature classes/tables, coded value domains, relationship classes) in ArcGIS Pro to track construction progress and QA/QC for a simulated 27 km energy infrastructure project
- Developed a Python/ArcPy quality-control script that validates geodata against business rules (domain values, referential integrity, completion-status consistency, coordinate system) and produces automated CSV reports
- Designed an ArcGIS Dashboard and Field Maps mobile data-collection workflow, plus an Enterprise permissions/deployment plan covering GIS admin, project manager, and field-engineer roles

**Interview questions to prepare for (we'll build real answers once the project exists):**
- How did you structure the geodatabase, and why relationship classes instead of just foreign-key text fields?
- How did you ensure data quality — what does the QC script catch that a coded value domain alone can't?
- Why UTM zone 32N instead of WGS84 for this project?
- How would you deploy this in ArcGIS Enterprise, and how would permissions differ between a field engineer and a project manager?
- How would field teams update construction progress, and how do you prevent bad data entry at the form level vs. catching it later?
- How would you automate the "Critical issue" notification, and what would you need (licensing, connectors) to actually run it?

---

*Files delivered alongside this plan: `generate_sample_data.py` (the generator), `contractors.csv`, `sections.csv`, `issues.csv`, `inspections.csv`, `known_data_quality_issues.md` (sample data), and `qc_construction_sections.py` (the ArcPy QC script).*
