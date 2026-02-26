from math import floor, ceil

def downscale_rgb(in_size, out_size, data):
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

         for input_x in range(min_input_x, max_input_x + 1):
            for input_y in range(min_input_y, max_input_y + 1):
               sum_r += data[input_x][input_y][0]
               sum_g += data[input_x][input_y][1]
               sum_b += data[input_x][input_y][2]
               count += 1

         output[x].append((sum_r // count, sum_g // count, sum_b // count))

   return output