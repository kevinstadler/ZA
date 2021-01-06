#!/usr/local/bin/python3

# ./layout.py -papersize 420 297 -box 27.5 -outermargin 15 data/{Moulsford,Kunming4sites,Oxford,Nunhead}.atlas
# ./layout.py -printareasize 247.5 197 data/{Glasgow18103,Glasgow9051,Moulsford,Kunming4sites,Oxford,Nunhead,Edinburgh}.atlas

import argparse
import configparser
import time
import os
from random import random

from math import ceil, cos, pi, radians, sin, sqrt
from pyproj import CRS, Transformer
from geojson import Point, Polygon, Feature, FeatureCollection, dump

parser = argparse.ArgumentParser(description='Build a geojson feature file to be used as the basis of a QGIS atlas.')
parser.add_argument('atlas', nargs='*', default='data/Kunming.atlas', help='atlas specification file')
parser.add_argument('--startpage', type=int, default=4, help='first page for page numbering')
parser.add_argument('-o', default='atlas.geojson', help='output filename')

parser.add_argument('-box', type=float, default=27.58, help='in mm')
parser.add_argument('--no-border', default=False, action='store_true', help='omit yellow border outside box (overridden by atlas config "border: true/false")')
parser.add_argument('--no-grid', default=False, action='store_true', help='omit blue grid around boxes (overridden by atlas config "grid: true/false")')
#parser.add_argument('-y', type=float, default=0, help='global y offset (for spreading pages)')
#parser.add_argument('-papersize', type=float, nargs=2, default=(297, 210), metavar=('width', 'height'), help='in mm (overridden by atlas config "papersize:")')
parser.add_argument('-papersize', type=float, nargs=2, default=(287, 210), metavar=('width', 'height'), help='in mm (overridden by atlas config "papersize:")')
#parser.add_argument('-printareasize', type=float, nargs=2, default=(247.5, 191), metavar=('width', 'height'), help='in mm (overridden by atlas config "printsize:")')
parser.add_argument('-printareasize', type=float, nargs=2, default=(253.5, 197), metavar=('width', 'height'), help='in mm (overridden by atlas config "printsize:")')
parser.add_argument('-bleed', type=float, default=3, help='this many mm on every side of the printareasize will be considered bleed (and cropmarks added)')

parser.add_argument('-dpi', type=int, default=500, help='layout export resolution (overridden by atlas config "dpi:")')
# FIXME bleed messes up the yellow border margin because I previously distinguished between visiblemargin and mapmargin.....
parser.add_argument('-outermargin', type=float, default=None, help='instead of specifying the printarea, give some margin (in mm)')

parser.add_argument('-write', default=False, action='store_true', help='write new layout straight to ZA2.qgs (overwriting any layouts of the same name)')
parser.add_argument('-index', default=False, action='store_true', help='TODO whether to query the PostGIS database to query all covered road/place names and write an -index.pdf file')
args = parser.parse_args()

nmaps = len(args.atlas)
atlasbooklet = nmaps == 1

# FIXME might have to NOT reuse this one?
config = configparser.ConfigParser(converters={'numbers': lambda value: [float(num) for num in value.strip('[]').split(',')] })

# if only 1 atlas file, read papersize, printareasize and other global options from atlas
if atlasbooklet:
  print("overwriting available args from atlas booklet....")
  config.read(args.atlas[0])
  if config.has_option('map', 'papersize'):
    args.papersize = config.getnumbers('map', 'papersize')
    if config.has_option('map', 'printareasize'):
      args.printareasize = config.getnumbers('map', 'printareasize')
    else:
      args.printareasize = args.papersize

  if config.has_option('map', 'bleed'):
    args.bleed = config.getfloat('map', 'bleed')
  if config.has_option('map', 'dpi'):
    args.dpi = config.getint('map', 'dpi')
  if config.has_option('map', 'border'):
    args.no_border = not config.getboolean('map', 'border')
  if config.has_option('map', 'grid'):
    args.no_grid = not config.getboolean('map', 'grid')

mapsperaxis = [1, 1]
#if False:
#  xmaps = ceil(sqrt(nmaps))
#  mapsperaxis = [ xmaps, ceil(nmaps / xmaps) ]

npages = ceil(nmaps / (mapsperaxis[0] * mapsperaxis[1]))

if args.outermargin == None:
  outermargins = list(map(lambda paper, print: (paper - print) / 2, args.papersize, args.printareasize))
else:
  outermargins = [ args.outermargin, args.outermargin ]
  args.printareasize = [l - 2 * args.outermargin for l in args.papersize]

desiredmapsize = list(map(lambda s, n: s / n, args.printareasize, mapsperaxis))

