#!/usr/bin/env python3
"""Home Assistant L10n — translation helper tool."""

import sys
import gettext
from datetime import datetime

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gio, GLib

from ha_l10n import __version__
from ha_l10n.connection import ConnectionDialog
from ha_l10n.entities import EntityBrowser
from ha_l10n.strings import StringsView, extract_strings_from_component, \
    load_translations_for_component, get_available_languages
from ha_l10n.editor import TranslationEditor
from ha_l10n.scanner import ScannerView
from ha_l10n.preview import PreviewView
from ha_l10n.export import ExportDialog
from ha_l10n.accessibility import AccessibilityManager

# Set up gettext
TEXTDOMAIN = 'ha-l10n'
gettext.textdomain(TEXTDOMAIN)
gettext.bindtextdomain(TEXTDOMAIN, '/usr/share/locale')
_ = gettext.gettext



def _settings_path():
    import os
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    d = os.path.join(xdg, "ha-l10n")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "settings.json")

def _load_settings():
    import os, json
    p = _settings_path()
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}

def _save_settings(s):
    import json
    with open(_settings_path(), "w") as f:
        json.dump(s, f, indent=2)

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_default_size(1100, 700)
        self.set_title(_("Home Assistant L10n"))

        self._ha_url = None
        self._ha_token = None
        self._connected = False

        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()

        # Connection button
        self._conn_btn = Gtk.Button(label=_("Connect"))
        self._conn_btn.set_icon_name("network-server-symbolic")
        self._conn_btn.connect("clicked", self._on_connect)
        header.pack_start(self._conn_btn)

        # Connection indicator
        self._conn_indicator = Gtk.Label(label="⚫")
        self._conn_indicator.set_tooltip_text(_("Not connected"))
        header.pack_start(self._conn_indicator)

        # Scan button
        scan_btn = Gtk.Button()
        scan_btn.set_icon_name("folder-open-symbolic")
        scan_btn.set_tooltip_text(_("Scan integrations"))
        scan_btn.connect("clicked", self._on_scan_btn)
        header.pack_start(scan_btn)

        # Language selector in header
        lang_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lang_label = Gtk.Label(label=_("Lang:"))
        lang_label.add_css_class("dim-label")
        lang_box.append(lang_label)
        self._lang_entry = Gtk.Entry()
        self._lang_entry.set_placeholder_text("sv")
        self._lang_entry.set_width_chars(5)
        self._lang_entry.set_max_width_chars(5)
        lang_box.append(self._lang_entry)
        header.pack_end(lang_box)

        # Menu button
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu = Gio.Menu()
        menu.append(_("Keyboard Shortcuts"), "app.shortcuts")
        menu.append(_("About"), "app.about")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        main_box.append(header)

        # View stack
        self._stack = Adw.ViewStack()
        self._stack.set_vexpand(True)

        # Entity browser
        self._entity_browser = EntityBrowser(self._get_connection)
        self._stack.add_titled_with_icon(
            self._entity_browser, "entities",
            _("Entities"), "view-list-symbolic")

        # Strings view
        self._strings_view = StringsView()
        self._stack.add_titled_with_icon(
            self._strings_view, "strings",
            _("Strings"), "accessories-text-editor-symbolic")

        # Editor
        self._editor = TranslationEditor(
            update_status_cb=self._set_status)
        self._stack.add_titled_with_icon(
            self._editor, "editor",
            _("Editor"), "document-edit-symbolic")

        # Scanner
        self._scanner = ScannerView(
            on_integration_selected=self._on_integration_selected,
            update_status_cb=self._set_status)
        self._stack.add_titled_with_icon(
            self._scanner, "scanner",
            _("Scanner"), "system-search-symbolic")

        # Preview
        self._preview = PreviewView()
        self._stack.add_titled_with_icon(
            self._preview, "preview",
            _("Preview"), "view-reveal-symbolic")

        main_box.append(self._stack)

        # View switcher bar
        switcher = Adw.ViewSwitcherBar()
        switcher.set_stack(self._stack)
        switcher.set_reveal(True)
        main_box.append(switcher)

        # Status bar
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_box.set_margin_start(8)
        status_box.set_margin_end(8)
        status_box.set_margin_top(4)
        status_box.set_margin_bottom(4)

        self._status_label = Gtk.Label(label=_("Ready"))
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_hexpand(True)
        self._status_label.add_css_class("dim-label")
        status_box.append(self._status_label)

        self._stats_label = Gtk.Label(label="")
        self._stats_label.set_halign(Gtk.Align.END)
        self._stats_label.add_css_class("dim-label")
        status_box.append(self._stats_label)

        main_box.append(status_box)

    def _set_status(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self._status_label.set_text(f"[{ts}] {msg}")

    def _get_connection(self):
        if self._ha_url and self._ha_token:
            return (self._ha_url, self._ha_token)
        return None

    def _on_connect(self, _btn):
        dialog = ConnectionDialog(self, on_connected=self._on_connected)
        dialog.present(self)

    def _on_connected(self, url, token):
        self._ha_url = url
        self._ha_token = token
        self._connected = True
        self._conn_indicator.set_text("🟢")
        self._conn_indicator.set_tooltip_text(
            _("Connected to %s") % url)
        self._set_status(_("Connected to %s") % url)
        # Auto-fetch entities
        self._entity_browser.refresh()

    def _on_scan_btn(self, _btn):
        self._stack.set_visible_child_name("scanner")

    def _on_integration_selected(self, info):
        """When an integration is selected in scanner, load its strings."""
        path = info['path']
        source = extract_strings_from_component(path)
        lang = self._lang_entry.get_text().strip() or "en"
        target = load_translations_for_component(path, lang)

        self._strings_view.load_strings(source, target)
        self._editor.set_component_path(path)
        self._editor.load_strings(source, target)

        total, translated, pct = self._strings_view.get_coverage_stats()
        self._stats_label.set_text(
            _("Strings: %d | Translated: %d | Coverage: %.0f%%")
            % (total, translated, pct))
        self._set_status(
            _("Loaded integration '%s'") % info['name'])

    def show_about(self, action, param):
        about = Adw.AboutDialog()
        about.set_application_name(_("Home Assistant L10n"))
        about.set_application_icon("se.danielnylander.ha-l10n")
        about.set_developer_name("Daniel Nylander")
        about.set_developers(["Daniel Nylander <daniel@danielnylander.se>"])
        about.set_version(__version__)
        about.set_website("https://github.com/yeager/ha-l10n")
        about.set_issue_url("https://github.com/yeager/ha-l10n/issues")
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_translator_credits(_("Translate this app: https://www.transifex.com/danielnylander/ha-l10n/"))
        about.present(self)

    def show_shortcuts(self, action, param):
        builder = Gtk.Builder()
        builder.add_from_string('''
        <interface>
          <object class="GtkShortcutsWindow" id="shortcuts">
            <property name="modal">True</property>
            <child>
              <object class="GtkShortcutsSection">
                <property name="section-name">shortcuts</property>
                <child>
                  <object class="GtkShortcutsGroup">
                    <property name="title" translatable="yes">General</property>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title" translatable="yes">Show Shortcuts</property>
                        <property name="accelerator">&lt;Primary&gt;slash</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title" translatable="yes">Refresh</property>
                        <property name="accelerator">F5</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title" translatable="yes">Export</property>
                        <property name="accelerator">&lt;Primary&gt;e</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title" translatable="yes">Quit</property>
                        <property name="accelerator">&lt;Primary&gt;q</property>
                      </object>
                    </child>
                  </object>
                </child>
              </object>
            </child>
          </object>
        </interface>
        ''')
        shortcuts = builder.get_object("shortcuts")
        shortcuts.set_transient_for(self)
        shortcuts.present()

    def show_export(self, action, param):
        dialog = ExportDialog(self, self._get_export_data)
        dialog.present(self)

    def _get_export_data(self):
        """Collect data for export."""
        return {
            'strings': self._strings_view.get_strings_data(),
            'source_strings': self._strings_view._source_strings,
            'translations': self._strings_view._target_strings,
            'target_lang': self._lang_entry.get_text().strip() or 'xx',
            'entities': self._entity_browser.get_entities(),
            'integrations': self._scanner.get_integrations(),
        }

    def refresh_data(self):
        """Refresh current view data."""
        page = self._stack.get_visible_child_name()
        self._set_status(_("Refreshing..."))
        if page == "entities":
            self._entity_browser.refresh()
        self._set_status(_("Refreshed"))


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id="se.danielnylander.ha-l10n")

    def do_activate(self):
        self.settings = _load_settings()
        window = self.props.active_window
        if not window:
            window = MainWindow(application=self)
        window.present()

    def do_startup(self):
        Adw.Application.do_startup(self)

        # Actions
        actions = [
            ("quit", self.quit_app),
            ("about", self.show_about),
            ("shortcuts", self.show_shortcuts),
            ("refresh", self.refresh_data),
            ("export", self.show_export),
        ]
        for name, cb in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)

        # Keyboard shortcuts
        self.set_accels_for_action("app.quit", ["<Primary>q"])
        self.set_accels_for_action("app.shortcuts", ["<Primary>slash"])
        self.set_accels_for_action("app.refresh", ["F5"])
        self.set_accels_for_action("app.export", ["<Primary>e"])

    def quit_app(self, action, param):
        self.quit()

    def show_about(self, action, param):
        window = self.props.active_window
        if window:
            window.show_about(action, param)

    def show_shortcuts(self, action, param):
        window = self.props.active_window
        if window:
            window.show_shortcuts(action, param)

    def refresh_data(self, action, param):
        window = self.props.active_window
        if window:
            window.refresh_data()

    def show_export(self, action, param):
        window = self.props.active_window
        if window:
            window.show_export(action, param)


