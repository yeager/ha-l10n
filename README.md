# Home Assistant L10n

[![Version](https://img.shields.io/badge/version-0.2.0-blue)](https://github.com/yeager/ha-l10n/releases)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%203.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Transifex](https://img.shields.io/badge/Transifex-Translate-green.svg)](https://www.transifex.com/danielnylander/ha-l10n/)

Translation status viewer for Home Assistant — GTK4/Adwaita.

![Screenshot](screenshots/main.png)

## Features

- **Translation stats** — view completion status for all HA components
- **Language selector** — check any of 60+ supported languages
- **Component browser** — frontend, backend, integrations, add-ons
- **Progress bars** — visual completion percentages
- **CSV export** — export stats with app branding (Ctrl+E)
- **Dark/light theme** toggle

## Installation

### Debian/Ubuntu

```bash
echo "deb [signed-by=/usr/share/keyrings/yeager-keyring.gpg] https://yeager.github.io/debian-repo stable main" | sudo tee /etc/apt/sources.list.d/yeager.list
curl -fsSL https://yeager.github.io/debian-repo/yeager-keyring.gpg | sudo tee /usr/share/keyrings/yeager-keyring.gpg > /dev/null
sudo apt update && sudo apt install ha-l10n
```

### Fedora/openSUSE

```bash
sudo dnf config-manager --add-repo https://yeager.github.io/rpm-repo/yeager.repo
sudo dnf install ha-l10n
```

### From source

```bash
git clone https://github.com/yeager/ha-l10n.git
cd ha-l10n && pip install -e .
ha-l10n
```

## Translation

Help translate on [Transifex](https://www.transifex.com/danielnylander/ha-l10n/).

## License

GPL-3.0-or-later — see [LICENSE](LICENSE) for details.

## Author

**Daniel Nylander** — [danielnylander.se](https://danielnylander.se)
