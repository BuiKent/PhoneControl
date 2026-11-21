Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir

launcher = ""
Set execObj = WshShell.Exec("where.exe pythonw.exe")
Do While Not execObj.StdOut.AtEndOfStream
    line = Trim(execObj.StdOut.ReadLine())
    If Len(line) > 0 And InStr(1, line, "WindowsApps", vbTextCompare) = 0 Then
        If fso.FileExists(line) Then
            launcher = """" & line & """"
            Exit Do
        End If
    End If
Loop
If launcher = "" Then launcher = "pythonw.exe"

WshShell.Run launcher & " """ & scriptDir & "\main.py""", 1, False
