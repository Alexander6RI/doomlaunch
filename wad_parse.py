from collections.abc import Callable
import json
import os
import re
import struct
from typing import IO, Optional

from downscale import downscale_rgb

dir_path = os.path.dirname(os.path.abspath(__file__))

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

class Mapset:
   def __init__(self, fullpath: str, name: str, is_iwad: bool):
      self.config_read: bool = False

      self.fullpath = fullpath
      self.name = name
      self.is_iwad = is_iwad

      self.titlepicpath: Optional[str] = None
      self.thumbnailpath: Optional[str] = None
      self.logopath: Optional[str] = None
      self.title = name
   
   def read_config_if_exists(self):
      try:
         with open(os.path.join(dir_path, "wad_meta", self.name + ".json"), "r") as meta_file:
            loaded_config = json.load(meta_file)

            self.titlepicpath = loaded_config["titlepicpath"]
            self.thumbnailpath = loaded_config["thumbnailpath"]
            self.logopath = loaded_config["logopath"]
            self.title = loaded_config["title"]

            self.config_read = True
      except FileNotFoundError:
         pass

   def write_config(self):
      os.makedirs(os.path.join(dir_path, "wad_meta"), exist_ok=True)
      with open(os.path.join(dir_path, "wad_meta", self.name + ".json"), "w") as meta_file:
         json.dump({"titlepicpath": self.titlepicpath, "thumbnailpath": self.thumbnailpath, "logopath": self.logopath, "title": self.title}, meta_file)

   def read_txt(self, text: str):
      fields = txtParse(text)

      if "Title" in fields:
         self.title = fields["Title"]
   
   def read_gameinfo(self, text: str):
      fields = gameinfoParse(text)
      
      if "startuptitle" in fields and self.title == self.name:
         self.title = json.loads(fields["startuptitle"])

def fixLumpName(name: str):
   if "\0" in name:
      return name[:name.index("\0")]
   return name

def is_ascii_str(input: bytes, check: str):
   try:
      input.decode("ascii")
      return (input == check)
   except UnicodeDecodeError:
      return False

