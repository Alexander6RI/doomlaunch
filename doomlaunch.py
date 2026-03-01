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
from downscale import downscale_rgb

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
mapsets = {}
mod_files = []
mod_names = []

profiles = {}

mod_checkboxes = []

def loadProfile():
   map_frame.lower()

   profile_name = selected_map.get()
   mapset = mapsets[profile_name]

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

   if mapset.is_iwad:
      iwad_box.configure(state="disabled")
      iwad_box.set(mapset.name)
   else:
      iwad_box.configure(state="readonly")

def updateProfile():
   profile_name = selected_map.get()

   if profile_name not in profiles:
      profiles[profile_name] = {}

   profiles[profile_name]["engine"] = engine_box.get()
   profiles[profile_name]["iwad"] = iwad_box.get()
   profiles[profile_name]["mods"] = [checkbox.cget("text") for checkbox, var in mod_checkboxes if var.get() == True]

def runDoom():
   mapset = mapsets[selected_map.get()]

   command = [engines[engine_names.index(engine_box.get())], "-iwad", iwad_files[iwad_names.index(iwad_box.get())]]

   if not mapset.is_iwad:
      command += ["-file", mapsets[selected_map.get()].fullpath]

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

def addWheelHandler(widget, widget_to_scroll):

   def handleWheel(event):
      delta = 0
      
      if sys.platform == 'darwin':
         delta = event.delta
      else:
         delta = event.delta / 40.0

      widget_to_scroll.yview_scroll(-1 * int(delta), "units")

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
   lump_sizes = {}

   for i in range(lump_count):
      lump_pointer = struct.unpack("<i", wad_file.read(4))[0]
      lump_size = struct.unpack("<i", wad_file.read(4))[0]
      lump_name = fixLumpName(wad_file.read(8).decode("ascii"))
      lumps[lump_name] = lump_pointer
      lump_sizes[lump_name] = lump_size

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

      wad_file.read(1)

      if wad_file.read(3).decode("ascii") == "PNG":
         wad_file.seek(lumps["TITLEPIC"])
         os.makedirs(os.path.join(dir_path, "titlepics"), exist_ok=True)
         with open(os.path.join(dir_path, "titlepics", os.path.basename(wad_path) + ".png"), "wb") as titlepic:
            titlepic.write(wad_file.read(lump_sizes["TITLEPIC"]))
            mapsets[os.path.basename(wad_path)].titlepicpath = os.path.join(dir_path, "titlepics", os.path.basename(wad_path) + ".png")

      else:
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

         os.makedirs(os.path.join(dir_path, "titlepics"), exist_ok=True)
         with open(os.path.join(dir_path, "titlepics", os.path.basename(wad_path) + ".ppm"), "wb") as titlepic:
            mapsets[os.path.basename(wad_path)].titlepicpath = os.path.join(dir_path, "titlepics", os.path.basename(wad_path) + ".ppm")

            # file header
            titlepic.write(b"P6\n") # magic number
            titlepic.write(b"# " + os.path.basename(wad_path).encode() + b"\n") # comment
            titlepic.write(str(width).encode() + b" " + str(height).encode() + b"\n") # width and height
            titlepic.write(b"255\n")   # depth

            # pixel data
            for y in range(height):
               for x in range(width):
                  color = palette[image_data_x_y[x][y]]
                  titlepic.write(struct.pack("<BBB", *color))
                  
         os.makedirs(os.path.join(dir_path, "thumbnails"), exist_ok=True)
         with open(os.path.join(dir_path, "thumbnails", os.path.basename(wad_path) + ".ppm"), "wb") as thumbnail:
            mapsets[os.path.basename(wad_path)].thumbnailpath = os.path.join(dir_path, "thumbnails", os.path.basename(wad_path) + ".ppm")

            thumbnail_width = int((320.0 / 200.0) * default_font_size * 2)
            thumbnail_height = int(default_font_size * 2 + 1)

            # file header
            thumbnail.write(b"P6\n") # magic number
            thumbnail.write(b"# " + os.path.basename(wad_path).encode() + b"\n") # comment
            thumbnail.write(f"{thumbnail_width} {thumbnail_height}\n".encode()) # width and height
            thumbnail.write(b"255\n")   # depth

            image_data_x_y_rgb = [[palette[index] for index in column] for column in image_data_x_y]

            # pixel data
            downscaled_data = downscale_rgb((width, height), (thumbnail_width, thumbnail_height), image_data_x_y_rgb)
            for y in range(thumbnail_height):
               for x in range(thumbnail_width):
                  color = downscaled_data[x][y]
                  thumbnail.write(struct.pack("<BBB", *color))
      
   if "M_DOOM" in lumps:
      wad_file.seek(lumps["M_DOOM"])

      wad_file.read(1)

      if wad_file.read(3).decode("ascii") == "PNG":
         wad_file.seek(lumps["M_DOOM"])
         os.makedirs(os.path.join(dir_path, "logos"), exist_ok=True)
         with open(os.path.join(dir_path, "logos", os.path.basename(wad_path) + ".png"), "wb") as logo:
            logo.write(wad_file.read(lump_sizes["M_DOOM"]))
            mapsets[os.path.basename(wad_path)].logopath = os.path.join(dir_path, "logos", os.path.basename(wad_path) + ".png")
      
      else:
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

            try:
               while True:
                  row_start = struct.unpack("<B", wad_file.read(1))[0]
                  if row_start == 255:
                     break

                  pixel_count = struct.unpack("<B", wad_file.read(1))[0]

                  wad_file.read(1) # padding byte

                  for j in range(pixel_count):
                     image_data_x_y[i][j + row_start] = struct.unpack("<B", wad_file.read(1))[0]

                  wad_file.read(1) # padding byte
            except struct.error as e:
               print("Error while parsing M_DOOM lump in " + wad_path + ", skipping logo generation")
               print(e)
               return

         os.makedirs(os.path.join(dir_path, "logos"), exist_ok=True)
         with open(os.path.join(dir_path, "logos", os.path.basename(wad_path) + ".ppm"), "wb") as logo:
            mapsets[os.path.basename(wad_path)].logopath = os.path.join(dir_path, "logos", os.path.basename(wad_path) + ".ppm")

            # file header
            logo.write(b"P6\n") # magic number
            logo.write(b"# " + os.path.basename(wad_path).encode() + b"\n") # comment
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

