import sys
import tkinter as tk
from tkinter import font
import tkinter.ttk as ttk
import subprocess
import os
import json
import struct

MAP_NONE_STRING = "<none>"
MAP_LATEST_STRING = "_latest"

dir_path = os.path.dirname(os.path.abspath(__file__))

default_palette = []

engines = [
]

iwad_folders = [
]

map_folders = [
]

mod_folders = [
]

engine_names = []
iwad_files = []
iwad_names = []
mapset_files = []
mapset_names = []
titlepics = {}
mod_files = []
mod_names = []

profiles = {}

mod_checkboxes = []

def loadProfile():
   profile_name = map_box.get()

   if profile_name in profiles:
      engine_box.set(profiles[profile_name]["engine"])
      iwad_box.set(profiles[profile_name]["iwad"])

      for checkbox, var in mod_checkboxes:
         if checkbox.cget("text") in profiles[profile_name]["mods"]:
            var.set(True)
         else:
            var.set(False)

def updateProfile():
   profile_name = map_box.get()

   if profile_name not in profiles:
      profiles[profile_name] = {}

   profiles[profile_name]["engine"] = engine_box.get()
   profiles[profile_name]["iwad"] = iwad_box.get()
   profiles[profile_name]["mods"] = [checkbox.cget("text") for checkbox, var in mod_checkboxes if var.get() == True]

def runDoom():
   command = [engines[engine_names.index(engine_box.get())], "-iwad", iwad_files[iwad_names.index(iwad_box.get())]]

   if map_box.get() != MAP_NONE_STRING:
      command += ["-file", mapset_files[mapset_names.index(map_box.get())]]

   for checkbox, var in mod_checkboxes:
      if var.get() == True:
         command += ["-file", mod_files[mod_names.index(checkbox.cget("text"))]]

   print("Running command " + str(command))
   subprocess.Popen(command)

   print("Writing profiles")
   updateProfile()
   profiles[MAP_LATEST_STRING] = map_box.get()
   with open(os.path.join(dir_path, "profiles.json"), "w") as profiles_file:
      json.dump(profiles, profiles_file, indent=2)

def handleWheel(event):
   delta = 0
   
   if sys.platform == 'darwin':
      delta = event.delta
   else:
      delta = event.delta / 40.0

   mod_canvas.yview_scroll(-1 * int(delta), "units")

def addWheelHandler(widget):
   widget.bind("<MouseWheel>", handleWheel)
   widget.bind("<Button-4>", handleWheel)
   widget.bind("<Button-5>", handleWheel)

def wadParse(wad_path):
   with open(wad_path, "rb") as wad_file:
      wad_type = wad_file.read(4).decode("ascii")
      lump_count = struct.unpack("<i", wad_file.read(4))[0]
      directory_pointer = struct.unpack("<i", wad_file.read(4))[0]

      if wad_type not in ["IWAD", "PWAD"]:
         return

      wad_file.seek(directory_pointer)

      lumps = {}

      for i in range(lump_count):
         lump_pointer = struct.unpack("<i", wad_file.read(4))[0]
         lump_size = struct.unpack("<i", wad_file.read(4))[0]
         lump_name = fixLumpName(wad_file.read(8).decode("ascii"))
         lumps[lump_name] = lump_pointer

      palette = []

      if "PLAYPAL" in lumps:
         wad_file.seek(lumps["PLAYPAL"])
         print("Reading palette from " + wad_path)
         for i in range(256):
            r, g, b = struct.unpack("<BBB", wad_file.read(3))
            palette.append((r, g, b))
      else:
         palette = default_palette

      if "TITLEPIC" in lumps:
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

         os.makedirs(os.path.join(dir_path, "thumbnails"), exist_ok=True)
         with open(os.path.join(dir_path, "thumbnails", os.path.basename(wad_path) + ".bmp"), "wb") as thumbnail:

            # file header
            thumbnail.write(b"BM")  # identifier
            thumbnail.write(struct.pack("<I", 14 + 40 + 256 * 4 + width * height))  # file size
            thumbnail.write(struct.pack("<HH", 0, 0)) # reserved
            thumbnail.write(struct.pack("<I", 14 + 40 + 256 * 4)) # pixel grid offset

            # detailed information header (BITMAPINFOHEADER)
            thumbnail.write(struct.pack("<I", 40)) # block size
            thumbnail.write(struct.pack("<ii", width, 0 - height)) # width and height (negative for top-down)
            thumbnail.write(struct.pack("<HH", 1, 8)) # planes and bits per pixel
            thumbnail.write(struct.pack("<I", 0))  # compression method
            thumbnail.write(struct.pack("<I", width * height)) # image size
            thumbnail.write(struct.pack("<ii", 2835, 2835)) # pixels per meter
            thumbnail.write(struct.pack("<II", 256, 0)) # color palette size and important colors

            # color palette, ARGB32
            for r, g, b in palette:
               thumbnail.write(struct.pack("<BBBB", b, g, r, 0))

            # pixel grid
            for y in range(height):
               for x in range(width):
                  index = image_data_x_y[x][y]
                  thumbnail.write(struct.pack("<B", index))
               
               # padding
               for i in range(width % 4):
                  thumbnail.write(struct.pack("<B", 0))


