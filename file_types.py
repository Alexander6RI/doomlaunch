import os
import traceback
import zipfile
from collections.abc import Callable
import os
import struct

from wad_parse import Mapset, wadParse, handleDoomGraphicLump, LumpOrFile, default_palette

def readLumps(mapset: Mapset, lumps: dict[str, LumpOrFile], thumbnail_size: tuple[int, int], basedir: str, handleWadReadError: Callable[[str], None]):
   palette = []

   if "playpal" in lumps:
      playpal = lumps["playpal"]
      
      try:
         for i in range(256):
            r, g, b = struct.unpack("<BBB", playpal.read(3))
            palette.append((r, g, b))
      except (RuntimeError, TypeError, struct.error) as e:
         handleWadReadError(playpal.get_error_prefix() + "error while reading palette:\n" + str(e))
         print(traceback.format_exc())
         palette = default_palette
   else:
      palette = default_palette

   if "titlepic" in lumps:
      titlepic = lumps["titlepic"]

      if titlepic.type == "png":
         titlepic.seek(0)
         os.makedirs(os.path.join(basedir, "titlepics"), exist_ok=True)
         with open(os.path.join(basedir, "titlepics", mapset.name + ".png"), "wb") as titlepic_out:
            titlepic_out.write(titlepic.read())
            mapset.titlepicpath = os.path.join(basedir, "titlepics", mapset.name + ".png")

      elif titlepic.type == "lmp":
         try:
            titlepicpath = os.path.join(basedir, "titlepics", mapset.name + ".ppm")
            thumbnailpath = os.path.join(basedir, "thumbnails", mapset.name + ".ppm")
            handleDoomGraphicLump(titlepic, palette, titlepicpath, thumbnail_size, thumbnailpath)
            mapset.titlepicpath = titlepicpath
            mapset.thumbnailpath = thumbnailpath

         except (RuntimeError, TypeError, struct.error) as e:
            handleWadReadError(titlepic.get_error_prefix() + "error while reading background:\n" + str(e))
            print(traceback.format_exc())
      
      else:
         handleWadReadError(titlepic.get_error_prefix() + "unsupported graphics format " + titlepic.type)

   if "m_doom" in lumps:
      m_doom = lumps["m_doom"]

      if m_doom.type == "png":
         m_doom.seek(0)
         os.makedirs(os.path.join(basedir, "logos"), exist_ok=True)
         with open(os.path.join(basedir, "logos", mapset.name + ".png"), "wb") as logo_out:
            logo_out.write(m_doom.read())
            mapset.logopath = os.path.join(basedir, "logos", mapset.name + ".png")

      elif m_doom.type == "lmp":
         try:
            logopath = os.path.join(basedir, "logos", mapset.name + ".ppm")

            if mapset.thumbnailpath == None:
               thumbnailpath = os.path.join(basedir, "thumbnails", mapset.name + ".ppm")
               handleDoomGraphicLump(m_doom, palette, logopath, thumbnail_size, thumbnailpath)
               mapset.thumbnailpath = thumbnailpath
            else:
               handleDoomGraphicLump(m_doom, palette, logopath, thumbnail_size, None)

            mapset.logopath = logopath

         except (RuntimeError, TypeError, struct.error) as e:
            handleWadReadError(m_doom.get_error_prefix() + "error while reading logo:\n" + str(e))
            print(traceback.format_exc())
      
      else:
         handleWadReadError(m_doom.get_error_prefix() + "unsupported graphics format " + m_doom.type)

   for wadinfo_name in ["wadinfo", mapset.name, mapset.name + ".wad", mapset.name + ".pk3", mapset.name + ".zip"]:
      if wadinfo_name.lower() in lumps:
         wadinfo = lumps[wadinfo_name.lower()]

         try:
            txt_content = wadinfo.read().decode("utf-8")
            mapset.read_txt(txt_content)
         except (RuntimeError, TypeError, struct.error) as e:
               handleWadReadError(wadinfo.get_error_prefix() + "error while reading wadinfo:\n" + str(e))
               print(traceback.format_exc())
   
   if "gameinfo" in lumps:
      gameinfo = lumps["gameinfo"]

      try:
         txt_content = gameinfo.read().decode("utf-8")
         mapset.read_gameinfo(txt_content)
      except (RuntimeError, TypeError, struct.error) as e:
         handleWadReadError(gameinfo.get_error_prefix() + "error while reading gameinfo:\n" + str(e))
         print(traceback.format_exc())

def read_zip(mapset: Mapset, zip_file: zipfile.ZipFile, pathToZip: list[str], thumbnail_size: tuple[int, int], basedir: str, handleWadReadError: Callable[[str], None]):
   lumpsInZip: dict[str, LumpOrFile] = {}

   for subfile in zip_file.namelist():
      if os.path.basename(subfile).startswith("."):
         continue

      if subfile.lower().endswith(".wad"):
         with zip_file.open(subfile) as wad_file:
            lumpsInWad = wadParse(LumpOrFile(memoryview(wad_file.read()), os.path.basename(subfile), "wad", subfile.split(os.path.sep), pathToZip), handleWadReadError)
            lumpsInZip.update(lumpsInWad)

      elif subfile.lower().endswith(".pk3") or subfile.lower().endswith(".zip"):
         with zip_file.open(subfile) as nested_zip_file:
            with zipfile.ZipFile(nested_zip_file) as nested_zip:
               read_zip(mapset, nested_zip, pathToZip + [subfile], thumbnail_size, basedir, handleWadReadError)

      else:
         new_lump = LumpOrFile(memoryview(zip_file.read(subfile)), os.path.basename(subfile), os.path.splitext(subfile)[1][1:].lower(), subfile.split(os.path.sep), pathToZip)
         lumpsInZip[new_lump.name] = new_lump

   readLumps(mapset, lumpsInZip, thumbnail_size, basedir, handleWadReadError)

def read_mapset(mapset: Mapset, filepath: str, thumbnail_size: tuple[int, int], basedir: str, handleWadReadError: Callable[[str], None]):
   extension = os.path.splitext(filepath)[1][1:].lower()

   if extension == "wad":
      with open(filepath, "rb") as file:
         lumps = wadParse(LumpOrFile(memoryview(file.read()), "input.wad", "wad", filepath.split(os.path.sep), []), handleWadReadError)
         readLumps(mapset, lumps, thumbnail_size, basedir, handleWadReadError)

   elif extension == "zip" or extension == "pk3":
      with zipfile.ZipFile(filepath) as zip_file:
         read_zip(mapset, zip_file, [filepath], thumbnail_size, basedir, handleWadReadError)

   else:
      handleWadReadError("unsupported file type: " + extension)

   txt_paths = [
      os.path.splitext(filepath)[0] + ".txt",
      os.path.splitext(filepath)[0] + ".TXT",
      filepath + ".txt",
      filepath + ".TXT",
   ]

   for txtpath in txt_paths:
      if os.path.isfile(txtpath):
         try:
            with open(txtpath, "r") as txtfile:
               txt_content = txtfile.read()
               mapset.read_txt(txt_content)
         except Exception as e:
            handleWadReadError("error while reading " + txtpath + ":\n" + str(e))
            print(traceback.format_exc())