from collections.abc import Callable
import json
import re
import struct
from typing import Optional
from pathlib import Path

from downscale import downscale_rgb

dir_path = Path(__file__).parent

default_palette = []

def txtParse(text: str):
   assert isinstance(text, str)

   EXPR = r"^\s*([^\s:]+(?:\s+[^\s:]+)*)\s*:\s*(\S+(?:\s+\S+)*)\s*$"

   fields: dict[str, str] = {}
   last_field = None

   for line in text.splitlines():
      if len(line) > 0 and not line.isspace() and not line.strip().startswith("="):
         match = re.search(EXPR, line)

         if match:
            last_field = match.group(1)
            fields[last_field] = match.group(2)
         elif last_field != None and last_field in fields:
            fields[last_field] = fields[last_field] + " " + line.strip()

   return fields

# it's not TOML because it supports tuples in the format STARTUPCOLORS = "#000000", "#FF0000"
# it's not INI because it has quotes around the values
# it's not YAML because of both, and also YAML uses colons instead of equals signs
def gameinfoParse(text: str):
   assert isinstance(text, str)

   fields: dict[str, str] = {}

   for line in text.splitlines():
      if len(line) > 0 and not line.isspace() and not line.strip().startswith("#"):
         sep = line.index("=")
         fields[line[:sep].strip().lower()] = line[sep+1:].strip()
      
   return fields

def readJsonOrPlain(text: str):
   try:
      return json.loads(text)
   except json.JSONDecodeError:
      return text

def str_or_none(input) -> Optional[str]:
   if not input:
      return None
   return str(input)

class Mapset:
   def __init__(self, fullpath: Path, name: str, is_iwad: bool):
      self.config_read: bool = False

      self.fullpath = fullpath
      self.name = name
      self.is_iwad = is_iwad

      self.titlepicpath: Optional[Path] = None
      self.thumbnailpath: Optional[Path] = None
      self.logopath: Optional[Path] = None
      self.title: str = name
      self.basegame: Optional[str] = (self.name if self.is_iwad else None)
   
   def read_config_if_exists(self):
      try:
         with open(dir_path / "wad_meta" / (self.name + ".json"), "r") as meta_file:
            loaded_config = json.load(meta_file)

            self.titlepicpath = Path(loaded_config["titlepicpath"])
            self.thumbnailpath = Path(loaded_config["thumbnailpath"])
            self.logopath = Path(loaded_config["logopath"])
            self.title = loaded_config["title"]
            self.basegame = loaded_config["basegame"]

            self.config_read = True
      except FileNotFoundError:
         pass

   def write_config(self):
      (dir_path / "wad_meta").mkdir(parents=True, exist_ok=True)
      with open(dir_path / "wad_meta" / (self.name + ".json"), "w") as meta_file:
         json.dump({"titlepicpath": str_or_none(self.titlepicpath), "thumbnailpath": str_or_none(self.thumbnailpath), "logopath": str_or_none(self.logopath), "title": self.title, "basegame": self.basegame}, meta_file)

   def read_txt(self, text: str):
      fields = txtParse(text)

      if "Title" in fields:
         self.title = fields["Title"]

      if "Game" in fields and not self.is_iwad:
         self.basegame = fields["Game"]
   
   def read_gameinfo(self, text: str):
      fields = gameinfoParse(text)
      
      if "startuptitle" in fields and self.title == self.name:
         self.title = readJsonOrPlain(fields["startuptitle"])

      if "iwad" in fields and not self.is_iwad:
         self.basegame = readJsonOrPlain(fields["iwad"])

def fixLumpName(name: str):
   if "\0" in name:
      return name[:name.index("\0")]
   return name

class LumpOrFile:
   def __init__(self, data: memoryview, name: str, type: str, path_general: Path):
      self.data = data
      self.name = path_general.stem.lower()
      self.type = type.lower()
      self.path_general = path_general

      if "." in name:
         self.type = path_general.suffix[1:].lower()

      self.amount_read: int = 0

   def read(self, size: int = -1) -> bytes:
      if self.amount_read >= len(self.data):
         return b""
      
      if size < 0:
         size = len(self.data) - self.amount_read

      if self.amount_read + size > len(self.data):
         size = len(self.data) - self.amount_read

      result = self.data[self.amount_read:self.amount_read+size].tobytes()
      self.amount_read += size
      return result
   
   def seek(self, offset: int):
      if offset < 0 or offset > len(self.data):
         raise RuntimeError("seek offset " + str(offset) + " is out of bounds")

      self.amount_read = offset

   def __len__(self):
      return len(self.data)
   
   def chunk(self, start: int, size: int, name: str, type: str, path_in_container: Path) -> "LumpOrFile":
      if start >= len(self.data):
         return LumpOrFile(memoryview(b""), name, type, self.path_general / path_in_container)
      
      if size < 0:
         size = len(self.data) - start

      if start + size > len(self.data):
         size = len(self.data) - start

      result = LumpOrFile(self.data[start:start+size], name, type, self.path_general / path_in_container)
      return result
   
   def get_error_prefix(self):
      return "".join(["in " + item + "\n" for item in self.path_general.parts]) + "\n"
   
   def eof(self):
      return (self.amount_read >= len(self.data))

