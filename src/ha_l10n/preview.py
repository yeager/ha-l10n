"""Live preview of translated entity strings."""

import gettext

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Pango

_ = gettext.gettext


class PreviewView(Gtk.Box):
    """Preview how translated strings appear in HA dashboard."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._entities = []
        self._translations = {}

        # Controls
        ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ctrl.set_margin_start(12)
        ctrl.set_margin_end(12)
        ctrl.set_margin_top(12)

        ctrl.append(Gtk.Label(label=_("Font size:")))
        self._font_adj = Gtk.Adjustment(value=14, lower=8, upper=32,
                                        step_increment=1)
        self._font_spin = Gtk.SpinButton(adjustment=self._font_adj)
        self._font_spin.connect("value-changed", self._on_font_changed)
        ctrl.append(self._font_spin)

        self.append(ctrl)

        # Preview area
        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)
        sw.set_margin_start(12)
        sw.set_margin_end(12)
        sw.set_margin_top(8)
        sw.set_margin_bottom(12)

        self._preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sw.set_child(self._preview_box)
        self.append(sw)

    def set_entities(self, entities, translations=None):
        """Set entities and optional translations for preview."""
        self._entities = entities
        self._translations = translations or {}
        self._rebuild()

    def _rebuild(self):
        # Clear
        child = self._preview_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._preview_box.remove(child)
            child = next_child

        font_size = int(self._font_adj.get_value())

        for entity in self._entities[:100]:  # Limit preview
            eid = entity.get('entity_id', '')
            attrs = entity.get('attributes', {})
            original = attrs.get('friendly_name', eid)
            translated = self._translations.get(eid, original)
            state = entity.get('state', '')

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.set_margin_start(8)
            row.set_margin_end(8)
            row.set_margin_top(2)
            row.set_margin_bottom(2)

            # Before
            before_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            before_box.set_hexpand(True)
            lbl_before = Gtk.Label(label=original)
            lbl_before.set_halign(Gtk.Align.START)
            attrs_desc = Pango.AttrList()
            attrs_desc.insert(Pango.attr_size_new(font_size * Pango.SCALE))
            lbl_before.set_attributes(attrs_desc)
            before_box.append(lbl_before)

            state_lbl = Gtk.Label(label=state)
            state_lbl.set_halign(Gtk.Align.START)
            state_lbl.add_css_class("dim-label")
            before_box.append(state_lbl)
            row.append(before_box)

            # Arrow
            arrow = Gtk.Label(label="→")
            row.append(arrow)

            # After
            after_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            after_box.set_hexpand(True)
            lbl_after = Gtk.Label(label=translated)
            lbl_after.set_halign(Gtk.Align.START)
            lbl_after.set_attributes(attrs_desc)
            if translated != original:
                lbl_after.add_css_class("success")
            after_box.append(lbl_after)

            state_lbl2 = Gtk.Label(label=state)
            state_lbl2.set_halign(Gtk.Align.START)
            state_lbl2.add_css_class("dim-label")
            after_box.append(state_lbl2)
            row.append(after_box)

            self._preview_box.append(row)

        if not self._entities:
            self._preview_box.append(
                Gtk.Label(label=_("No entities loaded. Connect to HA and refresh.")))

    def _on_font_changed(self, spin):
        self._rebuild()
