"""Entity browser for Home Assistant entities."""

import gettext
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango

_ = gettext.gettext


class EntityBrowser(Gtk.Box):
    """Browse HA entities grouped by domain."""

    def __init__(self, get_connection):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._get_connection = get_connection
        self._entities = []
        self._filtered_entities = []

        # Left pane: search + tree
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left.set_size_request(350, -1)

        # Search
        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text(_("Filter entities..."))
        self._search.connect("search-changed", self._on_filter)
        self._search.set_margin_start(8)
        self._search.set_margin_end(8)
        self._search.set_margin_top(8)
        left.append(self._search)

        # Entity list
        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)
        sw.set_hexpand(True)

        self._store = Gtk.TreeStore(str, str, str, bool)
        # columns: entity_id, friendly_name, state, is_untranslated
        self._tree = Gtk.TreeView(model=self._store)
        self._tree.set_headers_visible(True)
        self._tree.connect("cursor-changed", self._on_select)

        col_id = Gtk.TreeViewColumn(_("Entity ID"), Gtk.CellRendererText(), text=0)
        col_id.set_resizable(True)
        col_id.set_expand(True)
        self._tree.append_column(col_id)

        renderer_name = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn(_("Friendly Name"), renderer_name, text=1)
        col_name.set_resizable(True)
        col_name.set_cell_data_func(renderer_name, self._name_cell_func)
        self._tree.append_column(col_name)

        sw.set_child(self._tree)
        left.append(sw)
        self.append(left)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(sep)

        # Right pane: detail
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right.set_hexpand(True)
        right.set_margin_start(12)
        right.set_margin_end(12)
        right.set_margin_top(12)

        self._detail_title = Gtk.Label(label=_("Select an entity"))
        self._detail_title.set_halign(Gtk.Align.START)
        self._detail_title.add_css_class("title-2")
        right.append(self._detail_title)

        detail_sw = Gtk.ScrolledWindow()
        detail_sw.set_vexpand(True)
        self._detail_text = Gtk.TextView()
        self._detail_text.set_editable(False)
        self._detail_text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._detail_text.set_monospace(True)
        detail_sw.set_child(self._detail_text)
        right.append(detail_sw)
        self.append(right)

    def _name_cell_func(self, column, cell, model, iter_, data=None):
        """Highlight untranslated names."""
        is_untranslated = model.get_value(iter_, 3)
        if is_untranslated:
            cell.set_property("foreground", "#e5a50a")
            cell.set_property("weight", Pango.Weight.BOLD)
        else:
            cell.set_property("foreground-set", False)
            cell.set_property("weight", Pango.Weight.NORMAL)

    def _is_likely_english(self, name):
        """Heuristic: names with spaces and all ASCII are likely untranslated English."""
        if not name:
            return False
        return name.isascii() and ' ' in name

    def load_entities(self, states):
        """Load entities from HA states response."""
        self._entities = states
        self._rebuild_tree(states)

    def _rebuild_tree(self, entities):
        self._store.clear()
        domains = {}
        for e in entities:
            eid = e.get('entity_id', '')
            domain = eid.split('.')[0] if '.' in eid else _("unknown")
            if domain not in domains:
                domains[domain] = self._store.append(None, [domain, "", "", False])
            attrs = e.get('attributes', {})
            fname = attrs.get('friendly_name', '')
            state = e.get('state', '')
            untranslated = self._is_likely_english(fname)
            self._store.append(domains[domain], [eid, fname, state, untranslated])
        self._tree.expand_all()

    def _on_filter(self, entry):
        query = entry.get_text().lower()
        if not query:
            self._rebuild_tree(self._entities)
            return
        filtered = [e for e in self._entities
                     if query in e.get('entity_id', '').lower()
                     or query in e.get('attributes', {}).get('friendly_name', '').lower()]
        self._rebuild_tree(filtered)

    def _on_select(self, tree):
        sel = tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            return
        eid = model.get_value(iter_, 0)
        # Find entity data
        entity = None
        for e in self._entities:
            if e.get('entity_id') == eid:
                entity = e
                break
        if entity:
            self._detail_title.set_text(eid)
            import json
            buf = self._detail_text.get_buffer()
            buf.set_text(json.dumps(entity, indent=2, ensure_ascii=False))
        else:
            # Domain row
            self._detail_title.set_text(eid)
            count = sum(1 for e in self._entities if e.get('entity_id', '').startswith(eid + '.'))
            buf = self._detail_text.get_buffer()
            buf.set_text(_("%d entities in domain '%s'") % (count, eid))

    def refresh(self):
        """Refresh entities from HA."""
        conn = self._get_connection()
        if not conn:
            return
        url, token = conn

        def do_fetch():
            try:
                from ha_l10n.connection import fetch_states
                states = fetch_states(url, token)
                GLib.idle_add(lambda: self.load_entities(states))
            except Exception as e:
                GLib.idle_add(lambda: self._detail_title.set_text(
                    _("Error: %s") % str(e)))

        threading.Thread(target=do_fetch, daemon=True).start()

    def get_entities(self):
        """Return current entities for export."""
        return self._entities