def fixLumpName(name):
   if "\0" in name:
      return name[:name.index("\0")]
   return name

last_background_scale = -1
last_image_path = None
def processBackgroundImage():
   global last_background_scale, last_image_path

   if mapsets[selected_map.get()].titlepicpath != None and launch_background.winfo_width() > 1 and launch_background.winfo_height() > 1:
      image_full = tk.PhotoImage(file=mapsets[selected_map.get()].titlepicpath)
      scale_factor = ceil(launch_background.winfo_width() / image_full.width())
      if scale_factor != last_background_scale or mapsets[selected_map.get()].titlepicpath != last_image_path:
         launch_background.image = image_full.zoom(scale_factor, scale_factor)
         launch_background.configure(image=launch_background.image)
         last_background_scale = scale_factor
         last_image_path = mapsets[selected_map.get()].titlepicpath
   else:
      launch_background.configure(image=None)
      launch_background.image = None   # cause it to be garbage collected, because clearing it using configure doesn't seem to work
      last_background_scale = -1
      last_image_path = None

   launch_background.place(x=0, y=launch_button_outer.winfo_y(), relwidth=1, height=launch_button_outer.winfo_height())

class Mapset:
   def __init__(self, fullpath, name, is_iwad):
      self.fullpath = fullpath
      self.name = name
      self.is_iwad = is_iwad

      self.titlepicpath = None
      self.thumbnailpath = None
      self.logopath = None

