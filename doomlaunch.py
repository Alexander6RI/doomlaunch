from math import ceil
import sys
import tkinter as tk
from tkinter import font, filedialog, messagebox
import tkinter.ttk as ttk
import subprocess
import os
import json
import zipfile

from wad_parse import Mapset, wadParse

dir_path = os.path.dirname(os.path.abspath(__file__))

MAP_LATEST_STRING = "_latest"

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

   map_button.configure(text=mapset.title)

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

last_background_scale = -1
last_image_path = None
def processBackgroundImage():
   global last_background_scale, last_image_path

   if mapsets[selected_map.get()].titlepicpath != None and launch_background.winfo_width() > 1 and launch_background.winfo_height() > 1:
      image_full = tk.PhotoImage(file=mapsets[selected_map.get()].titlepicpath)
      scale_factor = ceil(launch_background.winfo_width() / image_full.width())
      if scale_factor != last_background_scale or mapsets[selected_map.get()].titlepicpath != last_image_path:
         launch_background.image = image_full.zoom(scale_factor, scale_factor) # pyright: ignore[reportAttributeAccessIssue]
         launch_background.configure(image=launch_background.image) # pyright: ignore[reportAttributeAccessIssue]
         last_background_scale = scale_factor
         last_image_path = mapsets[selected_map.get()].titlepicpath
   else:
      launch_background.configure(image=None) # pyright: ignore[reportArgumentType]
      launch_background.image = None   # pyright: ignore[reportAttributeAccessIssue] # cause it to be garbage collected, because clearing it using configure doesn't seem to work
      last_background_scale = -1
      last_image_path = None

   launch_background.place(x=0, y=launch_button_outer.winfo_y() - 2, relwidth=1, height=launch_button_outer.winfo_height() + 4)

def matchIgnoreCase(listToCheck: list[str], stringToMatch: str):
   for item in listToCheck:
      if item.lower() == stringToMatch.lower():
         return item
      
   return None

def handleWadReadError(message: str):
      print(message)
      messagebox.showerror(message=message)

def register_mapset(fullpath: str, name: str, is_iwad: bool):
      if name.lower().endswith(".wad"):
         mapset = Mapset(fullpath, name, is_iwad)
         mapsets[name] = mapset
         mapset.read_config_if_exists()

         if not mapset.config_read:
            try:
               with open(fullpath, "rb") as wad_file:
                  wadParse(mapset, wad_file, thumbnail_size, handleWadReadError)
            except (RuntimeError, ValueError) as e:
               print("Error while reading " + fullpath)
               print(e)
               messagebox.showerror(message="Error while reading " + name + ":\n\n" + str(e))
            
            try:
               with open(os.path.join(os.path.dirname(fullpath), os.path.splitext(name)[0] + ".txt"), "r") as txt_file:
                  mapset.read_txt(txt_file.read())
            except FileNotFoundError:
               pass
            except UnicodeDecodeError as e:
               handleWadReadError("error while reading text file:\nin " + os.path.join(os.path.dirname(fullpath), os.path.splitext(name)[0] + ".txt") + ":\n\n" + str(e) + "\n\n(likely text encoding error)")
            
            try:
               with open(os.path.join(os.path.dirname(fullpath), name + ".txt"), "r") as txt_file:
                  mapset.read_txt(txt_file.read())
            except FileNotFoundError:
               pass
            except UnicodeDecodeError as e:
               handleWadReadError("error while reading text file:\nin " + os.path.join(os.path.dirname(fullpath), name + ".txt") + ":\n\n" + str(e) + "\n\n(likely text encoding error)")
            
            mapset.write_config()
      
      elif name.lower().endswith(".pk3") or name.lower().endswith(".zip"):
         try:
            mapset = Mapset(fullpath, name, is_iwad)
            mapsets[name] = mapset
            mapset.read_config_if_exists()

            if not mapset.config_read:
               with zipfile.ZipFile(fullpath, "r") as pk3_file:
                  for subfile in pk3_file.namelist():
                     if subfile.lower().endswith(".wad"):
                        with pk3_file.open(subfile) as wad_file:
                           wadParse(mapset, wad_file, thumbnail_size, handleWadReadError)

                        txt_subfile = matchIgnoreCase(pk3_file.namelist(), subfile + ".txt")
                        if txt_subfile:
                           try:
                              with pk3_file.open(txt_subfile) as txt_file:
                                 mapset.read_txt(txt_file.read().decode("utf-8"))
                           except UnicodeDecodeError as e:
                              handleWadReadError("error while reading text file:\nin " + os.path.join(os.path.dirname(fullpath), name + ".txt") + ":\nin " + txt_subfile + ":\n\n" + str(e) + "\n\n(likely text encoding error)")
                              
                        txt_subfile = matchIgnoreCase(pk3_file.namelist(), os.path.splitext(subfile)[0].lower() + ".txt")
                        if txt_subfile:
                           try:
                              with pk3_file.open(txt_subfile) as txt_file:
                                 mapset.read_txt(txt_file.read().decode("utf-8"))
                           except UnicodeDecodeError as e:
                              handleWadReadError("error while reading text file:\nin " + os.path.join(os.path.dirname(fullpath), name + ".txt") + ":\nin " + txt_subfile + ":\n\n" + str(e) + "\n\n(likely text encoding error)")

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
                     elif os.path.basename(subfile).lower() == "wadinfo" or os.path.basename(subfile).lower() == "wadinfo.txt":
                        with pk3_file.open(subfile) as txt_file:
                           mapset.read_txt(txt_file.read().decode("utf-8"))
                     elif os.path.basename(subfile).lower() == "gameinfo" or os.path.basename(subfile).lower() == "gameinfo.txt":
                        with pk3_file.open(subfile) as gameinfo_file:
                           mapset.read_gameinfo(gameinfo_file.read().decode("utf-8"))
            
               try:
                  with open(os.path.join(os.path.dirname(fullpath), os.path.splitext(name)[0] + ".txt"), "r") as txt_file:
                     mapset.read_txt(txt_file.read())
               except FileNotFoundError:
                  pass
               except UnicodeDecodeError as e:
                  handleWadReadError("error while reading text file:\nin " + os.path.join(os.path.dirname(fullpath), os.path.splitext(name)[0] + ".txt") + ":\n\n" + str(e) + "\n\n(likely text encoding error)")
               
               try:
                  with open(os.path.join(os.path.dirname(fullpath), name + ".txt"), "r") as txt_file:
                     mapset.read_txt(txt_file.read())
               except FileNotFoundError:
                  pass
               except UnicodeDecodeError as e:
                  handleWadReadError("error while reading text file:\nin " + os.path.join(os.path.dirname(fullpath), name + ".txt") + ":\n\n" + str(e) + "\n\n(likely text encoding error)")
               
               mapset.write_config()

         except NotImplementedError as e:
            print("Error while reading " + fullpath + ", skipping thumbnail generation")
            print(e)

