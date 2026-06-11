Contains example systemd service configuration template for running the capture script as a background service.

___TEMPLATE ONLY - must be customized before use___

**This template is not usable as-is.  Paths, user name, and device identifiers must be customized for your environment.**

## Serial Port Permissions (Required)

Users must have permission to access the serial device.

On Raspberry Pi OS, this typically requires membership in the 'dialout' group.

## Basic Setup Steps

_Note: All commands are case-sensitive.  Differences in capitalization will change behavior or cause errors._

1. Identify your serial device:  
   ***ls /dev/serial/by-id/***

    This will list connected serial devices.  Use the full path shown here when configuring the service file.

2. Add your user to the dialout group (required for serial access):  
   ***sudo usermod -a -G dialout youruser***

   Log out and back in (or reboot) after running this command.

   If this step is skipped, the service file may run but no data will be received

4. Copy the service file:  
   ***sudo cp capture_serial.service /etc/systemd/system/***

5. Edit the service file to match your environment:

    On Raspberry Pi OS, you may use:
     - Mousepad (basic text editor
     - Thonny (user-friendly code editor)
    These can be opened from the application menu.

    Update the following fields:
     - User
     - ExecStart path
     - Serial device path

6. Reload systemd:  
   ***sudo systemctl daemon-reload***

7. Enable and start the service (_successive commands_):  
   ***sudo systemctl enable lsc-capture.service***  
   ***sudo systemctl start lsc-capture.service***

Once running, use the systemd_cheatsheet.md in the docs/ directory for service management and troubleshooting.