def main():
    app = Application()
    return app.run(sys.argv)


if __name__ == '__main__':
    main()

    # ── Welcome Dialog ───────────────────────────────────────

    def _show_welcome(self, win):
        dialog = Adw.Dialog()
        dialog.set_title(_("Welcome"))
        dialog.set_content_width(420)
        dialog.set_content_height(480)

        page = Adw.StatusPage()
        page.set_icon_name("preferences-desktop-locale-symbolic")
        page.set_title(_("Welcome to Home Assistant L10n"))
        page.set_description(_(
            "Track Home Assistant translation progress.\n\n✓ View translation stats per language\n✓ Find untranslated strings\n✓ Export translation reports\n✓ Compare language coverage"
        ))

        btn = Gtk.Button(label=_("Get Started"))
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.set_halign(Gtk.Align.CENTER)
        btn.set_margin_top(12)
        btn.connect("clicked", self._on_welcome_close, dialog)
        page.set_child(btn)

        box = Adw.ToolbarView()
        hb = Adw.HeaderBar()
        hb.set_show_title(False)
        box.add_top_bar(hb)
        box.set_content(page)
        dialog.set_child(box)
        dialog.present(win)

    def _on_welcome_close(self, btn, dialog):
        self.settings["welcome_shown"] = True
        _save_settings(self.settings)
        dialog.close()



# --- Session restore ---
import json as _json
import os as _os

def _save_session(window, app_name):
    config_dir = _os.path.join(_os.path.expanduser('~'), '.config', app_name)
    _os.makedirs(config_dir, exist_ok=True)
    state = {'width': window.get_width(), 'height': window.get_height(),
             'maximized': window.is_maximized()}
    try:
        with open(_os.path.join(config_dir, 'session.json'), 'w') as f:
            _json.dump(state, f)
    except OSError:
        pass

def _restore_session(window, app_name):
    path = _os.path.join(_os.path.expanduser('~'), '.config', app_name, 'session.json')
    try:
        with open(path) as f:
            state = _json.load(f)
        window.set_default_size(state.get('width', 800), state.get('height', 600))
        if state.get('maximized'):
            window.maximize()
    except (FileNotFoundError, _json.JSONDecodeError, OSError):
        pass