def changeFakeVistaButtonColors(frame, button, background, border):
   button.configure(background=background)
   frame.configure(background=border)

# the ttk button in the vista theme has a 1-pixel border around it, and it looks awful
def makeButtonThatDoesntSuck(parent, text):
   if ttk.Style().theme_use() == "vista":
      frame = tk.Frame(parent, background="#ADADAD", borderwidth=0)
      button = tk.Button(frame, text=text, background="#E1E1E1", activebackground="#CCE4F7", relief="flat", borderwidth=0, overrelief="flat", padx=4, pady=1)
      button.bind("<Enter>", lambda event: changeFakeVistaButtonColors(frame, button, "#E5F1FB", "#0078D7"))
      button.bind("<Leave>", lambda event: changeFakeVistaButtonColors(frame, button, "#E1E1E1", "#ADADAD"))
      button.bind("<FocusIn>", lambda event: changeFakeVistaButtonColors(frame, button, "#E1E1E1", "#0078D7"))
      button.bind("<FocusOut>", lambda event: changeFakeVistaButtonColors(frame, button, "#E1E1E1", "#ADADAD"))
      button.pack(fill="both", expand=True, padx=1, pady=1)
      return frame, button
   else:
      button = ttk.Button(parent, text=text)
      return button, button

def write_config():
   try:
      with open(os.path.join(dir_path, "config.txt"), "w") as config_file:
         config_file.writelines(["[engines]\n"])

         for engine in engines:
            config_file.writelines(engine)
            config_file.writelines("\n")

         config_file.writelines("[iwads]\n")

         for iwad_folder in iwad_folders:
            config_file.writelines(iwad_folder)
            config_file.writelines("\n")

         config_file.writelines("[maps]\n")

         for map_folder in map_folders:
            config_file.writelines(map_folder)
            config_file.writelines("\n")

         config_file.writelines("[mods]\n")

         for mod_folder in mod_folders:
            config_file.writelines(mod_folder)
            config_file.writelines("\n")

         messagebox.showinfo(message="Please restart Doomlaunch for the new config to take effect")
   except:
      messagebox.showerror(message="Error while writing config file")

def set_maps_folder():
   map_folders.clear()
   map_folders.append(filedialog.askdirectory(mustexist=True, title="Select maps folder"))
   write_config()

def set_mods_folder():
   mod_folders.clear()
   mod_folders.append(filedialog.askdirectory(mustexist=True, title="Select mods folder"))
   write_config()

def set_iwad_folder():
   iwad_folders.clear()
   iwad_folders.append(filedialog.askdirectory(mustexist=True, title="Select IWAD folder"))
   write_config()

