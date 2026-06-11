# Systemd Cheat Sheet

Used in a terminal window to manage the capture_serial systemd service on a Raspberry Pi deployment.  
Commands beginning with "sudo" require the current user to have sudo privileges (~admin access). 

## Service Lifecycle

__Reload service definitions:__
- sudo systemctl daemon-reload  
- (after editing a '.service' file)  

__Enable service at boot (run once):__
- sudo systemctl enable lsc-capture.service  

__Disable service at boot:__
- sudo systemctl disable lsc-capture.service  

__Start service now:__
- sudo systemctl start lsc-capture.service  

__Stop service:__
- sudo systemctl stop lsc-capture.service  

__Restart service:__
- sudo systemctl restart lsc-capture.service  

## Status & Health

__Check current status:__
- systemctl status lsc-capture.service --no-pager  
- (shows whether it's running, recent messages, and errors)  

__Logs (similar to Windows Event Viewer)__
- journalctl -u lsc-capture.service  

__Follow logs live:__
- journalctl -u lsc-capture.service -f  

__Show recent logs only:__  
- journalctl -u lsc-capture.service --since "10 minutes ago"  
- Content within " " can be modified (e.g. today, 2 hours ago, etc)  

__Show last 20 journal entries:__  
- journalctl -u lsc-capture.service -n 20 --no-pager**  
Options:  
  - u = unit  
  - n = number of entries to display    

__Confirm the service is enabled at boot:__  
- systemctl is-enabled lsc-capture.service  

## When You Change the Script

__If you modify 'capture_serial.py':__  
- sudo systemctl restart lsc-capture.service  
- Changes take effect immediately (no reboot required)  

### Very Important
- Never run the script manually while the service is running  
- Never enable the service until you are done testing manually  
- The serial port can only be owned by one process at a time.  

If the service is disabled and the script needs to be run:  
- python3 capture_serial.py
  