def register_mapset(fullpath, name, is_iwad):
   if name.lower().endswith(".wad"):
      mapsets[name] = Mapset(fullpath, name, is_iwad)
      needsToCheckForTitlepic = True
      
      if os.path.isfile(os.path.join(dir_path, "titlepics", name + ".ppm")):
         mapsets[name].titlepicpath = os.path.join(dir_path, "titlepics", name + ".ppm")
         needsToCheckForTitlepic = False

      if os.path.isfile(os.path.join(dir_path, "thumbnails", name + ".ppm")):
         mapsets[name].thumbnailpath = os.path.join(dir_path, "thumbnails", name + ".ppm")
         needsToCheckForTitlepic = False

      if os.path.isfile(os.path.join(dir_path, "logos", name + ".ppm")):
         mapsets[name].logopath = os.path.join(dir_path, "logos", name + ".ppm")
         needsToCheckForTitlepic = False

      if needsToCheckForTitlepic:
         with open(fullpath, "rb") as wad_file:
            wadParse(fullpath, wad_file)
   
   elif name.lower().endswith(".pk3") or name.lower().endswith(".zip"):
      try:
         mapsets[name] = Mapset(fullpath, name, is_iwad)
         needsToCheckForTitlepic = True
         
         if os.path.isfile(os.path.join(dir_path, "titlepics", name + ".ppm")):
            mapsets[name].titlepicpath = os.path.join(dir_path, "titlepics", name + ".ppm")
            needsToCheckForTitlepic = False

         if os.path.isfile(os.path.join(dir_path, "thumbnails", name + ".ppm")):
            mapsets[name].thumbnailpath = os.path.join(dir_path, "thumbnails", name + ".ppm")
            needsToCheckForTitlepic = False

         if os.path.isfile(os.path.join(dir_path, "logos", name + ".ppm")):
            mapsets[name].logopath = os.path.join(dir_path, "logos", name + ".ppm")
            needsToCheckForTitlepic = False

         if needsToCheckForTitlepic:
            with zipfile.ZipFile(fullpath, "r") as pk3_file:
               for subfile in pk3_file.namelist():
                  if subfile.lower().endswith(".wad"):
                     with pk3_file.open(subfile) as wad_file:
                        wadParse(fullpath, wad_file)
                  elif subfile.lower() == "graphics/titlepic.png":
                     target_file = pk3_file.getinfo(subfile)
                     target_file.filename = name + ".png" # to not preserve folder structure
                     pk3_file.extract(target_file, os.path.join(dir_path, "titlepics"))
                     mapsets[name].titlepicpath = os.path.join(dir_path, "titlepics", name + ".png")
                  elif subfile.lower() == "graphics/m_doom.png":
                     target_file = pk3_file.getinfo(subfile)
                     target_file.filename = name + ".png" # to not preserve folder structure
                     pk3_file.extract(target_file, os.path.join(dir_path, "logos"))
                     mapsets[name].logopath = os.path.join(dir_path, "logos", name + ".png")

      except NotImplementedError as e:
         print("Error while reading " + fullpath + ", skipping thumbnail generation")
         print(e)

def changeFakeVistaButtonColors(frame, button, background, border):
   button.configure(background=background)
   frame.configure(background=border)

def makeButtonThatDoesntSuck(parent, text):
   if ttk.Style().theme_use() == "vista":
      frame = tk.Frame(parent, background="#ADADAD", borderwidth=0)
      button = tk.Button(frame, text=text, background="#E1E1E1", activebackground="#CCE4F7", relief="flat", borderwidth=0, overrelief="flat", padx=5, pady=1)
      button.bind("<Enter>", lambda event: changeFakeVistaButtonColors(frame, button, "#E5F1FB", "#0078D7"))
      button.bind("<Leave>", lambda event: changeFakeVistaButtonColors(frame, button, "#E1E1E1", "#ADADAD"))
      button.bind("<FocusIn>", lambda event: changeFakeVistaButtonColors(frame, button, "#E1E1E1", "#0078D7"))
      button.bind("<FocusOut>", lambda event: changeFakeVistaButtonColors(frame, button, "#E1E1E1", "#ADADAD"))
      button.pack(fill="both", expand=True, padx=1, pady=1)
      return frame, button
   else:
      button = ttk.Button(parent, text=text)
      return button, button

