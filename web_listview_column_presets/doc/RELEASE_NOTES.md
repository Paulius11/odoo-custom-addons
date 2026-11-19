## Module web_listview_column_presets

#### 19.11.2026
#### Version 17.0.2.3.1
#### BUG FIX
- Lists in other modules' JavaScript tests no longer crash with "Service columnPreset is not available".

#### 18.11.2026
#### Version 17.0.2.3.0
#### UPDATE
- Presets are their own entries in the column menu, no longer fake column checkboxes.
- Fixed: every list left a page-wide observer and click listener behind.
- Fixed: any user could create a shared preset through the API, past the group check.
- Tests for personal and shared presets and their access rules.
