"""Export functionality for ha-l10n."""

import csv
import io
import json
import gettext
from datetime import datetime
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

from ha_l10n import __version__

_ = gettext.gettext

APP_LABEL = "HA L10n"
AUTHOR = "Daniel Nylander"


def export_csv(data, filepath):
    """Export string data to CSV."""
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([_("Key"), _("Source"), _("Target"), _("Status")])
        for item in data:
            writer.writerow([
                item.get('key', ''),
                item.get('source', ''),
                item.get('target', ''),
                item.get('status', ''),
            ])
        writer.writerow([])
        writer.writerow([f"{APP_LABEL} v{__version__} — {AUTHOR}"])


def export_json_report(data, filepath):
    """Export string data to JSON report."""
    report = {
        'generated': datetime.now().isoformat(),
        'total_strings': len(data),
        'translated': sum(1 for d in data if d.get('status') == 'translated'),
        'strings': data,
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def export_ha_json(translations, filepath):
    """Export translations in HA JSON format (nested)."""
    nested = {}
    for key, val in translations.items():
        if not val:
            continue
        parts = key.split('.')
        d = nested
        for p in parts[:-1]:
            d = d.setdefault(p, {})
        d[parts[-1]] = val
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(nested, f, indent=2, ensure_ascii=False)
        f.write('\n')


def export_pot(source_strings, filepath, package="ha-custom-component"):
    """Export source strings as a POT file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f'''# Translation template for {package}.
# Copyright (C) {datetime.now().year}
# This file is distributed under the same license as the {package} package.
#
#, fuzzy
msgid ""
msgstr ""
"Project-Id-Version: {package}\\n"
"POT-Creation-Date: {datetime.now().strftime('%Y-%m-%d %H:%M%z')}\\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"
"Language-Team: LANGUAGE <LL@li.org>\\n"
"Language: \\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"

''')
        for key, value in sorted(source_strings.items()):
            escaped = value.replace('\\', '\\\\').replace('"', '\\"')
            f.write(f'#. {key}\n')
            f.write(f'msgid "{escaped}"\n')
            f.write(f'msgstr ""\n\n')


def export_po(source_strings, translations, filepath, lang,
              package="ha-custom-component"):
    """Export translations as a PO file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f'''# {lang} translation for {package}.
#
msgid ""
msgstr ""
"Project-Id-Version: {package}\\n"
"PO-Revision-Date: {datetime.now().strftime('%Y-%m-%d %H:%M%z')}\\n"
"Language: {lang}\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"

''')
        for key, value in sorted(source_strings.items()):
            escaped_src = value.replace('\\', '\\\\').replace('"', '\\"')
            trans = translations.get(key, '')
            escaped_tgt = trans.replace('\\', '\\\\').replace('"', '\\"')
            f.write(f'#. {key}\n')
            f.write(f'msgid "{escaped_src}"\n')
            f.write(f'msgstr "{escaped_tgt}"\n\n')


class ExportDialog(Adw.Dialog):
    """Export dialog triggered by Ctrl+E."""

    def __init__(self, parent_window, get_export_data):
        super().__init__()
        self.set_title(_("Export"))
        self.set_content_width(400)
        self.set_content_height(350)
        self._parent_window = parent_window
        self._get_data = get_export_data

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

        group = Adw.PreferencesGroup(title=_("Export Format"))
        content.append(group)

        self._format_combo = Adw.ComboRow(title=_("Format"))
        model = Gtk.StringList()
        for fmt in [_("CSV Report"), _("JSON Report"),
                    _("HA JSON Translation"), _("POT File"), _("PO File")]:
            model.append(fmt)
        self._format_combo.set_model(model)
        group.add(self._format_combo)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        content.append(btn_box)

        export_btn = Gtk.Button(label=_("Export..."))
        export_btn.add_css_class("suggested-action")
        export_btn.connect("clicked", self._on_export)
        btn_box.append(export_btn)

        self._status = Gtk.Label(label="")
        self._status.set_halign(Gtk.Align.START)
        self._status.add_css_class("dim-label")
        content.append(self._status)

    def _on_export(self, _btn):
        fmt_idx = self._format_combo.get_selected()
        extensions = [".csv", ".json", ".json", ".pot", ".po"]
        ext = extensions[fmt_idx]

        dialog = Gtk.FileDialog()
        dialog.set_initial_name(f"ha-l10n-export{ext}")
        dialog.save(self._parent_window, None, self._on_save_response,
                     fmt_idx)

    def _on_save_response(self, dialog, result, fmt_idx):
        try:
            file = dialog.save_finish(result)
            if not file:
                return
            filepath = file.get_path()
            data = self._get_data()
            strings_data = data.get('strings', [])
            source = data.get('source_strings', {})
            translations = data.get('translations', {})
            lang = data.get('target_lang', 'xx')

            if fmt_idx == 0:
                export_csv(strings_data, filepath)
            elif fmt_idx == 1:
                export_json_report(strings_data, filepath)
            elif fmt_idx == 2:
                export_ha_json(translations, filepath)
            elif fmt_idx == 3:
                export_pot(source, filepath)
            elif fmt_idx == 4:
                export_po(source, translations, filepath, lang)

            self._status.set_text(_("Exported to %s") % filepath)
        except GLib.Error:
            pass
        except Exception as e:
            self._status.set_text(_("Error: %s") % str(e))
