# Deliberately introduced data-quality issues

These rows were corrupted on purpose so the ArcPy QC script has real problems to catch. Use this list to verify the script's output matches what's actually wrong in the data.

- Row 25 (originally SEC-025) was given a duplicate Section_ID (same as row 11, SEC-011) to test duplicate-ID detection.
- Row 4 (SEC-004) has Completion_Percent = 130 (invalid, must be 0-100) to test the range check.
- Row 3 (SEC-003) has Actual_End set before Actual_Start to test the date-order check.
- Row 6 (SEC-006) is marked Completed but Completion_Percent = 85, to test the status-vs-completion business rule.
- Row 8 (SEC-008) has a blank Contractor_ID to test the mandatory-field check.
- Row 16 (SEC-016) has Status = 'Paused', which is not a valid domain value (valid values: Not Started, In Progress, Delayed, Completed, On Hold), to test domain validation.
- Issue ISS-001 is Critical severity but has a blank Responsible_Person, to test that business rule.
