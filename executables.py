import struct
from pathlib import Path
import os
from typing import Literal

# https://stackoverflow.com/a/28952464
def read_link(path: Path):
   with open(path, 'rb') as stream:
      content = stream.read()
      # skip first 20 bytes (HeaderSize and LinkCLSID)
      # read the LinkFlags structure (4 bytes)
      lflags = struct.unpack('I', content[0x14:0x18])[0]
      position = 0x18
      # if the HasLinkTargetIDList bit is set then skip the stored IDList 
      # structure and header
      if (lflags & 0x01) == 1:
         position = struct.unpack('H', content[0x4C:0x4E])[0] + 0x4E
      last_pos = position
      position += 0x04
      # get how long the file information is (LinkInfoSize)
      length = struct.unpack('I', content[last_pos:position])[0]
      # skip 12 bytes (LinkInfoHeaderSize, LinkInfoFlags, and VolumeIDOffset)
      position += 0x0C
      # go to the LocalBasePath position
      lbpos = struct.unpack('I', content[position:position+0x04])[0]
      position = last_pos + lbpos
      # read the string at the given position of the determined length
      size= (length + last_pos) - position - 0x02
      temp = struct.unpack('c' * size, content[position:position+size])
      target = ''.join([chr(ord(a)) for a in temp])
      return target

program_names: dict[Path, str] = {}

if os.name == "nt":
   import json
   import subprocess
   import winreg

   REGISTRY_PATHS_TO_CHECK = [
      r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\App Paths",
      r"HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\App Paths",
   ]

   try:
      psresult = subprocess.run(["powershell", "-Command", "Get-StartApps | ConvertTo-Json"], capture_output=True, text=True, check=True)
      programs = psresult.stdout
   except subprocess.CalledProcessError as e:
      programs = "[]"
      print("failed to get list of windows programs: " + str(e.returncode))

   parsed: list[dict[Literal["Name"] | Literal["AppID"], str]] = json.loads(programs)

   for program in parsed:
      if not any(piece in program["Name"].lower() for piece in ("uninstall", "eula", "license", "help")):
         if len(program["AppID"]) > 3 and program["AppID"][0].isalpha() and program["AppID"][1] == ":" and program["AppID"][2] == "\\":
            path = Path(program["AppID"])
            if path.exists():
               program_names[path] = program["Name"]
         else:
            for key in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
               try:
                  with winreg.OpenKey(key, "Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\" + program["AppID"], 0, winreg.KEY_READ):
                     app_path, reg_type = winreg.QueryValueEx(key, "")
                     program_names[Path(app_path)] = program["Name"]
               except FileNotFoundError:
                  pass
               except OSError as e:
                  print(f"error while getting app path: type={key} name={program["Name"]} id={program["AppID"]}")
                  print(e)