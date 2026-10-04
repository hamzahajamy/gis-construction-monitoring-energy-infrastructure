# GIS-Based Construction Progress Monitoring for Energy Infrastructure

A portfolio project simulating end-to-end GIS support for a linear energy-infrastructure build — from geodatabase design through field data collection to automated issue alerting. Built on the Esri ArcGIS platform (Pro, Online, Dashboards, Field Maps) plus the ArcGIS API for Python.

## Scenario

A fictional ~25-section pipeline corridor between Hannover and Hildesheim, Germany (modeled as an H2 pipeline project), under active construction. The project tracks each section's construction progress, logs field inspections, and surfaces construction issues (including safety and quality-critical ones) from the field back to office staff in near real time.

## Why this project

Built as a focused demonstration of the GIS/geodata management workflow used in energy infrastructure delivery: structured data modeling, field data collection, dashboard reporting, and lightweight automation — the kind of stack commonly used by utilities, pipeline operators, and the engineering consultancies that support them. Scoped deliberately to stay realistic for a junior-to-mid-level role rather than over-engineered.

## Architecture

![Architecture](architecture-diagram.svg)

```
ArcGIS Pro (authoring)
  └─ File Geodatabase: layers, domains, relationships, QC script (ArcPy)
        │
        ▼
ArcGIS Online (hosting)
  └─ Hosted feature layers (Sections / Inspections / Issues / Contractors)
        │
        ├─► Web Map (symbology + pop-ups)
        │        └─► ArcGIS Dashboard (KPIs, charts, issue list, live map)
        │
        └─► Field Maps (mobile data collection)
                 └─► Form Builder: Inspection form, Issue-creation form (+ photos)
                        │
                        ▼
              Python script (ArcGIS API for Python)
                 — polls for unnotified Critical issues
                 — simulates an alert (console + local log)
                 — marks issue as notified (no duplicate alerts)
```

## Screenshots

**Dashboard** — live KPIs, status/severity breakdowns, open-issue list, and the corridor map in one view.
![Dashboard overview](screenshots/dashboard-overview.png)

**Web map** — the full pipeline corridor, sections colored by construction status.
![Web map corridor view](screenshots/webmap-corridor.png)

**Field-reported issue** — a construction issue logged through the Field Maps form, including its attribute record and the attached field photo.
![Issue detail popup](screenshots/issue-detail.png)
![Issue photo attachment](screenshots/issue-photo-attachment.png)

## Data model

Built and published as a hosted feature layer with four sub-layers/tables, each with coded-value domains and relationships back to `Section_ID`:

- **ConstructionSections** (line) — the pipeline corridor, segmented. Fields include `Section_ID`, `Status` (domain: Not Started / In Progress / Completed / Delayed / Paused), `Completion_Percent`, `Route_ID`, `Chainage_Start_km` / `Chainage_End_km`, `Length_m`, `Contractor_ID`, planned and actual start/end dates.
- **Inspections** (point) — field inspection records. `Inspection_ID`, `Section_ID`, `Inspection_Date`, `Inspection_Type` (e.g. Safety, Pre-Construction), `Inspector_Name`, `Inspection_Status` (domain: Pending / Passed / Failed), `Findings`, `Follow_Up_Required` (Yes/No domain).
- **ConstructionIssues** (point) — field-reported issues, including photo attachments. `Issue_ID` (manually assigned business ID, e.g. `ISS-013`), `Section_ID`, `Issue_Type`, `Issue_Severity` (domain: Critical / High / Medium / Low), `Description`, `Date_Reported`, `Responsible_Person`, `Status` (domain: Open / In Progress / Resolved / Closed), `Date_Resolved`, `Notification_Sent` (script-managed flag).
- **Contractors** (table) — contractor reference data, related to Sections via `Contractor_ID`.

## Data quality

An ArcPy QC script validates the geodatabase for common field-data issues (e.g. missing `Responsible_Person` on an open issue) before publishing. Deliberately left one seeded record (`ISS-001`) with a blank `Responsible_Person` as a live QC test case — the Dashboard and the alerting script both surface it rather than silently ignoring it, which is the correct behavior for a data-quality gap, not a bug.

A reusable ArcGIS Pro **Script Tool** wraps part of this logic as a proper geoprocessing tool with a parameter UI, rather than a one-off script — the more maintainable pattern for anything meant to be re-run by someone other than its author.

## Web GIS and Dashboard

Hosted feature layers are published to ArcGIS Online and consumed by a Web Map (with layer-specific symbology — sections colored by construction `Status`, points colored by their own severity/status fields independently of the line beneath them) and an ArcGIS Dashboard surfacing:

- KPI tiles: Completed / Delayed / Total Sections, Open Critical Issues
- Sections-by-status and issue-severity breakdowns (pie charts)
- A live list of open issues
- The full corridor map, click-through to feature detail

## Field data collection

Two ArcGIS Field Maps forms were built and validated (tested via Map Viewer's Editor widget, the practical browser-based stand-in for the mobile app):

- **Inspection form** — logs field inspections against a section.
- **Issue-creation form** — logs a new construction issue, including a photo attachment. Deliberately excludes `Date_Resolved` from the creation form (a field you resolve later, not at creation time) and leaves `Status` without a form-level default, a conscious trade-off: ArcGIS disables per-form defaults once a field carries a coded-value domain, routing default values through a separate feature-template mechanism outside Form Builder's scope. Rather than over-engineer a one-click convenience, `Status` is left as an explicit, domain-constrained manual selection — a deliberate, documented design decision rather than an oversight.

## Automated critical-issue alerting

A Python script (`critical_alerts.py`, using the ArcGIS API for Python) replaces what was originally planned as a Power Automate flow — dropped after confirming Power Automate's native ArcGIS connector is a premium-tier feature unavailable on the account in use. The script:

- Authenticates via a scoped OAuth 2.0 app credential (client ID/secret), rather than a personal password — granted access to exactly one item, with no organization-level privileges, following least-privilege practice.
- Queries the ConstructionIssues layer for `Issue_Severity = 'Critical' AND Notification_Sent <> 'Yes'`.
- Simulates sending an alert for each one found (printed and logged to `alerts_log.txt`) — the delivery mechanism (e.g. real email/SMS) is deliberately decoupled from the detection logic, so swapping in a real notification channel later is a small, isolated change.
- Marks each alerted issue as notified, so re-running the script never raises a duplicate alert. Verified empirically: run twice in a row, the second run finds zero unnotified issues.

## Backup and continuity

Because the hosting AGOL account runs through a university institutional org (access not guaranteed after graduation), all feature layer data — schema, domains, attachments included — was exported to a File Geodatabase for permanent, offline-owned storage. The Dashboard and Web Map, being AGOL-native app configurations with no direct export path, were preserved through systematic screenshots of their default and interactive states.

## Skills demonstrated

ArcGIS Pro (geodatabase design, domains, relationships, Script Tools) · ArcGIS Online (hosted feature layers, Web Map, Dashboards) · ArcGIS Field Maps / Form Builder · Python (ArcPy, ArcGIS API for Python) · OAuth 2.0 app authentication and least-privilege credential scoping · data quality assurance · construction/asset progress monitoring workflow design.
