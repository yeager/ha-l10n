"""String extractor for HA custom components and frontend."""

import json
import gettext
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango

_ = gettext.gettext

# Status constants
STATUS_TRANSLATED = "translated"
STATUS_UNTRANSLATED = "untranslated"
STATUS_FUZZY = "fuzzy"
STATUS_MISSING = "missing"


def extract_strings_from_component(component_path):
    """Extract translatable strings from a HA custom component directory.

    Returns dict: {dotted_key: english_string}
    """
    path = Path(component_path)
    strings = {}

    # strings.json
    strings_file = path / "strings.json"
    if strings_file.exists():
        try:
            data = json.loads(strings_file.read_text(encoding='utf-8'))
            _flatten_json(data, "", strings)
        except (json.JSONDecodeError, OSError):
            pass

    return strings


def load_translations_for_component(component_path, lang):
    """Load translations for a specific language from a component.

    Returns dict: {dotted_key: translated_string}
    """
    path = Path(component_path)
    translations = {}

    # translations/<lang>.json
    trans_file = path / "translations" / f"{lang}.json"
    if trans_file.exists():
        try:
            data = json.loads(trans_file.read_text(encoding='utf-8'))
            _flatten_json(data, "", translations)
        except (json.JSONDecodeError, OSError):
            pass

    return translations


def _flatten_json(data, prefix, result):
    """Flatten nested JSON into dotted keys."""
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else k
            _flatten_json(v, key, result)
    elif isinstance(data, str):
        result[prefix] = data


def extract_frontend_strings(frontend_path, lang='en'):
    """Extract strings from HA frontend translations directory."""
    path = Path(frontend_path) / "src" / "translations"
    if not path.exists():
        path = Path(frontend_path) / "translations"
    strings = {}
    lang_file = path / f"{lang}.json"
    if lang_file.exists():
        try:
            data = json.loads(lang_file.read_text(encoding='utf-8'))
            _flatten_json(data, "", strings)
        except (json.JSONDecodeError, OSError):
            pass
    return strings


def get_available_languages(component_path):
    """Get list of available translation languages for a component."""
    trans_dir = Path(component_path) / "translations"
    if not trans_dir.exists():
        return []
    return sorted(p.stem for p in trans_dir.glob("*.json"))


class StringsView(Gtk.Box):
    """View for browsing extracted strings with source vs target."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._source_strings = {}  # key -> english
        self._target_strings = {}  # key -> translated
        self._all_keys = []

        # Info bar
        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        info.set_margin_start(8)
        info.set_margin_end(8)
        info.set_margin_top(8)
        info.set_margin_bottom(4)

        self._count_label = Gtk.Label(label=_("No strings loaded"))
        self._count_label.set_halign(Gtk.Align.START)
        self._count_label.add_css_class("dim-label")
        info.append(self._count_label)

        self._coverage_label = Gtk.Label(label="")
        self._coverage_label.set_halign(Gtk.Align.END)
        self._coverage_label.set_hexpand(True)
        self._coverage_label.add_css_class("dim-label")
        info.append(self._coverage_label)
        self.append(info)

        # String list
        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)

        self._store = Gtk.ListStore(str, str, str, str)
        # columns: key, source, target, status
        self._tree = Gtk.TreeView(model=self._store)
        self._tree.set_headers_visible(True)

        col_key = Gtk.TreeViewColumn(_("Key"), Gtk.CellRendererText(), text=0)
        col_key.set_resizable(True)
        col_key.set_min_width(200)
        self._tree.append_column(col_key)

        col_src = Gtk.TreeViewColumn(_("Source (English)"), Gtk.CellRendererText(), text=1)
        col_src.set_resizable(True)
        col_src.set_expand(True)
        self._tree.append_column(col_src)

        col_tgt = Gtk.TreeViewColumn(_("Target"), Gtk.CellRendererText(), text=2)
        col_tgt.set_resizable(True)
        col_tgt.set_expand(True)
        self._tree.append_column(col_tgt)

        renderer_status = Gtk.CellRendererText()
        col_status = Gtk.TreeViewColumn(_("Status"), renderer_status, text=3)
        col_status.set_cell_data_func(renderer_status, self._status_cell_func)
        self._tree.append_column(col_status)

        sw.set_child(self._tree)
        self.append(sw)

    def _status_cell_func(self, column, cell, model, iter_, data=None):
        status = model.get_value(iter_, 3)
        if status == STATUS_TRANSLATED:
            cell.set_property("foreground", "#2ec27e")
        elif status == STATUS_MISSING:
            cell.set_property("foreground", "#e01b24")
        elif status == STATUS_FUZZY:
            cell.set_property("foreground", "#e5a50a")
        else:
            cell.set_property("foreground", "#77767b")

    def load_strings(self, source, target=None):
        """Load source and optionally target strings."""
        self._source_strings = source
        self._target_strings = target or {}
        self._rebuild()

    def _rebuild(self):
        self._store.clear()
        self._all_keys = sorted(self._source_strings.keys())
        translated = 0
        for key in self._all_keys:
            src = self._source_strings[key]
            tgt = self._target_strings.get(key, "")
            if tgt:
                status = STATUS_TRANSLATED
                translated += 1
            else:
                status = STATUS_MISSING
            self._store.append([key, src, tgt, status])

        total = len(self._all_keys)
        self._count_label.set_text(_("%d strings") % total)
        if total > 0:
            pct = (translated / total) * 100
            self._coverage_label.set_text(_("Coverage: %.0f%%") % pct)
        else:
            self._coverage_label.set_text("")

    def get_strings_data(self):
        """Return current strings for export."""
        data = []
        for key in self._all_keys:
            src = self._source_strings.get(key, "")
            tgt = self._target_strings.get(key, "")
            status = STATUS_TRANSLATED if tgt else STATUS_MISSING
            data.append({
                'key': key,
                'source': src,
                'target': tgt,
                'status': status,
            })
        return data

    def get_coverage_stats(self):
        """Return (total, translated, percentage)."""
        total = len(self._all_keys)
        translated = sum(1 for k in self._all_keys if self._target_strings.get(k))
        pct = (translated / total * 100) if total > 0 else 0
        return total, translated, pct
