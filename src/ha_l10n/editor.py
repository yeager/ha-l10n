"""Translation editor with side-by-side source/target."""

import json
import gettext
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

_ = gettext.gettext

STATUS_TRANSLATED = "translated"
STATUS_UNTRANSLATED = "untranslated"
STATUS_FUZZY = "fuzzy"


class TranslationEditor(Gtk.Box):
    """Side-by-side translation editor."""

    def __init__(self, update_status_cb=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._strings = {}  # key -> source
        self._translations = {}  # key -> target
        self._statuses = {}  # key -> status
        self._current_key = None
        self._component_path = None
        self._target_lang = None
        self._update_status = update_status_cb
        self._modified = False

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(8)
        toolbar.set_margin_bottom(4)

        # Language selector
        lang_label = Gtk.Label(label=_("Target language:"))
        toolbar.append(lang_label)

        self._lang_entry = Gtk.Entry()
        self._lang_entry.set_placeholder_text("sv")
        self._lang_entry.set_width_chars(6)
        self._lang_entry.connect("activate", self._on_lang_changed)
        toolbar.append(self._lang_entry)

        load_btn = Gtk.Button(label=_("Load"))
        load_btn.connect("clicked", self._on_lang_changed)
        toolbar.append(load_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)

        save_btn = Gtk.Button(label=_("Save"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        toolbar.append(save_btn)

        self.append(toolbar)

        # Main content: list on left, editor on right
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(300)
        self.append(paned)

        # Left: string list
        left_sw = Gtk.ScrolledWindow()
        self._list_store = Gtk.ListStore(str, str, str)
        # key, source_preview, status
        self._list_view = Gtk.TreeView(model=self._list_store)
        self._list_view.set_headers_visible(True)
        self._list_view.connect("cursor-changed", self._on_key_selected)

        col_key = Gtk.TreeViewColumn(_("Key"), Gtk.CellRendererText(), text=0)
        col_key.set_resizable(True)
        self._list_view.append_column(col_key)

        renderer_status = Gtk.CellRendererText()
        col_st = Gtk.TreeViewColumn(_("Status"), renderer_status, text=2)
        col_st.set_cell_data_func(renderer_status, self._status_cell_func)
        self._list_view.append_column(col_st)

        left_sw.set_child(self._list_view)
        paned.set_start_child(left_sw)

        # Right: side-by-side editor
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right.set_margin_start(8)
        right.set_margin_end(8)
        right.set_margin_top(8)

        self._key_label = Gtk.Label(label="")
        self._key_label.set_halign(Gtk.Align.START)
        self._key_label.add_css_class("title-4")
        right.append(self._key_label)

        side = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        side.set_vexpand(True)

        # Source (read-only)
        src_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        src_box.set_hexpand(True)
        src_label = Gtk.Label(label=_("Source (English)"))
        src_label.set_halign(Gtk.Align.START)
        src_label.add_css_class("dim-label")
        src_box.append(src_label)

        src_sw = Gtk.ScrolledWindow()
        src_sw.set_vexpand(True)
        self._source_view = Gtk.TextView()
        self._source_view.set_editable(False)
        self._source_view.set_wrap_mode(Gtk.WrapMode.WORD)
        src_sw.set_child(self._source_view)
        src_box.append(src_sw)
        side.append(src_box)

        # Target (editable)
        tgt_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        tgt_box.set_hexpand(True)
        tgt_label = Gtk.Label(label=_("Target"))
        tgt_label.set_halign(Gtk.Align.START)
        tgt_label.add_css_class("dim-label")
        tgt_box.append(tgt_label)

        tgt_sw = Gtk.ScrolledWindow()
        tgt_sw.set_vexpand(True)
        self._target_view = Gtk.TextView()
        self._target_view.set_editable(True)
        self._target_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._target_view.get_buffer().connect("changed", self._on_target_changed)
        tgt_sw.set_child(self._target_view)
        tgt_box.append(tgt_sw)
        side.append(tgt_box)

        right.append(side)

        # Action buttons
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_box.set_margin_bottom(8)

        copy_btn = Gtk.Button(label=_("Copy source to target"))
        copy_btn.connect("clicked", self._on_copy_source)
        action_box.append(copy_btn)

        self._status_combo = Gtk.DropDown.new_from_strings(
            [_("Translated"), _("Fuzzy"), _("Untranslated")])
        self._status_combo.set_selected(2)
        self._status_combo.connect("notify::selected", self._on_status_changed)
        action_box.append(self._status_combo)

        right.append(action_box)
        paned.set_end_child(right)

    def _status_cell_func(self, column, cell, model, iter_, data=None):
        status = model.get_value(iter_, 2)
        colors = {
            STATUS_TRANSLATED: "#2ec27e",
            STATUS_FUZZY: "#e5a50a",
            STATUS_UNTRANSLATED: "#77767b",
        }
        cell.set_property("foreground", colors.get(status, "#77767b"))

    def set_component_path(self, path):
        self._component_path = path

    def load_strings(self, source_strings, target_strings=None):
        """Load strings into the editor."""
        self._strings = source_strings
        self._translations = target_strings or {}
        self._statuses = {}
        for key in source_strings:
            if key in self._translations and self._translations[key]:
                self._statuses[key] = STATUS_TRANSLATED
            else:
                self._statuses[key] = STATUS_UNTRANSLATED
        self._rebuild_list()

    def _rebuild_list(self):
        self._list_store.clear()
        for key in sorted(self._strings.keys()):
            preview = self._strings[key][:40]
            status = self._statuses.get(key, STATUS_UNTRANSLATED)
            self._list_store.append([key, preview, status])

    def _on_key_selected(self, tree):
        sel = tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            return
        key = model.get_value(iter_, 0)
        self._current_key = key
        self._key_label.set_text(key)

        src_buf = self._source_view.get_buffer()
        src_buf.set_text(self._strings.get(key, ""))

        tgt_buf = self._target_view.get_buffer()
        tgt_buf.handler_block_by_func(self._on_target_changed)
        tgt_buf.set_text(self._translations.get(key, ""))
        tgt_buf.handler_unblock_by_func(self._on_target_changed)

        status = self._statuses.get(key, STATUS_UNTRANSLATED)
        idx = {STATUS_TRANSLATED: 0, STATUS_FUZZY: 1, STATUS_UNTRANSLATED: 2}.get(status, 2)
        self._status_combo.set_selected(idx)

    def _on_target_changed(self, buf):
        if self._current_key:
            start = buf.get_start_iter()
            end = buf.get_end_iter()
            text = buf.get_text(start, end, False)
            self._translations[self._current_key] = text
            if text:
                self._statuses[self._current_key] = STATUS_TRANSLATED
                self._status_combo.set_selected(0)
            self._modified = True

    def _on_status_changed(self, dropdown, _pspec):
        if self._current_key:
            idx = dropdown.get_selected()
            status = [STATUS_TRANSLATED, STATUS_FUZZY, STATUS_UNTRANSLATED][idx]
            self._statuses[self._current_key] = status
            self._rebuild_list()
            self._modified = True

    def _on_copy_source(self, _btn):
        if self._current_key:
            src = self._strings.get(self._current_key, "")
            self._target_view.get_buffer().set_text(src)

    def _on_lang_changed(self, _widget):
        lang = self._lang_entry.get_text().strip()
        if not lang or not self._component_path:
            return
        self._target_lang = lang
        from ha_l10n.strings import load_translations_for_component
        trans = load_translations_for_component(self._component_path, lang)
        self._translations = trans
        for key in self._strings:
            if key in trans and trans[key]:
                self._statuses[key] = STATUS_TRANSLATED
            else:
                self._statuses[key] = STATUS_UNTRANSLATED
        self._rebuild_list()

    def _on_save(self, _btn):
        if not self._component_path or not self._target_lang:
            return
        # Unflatten translations back to nested JSON
        nested = {}
        for key, val in self._translations.items():
            if not val:
                continue
            parts = key.split('.')
            d = nested
            for p in parts[:-1]:
                d = d.setdefault(p, {})
            d[parts[-1]] = val

        path = Path(self._component_path) / "translations"
        path.mkdir(parents=True, exist_ok=True)
        out = path / f"{self._target_lang}.json"
        out.write_text(json.dumps(nested, indent=2, ensure_ascii=False) + '\n',
                       encoding='utf-8')
        self._modified = False
        if self._update_status:
            self._update_status(_("Saved translations to %s") % str(out))
