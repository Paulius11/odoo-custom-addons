# Quick Language Switcher

Switch between languages instantly with a convenient navbar dropdown - no need to navigate to preferences!

![Language Switcher](static/description/screenshot_1.png)

## Features

- **Navbar Integration**: Language selector appears directly in the Odoo navbar for instant access
- **One-Click Switching**: Change languages with a single click - no page navigation required
- **All Languages**: Access all installed and activated languages from the dropdown
- **Instant Reload**: Interface updates immediately after language selection
- **Universal Compatibility**: Works on all Odoo screens and modules
- **Zero Configuration**: Ready to use immediately after installation - no setup needed

## Installation

1. Download the module to your Odoo addons directory
2. Update the app list in your Odoo instance
3. Install "Quick Language Switcher" from the Apps menu
4. The language switcher will appear automatically in your navbar

**Prerequisite**: Activate your desired languages in Settings → Translations → Languages before using the switcher.

## Configuration

### Prerequisites

Before using the language switcher, you need to activate languages:

1. Go to Settings → Translations → Languages
2. Find the languages you want to use
3. Click "Activate" for each language
4. The activated languages will automatically appear in the switcher

**Note**: Only activated languages will be shown in the language switcher dropdown.

## Usage

1. Look for the language switcher icon in the top navbar (next to your user menu)
2. Click the language switcher to open the dropdown
3. Select your desired language from the list
4. The page will reload automatically with the new language
5. Your language preference is saved for your session

**Tip**: The language switcher shows the language names in their native form (e.g., "English", "Español", "Français").

## Use Cases

- **International Teams**: Team members who speak multiple languages can quickly switch based on their preference
- **Multi-language Organizations**: Support employees working in different languages without navigation hassle
- **Client Demonstrations**: Easily switch languages during presentations to show features in client's preferred language
- **Translation Testing**: Developers and translators can quickly verify translations across different languages
- **Training Sessions**: Instructors can demonstrate the system in multiple languages

## Technical Details

- **Dependencies**: `web`, `base`
- **Compatibility**: Odoo 17.0+
- **License**: LGPL-3
- **Implementation**:
  - Lightweight JavaScript component
  - Uses Odoo's native language system
  - No database modifications required
  - Compatible with all language packs
- **Performance**: Minimal resource usage, native Odoo session handling 