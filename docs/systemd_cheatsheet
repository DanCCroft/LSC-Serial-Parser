# Systemd Cheat Sheet

Used in a terminal window  
- Commands leading with "sudo" require the current user to be part of the sudo group (~admin)  

## Service Lifecycle

Reload service definitions:
  - sudo systemctl daemon-reload  
  - (after editing a '.service' file)  

Enable service at boot (run once):
  - sudo systemctl enable lsc-capture.service  

Disable service at boot:
  - sudo systemctl disable lsc-capture.service  

Start service now:
  - sudo systemctl start lsc-capture.service  

Stop service:
  - sudo systemctl stop lsc-capture.service  

Restart service:
  - sudo systemctl restart lsc-capture.service  

## Status & Health

Check current status:
  - systemctl status lsc-capture.service  
  - (shows whether it's running, recent messages, and errors)  

Logs (Equivalent to Event Viewer)
  - journalctl -u lsc-capture.service  

Follow logs live
  - journalctl -u lsc-capture.service -f  

Show recent logs only:  
  - journalctl -u lsc-capture.service --since "10 minutes ago"  
  - Content within " " can be modified.  

Show last 20 journal entries:  
  - journalctl -u lsc-capture.service -n 20 --no pager  
  - u = unit  
  - n = number of entries to display  
  - --no pager: do not route through a pager  

## Safety Commands

Comfirm the service is enabled at boot:  
  - systemctl is-enabled lsc-capture.service  

## When You Change the Script

If you modify 'capture_serial.py':  
  - sudo systemctl restart lsc-capture.service  
  - no reboot required  

## Very Important
- Never run the script manually while the service is running  
- Never enable the service until you are done testing manually  
- The serial port can only be owned by one process at a time.  
- If the service is disabled and the script needs to be run:  
    - python3 capture_serial.py
  