try:
   with open(os.path.join(dir_path, "config.txt"), "r") as config_file:
      config_reading_list = engines

      for line in config_file:
         line = line.strip()
         if line.startswith("#") or not line:
            continue
         elif line == "[engines]":
            config_reading_list = engines
         elif line == "[iwads]":
            config_reading_list = iwad_folders
         elif line == "[maps]":
            config_reading_list = map_folders
         elif line == "[mods]":
            config_reading_list = mod_folders
         else:
            config_reading_list.append(line)
except FileNotFoundError:
   with open(os.path.join(dir_path, "config.txt"), "w") as config_file:
      config_file.writelines(["[engines]\n", "\n", "[iwads]\n", "\n", "[maps]\n", "\n", "[mods]\n", "\n"])

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
window.geometry("200x200")
window.title("Doom Launch")
window.bind("<Escape>", lambda event: window.destroy())
window.rowconfigure(2, weight=1)
window.columnconfigure(0, weight=1)
window.columnconfigure(1, weight=1)

default_font_size = font.nametofont("TkDefaultFont").actual().get("size")

for folder in iwad_folders:
   for file in os.listdir(folder):
      if file.lower().endswith(".wad") or file.lower().endswith(".pk3") or file.lower().endswith(".zip"):
         iwad_files.append(os.path.join(folder, file))
         iwad_names.append(file)
         register_mapset(os.path.join(folder, file), file, True)

for folder in map_folders:
   for file in os.listdir(folder):
      if file.lower().endswith(".wad") or file.lower().endswith(".pk3") or file.lower().endswith(".zip"):
         register_mapset(os.path.join(folder, file), file, False)

map_button_frame = tk.Frame(window, bg="white")

bolded_font = font.Font(weight="bold")
ttk.Style().configure("Header.Toolbutton", font=bolded_font, background="white")

map_button = ttk.Button(map_button_frame, text="", style="Header.Toolbutton")
map_button.configure(command=lambda: map_frame.tkraise())
map_button.pack(anchor="center", padx=5, pady=5)

map_button_frame.grid(row=0, column=0, columnspan=3, sticky="ew")

map_frame = tk.Frame(window)
map_frame.place(x=0, y=0, relwidth=1, relheight=1)
map_frame.rowconfigure(0, weight=1)
map_frame.columnconfigure(0, weight=1)

map_scrollbar = ttk.Scrollbar(map_frame, orient="vertical")
map_scrollbar.grid(row=0, column=1, sticky="ns")

map_canvas = tk.Canvas(map_frame, width=20, height=20, bg="white")
map_canvas.bind("<Configure>", lambda e: map_canvas.configure(scrollregion=map_canvas.bbox("all")))
map_canvas.grid(row=0, column=0, columnspan=1, sticky="nsew")
addWheelHandler(map_canvas, map_canvas)

map_scrollbar.configure(command=map_canvas.yview)
map_canvas.configure(yscrollcommand=map_scrollbar.set)

map_window = tk.Frame(map_canvas, bg="white")
addWheelHandler(map_window, map_canvas)

selected_map = tk.StringVar()

number_of_iwads = sum(1 for mapset in mapsets.values() if mapset.is_iwad)

