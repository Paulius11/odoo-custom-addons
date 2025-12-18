# User Permission Copy

Streamline user onboarding by copying permissions from one user to another with a simple wizard interface.

![User Permission Copy](static/description/screenshot_1.png)

## Features

- **Quick Replication**: Copy all permissions from a source user to one or more target users
- **Wizard Interface**: Easy-to-use guided process with clear steps
- **Complete Copy**: Transfers all security groups, access rights, and rule assignments
- **Safety First**: Confirmation dialog prevents accidental permission changes
- **Multi-user Support**: Copy permissions to multiple users at once
- **Audit Trail**: Track who copied what permissions and when

## Installation

1. Download the module to your Odoo addons directory
2. Update the app list in your Odoo instance
3. Install "User Permission Copy" from the Apps menu
4. Access the wizard from Settings → Users & Companies → Users

## Configuration

No additional configuration required. The module is ready to use immediately after installation.

## Usage

1. Navigate to Settings → Users & Companies → Users
2. Select the user whose permissions you want to copy (source user)
3. Click the "Copy Permissions" button (or use the Action menu)
4. In the wizard, select one or more target users
5. Review the summary showing what will be copied
6. Click "Confirm" to complete the permission copy
7. Target users will immediately have the same permissions as the source user

**Note**: The target user's existing permissions will be completely replaced with the source user's permissions.

## Use Cases

- **New Employee Onboarding**: Quickly set up new users with the same permissions as existing team members in the same role
- **Role Standardization**: Ensure all users in the same department or role have identical permissions
- **Permission Templates**: Use experienced users as templates when creating new user accounts
- **Team Restructuring**: Rapidly adjust permissions when reorganizing teams

## Technical Details

- **Dependencies**: `base`
- **Compatibility**: Odoo 17.0+
- **License**: LGPL-3
- **What Gets Copied**:
  - Security Groups (res.groups)
  - Access Rights (ir.model.access)
  - Record Rules (ir.rule)
- **What Doesn't Get Copied**:
  - User personal settings
  - Login credentials
  - User contact information
