' Stop Paper Crawler Web UI
' Double-click to stop the streamlit service

Option Explicit

Dim WshShell
Set WshShell = CreateObject("WScript.Shell")

On Error Resume Next
WshShell.Run "taskkill /F /IM streamlit.exe", 0, True
On Error GoTo 0

MsgBox "Paper Crawler Web UI stopped.", vbInformation, "Stopped"
