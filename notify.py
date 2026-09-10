"""Windows notification backends for WSL2.

Three backends, because toast delivery is unreliable for non-packaged apps:

  msgbox  a modal dialog. Confirmed working on this machine. Always renders,
          but steals focus and blocks until dismissed.
  balloon a tray balloon tip via NotifyIcon. No AppID registration needed.
  toast   a native Windows toast. Silently dropped on this machine: the API
          reports success and Setting=Enabled, but nothing renders.

Select with the GO_NOTIFY env var. Default is msgbox.
"""
import os, json, subprocess, sys

# cron runs with PATH=/usr/bin:/bin, so this must be absolute
POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
APP_ID = "opencode.Go.Monitor"
BACKEND = os.environ.get("GO_NOTIFY", "msgbox")


def _run(script, timeout=60):
    try:
        subprocess.run([POWERSHELL, "-NoProfile", "-Command", script],
                       check=True, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        print(f"notify: {BACKEND} backend failed: {e}", file=sys.stderr)
        return False


def _msgbox(title, message):
    return _run(f'''
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object System.Windows.Forms.Form
$f.TopMost = $true; $f.Size = New-Object System.Drawing.Size(1,1)
$f.StartPosition = "CenterScreen"; $f.Show()
[System.Windows.Forms.MessageBox]::Show($f, {json.dumps(message)}, {json.dumps(title)}, "OK", "Information") | Out-Null
''', timeout=3600)  # blocks until dismissed


def _balloon(title, message, seconds=15):
    return _run(f'''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.BalloonTipTitle = {json.dumps(title)}
$n.BalloonTipText = {json.dumps(message)}
$n.ShowBalloonTip({seconds * 1000})
$end = (Get-Date).AddSeconds({seconds - 1})
while ((Get-Date) -lt $end) {{ [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 200 }}
$n.Dispose()
''', timeout=seconds + 30)


def _toast(title, message):
    return _run(f'''
[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime] | Out-Null
$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$t.GetElementsByTagName("text").Item(0).AppendChild($t.CreateTextNode({json.dumps(title)})) | Out-Null
$t.GetElementsByTagName("text").Item(1).AppendChild($t.CreateTextNode({json.dumps(message)})) | Out-Null
$x=$t.GetElementsByTagName("toast").Item(0); $x.SetAttribute("duration","long")
$n=[Windows.UI.Notifications.ToastNotification]::new($t)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier({json.dumps(APP_ID)}).Show($n)
''')


BACKENDS = {"msgbox": _msgbox, "balloon": _balloon, "toast": _toast}


def notify(title, message):
    """Raise a notification using the GO_NOTIFY backend. Returns True on success."""
    fn = BACKENDS.get(BACKEND)
    if fn is None:
        print(f"notify: unknown backend {BACKEND!r}, "
              f"expected one of {', '.join(BACKENDS)}", file=sys.stderr)
        return False
    return fn(title, message)
