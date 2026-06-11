Contains example systemd service configuration template for running the capture script as a background service.

___TEMPLATE ONLY - must be customized before use___

## How to Find Your Serial Port ID

1. Open a command terminal window
2. Type: ***ls /dev/serial/by-id/***

## Serial Port Permissions (Required)

Users must have permission to access the serial device.

On Raspberry Pi OS, this typically requires membership in the 'dialout' group.

#### To add a user (case sensitive):

1. Open a command terminal window
2. Type: ***sudo usermod -a -G dialout youruser***

After running this command, log out and log back in (or reboot) for changes to take effect.

Without this step, the system may fail to receive serial data even if the service is running.
