from math import ceil
import sys
import tkinter as tk
from tkinter import font
import tkinter.ttk as ttk
import subprocess
import os
import json
import struct
import zipfile

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
   map_frame.lower()

   profile_name = selected_map.get()

   map_button.configure(text=profile_name)

   processBackgroundImage()

   if profile_name in profiles:
      engine_box.set(profiles[profile_name]["engine"])
      iwad_box.set(profiles[profile_name]["iwad"])

      for checkbox, var in mod_checkboxes:
         if checkbox.cget("text") in profiles[profile_name]["mods"]:
            var.set(True)
         else:
            var.set(False)

def updateProfile():
   profile_name = selected_map.get()

   if profile_name not in profiles:
      profiles[profile_name] = {}

   profiles[profile_name]["engine"] = engine_box.get()
   profiles[profile_name]["iwad"] = iwad_box.get()
   profiles[profile_name]["mods"] = [checkbox.cget("text") for checkbox, var in mod_checkboxes if var.get() == True]

def runDoom():
   command = [engines[engine_names.index(engine_box.get())], "-iwad", iwad_files[iwad_names.index(iwad_box.get())]]

   if selected_map.get() != MAP_NONE_STRING:
      command += ["-file", mapset_files[mapset_names.index(selected_map.get())]]

   for checkbox, var in mod_checkboxes:
      if var.get() == True:
         command += ["-file", mod_files[mod_names.index(checkbox.cget("text"))]]

   print("Running command " + str(command))
   subprocess.Popen(command)

   print("Writing profiles")
   updateProfile()
   profiles[MAP_LATEST_STRING] = selected_map.get()
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

def wadParse(wad_path, wad_file):
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

         try:
            while True:
               row_start = struct.unpack("<B", wad_file.read(1))[0]
               if row_start == 255:
                  break

               pixel_count = struct.unpack("<B", wad_file.read(1))[0]

               wad_file.read(1) # padding byte

               for j in range(pixel_count):
                  image_data_x_y[i].append(struct.unpack("<B", wad_file.read(1))[0])

               wad_file.read(1) # padding byte
         except struct.error as e:
            print("Error while parsing TITLEPIC lump in " + wad_path + ", skipping thumbnail generation")
            print(e)
            return

      os.makedirs(os.path.join(dir_path, "thumbnails"), exist_ok=True)
      with open(os.path.join(dir_path, "thumbnails", os.path.basename(wad_path) + ".ppm"), "wb") as thumbnail:
         titlepics[os.path.basename(wad_path)] = os.path.join(dir_path, "thumbnails", os.path.basename(wad_path) + ".ppm")

         # file header
         thumbnail.write(b"P6\n") # magic number
         thumbnail.write(b"# " + os.path.basename(wad_path).encode() + b"\n") # comment
         thumbnail.write(str(width).encode() + b" " + str(height).encode() + b"\n") # width and height
         thumbnail.write(b"255\n")   # depth

         # pixel data
         for y in range(height):
            for x in range(width):
               color = palette[image_data_x_y[x][y]]
               thumbnail.write(struct.pack("<BBB", *color))

def fixLumpName(name):
   if "\0" in name:
      return name[:name.index("\0")]
   return name

last_background_scale = -1
last_image_path = None
def processBackgroundImage():
   global last_background_scale, last_image_path

   if selected_map.get() in titlepics and launch_background.winfo_width() > 1 and launch_background.winfo_height() > 1:
      image_full = tk.PhotoImage(file=os.path.join(dir_path, titlepics[selected_map.get()]))
      scale_factor = ceil(launch_background.winfo_width() / image_full.width())
      if scale_factor != last_background_scale or titlepics[selected_map.get()] != last_image_path:
         launch_background.image = image_full.zoom(scale_factor, scale_factor)
         launch_background.configure(image=launch_background.image)
         last_background_scale = scale_factor
         last_image_path = titlepics[selected_map.get()]
   else:
      launch_background.configure(image=None)
      launch_background.image = None   # cause it to be garbage collected, because clearing it using configure doesn't seem to work
      last_background_scale = -1
      last_image_path = None

   launch_background.place(x=0, y=launch_button.winfo_y(), relwidth=1, height=launch_button.winfo_height())

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
      if file.lower().endswith(".wad"):
         mapset_files.append(os.path.join(folder, file))
         mapset_names.append(file)
         
         with open(os.path.join(folder, file), "rb") as wad_file:
            wadParse(os.path.join(folder, file), wad_file)
      
      elif file.lower().endswith(".pk3") or file.lower().endswith(".zip"):
         try:
            with zipfile.ZipFile(os.path.join(folder, file), "r") as pk3_file:
               has_added = False
               for name in pk3_file.namelist():
                  if name.lower().endswith(".wad"):
                     if not has_added:
                        mapset_files.append(os.path.join(folder, file))
                        mapset_names.append(file)
                        has_added = True

                     with pk3_file.open(name) as wad_file:
                        wadParse(os.path.join(folder, file), wad_file)
         except NotImplementedError as e:
            print("Error while reading " + os.path.join(folder, file) + ", skipping thumbnail generation")
            print(e)

