#!/usr/local/bin/python3.6

#./colortest.py -outfile basiccolors.pdf '#0055ff' '#ff6600' '#ffee00' '#ffacac' '#a4b9ee' '#ccd599' '#d8f0f8' // blue, primary/educational, secondary/other, pedestrian, motorway, greenspace, water

# more FINE GRAINED test for builtup, primary (centered around 40 hue), green, yellow border+overview bg in one, blue, commercial, leisure
#./colortest.py -outfile detailedhues.pdf -d 4 10 5 -- '#ffd599' '#ffb828' '#dfe8a7' '#fff5c9' '#3385d6' '#9f83b5' '#ba8550'

# front page colors
# blue: 230deg, 100%, 100%
# red: 5deg, 90%, 100%
# background light blue: 220deg, 20% saturation, 100% value
# saturation diff only 15, not 20
#./colortest.py -paper a4 -landscape -outfile front.pdf -d 5 15 5 -- '#002AFF' '#FF2D19' '#CCDDFF'
#./colortest.py -paper a4 -landscape -outfile front2.pdf -d 5 20 20 -- '#002AFF' '#FF2D19' '#CCDDFF'
# conclusions of the PROPER print shop test:
# blue: 244deg, 100% s, <69% v == #0C00B0 (looks v purple on screen??) in QGIS: #0b00b0
# red: 358deg, 95+-3% s, 100% v == #FF0D15
# backblue: 220deg, 8+-2% s, 69% v == #9EA4B0 (choose 10 saturation because otherwise completely gray)
# FIRST TO SECOND PRINT CHANGES
# blue goes from 19,94,242 to 12,0,176
# red goes from 235,26,7 to 255,13,21
# backblue goes from 204,209,255 to 158,164,176 (don't think that can be right???)

# yellow only
#./colortest.py -paper a4 -landscape -outfile yellow.pdf -n 2 7 1 -d 3 5 2 -- '#fffcb3'

#yellowborder: '#ffffc3'
# poi can be done through pedestrian
# healthcare can be done through greenspace
#./colortest.py -outfile areafills.pdf '#bbc2ff' // station, 

import argparse

#from webcolors import rgb_percent_to_hex
import papersize

from colour import Color # for parsing
#from colormath.color_objects import *
#from colormath.color_conversions import convert_color

import os
from decimal import Decimal
from math import floor

class ColorAction(argparse.Action):
  def __call__(self, parser, namespace, values, option_string=None):
#    if len(values) % 3 == 0:
#      print('TODO test')
#       return
    setattr(namespace, self.dest, [Color(v) for v in values])

class ColorSpaceAction(argparse.Action):
  def __call__(self, parser, namespace, values, option_string=None):
    setattr(namespace, self.dest, globals()[values + 'Color'])

class MakeThreeAction(argparse.Action):
  def __call__(self, parser, namespace, values, option_string=None):
    if len(values) == 1:
      values = [values[0] for i in range(3)]
    elif len(values) != 3:
      raise ValueError('Argument ' + option_string + ' requires either 1 or 3 arguments')
    setattr(namespace, self.dest, values)

parser = argparse.ArgumentParser(description='generate boxes of similar colors')

parser.add_argument('-paper', default='a4', help='papersize to n-up all created cards to')
parser.add_argument('-landscape', default=False, action='store_true')
parser.add_argument('-margin', default='1cm', help='non-printable margin (any parseable length specification)')

#colorspaces = ['sRGB', 'HSL', 'HSV', 'CMYK']
#parser.add_argument('-inspace', action=ColorSpaceAction, default=sRGBColor, help='colorspace that the colors argument should be interpreted as (default: sRGB)')
#parser.add_argument('-diffspace', action=ColorSpaceAction, default=HSLColor, help='colorspace that the variations should be generated in (default: HSL)')
parser.add_argument('-hsv', default=True, action='store_true', help='compute diffs in HSV space (as opposed to the default HSL)')

parser.add_argument('-n', type=int, nargs='+', action=MakeThreeAction, default=[2, 2, 2], help='number of colour variations per direction per dimension (i.e. either 1 or 3 arguments should be provided). Along the dimension there will be 1+2*n boxes.')

parser.add_argument('-d', type=float, nargs='+', action=MakeThreeAction, default=[5, 20, 10], help='diff as a fraction of 255 (per dimension)')

parser.add_argument('-outfile', default='colortest.pdf', help='the file to write the test page to')
parser.add_argument('colors', nargs='+', action=ColorAction, help='color specifications (value triplets or hex/webcolor strings)')

