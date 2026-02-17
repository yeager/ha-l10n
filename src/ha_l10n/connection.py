"""Home Assistant connection management."""

import json
import os
import gettext
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

_ = gettext.gettext

CONFIG_DIR = Path(os.path.expanduser("~/.config/ha-l10n"))
INSTANCES_FILE = CONFIG_DIR / "instances.json"


def _ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_instances():
    """Load saved HA instances."""
    if INSTANCES_FILE.exists():
        try:
            with open(INSTANCES_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_instances(instances):
    """Save HA instances to config."""
    _ensure_config_dir()
    with open(INSTANCES_FILE, 'w') as f:
        json.dump(instances, f, indent=2)


def ha_api_request(url, token, endpoint):
    """Make a request to the HA REST API."""
    full_url = urljoin(url.rstrip('/') + '/', endpoint.lstrip('/'))
    req = Request(full_url)
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Content-Type', 'application/json')
    resp = urlopen(req, timeout=10)
    return json.loads(resp.read().decode('utf-8'))


def test_connection(url, token):
    """Test connection to HA instance. Returns (success, message)."""
    try:
        data = ha_api_request(url, token, '/api/')
        return True, data.get('message', _("Connected"))
    except HTTPError as e:
        return False, _("HTTP Error: %s") % e.code
    except URLError as e:
        return False, _("Connection failed: %s") % e.reason
    except Exception as e:
        return False, str(e)


def fetch_states(url, token):
    """Fetch all entity states from HA."""
    return ha_api_request(url, token, '/api/states')


class ConnectionDialog(Adw.Dialog):
    """Dialog for managing HA connections."""

    def __init__(self, parent_window, on_connected=None):
        super().__init__()
        self.set_title(_("Connect to Home Assistant"))
        self.set_content_width(500)
        self.set_content_height(400)
        self._parent_window = parent_window
        self._on_connected = on_connected

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        self.set_child(toolbar_view)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        toolbar_view.set_content(content)

        # Profile selector
        profiles_group = Adw.PreferencesGroup(title=_("Saved Instances"))
        content.append(profiles_group)

        self._profile_combo = Adw.ComboRow(title=_("Profile"))
        self._profile_model = Gtk.StringList()
        self._instances = load_instances()
        self._profile_model.append(_("New connection"))
        for inst in self._instances:
            self._profile_model.append(inst.get('name', inst.get('url', '')))
        self._profile_combo.set_model(self._profile_model)
        self._profile_combo.connect("notify::selected", self._on_profile_selected)
        profiles_group.add(self._profile_combo)

        # Connection details
        conn_group = Adw.PreferencesGroup(title=_("Connection Details"))
        content.append(conn_group)

        self._name_row = Adw.EntryRow(title=_("Name"))
        conn_group.add(self._name_row)

        self._url_row = Adw.EntryRow(title=_("URL"))
        self._url_row.set_text("http://homeassistant.local:8123")
        conn_group.add(self._url_row)

        self._token_row = Adw.PasswordEntryRow(title=_("Long-Lived Access Token"))
        conn_group.add(self._token_row)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        content.append(btn_box)

        self._test_btn = Gtk.Button(label=_("Test Connection"))
        self._test_btn.connect("clicked", self._on_test)
        btn_box.append(self._test_btn)

        self._save_btn = Gtk.Button(label=_("Save Profile"))
        self._save_btn.add_css_class("suggested-action")
        self._save_btn.connect("clicked", self._on_save)
        btn_box.append(self._save_btn)

        self._connect_btn = Gtk.Button(label=_("Connect"))
        self._connect_btn.add_css_class("suggested-action")
        self._connect_btn.connect("clicked", self._on_connect)
        btn_box.append(self._connect_btn)

        # Status
        self._status = Gtk.Label(label="")
        self._status.set_halign(Gtk.Align.START)
        self._status.add_css_class("dim-label")
        content.append(self._status)

        self._delete_btn = Gtk.Button(label=_("Delete Profile"))
        self._delete_btn.add_css_class("destructive-action")
        self._delete_btn.connect("clicked", self._on_delete)
        self._delete_btn.set_sensitive(False)
        btn_box.prepend(self._delete_btn)

    def _on_profile_selected(self, combo, _pspec):
        idx = combo.get_selected()
        if idx > 0 and idx - 1 < len(self._instances):
            inst = self._instances[idx - 1]
            self._name_row.set_text(inst.get('name', ''))
            self._url_row.set_text(inst.get('url', ''))
            self._token_row.set_text(inst.get('token', ''))
            self._delete_btn.set_sensitive(True)
        else:
            self._name_row.set_text("")
            self._url_row.set_text("http://homeassistant.local:8123")
            self._token_row.set_text("")
            self._delete_btn.set_sensitive(False)

    def _on_test(self, _btn):
        url = self._url_row.get_text()
        token = self._token_row.get_text()
        self._status.set_text(_("Testing..."))

        def do_test():
            ok, msg = test_connection(url, token)
            GLib.idle_add(lambda: self._status.set_text(
                "✅ " + msg if ok else "❌ " + msg))

        import threading
        threading.Thread(target=do_test, daemon=True).start()

    def _on_save(self, _btn):
        name = self._name_row.get_text() or self._url_row.get_text()
        url = self._url_row.get_text()
        token = self._token_row.get_text()

        entry = {'name': name, 'url': url, 'token': token}

        idx = self._profile_combo.get_selected()
        if idx > 0 and idx - 1 < len(self._instances):
            self._instances[idx - 1] = entry
        else:
            self._instances.append(entry)

        save_instances(self._instances)
        self._status.set_text(_("Profile saved"))

    def _on_delete(self, _btn):
        idx = self._profile_combo.get_selected()
        if idx > 0 and idx - 1 < len(self._instances):
            del self._instances[idx - 1]
            save_instances(self._instances)
            # Rebuild model
            while self._profile_model.get_n_items() > 0:
                self._profile_model.remove(0)
            self._profile_model.append(_("New connection"))
            for inst in self._instances:
                self._profile_model.append(inst.get('name', inst.get('url', '')))
            self._profile_combo.set_selected(0)
            self._status.set_text(_("Profile deleted"))

    def _on_connect(self, _btn):
        url = self._url_row.get_text()
        token = self._token_row.get_text()
        self._status.set_text(_("Connecting..."))

        def do_connect():
            ok, msg = test_connection(url, token)
            def finish():
                if ok:
                    self._status.set_text("✅ " + msg)
                    if self._on_connected:
                        self._on_connected(url, token)
                    self.close()
                else:
                    self._status.set_text("❌ " + msg)
            GLib.idle_add(finish)

        import threading
        threading.Thread(target=do_connect, daemon=True).start()