bolded_font = font.Font(weight="bold")
map_button = tk.Button(window, text="", font=bolded_font, bg="white")
map_button.configure(command=lambda: map_frame.tkraise())
map_button.grid(row=0, column=0, columnspan=3, sticky="ew")

map_frame = tk.Frame(window)
map_frame.place(x=0, y=0, relwidth=1, relheight=0.75)
map_frame.rowconfigure(0, weight=1)
map_frame.columnconfigure(0, weight=1)

map_scrollbar = ttk.Scrollbar(map_frame, orient="vertical")
map_scrollbar.grid(row=0, column=1, sticky="ns")

map_canvas = tk.Canvas(map_frame, width=20, height=20, bg="white")
map_canvas.bind("<Configure>", lambda e: map_canvas.configure(scrollregion=map_canvas.bbox("all")))
map_canvas.grid(row=0, column=0, columnspan=1, sticky="nsew")

map_scrollbar.configure(command=map_canvas.yview)
map_canvas.configure(yscrollcommand=map_scrollbar.set)

map_window = tk.Frame(map_canvas, bg="white")

selected_map = tk.StringVar()
for index, map_name in enumerate(mapset_names):
   button = tk.Radiobutton(map_window, text=map_name, value=map_name, variable=selected_map, command=loadProfile, indicator=0, borderwidth=0, highlightthickness=0, anchor="w", bg="white")
   height = button.winfo_reqheight()

   button.grid(row=index, column=1, sticky="ew")

   if map_name in titlepics:
      image_full = tk.PhotoImage(file=titlepics[map_name])
      scale_factor = ceil(max(image_full.height() / height, image_full.width() / (height * (320.0 / 200.0))))
      image = image_full.subsample(scale_factor, scale_factor)
      image_label = tk.Label(map_window, image=image, borderwidth=0)
      image_label.image = image # to save from garbage collection
      image_label.grid(row=index, column=0, sticky="w")

map_canvas.create_window((0, 0), window=map_window, anchor="nw")

for engine in engines:
   engine_names.append(os.path.basename(engine))

engine_box = ttk.Combobox(window, state="readonly", values=engine_names)
engine_box.bind("<<ComboboxSelected>>", lambda event: updateProfile())
engine_box.grid(row=1, column=0, columnspan=1, sticky="ew")

for folder in iwad_folders:
   for file in os.listdir(folder):
      if file.lower().endswith(".wad") or file.lower().endswith(".pk3") or file.lower().endswith(".zip"):
         iwad_files.append(os.path.join(folder, file))
         iwad_names.append(file)

iwad_box = ttk.Combobox(window, state="readonly", values=iwad_names)
iwad_box.bind("<<ComboboxSelected>>", lambda event: updateProfile())
iwad_box.grid(row=1, column=1, columnspan=2, sticky="ew")

if MAP_LATEST_STRING in profiles:
   selected_map.set(profiles[MAP_LATEST_STRING])
else:
   selected_map.set(MAP_NONE_STRING)

for folder in mod_folders:
   for file in os.listdir(folder):
      if file.lower().endswith(".wad") or file.lower().endswith(".pk3") or file.lower().endswith(".zip"):
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

launch_background = tk.Label(window, bg="white", image=None)
launch_background.lower()
window.bind("<Configure>", lambda event: processBackgroundImage())

loadProfile()

window.mainloop()