args = parser.parse_args()
#colors = [convert_color(args.inspace(*col.rgb), args.diffspace) for col in args.colors] # FIXME only works for sRGBColor inspace right now!
colors = args.colors
args.d = [d / 255 for d in args.d]

def swapvalue(lst, i, newvalue):
  lst[i] = newvalue
  return lst

def hsltohsv(hsl):
  v = hsl[2] + hsl[1] * min(hsl[2], 1-hsl[2])
  return [hsl[0], 0 if v == 0 else 2 * (1 - hsl[2] / v), v]

def hsvtohsl(hsv):
  l = hsv[2] * (1 - hsv[1] / 2)
  return [hsv[0], 0 if (l == 0 or l == 1) else (hsv[2] - l) / min(l, 1-l), l]

# generate neighbouring colors
def gethsvneighbours(col, dim):
  n = 1 + 2 * args.n[dim]
  col = hsltohsv(col.hsl)
  if dim == 0:
    # allow overrun of hue
    mn = col[dim] - args.n[dim] * args.d[dim]
  else:
    mn = max(0, min(col[dim] - args.n[dim] * args.d[dim], 1 - (n-1) * args.d[dim]))
  # this works, but it loses the computed hsvg values again by converting into hsl...
  return [Color(hsl=hsvtohsl(swapvalue(list(col), dim, mn + i * args.d[dim]))) for i in range(n)]

def gethslneighbours(col, dim):
  n = 1 + 2 * args.n[dim]
  # make editable (tuples are immutable!)
#  colt = list(col.get_value_tuple())
  # colt[dim] - args.n[dim] * args.d[dim], but clamped to [0, 1 - (n-1) * args.d[dim]]
  if dim == 0:
    # allow overrun of hue
    mn = col.hsl[dim] - args.n[dim] * args.d[dim]
  else:
    mn = max(0, min(col.hsl[dim] - args.n[dim] * args.d[dim], 1 - (n-1) * args.d[dim]))
  return [Color(hsl=swapvalue(list(col.hsl), dim, mn + i * args.d[dim])) for i in range(n)]
#  return [args.diffspace(*swapvalue(colt, dim, i*args.d[dim])) for i in range(n)]

getneighbours = gethsvneighbours if args.hsv else gethslneighbours

# calculate neighbours in the 'diffspace'
# 1st dim is top-down next to each other boxes (saturation)
# 2nd dim is left-right spaced groups (hue)
# 3rd dim is left-right next to each other boxes (lightness)
dimorder = (1, 0, 2)

d1neighbours = [getneighbours(col, dimorder[0]) for col in colors]
d2neighbours = [[getneighbours(col, dimorder[1]) for col in sublist] for sublist in d1neighbours]
d3neighbours = [[[getneighbours(col, dimorder[2]) for col in sublist] for sublist in mainlist] for mainlist in d2neighbours]

# boxes along the x axis = 1st dimension * (2nd dimension + 1 for spacing) - 1
nx = (len(d3neighbours[0][0]) + 1) * len(d3neighbours[0][0][0]) - 1
# boxes along the y axis = ncolors * (3rd dimension + 1 for spacing) - 1
ny = (len(d3neighbours[0]) + 1) * len(colors) - 1

# all in pt
size = papersize.parse_papersize(args.paper)
if args.landscape:
  size = papersize.rotate(size, papersize.LANDSCAPE)
margin = papersize.parse_length(args.margin)

printsize = [s - 2*margin for s in size]
boxwidth = printsize[0] / nx
boxheight = printsize[1] / ny
print(f'{nx}x{ny} fits {boxwidth}x{boxheight}')

boxwidth = min(boxwidth, boxheight)
boxheight = min(boxwidth, boxheight)
print('box size: ' + str(boxheight/3) + ' mm')
#boxsize = min(boxwidth, boxheight)

# parse rectangle/square specs
#def parserectanglespec(spec):
#  try:
#    return papersize.parse_papersize(spec)
#  except:
#    length = papersize.parse_length(spec)
#    return [length, length]

#args.rectangle = [parserectanglespec(re) for re in args.rectangle]

# def parsecolor(spec):
#   try:
#     spec = webcolors.name_to_hex(spec)
#   except:
#     pass
#   return sRGBColor.new_from_rgb_hex(spec)

# colors = { col: parsecolor(col) for col in args.color }

