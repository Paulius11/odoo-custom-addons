# Release notes

## 17.0.4.1.0

- Code-term changes reach every worker of a multi-worker server, and stay within their own database.
- Translators can no longer create changes or history entries directly, or point a term at another record.
- Rebuilding the term list is refused for users outside the Translator group.
- Translation mode: the Close button of an error dialog and notifications work again.
- English users get a notice instead of an English term list nobody can edit.
- The column you type in gets room in the Terms and Changes lists.

## 17.0.4.0.0

- Saved translations now apply to every module's strings (Python `_()` and JS `_t`), not only this addon's.
- Menus, field labels, selection values, view text and action names can be translated too.
- Edits are drafts until Apply; every Apply and Revert is kept in History.
- Revert one term, one change set, or everything back to Odoo's own translation; uninstalling restores the originals.
- Changes come back by themselves after a module upgrade or a language reload.
- Translation mode: click any text; one popup per click; it lists every place that text appears.
- One Terms list replaces Browse All, Comparison and Quick Translation.
- New Translator group; Settings admins have it.
- Translations that drop placeholders or add HTML tags are refused.
- Lithuanian translation of the addon's own screens.
- The term list rebuilds itself after modules are installed or upgraded.