# allocate at least 8mm of (yellow) margin plus bleed on all sides
#nboxes = list(map(lambda d: ( d - 16 - args.bleed) // args.box, desiredmapsize))
nboxes = [(d - 16) // args.box for d in desiredmapsize]

innermapsize = desiredmapsize if args.no_border and args.no_grid else list(map(lambda n: n * args.box, nboxes))
visiblemargins = list(map(lambda d, i: (d - i) / 2, desiredmapsize, innermapsize))

#outermapsize = list(map(lambda d: d + 2 * args.bleed, desiredmapsize))
outermapsize = desiredmapsize

mapmargins = list(map(lambda d, i: (d - i) / 2, outermapsize, innermapsize))

def sizespecstring(array):
  return ','.join(map(str, array))
outermapsizespec = sizespecstring(outermapsize)
papersizespec = sizespecstring(args.papersize)

### OUTER MAP
# the outer map goes from 0,0 to totalsize
## FRAMES, GRIDS, LABELS
# yellow frame offset can't be negative, so needs to be zero on the *smaller* margin
yellowborderwidth = 2 * min(visiblemargins)
# the center of the frame stroke is 0 on the smaller margin, margin - yellowborderwidth/2 on the larger one
yellowborderoffset = [m - yellowborderwidth / 2 for m in visiblemargins]
# reduce interval on the wider margin length so that the second one doesn't leave the page
yellowframeinterval = list(map(lambda d, o: d - 2*o, desiredmapsize, yellowborderoffset))
# grid interval is args.box, grid offset is totalmargins

### COVER RECTANGLE
# size is innermapsize, offset is totalmargins

### INNER MAP
# inner map size is innermapsize
# inner map offset is totalmargins
### FRAMES, GRIDS, LABELS
# grid interval is args.box, grid offset is 0
# label backgrounds and labels both shown OUTSIDE frame with distance ?mm to map frame
# label backgrounds and labels interval is x, offset is totalmargins + x/2

def getid():
  return str(round(1000000 * random()))

def dataDefinedBlues(propertyNames, other = ''):
  tagname = 'dataDefinedProperties' if (propertyNames[0] == 'dataDefinedBackgroundColor' or propertyNames[0] == 'dataDefinedFrameColor' or propertyNames[0] == 'dataDefinedFontColor') else 'data_defined_properties' # backgroundColor for textboxes, fillColor/outlineColor for triangles + blue grid
  return '''<''' + tagname + '''>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties" type="Map">''' + "".join(['''<Option name="''' + propertyName + '''" type="Map">
                    <Option name="active" value="true" type="bool"/>
                    <Option name="expression" value="project_color('blue')" type="QString"/>
                    <Option name="type" value="3" type="int"/>
                  </Option>''' for propertyName in propertyNames]) + other + '''
                </Option>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </''' + tagname + '''>'''

def dataDefinedBlue(propertyName, other = ''):
  return dataDefinedBlues([propertyName], other)

# a map <LayoutItem>
def getmapxml(name, offset, size, extent, theme, proj4, zindex = 0, custompropertiesandgrids = '', rotation = 0, atlas=True, customattributes = ''):
  # was 0 if inner else 0 wtf is mapFlags
  # TODO set a fixed uuid that can be referred to by scale lines
  return ('<LayoutItem uuid="' + name + '" size="' + size + ',mm" mapFlags="' + str(0 if True else 1) + '" blendMode="' + str(6 if theme == 'mono' else 0) + '" followPreset="true" position="' + offset + ',mm" zValue="' + str(zindex) + '" positionOnPage="' + offset + ',mm" type="65639" followPresetName="' + theme + '" visibility="1" id="' + name + '" mapRotation="' + str(rotation) + '" positionLock="true" ' + customattributes + '>' + custompropertiesandgrids + '<Extent xmin="' + extent[0][0] + '" xmax="' + extent[0][1] + '" ymin="' + extent[1][0] + '" ymax="' + extent[1][1] + '"/><crs><spatialrefsys><proj4>' + proj4 + '</proj4></spatialrefsys></crs><AtlasMap margin="0" scalingMode="0" atlasDriven="' + str(1 if atlas else 0) + '"/></LayoutItem>')

def getcrs(config):
  return CRS.from_user_input(config['map']['proj'])

# for teasing apart atlas page specs
def getlist(spec):
  split = spec.find('-', 1)
  if split > 0:
    return range(int(spec[:split]), int(spec[split+1:]) + 1)
  else:
    return [int(spec)]
def parselist(xspec):
  # FIXME ignore whitespace everywhere?
  return [page for sublist in map(getlist, xspec.split(', ')) for page in sublist]

def getmaplayout(layoutname, config, outermapoffset):

  crs = getcrs(config)
  wgs = CRS.from_epsg(4326)

  # always use longlat
  fromwgs = Transformer.from_crs(wgs, crs, always_xy=True)
  towgs = Transformer.from_crs(crs, wgs, always_xy=True)

  center = config.getnumbers('map', 'center')
  crscenter = fromwgs.transform(center[0], center[1])

  rotation = config.getfloat('map', 'rotation') if config.has_option('map', 'rotation') else 0

  scale = config.getfloat('map', 'scale')
  # TODO merge both argument specs by calling defaultsdict.update(overridedict)?

  scaledinnermapsize = [d * scale / 1000 for d in innermapsize]
  scaledtotalmapsize = [d * scale / 1000 for d in outermapsize]

  # TODO add overbleed and offset from spacing maps
  outermapoffsetspec = sizespecstring(outermapoffset)

  innermapoffset = map(lambda a, b: a + b, mapmargins, outermapoffset)
  innermapoffsetspec = sizespecstring(innermapoffset)

  totalmarginspec = sizespecstring(mapmargins)
  innermapsizespec = sizespecstring(innermapsize)

  if atlasbooklet and config.has_section('pages'):
    print("Creating atlas index with " + str(scaledinnermapsize[0]) + "x" + str(scaledinnermapsize[1]) + " meters per page")

    # make an array of arrays
    pagespec = { yspec: parselist(config.get('pages', yspec)) for yspec in config['pages'] }
    # add one on each side so neighbourhood can be checked easily
    dy = -min([ round(float(y)) for y in pagespec.keys() ]) + 1
    ny = 1 + dy + max([ round(float(y)) for y in pagespec.keys() ])
    dx = -min([ round(float(x)) for xs in pagespec.values() for x in xs ]) + 1
    nx = 1 + dx + max([ round(float(x)) for xs in pagespec.values() for x in xs ])

    # create matrix representation
    pagematrix = [[0 for x in range(nx+1)] for y in range(ny+1)]
    pagenum = args.startpage
    for (rowname, rowspec) in pagespec.items():
      for page in rowspec:
        pagematrix[int(rowname) + dy][page + dx] = pagenum
        pagenum += 2

    # http://danceswithcode.net/engineeringnotes/rotations_in_2d/rotations_in_2d.html
    s = sin(radians(rotation))
    c = cos(radians(rotation))
    xoffset = scaledinnermapsize[0]
    yoffset = scaledinnermapsize[1]

    def atlaspagefeatures(x, y):
      # re-offset the matrix dx/dy offset from outside (only here)
      # change the sign of the y here because the y order direction changed...
      pagecenter = [ crscenter[0] + c * (x-dx) * xoffset + s * (y-dy) * yoffset, crscenter[1] - c * (y-dy) * yoffset + s * (x-dx) * xoffset ]
    #  xs = list(map(lambda center, mapsize: [ center + mapsize / 2, center - mapsize / 2 ], pagecenter, offsets))
      polygon = Polygon([[
        towgs.transform(pagecenter[0] + c * xoffset / 2 - s * yoffset / 2, pagecenter[1] + c * yoffset / 2 + s * xoffset / 2),
        towgs.transform(pagecenter[0] + c * xoffset / 2 + s * yoffset / 2, pagecenter[1] - c * yoffset / 2 + s * xoffset / 2),
        towgs.transform(pagecenter[0] - c * xoffset / 2 + s * yoffset / 2, pagecenter[1] - c * yoffset / 2 - s * xoffset / 2),
        towgs.transform(pagecenter[0] - c * xoffset / 2 - s * yoffset / 2, pagecenter[1] + c * yoffset / 2 - s * xoffset / 2),
        towgs.transform(pagecenter[0] + c * xoffset / 2 - s * yoffset / 2, pagecenter[1] + c * yoffset / 2 + s * xoffset / 2)
        ]])
      return [Feature(geometry=Point(towgs.transform(pagecenter[0], pagecenter[1])), properties={"type": "atlaspage", "page": pagematrix[y][x],
          "leftpage": pagematrix[y][x], "rightpage": pagematrix[y][x] + 1,
          "left": pagematrix[y][x-1] + 1*(pagematrix[y][x-1] != 0), "right": pagematrix[y][x+1], "top": pagematrix[y-1][x], "bottom": pagematrix[y+1][x]}),
       Feature(geometry=polygon, properties={"type": "atlaspage", "page": pagematrix[y][x]}),
       Feature(geometry=Point(towgs.transform(pagecenter[0] - xoffset / 4, pagecenter[1])), properties={"type": "printpage", "page": pagematrix[y][x]}),
       Feature(geometry=Point(towgs.transform(pagecenter[0] + xoffset / 4, pagecenter[1])), properties={"type": "printpage", "page": pagematrix[y][x] + 1})]

    perpagefeatures = [ atlaspagefeatures(x+dx, int(y)+dy) for (y,xs) in pagespec.items() for x in xs ]
    feature_collection = FeatureCollection([feature for pagefeatures in perpagefeatures for feature in pagefeatures])

    with open(args.o, 'w') as f:
      dump(feature_collection, f)
      print('Atlas features written to ' + args.o)
      # TODO calculate probably THICKNESS based on page numbers
      ndoublepages = len(feature_collection['features'])/4
      print(str(ndoublepages) + ' atlas features (a double page each) corresponds to the same number of pages')
      # GGW: 164 map pages + 92 index pages = 1cm
      # 256 pages = 128 double pages = 1cm
      print('EXPECTED BOOK THICKNESS (without index): ' + str(ndoublepages/128) + 'cm')
      # 60% extra index
      if args.index:
        print('EXPECTED BOOK THICKNESS (*with* index): ' + str(ndoublepages*1.6/128) + 'cm')

  # needs arrays!
  def getgrid(name, intervals, offsets, options, markerspec, inner = False, disabledSides = []):
    # annotationPosition 0 = inner, 1 = outer // annotationDisplay 0 = all 3 = disabled
    disabledAnnotations = ' '.join(map(lambda side: side + 'AnnotationDisplay="3"', disabledSides))
    return '<ComposerMapGrid uuid="{' + getid() + '}" show="1" unit="1" name="' + name + '" ' + disabledAnnotations + ' bottomAnnotationPosition="' + str(0 if inner else 1) + '" leftAnnotationPosition="' + str(0 if inner else 1) + '" topAnnotationPosition="' + str(0 if inner else 1) + '" rightAnnotationPosition="' + str(0 if inner else 1) + '" intervalY="' + str(intervals[1]) + '" gridFrameWidth="2" offsetX="' + str(offsets[0]) + '" intervalX="' + str(intervals[0]) + '" offsetY="' + str(offsets[1]) + '" ' + options + '>' + markerspec + '</ComposerMapGrid>'

  labelbgsize = 5.9
  # not spot-on, but would match the non-swung 6/9 of the page labels: <text-style fontSize="12" fontFamily="D-DIN" namedStyle="DIN-Bold" textColor="255,255,255,255">
  labelspec = '''<text-style fontSize="12" fontFamily="Helvetica Neue" namedStyle="Condensed Bold" textColor="255,255,255,255">
  <background shapeDraw="1" shapeSizeType="1" shapeType="3" shapeSizeUnit="MM" shapeOffsetY="-2.4" />
  <!-- don't draw the background in the corners -->
  <dd_properties>
    <Option type="Map">
      <Option name="name" value="" type="QString"/>
      <Option name="properties" type="Map">
        <Option name="ShapeFillColor" type="Map">
          <Option value="true" name="active" type="bool"/>
          <Option value="project_color('blue')" name="expression" type="QString"/>
          <Option value="3" name="type" type="int"/>
        </Option>
        <Option name="ShapeSizeX" type="Map">
          <Option name="active" value="true" type="bool"/>
          <Option name="expression" value="if(@grid_number > ''' + str(mapmargins[0]) + ''' AND @grid_number &lt; if(@grid_axis = 'x', ''' + str(mapmargins[0] + args.box * nboxes[0]) + ''', ''' + str(mapmargins[1] + args.box * nboxes[1]) + '''), ''' + str(labelbgsize) + ''', 0)" type="QString"/>
          <Option name="type" value="3" type="int"/>
        </Option>
        <Option name="ShapeSizeY" type="Map">
          <Option name="active" value="true" type="bool"/>
          <Option name="expression" value="if(@grid_number > ''' + str(mapmargins[0]) + ''' AND @grid_number &lt; if(@grid_axis = 'x', ''' + str(mapmargins[0] + args.box * nboxes[0]) + ''', ''' + str(mapmargins[1] + args.box * nboxes[1]) + '''), ''' + str(labelbgsize) + ''', 0)" type="QString"/>
          <Option name="type" value="3" type="int"/>
        </Option>
      </Option>
    </Option>
  </dd_properties>
</text-style>'''

  def getlabelgrid(name, intervals, offsets, options):
    return getgrid(name, intervals, offsets, options, labelspec, True)

  def getbluegridspec(main):
    return '''
      <lineStyle>
        <symbol name="" force_rhr="0" clip_to_extent="1" alpha="1" type="line">
          <layer locked="0" class="SimpleLine" pass="0" enabled="1">
            <prop v="solid" k="line_style"/>
            <prop v="''' + str(.4 if main else .25) + '''" k="line_width"/>
            <prop v="Point" k="line_width_unit"/>''' + dataDefinedBlue('outlineColor') + '''
          </layer>
        </symbol>
      </lineStyle>'''

  # was: 2.7 outside for bg, 5.5 outside for label (label should be 2.4-2.6ish more)
#  labelbgexpression = "if(@grid_number &gt; " + str(mapmargins[0]) + " AND @grid_number &lt; if(@grid_axis = 'x', " + ','.join(map(lambda n, m: str(args.box * n + m), nboxes, mapmargins)) + "),  'l', '')"
#  lrlabelbgoptions = 'gridStyle="3" showAnnotation="1" annotationFontColor="' + bluestring + ',255" frameAnnotationDistance="' + str(mapmargins[0] - 10) + '" annotationFormat="8" annotationExpression="' + labelbgexpression + '"'
#  tblabelbgoptions = 'gridStyle="3" showAnnotation="1" annotationFontColor="' + bluestring + ',255" frameAnnotationDistance="' + str(mapmargins[1] - 10) + '" annotationFormat="8" annotationExpression="' + labelbgexpression + '"'
#  labelbgspec = '<annotationFontProperties description="Wingdings,30,-1,5,50,0,0,0,0,0,Regular" style="Regular"/>'

  labelindices = list(map(lambda m: 'ceil((@grid_number - ' + str(m) + ') / ' + str(args.box) + ')', mapmargins))
  labelexpression = "if(@grid_number &lt; " + str(mapmargins[0]) + ", '', if(@grid_axis = 'x', if(@grid_number &lt; " + str(args.box * nboxes[0] + mapmargins[0]) + ", char(64 + " + labelindices[0] + "), ''), if(@grid_number &lt; " + str(args.box * nboxes[1] + mapmargins[1]) + ", " + str(nboxes[1] + 1) + " - " + labelindices[1] + ", '')))"

#  lrlabeloptions = 'uuid="{' + getid() + '}" gridStyle="3" showAnnotation="1" annotationFontColor="255,255,255,255" frameAnnotationDistance="' + str(mapmargins[0] - 7.3) + '" annotationFormat="8" annotationExpression="' + labelexpression + '"'
#  tblabeloptions = 'uuid="{' + getid() + '}" gridStyle="3" showAnnotation="1" annotationFontColor="255,255,255,255" frameAnnotationDistance="' + str(mapmargins[1] - 7.5) + '" annotationFormat="8" annotationExpression="' + labelexpression + '"'

  # FIXME EITHER make this an outer grid on the color layer instead, OR gotta change the printareasize so that the yellow margin is the same in all direction (at least in terms of effective printing, but then might have to specify different x and y bleeds to put the cropmarks in the right places...)
  newlabeloptions = 'gridStyle="3" showAnnotation="1" frameAnnotationDistance="' + str(mapmargins[1] - labelbgsize - 1) + '" annotationFormat="8" annotationExpression="' + labelexpression + '"' # -1 is a compromise between top/bottom (which would want -2) and left/right (which would want 0)

  yellowborderoptions = 'blendMode="16"'
  # pre-colortest was: 255,255,195
  # after first colortest was 250,250,175
  # after big yellow sheet: 255,251,143
  yellowborderspec = '''
        <lineStyle>
          <symbol name="" force_rhr="0" clip_to_extent="1" alpha="1" type="line">
            <layer locked="0" class="SimpleLine" pass="0" enabled="1">
              <prop v="250,250,175,255" k="line_color"/>
              <prop v="solid" k="line_style"/>
              <prop v="''' + str(yellowborderwidth) + '''" k="line_width"/>
              <prop v="MM" k="line_width_unit"/>
            </layer>
          </symbol>
        </lineStyle>'''

  def getmap(inner, theme, zindex = 0, grids = False):
#    name = layoutname + ' ' + ('inner map' if inner else 'labels' if labels else 'outer map')
    name = layoutname + ' ' + theme
    size = innermapsizespec if inner else outermapsizespec
    offset = innermapoffsetspec if inner else outermapoffsetspec

    gridspec = ''
    if not inner:
      if grids and not args.no_grid:
        gridspec = getgrid(layoutname + ' blue grid main', [2*args.box, 2*args.box], mapmargins, '', getbluegridspec(True))
        gridspec += getgrid(layoutname + ' blue grid secondary', [2*args.box, 2*args.box], [m + args.box for m in mapmargins], '', getbluegridspec(False))
        labeloffset = [m + args.box / 2 for m in mapmargins]
#        gridspec += getgrid(layoutname + ' label backgrounds', [args.box, args.box], labeloffset, labelbgoptions, labelbgspec, True)
#        gridspec += getgrid(layoutname + ' labels backgrounds LR', [args.box, args.box], labeloffset, lrlabelbgoptions, labelbgspec, True, ['top', 'bottom'])
#        gridspec += getgrid(layoutname + ' labels backgrounds TB', [args.box, args.box], labeloffset, tblabelbgoptions, labelbgspec, True, ['left', 'right'])
#        gridspec += getgrid(layoutname + ' labels LR', [args.box, args.box], labeloffset, lrlabeloptions, labelspec, True, ['top', 'bottom'])
#        gridspec += getgrid(layoutname + ' labels TB', [args.box, args.box], labeloffset, tblabeloptions, labelspec, True, ['left', 'right'])
        gridspec += getlabelgrid(layoutname + ' labels', [args.box, args.box], labeloffset, newlabeloptions)
      elif not grids and not args.no_border:
        gridspec += getgrid(layoutname + ' yellow border', yellowframeinterval, yellowborderoffset, yellowborderoptions, yellowborderspec)

    # use scale and crs to calculate extent
    extent = list(map(lambda center, size: [str(center - size / 2), str(center + size / 2)], crscenter, scaledinnermapsize if inner else scaledtotalmapsize))

    # mapflags: allow cut off labels (1) for outer map ('labels'), but not inner (region/boundary labels)
    #  background="''' + str(False if labels else True) + '''"
    # to_proj4() gives a warning, but at least it works (unlike to_wkt() for SE Asia, BNG)
    proj4 = crs.to_proj4()

#    backgroundblue = 255 if inner else 170
#      <BackgroundColor red="255" green="255" blue="''' + str(backgroundblue) + '''" alpha="255" />
    customproperties = ''
    if config.has_option('map', 'baselinescale'):
      customproperties = '<LayoutObject><customproperties><property key="variableNames" value="baseline_scale"/><property key="variableValues" value="' + str(round(config.getfloat('map', 'baselinescale'))) + '"/></customproperties></LayoutObject>'
    elif config.has_option('map', 'magnification'):
      customproperties = '<LayoutObject><customproperties><property key="variableNames" value="baseline_scale"/><property key="variableValues" value="' + str(round(20000 / config.getfloat('map', 'magnification'))) + '"/></customproperties></LayoutObject>'
    # blendmode was str(5 if inner else 0)
    return ('''<LayoutItem size="''' + size + ''',mm" mapFlags="''' + str(0 if inner else 1) + '''" blendMode="''' + str(6 if theme == 'mono' else 0) + '''" followPreset="true" position="''' + offset + ''',mm" zValue="''' + str(zindex) + '''" positionOnPage="''' + offset + ''',mm" outlineWidthM="13,mm" type="65639" followPresetName="''' + theme + '''" visibility="1" id="''' + name + '''" mapRotation="''' + str(rotation) + '''" positionLock="true">''' +
      customproperties +
      '''<Extent xmin="''' + extent[0][0] + '''" xmax="''' + extent[0][1] + '''" ymin="''' + extent[1][0] + '''" ymax="''' + extent[1][1] + '''"/>
      <crs>
        <spatialrefsys>
          <proj4>''' + proj4 + '''</proj4>
        </spatialrefsys>
      </crs>
      ''' + gridspec + '''
      <AtlasMap margin="0" scalingMode="0" atlasDriven="1"/>
    </LayoutItem>''')
#      <labelBlockingItems/>

  extent = list(map(lambda center, size: [str(center - size / 2), str(center + size / 2)], crscenter, scaledtotalmapsize))
  mn = towgs.transform(extent[0][0], extent[1][0])
  mx = towgs.transform(extent[0][1], extent[1][1])
  return (getmap(False, 'blank', 2, True) + getmap(True, 'coloring', 0) + getmap(False, 'mono', 1), '  <bookmark><id>' + getid() + '</id><name>' + layoutname + '</name><project></project><xmin>' + str(mn[0]) + '</xmin><xmax>' + str(mx[0]) + '</xmax><ymin>' + str(mn[1]) + '</ymin><ymax>' + str(mx[1]) + '</ymax><sr_id>3452</sr_id></bookmark>\n')


#    <!-- cover rectangle -->
#    <LayoutItem zValue="1" type="65643" shapeType="1" positionOnPage="''' + innermapoffsetspec + ''',mm" position="''' + innermapoffsetspec + ''',mm" size="''' + innermapsizespec + ''',mm" id="''' + getid() + '''">
#      <symbol alpha="1" type="fill" clip_to_extent="1">
#        <layer class="SimpleFill" enabled="1">
#          <prop k="color" v="255,255,255,255"/>
#          <prop k="outline_style" v="no"/>
#          <prop k="style" v="solid"/>
#        </layer>
#      </symbol>
#    </LayoutItem>
#    ''' 

layoutname = os.path.basename(args.atlas[0]).split('.')[0]

# <Layout> with <PageCollection></PageCollection> but NO closing tag! (need to append some <LayoutItem>s and optional <customproperties> first)
def getlayoutintro(name, npages = 1):
  return '<Layout name="' + name + '" printResolution="' + str(args.dpi) + '" units="mm"><PageCollection>' + ''.join(['<LayoutItem size="' + papersizespec + ',mm" position="0,' + str(i * (args.papersize[1] + 10)) + ',mm" type="65638"></LayoutItem>' for i in range(npages) ]) + '</PageCollection>'

# unitType one of 'km', 'mi'
# referencePoint is the LEFT end!
def getscaleline(mapUuid, position, blueonwhite = True, km = True):
  return f'''<LayoutItem background="false" boxContentSpace="3" frame="false" height="{1.5 if blueonwhite else .7}" labelBarSpace="1" labelHorizontalPlacement="0" labelVerticalPlacement="{1 if km else 0}" mapUuid="{mapUuid}" numMapUnitsPerScaleBarUnit="1" numSegments="{7 if km else 5}" numSegmentsLeft="0" numSubdivisions="1" numUnitsPerSegment="1" outlineWidth="0.33" outlineWidthM="1.33,pt" position="{position},mm" positionLock="false" referencePoint="3" segmentSizeMode="0" size="40,10,mm" style="Line Ticks {'Down' if km else 'Up'}" type="65646" unitLabel="{'Kilometres' if km else 'Miles'}" unitType="{'km' if km else 'mi'}" visibility="1" zValue="20">
        <FrameColor alpha="0" blue="0" green="0" red="0" /><!-- default to black for intro page, set to blue by below -->
        <BackgroundColor alpha="255" blue="255" green="255" red="255" />
        <LayoutObject>{dataDefinedBlue('dataDefinedFrameColor' if blueonwhite else 'dataDefinedBackgroundColor')}</LayoutObject>
        <text-style fontFamily="HelveticaNeue Condensed" fontSize="6" fontSizeUnit="Point" fontWeight="50" namedStyle="Condensed Regular" textColor="255,255,255,255">
          <dd_properties>
            <Option type="Map">
              <Option type="QString" name="name" value=""/>
              <Option type="Map" name="properties">''' + ('''<Option type="Map" name="Color">
                  <Option type="bool" name="active" value="true"/>
                  <Option type="QString" name="expression" value="project_color('blue')"/>
                  <Option type="int" name="type" value="3"/>
                </Option>''' if blueonwhite else '') + f'''</Option>
              <Option type="QString" name="type" value="collection"/>
            </Option>
          </dd_properties>
        </text-style>
        <lineSymbol>
          <symbol alpha="1" force_rhr="0" type="line" name="" clip_to_extent="1">
            <layer enabled="1" locked="0" pass="0" class="SimpleLine">
              <prop k="line_color" v="255,255,255,255" />
              <prop k="line_style" v="{'no' if (blueonwhite and km) else 'solid'}"/>
              <prop k="line_width" v="{0.25 if blueonwhite else 1.5}"/>
              <prop k="line_width_unit" v="Point"/>
              {dataDefinedBlue('outlineColor') if blueonwhite else ''}
            </layer>
          </symbol>
        </lineSymbol>
        <divisionLineSymbol>
          <symbol alpha="1" force_rhr="0" type="line" name="" clip_to_extent="1">
            <layer enabled="1" locked="0" pass="0" class="SimpleLine">
              <prop k="line_color" v="255,255,255,255" />
              <prop k="line_width" v="0.25"/>
              <prop k="line_width_unit" v="Point"/>
              {dataDefinedBlue('outlineColor') if blueonwhite else ''}
            </layer>
          </symbol>
        </divisionLineSymbol>
      </LayoutItem>'''

output = getlayoutintro(layoutname)

# output = '''<Layout name="''' + layoutname + '''" printResolution="''' + str(args.dpi) + '''" units="mm">
#     <Grid resUnits="mm" offsetY="0" offsetUnits="mm" offsetX="0" resolution="10"/>
#     <PageCollection>'''

# for i in range(npages):
#   output += '''      <LayoutItem size="''' + papersizespec + ''',mm" position="0,''' + str(i * (args.papersize[1] + 10)) + ''',mm" zValue="0" positionOnPage="0,0,mm" blendMode="0" outlineWidthM="0.3,mm" type="65638" visibility="1" id="" background="true">
#         <FrameColor green="0" blue="0" alpha="255" red="0"/>
#         <BackgroundColor green="255" blue="255" alpha="255" red="255"/>
#       </LayoutItem>'''
# output += '</PageCollection>'

bookmarks = ''
for i in range(len(args.atlas)):
  if npages == 1:
    # for multiple maps per page
    offsets = [i % mapsperaxis[0], i // mapsperaxis[0]]
    outermapoffset = list(map(lambda m, o, s: m + o * s, outermargins, offsets, outermapsize))
  else:
    outermapoffset = (outermargins[0], i * (args.papersize[1] + 10) + outermargins[1])

  layoutname = os.path.basename(args.atlas[i]).split('.')[0]
  config.read(args.atlas[i])
  (maps, bookmark) = getmaplayout(layoutname, config, outermapoffset)
  bookmarks += bookmark
  output += maps

if atlasbooklet:
  pageendtofirstgrid = list(map(lambda om, im: om + im, outermargins, mapmargins))
  # horizontaloffset is pageendtofirstgrid[0] for left, args.papersize[0] - pageendtofirstgrid[0] for right
  verticaloffset = str(pageendtofirstgrid[1] - 2) # mm higher
  # referencePoint="8" for bottom right, referencePoint="6" for bottom left

  def opacity(condition):
    return '' if condition == None else '<Option name="dataDefinedOpacity" type="Map"><Option name="active" value="true" type="bool"/><Option name="expression" value="' + condition + '" type="QString"/><Option name="type" value="3" type="int"/></Option>'

  def labelfontspec(fontsize, numbers = True):
    if numbers: # Avenir Next Condensed Medium looks a lot like Helvetica neue Condensed Bold, but is even taller, but the 6s and 9s aren't curved
#      return '<LabelFont style="Medium" description="Avenir Next Condensed,' + str(fontsize) + ',-1,5,57,0,0,0,0,0,Medium"/><FontColor blue="255" green="255" red="255" alpha="255"/>'
      if fontsize >= 28:
        # big fat title
        return f'<LabelFont description="Helvetica Neue,{fontsize},-1,5,75,0,0,0,0,0,Bold" style="Bold"/><FontColor blue="255" green="255" red="255" alpha="255"/>'
      elif fontsize >= 18:
        # these are the page labels
#        return '<LabelFont style="Bold" description="DIN Alternate,' + str(fontsize) + ',-1,5,75,0,0,0,0,0,Bold"/><FontColor blue="255" green="255" red="255" alpha="255"/>'
        # style: Regular or DINCondensed-Bold
        return f'<LabelFont style="DINCondensed-Bold" description="D-DIN Condensed,{fontsize},-1,5,50,0,0,0,0,0,DINCondensed-Bold"/><FontColor blue="255" green="255" red="255" alpha="255"/>'
      elif fontsize >= 11: # 'CONTENT', 'REFERENCE' etc -- Medium a bit too small, try Bold
        return f'<LabelFont description="Helvetica Neue,{fontsize},-1,5,57,0,0,0,0,0,Bold" style="Bold"/><FontColor blue="255" green="255" red="255" alpha="255"/>'
      else:
        # small page index labels look good with Condensed Bold (8pt)
        return f'<LabelFont style="Condensed Bold" description="Helvetica Neue,{fontsize},-1,5,75,0,0,0,0,0,Condensed Bold"/><FontColor blue="255" green="255" red="255" alpha="255"/>'
#        return '<LabelFont style="Condensed Regular" description="HelveticaNeue Condensed,' + str(fontsize) + ',-1,5,50,0,0,0,0,0,Condensed Regular"/><FontColor blue="255" green="255" red="255" alpha="255"/>'
    # for general text: Helvetica-ish font
    else:
      return f'<LabelFont description="Helvetica,{fontsize},-1,5,75,0,0,0,0,0,Condensed Black" style="Condensed Black"/>'

  def bluetextbox(id, size, position, labelText, fontsize = 14, opacityCondition = None, rotation = 0, referencePoint = 4, blueonwhite = False, frame = False, attributes = 'valign="128" marginX="0" marginY="0"'):
    # if blueonwhite is true, set an outlinewidth and enable HTML to set the correct font color
    if blueonwhite:
      labelText = f"&lt;span style=&quot;display:block;margin-top:0.4em;color:rgb([%project_color('blue')%]);&quot;&gt;{labelText}&lt;/span&gt;"
    # TODO set frame=true, outlineWidthM="1.33,pt"?
    # attributes = ' marginX="0" marginY="0" valign="128"'
    return f'<LayoutItem id="{id}" referencePoint="{referencePoint}" position="{position},mm" size="{size},mm" labelText="{labelText}" frame="' + ('true' if (frame or blueonwhite) else 'false') + '" outlineWidthM="1.33,pt" htmlState="' + str(1 if blueonwhite else 0) + '" itemRotation="' + str(rotation) + '" background="true" type="65641" zValue="5" uuid="{' + getid() + '}" positionLock="true" halign="4" ' + attributes + '><FrameColor alpha="255" blue="0" red="0" green="0"/>' + labelfontspec(fontsize, not blueonwhite) + '<LayoutObject>' + (dataDefinedBlues(['dataDefinedFontColor', 'dataDefinedFrameColor']) if blueonwhite else dataDefinedBlue('dataDefinedBackgroundColor', opacity(opacityCondition))) + '</LayoutObject></LayoutItem>'
# <BackgroundColor blue="255" green="255" red="255" alpha="255"/>

  output += bluetextbox('leftpagelabel', '9.5,7', str(pageendtofirstgrid[0]) + ',' + verticaloffset, "[%attribute(@atlas_feature, 'leftpage')%]", 20, referencePoint=8)
  output += bluetextbox('rightpagelabel', '9.5,7', str(args.papersize[0] - pageendtofirstgrid[0]) + ',' + verticaloffset, "[%attribute(@atlas_feature, 'rightpage')%]", 20, referencePoint=6)

  linkboxwidthheight = [6.5, 3.3]
  linkboxspec = ','.join(map(str, linkboxwidthheight))

  def linkbox(atlasFeatureAttribute, textFunction, position, rotation = 0):
    condition = "if(attribute(@atlas_feature, '" + atlasFeatureAttribute + "') != 0, 100, 0)"
    return bluetextbox(atlasFeatureAttribute + 'link' + textFunction, linkboxspec, position, "[%attribute(@atlas_feature, '" + atlasFeatureAttribute + "')" + textFunction + "%]", 8, condition, rotation, 4) + '''      <LayoutItem position="''' + position + ''',mm" blendMode="0" opacity="1" shapeType="2" referencePoint="4" itemRotation="''' + str(180 if atlasFeatureAttribute == 'bottom' else rotation) + '''" zValue="12" visibility="1" uuid="{''' + getid() + '''}" size="''' + str(linkboxwidthheight[0]) + ''',2.5,mm" frameJoinStyle="miter" id="''' + atlasFeatureAttribute + 'link' + textFunction + '''triangle" cornerRadiusMeasure="0,mm" frame="false" type="65643" background="false" positionLock="true">
        <symbol clip_to_extent="1" force_rhr="0" type="fill" alpha="1">
          <layer enabled="1" class="SimpleFill" locked="0" pass="0">
            <prop k="border_width_map_unit_scale" v="3x:0,0,0,0,0,0"/>
            <prop k="color" v="0,0,255,255"/>
            <prop k="joinstyle" v="bevel"/>
            <prop k="offset" v="0,''' + str(-(linkboxwidthheight[1] + 1)) + '''"/><!-- 180 degree rotation is relative to center? so needs to be -4 - 2.5 for the height? -->
            <prop k="offset_map_unit_scale" v="3x:0,0,0,0,0,0"/>
            <prop k="offset_unit" v="MM"/>
            <prop k="outline_color" v="0,0,0,0"/>
            <prop k="outline_style" v="solid"/>
            <prop k="outline_width" v="0.26"/>
            <prop k="outline_width_unit" v="MM"/>
            <prop k="style" v="solid"/>
            <prop k="style" v="solid"/>''' + dataDefinedBlue('fillColor', '''<Option name="fillStyle" type="Map"><Option name="active" value="true" type="bool"/><Option name="expression" value="if(attribute(@atlas_feature, \'''' + atlasFeatureAttribute + '''') != 0, 'solid', 'no')" type="QString"/><Option name="type" value="3" type="int"/></Option>''') + '''
          </layer>
        </symbol>
      </LayoutItem>'''

  linkboxmargin = 2.5
  linkboxdistance = linkboxwidthheight[1]/2 + linkboxmargin
  output += linkbox('top', '', ','.join([str(outermargins[0] + mapmargins[0] + innermapsize[0] / 4), str(outermargins[1] + mapmargins[1] - linkboxdistance)]))
  output += linkbox('top', '+1', ','.join([str(outermargins[0] + mapmargins[0] + 3*innermapsize[0] / 4), str(outermargins[1] + mapmargins[1] - linkboxdistance)]))

  output += linkbox('left', '', ','.join([str(outermargins[0] + mapmargins[0] - linkboxdistance), str(args.papersize[1] / 2)]), -90)
  output += linkbox('right', '', ','.join([str(args.papersize[0] - (outermargins[0] + mapmargins[0] - linkboxdistance)), str(args.papersize[1] / 2)]), 90)

  output += linkbox('bottom', '', ','.join([str(outermargins[0] + mapmargins[0] + innermapsize[0] / 4), str(outermargins[1] + mapmargins[1] + innermapsize[1] + linkboxdistance)]))
  output += linkbox('bottom', '+1', ','.join([str(outermargins[0] + mapmargins[0] + 3*innermapsize[0] / 4), str(outermargins[1] + mapmargins[1] + innermapsize[1] + linkboxdistance)]))

    # <LayoutItem id="rightlink" itemRotation="90" uuid="{''' + getid() + '''}" type="65641" referencePoint="4 " halign="4" size="6.5,3,mm" zValue="9" visibility="1" position="''' + str(args.papersize[0] - (outermargins[0] + mapmargins[0]) + 2.5) + ''',''' + str(args.papersize[1] / 2) + ''',mm" background="true" valign="128" labelText="[%attribute(@atlas_feature, 'right')%]">
    #   <FrameColor blue="0" green="0" red="0" alpha="255"/>
    #   <BackgroundColor blue="255" green="51" red="51" alpha="255"/>
    #   <LayoutObject>
    #     <dataDefinedProperties>
    #       <Option type="Map">
    #         <Option name="name" value="" type="QString"/>
    #         <Option name="properties" type="Map">
    #           <Option name="dataDefinedOpacity" type="Map">
    #             <Option name="active" value="true" type="bool"/>
    #             <Option name="expression" value="if(attribute(@atlas_feature, 'right') != 0, 100, 0)" type="QString"/>
    #             <Option name="type" value="3" type="int"/>
    #           </Option>
    #         </Option>
    #       </Option>
    #     </dataDefinedProperties>
    #     <customproperties/>
    #   </LayoutObject>
    #   <LabelFont style="" description=".SF NS Text,12,-1,5,50,0,0,0,0,0"/>
    #   <FontColor blue="255" green="255" red="255" alpha="255"/>
    # </LayoutItem>

  if args.bleed != 0:
    print('adding cropmarks to indicate bleed portion of map margin')

    cropmarklength = args.bleed/2
    def cropmark(position, rotation):
      # move cropmark just outside the bleed, with a mark length of bleed as well
      return '''<LayoutItem outlineWidth="1" position="''' + ','.join(map(str, position)) + ''',mm" opacity="1" referencePoint="5" outlineWidthM="0.2,mm" itemRotation="''' + str(rotation) + '''" zValue="18" visibility="1" markerMode="0" uuid="{''' + getid() + '''}" size="''' + str(cropmarklength) + ''',''' + str(cropmarklength) + ''',mm" id="cropmark''' + getid() + '''" type="65645" positionLock="true" startMarkerMode="0">
        <LayoutObject>
          <dataDefinedProperties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </dataDefinedProperties>
          <customproperties/>
        </LayoutObject>
        <symbol type="line" alpha="1">
          <layer enabled="1" class="SimpleLine" locked="0" pass="0">
            <prop k="align_dash_pattern" v="0"/>
            <prop k="capstyle" v="square"/>
            <prop k="joinstyle" v="bevel"/>
            <prop k="line_color" v="0,0,0,255"/>
            <prop k="line_style" v="solid"/>
            <prop k="line_width" v="0.3"/>
            <prop k="line_width_unit" v="MM"/>
            <prop k="offset" v="''' + str(cropmarklength/2) + '''"/>
            <prop k="offset_unit" v="MM"/>
          </layer>
        </symbol>
        <nodes>
          <node x="''' + str(-args.bleed) + '''" y="''' + str(-args.bleed) + '''"/>
          <node x="''' + str(-args.bleed + cropmarklength) + '''" y="''' + str(-args.bleed) + '''"/>
        </nodes></LayoutItem>'''

    # top left (horizontal then vertical)
    cropmarkposition = list(map(lambda m: m + args.bleed, outermargins))
    output += cropmark(cropmarkposition, 0) + cropmark(cropmarkposition, 90)
    # top right
    topright = [cropmarkposition[0], args.papersize[1] - cropmarkposition[1]]
    output += cropmark(topright, 0) + cropmark(topright, -90)
    # bottom left
    cropmarkposition[0] = args.papersize[0] - cropmarkposition[0]
    output += cropmark(cropmarkposition, 180) + cropmark(cropmarkposition, 90)
    # bottom right
    cropmarkposition[1] = args.papersize[1] - cropmarkposition[1]
    output += cropmark(cropmarkposition, 180) + cropmark(cropmarkposition, -90)

  output += '''<customproperties>
      <!-- property key="atlasRasterFormat" value="jpg"/ -->
      <property key="forceVector" value="0"/>
      <property key="pdfDisableRasterTiles" value="0"/>
      <property key="pdfIncludeMetadata" value="0"/>
      <property key="pdfTextFormat" value="0"/>
      <property key="rasterize" value="true"/>
      <property key="singleFile" value="true"/>
    </customproperties>
    <Atlas enabled="1" coverageLayerProvider="ogr" coverageLayerSource="/Users/kevin/ZA/atlas.geojson|layername=atlas|geometrytype=Point|subset=&quot;type&quot; = 'atlaspage'" coverageLayer="atlaspage_features_55f7c9af_890c_43b3_bd7c_e250a3a7ec39" pageNameExpression="&quot;page&quot;" coverageLayerName="atlaspage features" hideCoverage="1" filenamePattern="'output_'||@atlas_featurenumber" />
  '''
output += '</Layout>'

from xml.etree.ElementTree import fromstring, parse, ParseError #, indent

# check for well-formedness
newlayout = fromstring(output)

if atlasbooklet:
  crs = getcrs(config)
  wgs = CRS.from_epsg(4326)
  fromwgs = Transformer.from_crs(wgs, crs, always_xy=True)

  # the center of the overview should be this much from the atlas center
  ys = [int(yspec) for yspec in config['pages']]
  xs = [item for yspec in config['pages'] for item in parselist(config.get('pages', yspec))]
  overviewcenteroffset = [(min(xs) + max(xs)) / 2, ((min(ys) + max(ys))) / -2] # shift direction of y axis around because of stupid atlas definition
  # kunming hack (shifts right)
  overviewcenteroffset[0] = overviewcenteroffset[0] - 1 # was .7, but for clean split needs a whole number

  center = config.getnumbers('map', 'center')
  crscenter = fromwgs.transform(center[0], center[1])
  # adjust crscenter by the appropriate meters (divide by thousand because mapsize is in)
  crscenter = list(map(lambda origcenter, oviewshift, mapsize: origcenter + oviewshift * mapsize * config.getfloat('map', 'scale') / 1000, crscenter, overviewcenteroffset, innermapsize))
  # calculate adjusted wgs center

  center = Transformer.from_crs(crs, wgs, always_xy=True).transform(crscenter[0], crscenter[1])

  # the overview map should end (6+args.bleed)/2 before the bleed border (because the rest will be filled up by the outline frame), so deduct that much from the outermapsize
  overviewmapsize = [d - (6+args.bleed) for d in outermapsize]

  # in Glasgow one overview box is 13mm high, on the print page the same area is 6*27.5=165cm, so overview scale is map scale * 12.7
  mapscale = config.getfloat('map', 'scale')
#  overviewscale = mapscale * 12.5
  overviewscale = 280000 # ugly kunming hack
  overviewscaledtotalmapsize = [d * overviewscale / 1000 for d in overviewmapsize]
  extent = list(map(lambda center, size: [str(center - size / 2), str(center + size / 2)], crscenter, overviewscaledtotalmapsize))

  # offset onto second page (y coordinate only)
  offset = sizespecstring([(args.papersize[0] - overviewmapsize[0]) / 2, args.papersize[1] + 10 + (args.papersize[1] - overviewmapsize[1]) / 2])

  # pass information about the height of one blue box (in meters/map units) to the layout so that the font size of the big (place) labels can be adjusted dynamically
  # CITY label is 4mm high, TOWN 2-2.8mm, suburbs(bold) 1.8-2mm, villages 1.2mm (like this: @atlaspageboxheight * 4 / 13)
  # kunming hack
  atlasboxheight = 3600
#  atlasboxheight = innermapsize[1] * mapscale / 1000

  overviewlayout = getlayoutintro(layoutname + ' overview', 2) + getmapxml(layoutname, offset, sizespecstring(overviewmapsize), extent, 'Overview', getcrs(config).to_proj4(), custompropertiesandgrids='<LayoutObject>' + dataDefinedBlue('dataDefinedFrameColor') + '<customproperties><property key="variableNames" value="atlaspageboxheight"/><property key="variableValues" value="' + str(atlasboxheight) + '"/></customproperties></LayoutObject>', atlas=False, customattributes='frame="true" outlineWidthM="' + str(6 + args.bleed) + ',mm"')

  # add A FULL PAGE+1cm (vertical) to all positions (for a4 landscape, 21cm high, the offset of the corner of the second page is 220mm)
  verticaloffset = str(args.papersize[1] + 10 + outermargins[1] + 20) # last element is half the outlinewidth + 4mm on each side or something like that

  # labels on first page
  overviewlayout += bluetextbox('title', sizespecstring([ outermapsize[0] / 2, 18 + args.bleed ]), sizespecstring([ args.papersize[0] / 2, outermargins[1] ]), f'Z-A {layoutname.upper()}', 28, referencePoint=0, attributes = ' valign="64" marginX="0" marginY="3"') # 3mm offset from bottom
  # mode="1" for raster
  overviewlayout += '<LayoutItem pictureHeight="127.5" svgBorderWidth="0" mapUuid="" mode="1" northOffset="0" type="65640" size="105.5,127.5,mm" uuid="{' + getid() + '}" position="' + sizespecstring([ args.papersize[0] / 2 + 10, outermargins[1] + args.bleed + 18 ]) + ',mm" northMode="0" background="false" referencePoint="0" file="./legend.png" pictureWidth="105.5" zValue="24" resizeMode="3" />'

  # top center as reference point for these two: HELVETICA NEUE MEDIUM 11
  overviewlayout += bluetextbox('contents', '37.5,4', sizespecstring([ args.papersize[0]/2 + (outermapsize[0] - 2*args.bleed)/4, outermargins[1] + args.bleed + 19.5 ]), 'CONTENTS', 11, referencePoint=1)
  overviewlayout += bluetextbox('reference', '37.5,4', sizespecstring([ args.papersize[0]/2 + (outermapsize[0] - 2*args.bleed)/4, outermargins[1] + args.bleed + 40.8 ]), 'REFERENCE', 11, referencePoint=1)

  # set frame True for a black frame, add 1mm extra on each side so it's definitely cut off (by pdf cutting) on the left
  overviewlayout += bluetextbox('firstpagescale', sizespecstring([ outermapsize[0] / 2 + 2, 19 ]), sizespecstring([ args.papersize[0] / 2 - 1, 155 ]), "SCALE", 13, referencePoint=0, attributes=' valign="32" marginX="0" marginY="1"', frame = True) # valign scale label at the top
  overviewlayout += getscaleline(layoutname, sizespecstring([ args.papersize[0]*3 / 4 - 10 , 165 ]), km=True, blueonwhite = False)

  # add/subtract 6 (bleed + half of outlinewidth) because of frame eaten up by outer blue frame
  overviewlayout += bluetextbox('leftpagelabel', '7,7', sizespecstring([4 + pageendtofirstgrid[0], verticaloffset]), "2", 20, referencePoint=8)
  overviewlayout += bluetextbox('rightpagelabel', '7,7', sizespecstring([args.papersize[0] - pageendtofirstgrid[0] - 4, verticaloffset]), "3", 20, referencePoint=6)

  overviewlayout += bluetextbox('key', '44,6', '78,241', 'KEY TO MAP PAGES', fontsize = 11, blueonwhite = True)
  overviewlayout += bluetextbox('scalebox', '44,17', '61,401', 'SCALE', fontsize = 8, blueonwhite = True)
  overviewlayout += getscaleline(layoutname, '38,400', km=False) # miles scaleline
  overviewlayout += getscaleline(layoutname, '38,404.7', km=True) # km scaleline

  cropmarkpositiononsinglepage = [m + args.bleed for m in outermargins]
  for page in range(2):
    cropmarkposition = [cropmarkpositiononsinglepage[0], cropmarkpositiononsinglepage[1] + page * (args.papersize[1] + 10)]
    # top left
    overviewlayout += cropmark(cropmarkposition, 0) + cropmark(cropmarkposition, 90)
    # top right
    cropmarkposition[0] = args.papersize[0] - cropmarkposition[0]
    overviewlayout += cropmark(cropmarkposition, 180) + cropmark(cropmarkposition, 90)
    # bottom left
    cropmarkposition = [cropmarkpositiononsinglepage[0], cropmarkposition[1] + args.papersize[1] - 2*cropmarkpositiononsinglepage[1]]
    overviewlayout += cropmark(cropmarkposition, 0) + cropmark(cropmarkposition, -90)
    # bottom right
    cropmarkposition[0] = args.papersize[0] - cropmarkposition[0]
    overviewlayout += cropmark(cropmarkposition, 180) + cropmark(cropmarkposition, -90)

  # force raster export by default to avoid this discoloration bug: https://issues.qgis.org/issues/4641
  overviewlayout += '<customproperties><property value="true" key="rasterize"/></customproperties>'

  overviewlayout += '</Layout>'
  newoverview = fromstring(overviewlayout)

if args.write:

  projectdoc = parse('ZA2.qgs')
  layouts = projectdoc.find("./Layouts")
  def addlayout(newlayout):
    print('adding layout "' + newlayout.get('name') + '" to ZA2.qgs')
    existing = layouts.find("./Layout[@name='" + newlayout.get('name') + "']")
    if existing:
      layouts.remove(existing)
    layouts.append(newlayout)

  addlayout(newlayout)

  if atlasbooklet:
    # TODO find all LayoutItem/mapUuid attributes and set them to the uuid of the overview map item
    addlayout(newoverview)

#  indent(projectdoc)
  projectdoc.write('ZA2.qgs')

  if args.index:
    print("TODO connect go PostGIS and collate road/place index list...")
    # for every road name, find left-most starting point of all such-named segments? (alternatively: the CENTER of all? (i.e. take extent box first))

else:
  print(output)

if not atlasbooklet:
  print("multi-map layout, skipping creation of atlas.geojson file. Here's QGIS bookmarks for the atlas's center pages instead:")
  print(bookmarks)