def handleDoomGraphicLump(lump: LumpOrFile, palette: list[tuple[int, int, int]], outpath: Path, thumbnail_size: tuple[int, int], thumbnail_outpath: Optional[Path]):

   lump.seek(0)
   image_data_x_y: dict[int, dict[int, int]] = {}

   width = struct.unpack("<H", lump.read(2))[0]
   height = struct.unpack("<H", lump.read(2))[0]
   xoffset = struct.unpack("<h", lump.read(2))[0]
   yoffset = struct.unpack("<h", lump.read(2))[0]

   column_pointers = []

   for i in range(width):
      column_pointers.append(struct.unpack("<I", lump.read(4))[0])

   for i in range(width):
      lump.seek(column_pointers[i])
      image_data_x_y[i] = {}

      while True:
         row_start = struct.unpack("<B", lump.read(1))[0]
         if row_start == 255:
            break

         pixel_count = struct.unpack("<B", lump.read(1))[0]

         lump.read(1) # padding byte

         for j in range(pixel_count):
            image_data_x_y[i][j + row_start] = struct.unpack("<B", lump.read(1))[0]

         lump.read(1) # padding byte

   outpath.parent.mkdir(parents=True, exist_ok=True)
   with open(outpath, "wb") as logo:

      # file header
      logo.write(b"P6\n") # magic number
      logo.write(b"# " + str(outpath).encode() + b"\n") # comment
      logo.write(str(width).encode() + b" " + str(height).encode() + b"\n") # width and height
      logo.write(b"255\n")   # depth

      # pixel data
      for y in range(height):
         for x in range(width):
            if x in image_data_x_y and y in image_data_x_y[x]:
               color = palette[image_data_x_y[x][y]]
               logo.write(struct.pack("<BBB", *color))
            else:
               logo.write(struct.pack("<BBB", 255, 255, 255))
   
   if thumbnail_outpath:
      thumbnail_outpath.parent.mkdir(parents=True, exist_ok=True)
      with open(thumbnail_outpath, "wb") as thumbnail:

         # file header
         thumbnail.write(b"P6\n") # magic number
         thumbnail.write(b"# " + str(thumbnail_outpath).encode() + b"\n") # comment
         thumbnail.write(f"{thumbnail_size[0]} {thumbnail_size[1]}\n".encode()) # width and height
         thumbnail.write(b"255\n")   # depth

         image_data_x_y_rgb = []
         
         for x in range(width):
            image_data_x_y_rgb.append([])
            for y in range(height):
               if x in image_data_x_y and y in image_data_x_y[x]:
                  color = palette[image_data_x_y[x][y]]
                  image_data_x_y_rgb[x].append(color)
               else:
                  image_data_x_y_rgb[x].append((255, 255, 255))

         # pixel data
         downscaled_data = downscale_rgb((width, height), thumbnail_size, image_data_x_y_rgb)
         for y in range(thumbnail_size[1]):
            for x in range(thumbnail_size[0]):
               color = downscaled_data[x][y]
               thumbnail.write(struct.pack("<BBB", *color))

def print_lumps(lumps: dict[str, LumpOrFile]):
   for lumpname in lumps:
      lump = lumps[lumpname]
      print(f"{lumpname}:\t{lump.type}\t{lump.path_general}")

def check_magic_number(lump: LumpOrFile, *args: int):
   for arg in args:
      if not lump.eof() and int(lump.read(1)[0]) != arg:
         return False
      
   return True

def wadParse(wad_file: LumpOrFile, handleWadReadError: Callable[[str], None]) -> dict[str, LumpOrFile]:
   wad_type = wad_file.read(4).decode("ascii")
   lump_count = struct.unpack("<i", wad_file.read(4))[0]
   directory_pointer = struct.unpack("<i", wad_file.read(4))[0]

   if wad_type not in ["IWAD", "PWAD"]:
      handleWadReadError(wad_file.get_error_prefix() + "error while reading WAD file:\n" + f"Invalid WAD type: {wad_type}")

   wad_file.seek(directory_pointer)

   lumps: dict[str, LumpOrFile] = {}
   lump_pointers: dict[str, int] = {}
   lump_sizes = {}

   for i in range(lump_count):
      lump_pointer = struct.unpack("<i", wad_file.read(4))[0]
      lump_size = struct.unpack("<i", wad_file.read(4))[0]
      lump_name = fixLumpName(wad_file.read(8).decode("ascii"))
      new_lump = wad_file.chunk(lump_pointer, lump_size, lump_name, "lmp", Path(lump_name))

      if not "." in lump_name:
         new_lump.seek(0)
         if check_magic_number(new_lump, 0x89, 0x50, 0x4E, 0x47):
            new_lump.type = "png"
         else:
            new_lump.seek(0)
            if check_magic_number(new_lump, 0xFF, 0xD8, 0xFF):
               new_lump.type = "jpg"
            else:
               new_lump.type = "lmp"

         new_lump.seek(0)

      lump_pointers[new_lump.name] = lump_pointer
      lump_sizes[new_lump.name] = lump_size
      lumps[new_lump.name] = new_lump

   return lumps

with open(dir_path / "default_palette.csv", "r") as palette_file:
   for line in palette_file:
      r, g, b = line.strip().split(",")
      default_palette.append((int(r), int(g), int(b)))