def wadParse(mapset: Mapset, wad_file: IO[bytes], thumbnail_size: tuple[int, int], handleWadReadError: Callable[[str], None]):
   wad_type = wad_file.read(4).decode("ascii")
   lump_count = struct.unpack("<i", wad_file.read(4))[0]
   directory_pointer = struct.unpack("<i", wad_file.read(4))[0]

   if wad_type not in ["IWAD", "PWAD"]:
      return

   wad_file.seek(directory_pointer)

   lumps = {}
   lump_sizes = {}

   for i in range(lump_count):
      lump_pointer = struct.unpack("<i", wad_file.read(4))[0]
      lump_size = struct.unpack("<i", wad_file.read(4))[0]
      lump_name = fixLumpName(wad_file.read(8).decode("ascii"))
      lumps[lump_name] = lump_pointer
      lump_sizes[lump_name] = lump_size

   palette = []

   if "PLAYPAL" in lumps:
      try:
         wad_file.seek(lumps["PLAYPAL"])
         for i in range(256):
            r, g, b = struct.unpack("<BBB", wad_file.read(3))
            palette.append((r, g, b))
      except (RuntimeError, TypeError, struct.error) as e:
         handleWadReadError("error while reading palette:\nin " + mapset.fullpath + ":\n\n" + str(e))
         palette = default_palette
   else:
      palette = default_palette

   if "TITLEPIC" in lumps:
      wad_file.seek(lumps["TITLEPIC"])

      wad_file.read(1)

      if is_ascii_str(wad_file.read(3), "PNG"):
         wad_file.seek(lumps["TITLEPIC"])
         os.makedirs(os.path.join(dir_path, "titlepics"), exist_ok=True)
         with open(os.path.join(dir_path, "titlepics", mapset.name + ".png"), "wb") as titlepic:
            titlepic.write(wad_file.read(lump_sizes["TITLEPIC"]))
            mapset.titlepicpath = os.path.join(dir_path, "titlepics", mapset.name + ".png")

      else:
         try:
            wad_file.seek(lumps["TITLEPIC"])
            image_data_x_y = []

            width = struct.unpack("<H", wad_file.read(2))[0]
            height = struct.unpack("<H", wad_file.read(2))[0]
            xoffset = struct.unpack("<h", wad_file.read(2))[0]
            yoffset = struct.unpack("<h", wad_file.read(2))[0]

            column_pointers = []

            for i in range(width):
               column_pointers.append(struct.unpack("<I", wad_file.read(4))[0] + lumps["TITLEPIC"])

            for i in range(width):
               wad_file.seek(column_pointers[i])
               image_data_x_y.append([])

               while True:
                  row_start = struct.unpack("<B", wad_file.read(1))[0]
                  if row_start == 255:
                     break

                  pixel_count = struct.unpack("<B", wad_file.read(1))[0]

                  wad_file.read(1) # padding byte

                  for j in range(pixel_count):
                     image_data_x_y[i].append(struct.unpack("<B", wad_file.read(1))[0])

                  wad_file.read(1) # padding byte

            os.makedirs(os.path.join(dir_path, "titlepics"), exist_ok=True)
            with open(os.path.join(dir_path, "titlepics", mapset.name + ".ppm"), "wb") as titlepic:
               mapset.titlepicpath = os.path.join(dir_path, "titlepics", mapset.name + ".ppm")

               # file header
               titlepic.write(b"P6\n") # magic number
               titlepic.write(b"# " + mapset.name.encode() + b"\n") # comment
               titlepic.write(str(width).encode() + b" " + str(height).encode() + b"\n") # width and height
               titlepic.write(b"255\n")   # depth

               # pixel data
               for y in range(height):
                  for x in range(width):
                     color = palette[image_data_x_y[x][y]]
                     titlepic.write(struct.pack("<BBB", *color))
                     
            os.makedirs(os.path.join(dir_path, "thumbnails"), exist_ok=True)
            with open(os.path.join(dir_path, "thumbnails", mapset.name + ".ppm"), "wb") as thumbnail:
               mapset.thumbnailpath = os.path.join(dir_path, "thumbnails", mapset.name + ".ppm")

               # file header
               thumbnail.write(b"P6\n") # magic number
               thumbnail.write(b"# " + mapset.name.encode() + b"\n") # comment
               thumbnail.write(f"{thumbnail_size[0]} {thumbnail_size[1]}\n".encode()) # width and height
               thumbnail.write(b"255\n")   # depth

               image_data_x_y_rgb = [[palette[index] for index in column] for column in image_data_x_y]

               # pixel data
               downscaled_data = downscale_rgb((width, height), thumbnail_size, image_data_x_y_rgb)
               for y in range(thumbnail_size[1]):
                  for x in range(thumbnail_size[0]):
                     color = downscaled_data[x][y]
                     thumbnail.write(struct.pack("<BBB", *color))

         except (RuntimeError, TypeError, struct.error) as e:
            handleWadReadError("error while reading titlepic:\nin " + mapset.fullpath + ":\n\n" + str(e))
      
   if "M_DOOM" in lumps:
      wad_file.seek(lumps["M_DOOM"])

      wad_file.read(1)

      if is_ascii_str(wad_file.read(3), "PNG"):
         wad_file.seek(lumps["M_DOOM"])
         os.makedirs(os.path.join(dir_path, "logos"), exist_ok=True)
         with open(os.path.join(dir_path, "logos", mapset.name + ".png"), "wb") as logo:
            logo.write(wad_file.read(lump_sizes["M_DOOM"]))
            mapset.logopath = os.path.join(dir_path, "logos", mapset.name + ".png")
      
      else:
         try:
            wad_file.seek(lumps["M_DOOM"])
            image_data_x_y = {}

            width = struct.unpack("<H", wad_file.read(2))[0]
            height = struct.unpack("<H", wad_file.read(2))[0]
            xoffset = struct.unpack("<h", wad_file.read(2))[0]
            yoffset = struct.unpack("<h", wad_file.read(2))[0]

            column_pointers = []

            for i in range(width):
               column_pointers.append(struct.unpack("<I", wad_file.read(4))[0] + lumps["M_DOOM"])

            for i in range(width):
               wad_file.seek(column_pointers[i])
               image_data_x_y[i] = {}

               while True:
                  row_start = struct.unpack("<B", wad_file.read(1))[0]
                  if row_start == 255:
                     break

                  pixel_count = struct.unpack("<B", wad_file.read(1))[0]

                  wad_file.read(1) # padding byte

                  for j in range(pixel_count):
                     image_data_x_y[i][j + row_start] = struct.unpack("<B", wad_file.read(1))[0]

                  wad_file.read(1) # padding byte

            os.makedirs(os.path.join(dir_path, "logos"), exist_ok=True)
            with open(os.path.join(dir_path, "logos", mapset.name + ".ppm"), "wb") as logo:
               mapset.logopath = os.path.join(dir_path, "logos", mapset.name + ".ppm")

               # file header
               logo.write(b"P6\n") # magic number
               logo.write(b"# " + mapset.name.encode() + b"\n") # comment
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

         except (RuntimeError, TypeError, struct.error) as e:
            handleWadReadError("error while reading logo:\nin " + mapset.fullpath + ":\n\n" + str(e))

   if "WADINFO" in lumps:
      wad_file.seek(lumps["WADINFO"])

      try:
         txt_content = wad_file.read(lump_sizes["WADINFO"]).decode("utf-8")
         mapset.read_txt(txt_content)
      except (RuntimeError, TypeError, struct.error) as e:
         handleWadReadError("error while reading WADINFO:\nin " + mapset.fullpath + ":\n\n" + str(e))
   
   if "GAMEINFO" in lumps:
      wad_file.seek(lumps["GAMEINFO"])

      try:
         txt_content = wad_file.read(lump_sizes["GAMEINFO"]).decode("utf-8")
         mapset.read_gameinfo(txt_content)
      except (RuntimeError, TypeError, struct.error) as e:
         handleWadReadError("error while reading GAMEINFO:\nin " + mapset.fullpath + ":\n\n" + str(e))

with open(os.path.join(dir_path, "default_palette.csv"), "r") as palette_file:
   for line in palette_file:
      r, g, b = line.strip().split(",")
      default_palette.append((int(r), int(g), int(b)))