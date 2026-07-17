import traceback
import zipfile
from collections.abc import Callable
import struct
from pathlib import Path

from wad_parse import Mapset, wadParse, handleDoomGraphicLump, LumpOrFile, default_palette, LumpContainer, check_magic_numbers

def readLumps(mapset: Mapset, lumps: LumpContainer, thumbnail_size: tuple[int, int], basedir: Path, extraWadNames: list[str], handleWadReadError: Callable[[str], None]):
   palette = []

   playpal = lumps.get("playpal")
   if playpal:
      
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

   titlepic = lumps.get("titlepic", "png", "lmp")
   if titlepic:

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

   m_doom = lumps.get("m_doom", "png", "lmp")
   if m_doom:

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

   wadinfo_names = set(["wadinfo", mapset.fullpath.stem, mapset.fullpath.name] + extraWadNames + [Path(i).stem.lower() for i in extraWadNames])

   for wadinfo_name in wadinfo_names:
      wadinfo = lumps.get(wadinfo_name, "txt", "lmp")
      if wadinfo:

         try:
            txt_content = wadinfo.read_as_text()
            mapset.read_txt(txt_content)
         except UnicodeDecodeError as e:
            handleWadReadError(wadinfo.get_error_prefix() + "error while reading wadinfo:\n" + str(e) + "\n\n(text encoding error)")
            print(traceback.format_exc())
         except (RuntimeError, TypeError, struct.error) as e:
            handleWadReadError(wadinfo.get_error_prefix() + "error while reading wadinfo:\n" + str(e))
            print(traceback.format_exc())
   
   gameinfo = lumps.get("gameinfo", "txt", "lmp")
   if gameinfo:

      try:
         txt_content = gameinfo.read_as_text()
         mapset.read_gameinfo(txt_content)
      except UnicodeDecodeError as e:
         handleWadReadError(gameinfo.get_error_prefix() + "error while reading gameinfo:\n" + str(e) + "\n\n(text encoding error)")
         print(traceback.format_exc())
      except (RuntimeError, TypeError, struct.error) as e:
         handleWadReadError(gameinfo.get_error_prefix() + "error while reading gameinfo:\n" + str(e))
         print(traceback.format_exc())

def read_zip(mapset: Mapset, zip_file: zipfile.ZipFile, pathToZip: Path, thumbnail_size: tuple[int, int], basedir: Path, handleWadReadError: Callable[[str], None]):
   lumpsInZip = LumpContainer()
   wadNames: list[str] = []

   for subfile_str in zip_file.namelist():
      subfile = Path(subfile_str)
      if subfile.name.startswith("."):
         continue

      if subfile.suffix.lower() == ".wad":
         wadNames.append(subfile.name)
         with zip_file.open(subfile_str) as wad_file:
            lumpsInWad = wadParse(LumpOrFile(memoryview(wad_file.read()), subfile.name, "wad", pathToZip / subfile), handleWadReadError)
            readLumps(mapset, lumpsInWad, thumbnail_size, basedir, [], handleWadReadError)

      elif subfile.suffix.lower() == ".pk3" or subfile.suffix.lower() == ".zip":
         wadNames.append(subfile.name)
         with zip_file.open(subfile_str) as nested_zip_file:
            with zipfile.ZipFile(nested_zip_file) as nested_zip:
               read_zip(mapset, nested_zip, pathToZip / subfile, thumbnail_size, basedir, handleWadReadError)

      else:
         new_lump = LumpOrFile(memoryview(zip_file.read(subfile_str)), subfile.name, subfile.suffix[1:].lower(), pathToZip / subfile)
         if len(new_lump.type) == 0:
            new_lump.type = check_magic_numbers(new_lump)
         lumpsInZip.put(new_lump)

   readLumps(mapset, lumpsInZip, thumbnail_size, basedir, wadNames, handleWadReadError)

def read_mapset(mapset: Mapset, filepath: Path, thumbnail_size: tuple[int, int], basedir: Path, handleWadReadError: Callable[[str], None]):
   extension = filepath.suffix[1:].lower()

   if extension == "wad":
      with open(filepath, "rb") as file:
         lumps = wadParse(LumpOrFile(memoryview(file.read()), filepath.stem, "wad", filepath), handleWadReadError)
         readLumps(mapset, lumps, thumbnail_size, basedir, [], handleWadReadError)

   elif extension == "zip" or extension == "pk3":
      with zipfile.ZipFile(filepath) as zip_file:
         read_zip(mapset, zip_file, filepath, thumbnail_size, basedir, handleWadReadError)

   else:
      handleWadReadError("unsupported file type: " + extension + " (" + mapset.name + ")")

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