def drawbox(col, xoffset, yoffset):
  return ' '.join(str(x) for x in col.rgb) + ' setrgbcolor ' + str(margin + xoffset * boxwidth) + ' ' + str(margin + yoffset * boxheight) + ' ' + str(boxwidth)+ ' ' + str(boxheight) + ' rectfill '

def drawlabel(text, xoffset, yoffset):
  return ' 0 setgray ' + str(margin + xoffset * boxwidth + 12) + ' ' + str(margin + yoffset * boxheight + 5) + ' moveto (' + str(round(255*text)) + ') show '

postscript = '/Times 10 selectfont '
x = 0
y = 0
for color in d3neighbours:
  for d3 in color:
    # this one goes top-down
    # reset horizontal axis
    x = 0
    for d2 in d3:
      # left right (tight)
#      print(d2[0].hsl[dimorder[1]])
      for d1 in d2:
        # left right (groups)
#        print(d1.hsl[dimorder[2]])
        postscript += drawbox(d1, x, y)
        x = x+1
        # add blank column
      x = x+1
    # write saturation levels (td)
    postscript += drawlabel((hsltohsv(d3[0][0].hsl)[1] if args.hsv else d3[0][0].hsl[dimorder[0]])*100/255, -1, y)
    y = y+1
  # hue *extremes* only (lr-boxes)
  postscript += drawlabel(d3[0][0].hsl[dimorder[1]]*360/255, args.n[dimorder[1]], y)
  postscript += drawlabel(d3[4][0].hsl[dimorder[1]]*360/255, args.n[dimorder[1]] + 2*args.n[dimorder[2]]*(2+2*args.n[dimorder[1]]), y)
  # value *extremes* only (lr)
  mn = hsltohsv(d3[0][0].hsl)[2] if args.hsv else d3[0][0].hsl[dimorder[2]]
  mx = hsltohsv(d3[0][2 * args.n[2]].hsl)[2] if args.hsv else d3[0][2 * args.n[2]].hsl[dimorder[2]]
  postscript += drawlabel(mn*100/255, args.n[dimorder[2]] + args.n[dimorder[2]]*(2+2*args.n[dimorder[1]]) - 2, y)
  postscript += drawlabel(mx*100/255, args.n[dimorder[2]] + args.n[dimorder[2]]*(2+2*args.n[dimorder[1]]) + 2, y)
  # add blank line
  y = y+1

#for colname, rgb in colors.items():
#  for (x,y) in args.rectangle:
#    pos = [(dim / 2 - s / 2) for (dim, s) in zip(size, (x,y))]
#    pos.extend([x, y])
#    pos = ' '.join([str(x) for x in pos])
#    postscript += setcolor(rgb) + pos + ' rectfill showpage '

#  for r in args.circle:
#    pos = [dim / 2 for dim in size]
#    pos.extend([r, 0, 360])
#    pos = ' '.join([str(x) for x in pos])
#    postscript += setcolor(rgb) + pos + ' arc fill showpage '


  # a4 is 595x842 pt
  # a5 is 420x595 pt
  # a6 is 297x420 pt
#  1 0 0 setrgbcolor x y dx dy rectfill showpage

#postscript = '1 0 0 setrgbcolor 0 0 200 200 rectfill showpage'

def isnamedsize(spec):
  try:
    papersize.parse_couple(spec)
    return False
  except:
    papersize.parse_papersize(spec)
    return True

#if isnamedsize(args.paper):
#  gsspec = '-sPAPERSIZE=' + args.paper
#else:
gsspec = '-dDEVICEWIDTHPOINTS=' + str(round(size[0])) + ' -dDEVICEHEIGHTPOINTS=' + str(round(size[1]))

#print(postscript)

os.system('gs -q ' + gsspec + ' -dBATCH -dNOPAUSE -sDEVICE=pdfwrite -sOutputFile=' + args.outfile + ' -c "' + postscript + '"')

# if args.nup:
#   # calculate fit
#   paper = papersize.parse_papersize(args.paper)

#   nup = [str(floor(p / s)) for (s, p) in zip(size, paper)]
#   # TODO check for improved fit in landscape
#   #landscape = False

#   if isnamedsize(args.paper):
#     texspec = '--paper ' + args.paper
#   else:
#     texspec = '--papersize \'{' + ','.join([str(dim) + 'pt' for dim in paper]) + '}\''

#   os.system('pdfjam -q ' + texspec + ' --nup ' + 'x'.join(nup) + ' --suffix nup --frame true --noautoscale true ' + args.outfile)
