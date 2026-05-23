import traceback
import zipfile
from collections.abc import Callable
import struct
from pathlib import Path

from wad_parse import Mapset, wadParse, handleDoomGraphicLump, LumpOrFile, default_palette

def readLumps(mapset: Mapset, lumps: dict[str, LumpOrFile], thumbnail_size: tuple[int, int], basedir: Path, handleWadReadError: Callable[[str], None]):
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
         (basedir / "titlepics").mkdir(parents=True, exist_ok=True)
         with open(basedir / "titlepics" / (mapset.name + ".png"), "wb") as titlepic_out:
            titlepic_out.write(titlepic.read())
            mapset.titlepicpath = basedir / "titlepics" / (mapset.name + ".png")

      elif titlepic.type == "lmp":
         try:
            titlepicpath = basedir / "titlepics" / (mapset.name + ".ppm")
            thumbnailpath = basedir / "thumbnails" / (mapset.name + ".ppm")
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
         (basedir / "logos").mkdir(parents=True, exist_ok=True)
         with open(basedir / "logos" / (mapset.name + ".png"), "wb") as logo_out:
            logo_out.write(m_doom.read())
            mapset.logopath = basedir / "logos" / (mapset.name + ".png")

      elif m_doom.type == "lmp":
         try:
            logopath = basedir / "logos" / (mapset.name + ".ppm")

            if mapset.thumbnailpath == None:
               thumbnailpath = basedir / "thumbnails" / (mapset.name + ".ppm")
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

   for wadinfo_name in ["wadinfo", mapset.fullpath.stem, mapset.fullpath.name]:
      if wadinfo_name.lower() in lumps:
         wadinfo = lumps[wadinfo_name.lower()]

         try:
            txt_content = wadinfo.read().decode("utf-8")
            mapset.read_txt(txt_content)
         except UnicodeDecodeError as e:
            handleWadReadError(wadinfo.get_error_prefix() + "error while reading wadinfo:\n" + str(e) + "\n\n(text encoding error)")
            print(traceback.format_exc())
         except (RuntimeError, TypeError, struct.error) as e:
            handleWadReadError(wadinfo.get_error_prefix() + "error while reading wadinfo:\n" + str(e))
            print(traceback.format_exc())
   
   if "gameinfo" in lumps:
      gameinfo = lumps["gameinfo"]

      try:
         txt_content = gameinfo.read().decode("utf-8")
         mapset.read_gameinfo(txt_content)
      except UnicodeDecodeError as e:
         handleWadReadError(wadinfo.get_error_prefix() + "error while reading wadinfo:\n" + str(e) + "\n\n(text encoding error)")
         print(traceback.format_exc())
      except (RuntimeError, TypeError, struct.error) as e:
         handleWadReadError(gameinfo.get_error_prefix() + "error while reading gameinfo:\n" + str(e))
         print(traceback.format_exc())

def read_zip(mapset: Mapset, zip_file: zipfile.ZipFile, pathToZip: Path, thumbnail_size: tuple[int, int], basedir: Path, handleWadReadError: Callable[[str], None]):
   lumpsInZip: dict[str, LumpOrFile] = {}

   for subfile_str in zip_file.namelist():
      subfile = Path(subfile_str)
      if subfile.name.startswith("."):
         continue

      if subfile.suffix.lower() == ".wad":
         with zip_file.open(subfile_str) as wad_file:
            lumpsInWad = wadParse(LumpOrFile(memoryview(wad_file.read()), subfile.name, "wad", pathToZip / subfile), handleWadReadError)
            lumpsInZip.update(lumpsInWad)

      elif subfile.suffix.lower() == ".pk3" or subfile.suffix.lower() == ".zip":
         with zip_file.open(subfile_str) as nested_zip_file:
            with zipfile.ZipFile(nested_zip_file) as nested_zip:
               read_zip(mapset, nested_zip, pathToZip / subfile, thumbnail_size, basedir, handleWadReadError)

      else:
         new_lump = LumpOrFile(memoryview(zip_file.read(subfile_str)), subfile.name, subfile.suffix[1:].lower(), pathToZip / subfile)
         lumpsInZip[new_lump.name] = new_lump

   readLumps(mapset, lumpsInZip, thumbnail_size, basedir, handleWadReadError)

def read_mapset(mapset: Mapset, filepath: Path, thumbnail_size: tuple[int, int], basedir: Path, handleWadReadError: Callable[[str], None]):
   extension = filepath.suffix[1:]

   if extension == "wad":
      with open(filepath, "rb") as file:
         lumps = wadParse(LumpOrFile(memoryview(file.read()), filepath.stem, "wad", filepath), handleWadReadError)
         readLumps(mapset, lumps, thumbnail_size, basedir, handleWadReadError)

   elif extension == "zip" or extension == "pk3":
      with zipfile.ZipFile(filepath) as zip_file:
         read_zip(mapset, zip_file, filepath, thumbnail_size, basedir, handleWadReadError)

   else:
      handleWadReadError("unsupported file type: " + extension)

   txt_paths = [
      filepath.parent / (filepath.stem + ".txt"),
      filepath.parent / (filepath.stem + ".TXT"),
      filepath.parent / (filepath.name + ".txt"),
      filepath.parent / (filepath.name + ".TXT"),
   ]

   for txtpath in txt_paths:
      if txtpath.exists():
         try:
            with open(txtpath, "r") as txtfile:
               txt_content = txtfile.read()
               mapset.read_txt(txt_content)
         except UnicodeDecodeError as e:
            handleWadReadError("error while reading " + str(txtpath) + ":\n" + str(e) + "\n\n(text encoding error)")
            print(traceback.format_exc())
         except Exception as e:
            handleWadReadError("error while reading " + str(txtpath) + ":\n" + str(e))
            print(traceback.format_exc())