def fixLumpName(name):
   if "\0" in name:
      return name[:name.index("\0")]
   return name

try:
   with open(os.path.join(dir_path, "config.txt"), "r") as config_file:
      list = engines

      for line in config_file:
         line = line.strip()
         if line.startswith("#") or not line:
            continue
         elif line == "[engines]":
            list = engines
         elif line == "[iwads]":
            list = iwad_folders
         elif line == "[maps]":
            list = map_folders
         elif line == "[mods]":
            list = mod_folders
         else:
            list.append(line)
except FileNotFoundError:
   with open(os.path.join(dir_path, "config.txt"), "w") as config_file:
      config_file.writelines(["[engines]", "", "[iwads]", "", "[maps]", "", "[mods]", ""])

try:
   with open(os.path.join(dir_path, "profiles.json"), "r") as profiles_file:
      profiles = json.load(profiles_file)
except FileNotFoundError:
   profiles = {}

with open(os.path.join(dir_path, "default_palette.csv"), "r") as palette_file:
   for line in palette_file:
      r, g, b = line.strip().split(",")
      default_palette.append((int(r), int(g), int(b)))

window = tk.Tk()
window.geometry("250x250")
window.title("Doom Launch")
window.bind("<Escape>", lambda event: window.destroy())
window.rowconfigure(2, weight=1)
window.columnconfigure(0, weight=1)
window.columnconfigure(1, weight=1)

mapset_files.append(MAP_NONE_STRING)
mapset_names.append(MAP_NONE_STRING)
for folder in map_folders:
   for file in os.listdir(folder):
      if file.lower().endswith(".wad") or file.lower().endswith(".pk3"):
         mapset_files.append(os.path.join(folder, file))
         mapset_names.append(file)
         wadParse(os.path.join(folder, file))

bolded_font = font.Font(weight="bold")
map_box = ttk.Combobox(window, state="readonly", values=mapset_names, font=bolded_font)
map_box.bind("<<ComboboxSelected>>", lambda event: loadProfile())
map_box.grid(row=0, column=0, columnspan=3, sticky="ew")

for engine in engines:
   engine_names.append(os.path.basename(engine))

engine_box = ttk.Combobox(window, state="readonly", values=engine_names)
engine_box.bind("<<ComboboxSelected>>", lambda event: updateProfile())
engine_box.grid(row=1, column=0, columnspan=1, sticky="ew")

for folder in iwad_folders:
   for file in os.listdir(folder):
      if file.lower().endswith(".wad") or file.lower().endswith(".pk3"):
         iwad_files.append(os.path.join(folder, file))
         iwad_names.append(file)

iwad_box = ttk.Combobox(window, state="readonly", values=iwad_names)
iwad_box.bind("<<ComboboxSelected>>", lambda event: updateProfile())
iwad_box.grid(row=1, column=1, columnspan=2, sticky="ew")

if MAP_LATEST_STRING in profiles:
   map_box.set(profiles[MAP_LATEST_STRING])
else:
   map_box.set(MAP_NONE_STRING)

for folder in mod_folders:
   for file in os.listdir(folder):
      if file.lower().endswith(".wad") or file.lower().endswith(".pk3"):
         mod_files.append(os.path.join(folder, file))
         mod_names.append(file)

mod_scrollbar = ttk.Scrollbar(window, orient="vertical")
mod_scrollbar.grid(row=2, column=2, sticky="ns")

mod_canvas = tk.Canvas(window, width=20, height=20)
mod_canvas.bind("<Configure>", lambda e: mod_canvas.configure(scrollregion=mod_canvas.bbox("all")))
addWheelHandler(mod_canvas)
mod_canvas.grid(row=2, column=0, columnspan=2, sticky="nsew")

mod_scrollbar.configure(command=mod_canvas.yview)
mod_canvas.configure(yscrollcommand=mod_scrollbar.set)

mod_window = tk.Frame(mod_canvas)
addWheelHandler(mod_window)

for index, mod_name in enumerate(mod_names):
   var = tk.BooleanVar()
   checkbox = ttk.Checkbutton(mod_window, text=mod_name, variable=var, command=updateProfile)
   addWheelHandler(checkbox)
   checkbox.grid(row=index, column=0, sticky="w")
   mod_checkboxes.append((checkbox, var))

mod_canvas.create_window((0, 0), window=mod_window, anchor="nw")

launch_button = ttk.Button(window, text="Launch Doom", command=runDoom)
launch_button.grid(row=3, column=0, columnspan=3)

loadProfile()

window.mainloop()