Set sh = CreateObject("WScript.Shell")
p = WScript.ScriptFullName
base = Left(p, InStrRev(p, "\"))
sh.CurrentDirectory = base
cmd = """" & base & ".venv\Scripts\pythonw.exe"" """ & base & "main.py"""
sh.Run cmd, 0, False