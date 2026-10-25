"""Filters accepted by pywebview 6's parser (which rejects hyphenated suffixes)."""
# .cove-plugin is validated from ZIP contents after selection. *.* is deliberate:
# passing *.cove-plugin to pywebview fails before the native picker can open.
PLUGIN_FILTERS = ('Cove plugin packages (*.*)', 'ZIP archives (*.zip)')
PLUGIN_SAVE_FILTERS = ('Cove plugin package (*.*)',)
PYTHON_FILTERS = ('Python executables (*.exe)',)
ZIP_FILTERS = ('ZIP archives (*.zip)',)
