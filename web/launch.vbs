' Paper Crawler Web UI Launcher (no CMD window)
' Double-click to start, then open http://127.0.0.1:8501 in browser
' To stop: double-click stop.vbs in the same folder

Option Explicit

Dim WshShell, fso, projectRoot, streamlitExe, cmd
Dim env

Set fso = CreateObject("Scripting.FileSystemObject")
projectRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
streamlitExe = projectRoot & "\.venv\Scripts\streamlit.exe"

If Not fso.FileExists(streamlitExe) Then
    MsgBox "streamlit.exe not found." & vbCrLf & "Please run: pip install -r requirements.txt", vbCritical, "Launch Failed"
    WScript.Quit 1
End If

Set WshShell = CreateObject("WScript.Shell")
Set env = WshShell.Environment("PROCESS")

env("STREAMLIT_TELEMETRY_OPT_OUT") = "1"
env("STREAMLIT_BROWSER_GATHERUSAGESTATS") = "false"
env("STREAMLIT_SERVER_ADDRESS") = "127.0.0.1"
env("STREAMLIT_SERVER_PORT") = "8501"
env("STREAMLIT_SERVER_HEADLESS") = "true"

cmd = """" & streamlitExe & """ run """ & projectRoot & "\web\streamlit_app.py"""

WshShell.Run cmd, 0, False

MsgBox "Paper Crawler Web UI started!" & vbCrLf & vbCrLf & _
       "Open in browser: http://127.0.0.1:8501" & vbCrLf & vbCrLf & _
       "To stop: double-click stop.vbs", vbInformation, "Started"