def add_engine():
   engines.append(filedialog.askopenfilename(title="Select engine exe"))
   write_config()

def remove_engine(engine_path: str):
   if engine_path in engines:
      engines.remove(engine_path)
      write_config()

def display_about():
   messagebox.showinfo(message="""Doomlaunch by Alexander6RI

Made using Python and tkinter

Icon from Silk by FamFamFam and its SVG adaptation by frhun""")

def remove_engine_command(engine: str):
   def remove_engine():
      print(engine)
      if engine in engines:
         engines.remove(engine)
         write_config()
   return remove_engine

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

for engine in engines:
   engine_names.append(os.path.basename(engine))

window = tk.Tk()
window.geometry("210x200")
window.title("Doomlaunch")
window.iconbitmap(os.path.join(dir_path, "disk_multiple.ico"))
window.bind("<Escape>", lambda event: window.destroy())
window.rowconfigure(2, weight=1)
window.columnconfigure(0, weight=1)
window.columnconfigure(1, weight=1)

menubar = tk.Menu(window)
filemenu = tk.Menu(menubar, tearoff=0)

filemenu.add_command(label="Set maps folder", command=set_maps_folder)
filemenu.add_command(label="Set mods folder", command=set_mods_folder)
filemenu.add_command(label="Set IWAD folder", command=set_iwad_folder)
filemenu.add_command(label="Add game engine", command=add_engine)
engines_menu = tk.Menu(filemenu)
for index, engine in enumerate(engine_names):
   engines_menu.add_command(label=engine, command=remove_engine_command(engines[index]))
filemenu.add_cascade(label="Remove game engine...", menu=engines_menu)

filemenu.add_separator()

filemenu.add_command(label="About", command=display_about)
filemenu.add_command(label="Exit", command=window.destroy)

menubar.add_cascade(label="File", menu=filemenu)
window.configure(menu=menubar)

default_font_size = font.nametofont("TkDefaultFont").actual().get("size")
thumbnail_size = (int((320.0 / 200.0) * default_font_size * 2), int(default_font_size * 2 + 1))

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
   
   button = tk.Radiobutton(map_window, text=mapset.title, value=mapset.name, variable=selected_map, command=loadProfile, indicatoron=False, borderwidth=0, highlightthickness=0, anchor="w", bg="white")
   height = button.winfo_reqheight()

   button.grid(row=row, column=1, sticky="ew")
   addWheelHandler(button, map_canvas)

   if mapset.thumbnailpath != None:
      image = tk.PhotoImage(file=mapset.thumbnailpath)
      image_label = tk.Label(map_window, image=image, borderwidth=0)
      image_label.image = image # pyright: ignore[reportAttributeAccessIssue] # to save from garbage collection
      image_label.grid(row=row, column=0, sticky="w")
      addWheelHandler(image_label, map_canvas)
   elif mapset.titlepicpath != None:
      image_full = tk.PhotoImage(file=mapset.titlepicpath)
      thumbnail_width = int((320.0 / 200.0) * default_font_size * 2)
      thumbnail_height = int(default_font_size * 2 + 1)
      shrink_factor = max(ceil(image_full.width() / thumbnail_width), ceil(image_full.height() / thumbnail_height))
      image = image_full.subsample(shrink_factor, shrink_factor)
      image_label = tk.Label(map_window, image=image, borderwidth=0)
      image_label.image = image # pyright: ignore[reportAttributeAccessIssue] # to save from garbage collection
      image_label.grid(row=row, column=0, sticky="w")
      addWheelHandler(image_label, map_canvas)
   elif mapset.logopath != None:
      image_full = tk.PhotoImage(file=mapset.logopath)
      logo_width = int((320.0 / 200.0) * default_font_size * 2)
      logo_height = int(default_font_size * 2 + 1)
      shrink_factor = max(ceil(image_full.width() / logo_width), ceil(image_full.height() / logo_height))
      image = image_full.subsample(shrink_factor, shrink_factor)
      image_label = tk.Label(map_window, image=image, borderwidth=0)
      image_label.image = image # pyright: ignore[reportAttributeAccessIssue] # to save from garbage collection
      image_label.grid(row=row, column=0, sticky="w")
      addWheelHandler(image_label, map_canvas)

iwad_pwad_separator = ttk.Separator(map_window, orient="horizontal")
iwad_pwad_separator.grid(row=number_of_iwads, column=0, columnspan=2, sticky="ew", pady=0)

map_canvas.create_window((0, 0), window=map_window, anchor="nw")

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
launch_button_outer.grid(row=3, column=0, columnspan=3, padx=2, pady=2)

launch_background = tk.Label(window, bg="white", image=None) # pyright: ignore[reportArgumentType]
launch_background.lower()
window.bind("<Configure>", lambda event: processBackgroundImage())

loadProfile()

window.mainloop()