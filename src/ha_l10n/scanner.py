"""Integration scanner for HA custom components."""

import json
import gettext
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

_ = gettext.gettext


def scan_integrations(config_path):
    """Scan a HA config dir for custom components.

    Returns list of dicts: {name, path, has_strings, has_translations, languages, coverage}
    """
    path = Path(config_path)
    # Try custom_components/ subdir
    cc = path / "custom_components"
    if cc.exists():
        path = cc
    elif not any(path.iterdir()):
        return []

    results = []
    for item in sorted(path.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith('.') or item.name == '__pycache__':
            continue

        info = {
            'name': item.name,
            'path': str(item),
            'has_strings': (item / "strings.json").exists(),
            'has_translations': (item / "translations").exists(),
            'languages': [],
            'string_count': 0,
            'coverage': {},
        }

        if info['has_strings']:
            try:
                data = json.loads((item / "strings.json").read_text(encoding='utf-8'))
                strings = {}
                _flatten(data, "", strings)
                info['string_count'] = len(strings)
            except (json.JSONDecodeError, OSError):
                pass

        if info['has_translations']:
            trans_dir = item / "translations"
            langs = sorted(p.stem for p in trans_dir.glob("*.json"))
            info['languages'] = langs
            for lang in langs:
                try:
                    tdata = json.loads(
                        (trans_dir / f"{lang}.json").read_text(encoding='utf-8'))
                    tstrings = {}
                    _flatten(tdata, "", tstrings)
                    if info['string_count'] > 0:
                        info['coverage'][lang] = len(tstrings) / info['string_count'] * 100
                    else:
                        info['coverage'][lang] = 0
                except (json.JSONDecodeError, OSError):
                    info['coverage'][lang] = 0

        results.append(info)
    return results


def _flatten(data, prefix, result):
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else k
            _flatten(v, key, result)
    elif isinstance(data, str):
        result[prefix] = data


class ScannerView(Gtk.Box):
    """View for scanning HA integrations."""

    def __init__(self, on_integration_selected=None, update_status_cb=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._integrations = []
        self._on_selected = on_integration_selected
        self._update_status = update_status_cb
        self._scan_path = None

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(8)
        toolbar.set_margin_bottom(4)

        self._path_label = Gtk.Label(label=_("No directory selected"))
        self._path_label.set_halign(Gtk.Align.START)
        self._path_label.set_hexpand(True)
        self._path_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        toolbar.append(self._path_label)

        open_btn = Gtk.Button(label=_("Open Folder..."))
        open_btn.connect("clicked", self._on_open)
        toolbar.append(open_btn)

        scan_btn = Gtk.Button(label=_("Scan"))
        scan_btn.add_css_class("suggested-action")
        scan_btn.connect("clicked", self._on_scan)
        toolbar.append(scan_btn)

        self.append(toolbar)

        # Results list
        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)

        self._store = Gtk.ListStore(str, str, str, str, str)
        # name, strings_json, translations_dir, languages, coverage_summary
        self._tree = Gtk.TreeView(model=self._store)
        self._tree.set_headers_visible(True)
        self._tree.connect("row-activated", self._on_row_activated)

        for i, (title, expand) in enumerate([
            (_("Integration"), True),
            (_("strings.json"), False),
            (_("translations/"), False),
            (_("Languages"), False),
            (_("Coverage"), False),
        ]):
            col = Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=i)
            col.set_resizable(True)
            if expand:
                col.set_expand(True)
            self._tree.append_column(col)

        sw.set_child(self._tree)
        self.append(sw)

    def _on_open(self, _btn):
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Select HA config or custom_components directory"))
        dialog.select_folder(
            self._get_window(), None, self._on_folder_selected)

    def _get_window(self):
        w = self.get_root()
        return w if isinstance(w, Gtk.Window) else None

    def _on_folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                self._scan_path = path
                self._path_label.set_text(path)
        except GLib.Error:
            pass

    def _on_scan(self, _btn):
        if not self._scan_path:
            return
        self._integrations = scan_integrations(self._scan_path)
        self._rebuild()
        if self._update_status:
            self._update_status(
                _("Found %d integrations") % len(self._integrations))

    def scan_path(self, path):
        """Programmatically scan a path."""
        self._scan_path = path
        self._path_label.set_text(path)
        self._integrations = scan_integrations(path)
        self._rebuild()

    def _rebuild(self):
        self._store.clear()
        for info in self._integrations:
            has_s = "✅" if info['has_strings'] else "❌"
            has_t = "✅" if info['has_translations'] else "❌"
            langs = ", ".join(info['languages']) if info['languages'] else "—"
            cov_parts = []
            for lang, pct in info['coverage'].items():
                cov_parts.append(f"{lang}: {pct:.0f}%")
            cov = ", ".join(cov_parts) if cov_parts else "—"
            self._store.append([info['name'], has_s, has_t, langs, cov])

    def _on_row_activated(self, tree, path, column):
        iter_ = self._store.get_iter(path)
        name = self._store.get_value(iter_, 0)
        for info in self._integrations:
            if info['name'] == name:
                if self._on_selected:
                    self._on_selected(info)
                break

    def get_integrations(self):
        return self._integrations
