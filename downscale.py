from math import floor, ceil
from pathlib import Path
import struct

def downscale_rgb(in_size: tuple[int, int], out_size: tuple[int, int], data: list[list[tuple[int, int, int]]]) -> list[list[tuple[int, int, int]]]:
   """image format: data[x][y][channel]"""

   scale_factor_x = in_size[0] / out_size[0]
   scale_factor_y = in_size[1] / out_size[1]

   output = []

   for x in range(out_size[0]):
      output.append([])
      for y in range(out_size[1]):
         min_input_x = floor((x + 0.25) * scale_factor_x)
         max_input_x = ceil((x + 0.75) * scale_factor_x)
         min_input_y = floor((y + 0.25) * scale_factor_y)
         max_input_y = ceil((y + 0.75) * scale_factor_y)

         sum_r = 0
         sum_g = 0
         sum_b = 0
         count = 0

         for input_x in range(min_input_x, max_input_x):
            for input_y in range(min_input_y, max_input_y):
               sum_r += data[input_x][input_y][0]
               sum_g += data[input_x][input_y][1]
               sum_b += data[input_x][input_y][2]
               count += 1

         output[x].append((sum_r // count, sum_g // count, sum_b // count))

   return output

def convert_pixel_format(input: float | tuple[int, ...]) -> tuple[int, int, int]:
   if type(input) == float:
      return (round(input * 255), round(input * 255), round(input * 255))

   elif isinstance(input, tuple):
      if len(input) == 3:
         return input
      elif len(input) == 1:
         return (input[0], input[0], input[0])
      elif len(input) == 4:
         return ((input[0] * input[3]) // 255, (input[1] * input[3]) // 255, (input[2] * input[3]) // 255)
      else:
         return (0, 0, 0)

   else:
      return (0, 0, 0)

def try_to_downscale_png(source: Path, destination: Path, thumbnail_size: tuple[int, int]) -> Path | None:
   # open the png titlepic, convert to rgb data using pil, and downscale, but only if pillow is actually available

   try:
      from PIL import Image

      with Image.open(source) as img:
         size_factors = (thumbnail_size[0] * 1.0 / img.width, thumbnail_size[1] * 1.0 / img.height)
         smaller_factor = min(size_factors[0], size_factors[1])
         final_size = (round(img.width * smaller_factor), round(img.height * smaller_factor))

         if img.width > 320 * 2 or img.height > 320 * 2:
            # downscale to avoid running out of memory
            # on my computer, the thumbnail width as of writing is 36 px, so a standard titlepic of 320px has a scale factor of 8.89
            mem_downscale_factor = min((final_size[0] * 10.0) / img.width, (final_size[1] * 10.0) / img.height)
            img = img.resize((round(img.width * mem_downscale_factor), round(img.height * mem_downscale_factor)), Image.Resampling.LANCZOS)
            img.save(destination.parent / ("temp_" + destination.name))
         
         pixels: list[list[tuple[int, int, int]]] = []
         data = img.load()
         if data is not None:
            for x in range(img.width):
               pixels.append([])
               for y in range(img.height):
                  pixels[x].append(convert_pixel_format(data[x, y]))

         downscaled_data = downscale_rgb((img.width, img.height), final_size, pixels)

      destination.parent.mkdir(parents=True, exist_ok=True)
      with open(destination, "wb") as thumbnail:

         # file header
         thumbnail.write(b"P6\n") # magic number
         thumbnail.write(b"# " + str(destination).encode() + b"\n") # comment
         thumbnail.write(f"{final_size[0]} {final_size[1]}\n".encode()) # width and height
         thumbnail.write(b"255\n")   # depth

         # pixel data
         for y in range(final_size[1]):
            for x in range(final_size[0]):
               color = downscaled_data[x][y]
               thumbnail.write(struct.pack("<BBB", *color))

         return destination

   except ImportError:
      return None