for index, mapset in enumerate(mapsets.values()):
   row = index
   if not mapset.is_iwad:
      row = row + 1
   
   button = tk.Radiobutton(map_window, text=mapset.name, value=mapset.name, variable=selected_map, command=loadProfile, indicator=0, borderwidth=0, highlightthickness=0, anchor="w", bg="white")
   height = button.winfo_reqheight()

   button.grid(row=row, column=1, sticky="ew")
   addWheelHandler(button, map_canvas)

   if mapset.thumbnailpath != None:
      image = tk.PhotoImage(file=mapset.thumbnailpath)
      image_label = tk.Label(map_window, image=image, borderwidth=0)
      image_label.image = image # to save from garbage collection
      image_label.grid(row=row, column=0, sticky="w")
      addWheelHandler(image_label, map_canvas)
   elif mapset.titlepicpath != None:
      image_full = tk.PhotoImage(file=mapset.titlepicpath)
      thumbnail_width = int((320.0 / 200.0) * default_font_size * 2)
      thumbnail_height = int(default_font_size * 2 + 1)
      shrink_factor = max(ceil(image_full.width() / thumbnail_width), ceil(image_full.height() / thumbnail_height))
      image = image_full.subsample(shrink_factor, shrink_factor)
      image_label = tk.Label(map_window, image=image, borderwidth=0)
      image_label.image = image # to save from garbage collection
      image_label.grid(row=row, column=0, sticky="w")
      addWheelHandler(image_label, map_canvas)
   elif mapset.logopath != None:
      image_full = tk.PhotoImage(file=mapset.logopath)
      logo_width = int((320.0 / 200.0) * default_font_size * 2)
      logo_height = int(default_font_size * 2 + 1)
      shrink_factor = max(ceil(image_full.width() / logo_width), ceil(image_full.height() / logo_height))
      image = image_full.subsample(shrink_factor, shrink_factor)
      image_label = tk.Label(map_window, image=image, borderwidth=0)
      image_label.image = image # to save from garbage collection
      image_label.grid(row=row, column=0, sticky="w")
      addWheelHandler(image_label, map_canvas)

iwad_pwad_separator = ttk.Separator(map_window, orient="horizontal")
iwad_pwad_separator.grid(row=number_of_iwads, column=0, columnspan=2, sticky="ew", pady=0)

map_canvas.create_window((0, 0), window=map_window, anchor="nw")

for engine in engines:
   engine_names.append(os.path.basename(engine))

engine_box = ttk.Combobox(window, state="readonly", values=engine_names)
engine_box.bind("<<ComboboxSelected>>", lambda event: updateProfile())
engine_box.grid(row=1, column=0, columnspan=1, sticky="ew")

iwad_box = ttk.Combobox(window, state="readonly", values=iwad_names)
iwad_box.bind("<<ComboboxSelected>>", lambda event: updateProfile())
iwad_box.grid(row=1, column=1, columnspan=2, sticky="ew")

if MAP_LATEST_STRING in profiles and profiles[MAP_LATEST_STRING] in mapsets:
   selected_map.set(profiles[MAP_LATEST_STRING])
else:
   selected_map.set(list(mapsets.keys())[0])

for folder in mod_folders:
   for file in os.listdir(folder):
      if file.lower().endswith(".wad") or file.lower().endswith(".pk3") or file.lower().endswith(".zip"):
         mod_files.append(os.path.join(folder, file))
         mod_names.append(file)

mod_scrollbar = ttk.Scrollbar(window, orient="vertical")
mod_scrollbar.grid(row=2, column=2, sticky="ns")

mod_canvas = tk.Canvas(window, width=20, height=20)
mod_canvas.bind("<Configure>", lambda e: mod_canvas.configure(scrollregion=mod_canvas.bbox("all")))
addWheelHandler(mod_canvas, mod_canvas)
mod_canvas.grid(row=2, column=0, columnspan=2, sticky="nsew")

mod_scrollbar.configure(command=mod_canvas.yview)
mod_canvas.configure(yscrollcommand=mod_scrollbar.set)

mod_window = tk.Frame(mod_canvas)
addWheelHandler(mod_window, mod_canvas)

for index, mod_name in enumerate(mod_names):
   var = tk.BooleanVar()
   checkbox = ttk.Checkbutton(mod_window, text=mod_name, variable=var, command=updateProfile)
   addWheelHandler(checkbox, mod_canvas)
   checkbox.grid(row=index, column=0, sticky="w")
   mod_checkboxes.append((checkbox, var))

mod_canvas.create_window((0, 0), window=mod_window, anchor="nw")

launch_button_outer, launch_button_inner = makeButtonThatDoesntSuck(window, text="Launch Doom")
launch_button_inner.configure(command=runDoom)
launch_button_outer.grid(row=3, column=0, columnspan=3)

launch_background = tk.Label(window, bg="white", image=None)
launch_background.lower()
window.bind("<Configure>", lambda event: processBackgroundImage())

loadProfile()

window.mainloop()