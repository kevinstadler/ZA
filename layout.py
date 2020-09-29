#!/usr/local/bin/python3

# ./layout.py -papersize 420 297 -box 27.5 -outermargin 15 data/{Moulsford,Kunming4sites,Oxford,Nunhead}.atlas
# ./layout.py -printareasize 247.5 197 data/{Glasgow18103,Glasgow9051,Moulsford,Kunming4sites,Oxford,Nunhead,Edinburgh}.atlas

import argparse
import configparser
import ast
import time
import os
from random import random

from math import ceil, sqrt
from pyproj import CRS, Transformer
from geojson import Point, Polygon, Feature, FeatureCollection, dump

# was: 0 86, 208
blue = [51, 51, 255]
bluestring = ','.join(map(str, blue))

parser = argparse.ArgumentParser(description='Build a geojson feature file to be used as the basis of a QGIS atlas.')
parser.add_argument('atlas', nargs='*', default='data/Kunming.atlas', help='atlas specification file')
parser.add_argument('--startpage', type=int, default=4, help='first page for page numbering')
parser.add_argument('-o', default='atlas.geojson', help='output filename')

parser.add_argument('-box', type=float, default=27.5, help='in mm')
parser.add_argument('--no-border', default=False, action='store_true', help='omit yellow border outside box (overridden by atlas config "border: true/false")')
parser.add_argument('--no-grid', default=False, action='store_true', help='omit blue grid around boxes (overridden by atlas config "grid: true/false")')
#parser.add_argument('-y', type=float, default=0, help='global y offset (for spreading pages)')
parser.add_argument('-papersize', type=float, nargs=2, default=(297, 210), metavar=('width', 'height'), help='in mm (overridden by atlas config "papersize:")')
parser.add_argument('-printareasize', type=float, nargs=2, default=(247.5, 191), metavar=('width', 'height'), help='in mm (overridden by atlas config "printsize:")')
parser.add_argument('-dpi', type=int, default=300, help='layout export resolution (overridden by atlas config "dpi:")')
parser.add_argument('-bleed', type=float, default=0, help='in mm') # TODO make 10 instead, add to printareasize
parser.add_argument('-outermargin', type=float, default=None, help='instead of specifying the printarea, give some margin (in mm)')
args = parser.parse_args()

nmaps = len(args.atlas)
atlasbooklet = nmaps == 1

# FIXME might have to NOT reuse this one?
config = configparser.ConfigParser(converters={'numbers': lambda value: [float(num) for num in value.strip('[]').split(',')] })
print(args)

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
  args.printareasize = list(map(lambda l: l - 2 * args.outermargin, args.papersize))

desiredmapsize = list(map(lambda s, n: s / n, args.printareasize, mapsperaxis))

# allocate at least 8mm of (yellow) margin plus bleed on all sides
nboxes = list(map(lambda d: ( d - 16 - args.bleed) // args.box, desiredmapsize))

innermapsize = list(map(lambda n: n * args.box, nboxes))
visiblemargins = list(map(lambda d, i: (d - i) / 2, desiredmapsize, innermapsize))

outermapsize = list(map(lambda d: d + 2 * args.bleed, desiredmapsize))

mapmargins = list(map(lambda d, i: (d - i) / 2, outermapsize, innermapsize))

outermapsizespec = ','.join(map(str, outermapsize))
papersizespec = ','.join(map(str, args.papersize))

### OUTER MAP
# the outer map goes from 0,0 to totalsize
## FRAMES, GRIDS, LABELS
# yellow frame offset can't be negative, so needs to be zero on the *smaller* margin
yellowborderwidth = 2 * min(visiblemargins)
# the center of the frame stroke is 0 on the smaller margin, margin - yellowborderwidth/2 on the larger one
yellowborderoffset = list(map(lambda m: m - yellowborderwidth / 2, visiblemargins))
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

def getmaplayout(layoutname, config, outermapoffset):

  crs = CRS.from_user_input(config['map']['proj'])
  wgs = CRS.from_epsg(4326)

  # always use longlat
  fromwgs = Transformer.from_crs(wgs, crs, always_xy=True)
  towgs = Transformer.from_crs(crs, wgs, always_xy=True)

  center = config.getnumbers('map', 'center')
  crscenter = fromwgs.transform(center[0], center[1])

  scale = config.getfloat('map', 'scale')
  # TODO merge both argument specs by calling defaultsdict.update(overridedict)?

  scaledinnermapsize = list(map(lambda d: d * scale / 1000, innermapsize))
  scaledtotalmapsize = list(map(lambda d: d * scale / 1000, outermapsize))

  # TODO add overbleed and offset from spacing maps
  outermapoffsetspec = ','.join(map(str, outermapoffset))

  innermapoffset = map(lambda a, b: a + b, mapmargins, outermapoffset)
  innermapoffsetspec = ','.join(map(str, innermapoffset))

  totalmarginspec = ','.join(map(str, mapmargins))
  innermapsizespec = ','.join(map(str, innermapsize))

  if atlasbooklet and config.has_section('pages'):
    def addpage(featurelist, towgs, crscenter, x, y, xoffset, yoffset, pagenum):
      pagecenter = [ crscenter[0] + x * xoffset, crscenter[1] + y * yoffset ]
      featurelist.append(Feature(geometry=Point(towgs.transform(pagecenter[0], pagecenter[1])), properties={"type": "atlaspage", "page": page}))

    #  xs = list(map(lambda center, mapsize: [ center + mapsize / 2, center - mapsize / 2 ], pagecenter, offsets))

      polygon = Polygon([[
        towgs.transform(pagecenter[0] + xoffset / 2, pagecenter[1] + yoffset / 2),
        towgs.transform(pagecenter[0] + xoffset / 2, pagecenter[1] - yoffset / 2),
        towgs.transform(pagecenter[0] - xoffset / 2, pagecenter[1] - yoffset / 2),
        towgs.transform(pagecenter[0] - xoffset / 2, pagecenter[1] + yoffset / 2),
        towgs.transform(pagecenter[0] + xoffset / 2, pagecenter[1] + yoffset / 2)
        ]])
      featurelist.append(Feature(geometry=polygon, properties={"type": "atlaspage", "page": page}))
      # TODO add page 'link' features?
      # *printpage*
      featurelist.append(Feature(geometry=Point(towgs.transform(pagecenter[0] - xoffset / 4, pagecenter[1])), properties={"type": "printpage", "page": pagenum}))
      featurelist.append(Feature(geometry=Point(towgs.transform(pagecenter[0] + xoffset / 4, pagecenter[1])), properties={"type": "printpage", "page": pagenum + 1}))
      return pagenum + 2


    print("Creating atlas index with " + str(scaledinnermapsize[0]) + "x" + str(scaledinnermapsize[1]) + " meters per page")

    pagefeatures = []

    page = args.startpage
    for yspec in config['pages']:
      y = int(yspec)
      # FIXME ignore whitespace everywhere?
      for xspec in config['pages'][yspec].split(', '):
        split = xspec.find('-', 1)
        if split > 0:
          # loop through spec
          for x in range(int(xspec[:split]), int(xspec[split+1:]) + 1):
            page = addpage(pagefeatures, towgs, crscenter, x, y, scaledinnermapsize[0], scaledinnermapsize[1], page)
        else:
          page = addpage(pagefeatures, towgs, crscenter, int(xspec), y, scaledinnermapsize[0], scaledinnermapsize[1], page)

    feature_collection = FeatureCollection(pagefeatures)

    with open(args.o, 'w') as f:
       dump(feature_collection, f)
       print('Atlas features written to ' + args.o)

  def getid():
    return str(round(1000000 * random()))

  # needs arrays!
  def getgrid(name, intervals, offsets, options, markerspec, inner = False, disabledSides = []):
    # annotationPosition 0 = inner, 1 = outer // annotationDisplay 0 = all 3 = disabled
    disabledAnnotations = ' '.join(map(lambda side: side + 'AnnotationDisplay="3"', disabledSides))
    return '<ComposerMapGrid uuid="{' + getid() + '}" show="1" unit="1" name="' + name + '" ' + disabledAnnotations + ' bottomAnnotationPosition="' + str(0 if inner else 1) + '" leftAnnotationPosition="' + str(0 if inner else 1) + '" topAnnotationPosition="' + str(0 if inner else 1) + '" rightAnnotationPosition="' + str(0 if inner else 1) + '" intervalY="' + str(intervals[1]) + '" gridFrameWidth="2" offsetX="' + str(offsets[0]) + '" intervalX="' + str(intervals[0]) + '" offsetY="' + str(offsets[1]) + '" ' + options + '>' + markerspec + '</ComposerMapGrid>'

  bluegridoptions = 'uuid="{' + getid() + '}"'
  bluegridspec = '''
      <lineStyle>
        <symbol name="" force_rhr="0" clip_to_extent="1" alpha="1" type="line">
          <layer locked="0" class="SimpleLine" pass="0" enabled="1">
            <prop v="''' + bluestring + ''',255" k="line_color"/>
            <prop v="solid" k="line_style"/>
            <prop v="0.15" k="line_width"/><!-- TODO find right line width: 3 too wide, 1 too narrow -->
            <prop v="MM" k="line_width_unit"/>
          </layer>
        </symbol>
      </lineStyle>'''

  # was: 2.7 outside for bg, 5.5 outside for label (label should be 2.4-2.6ish more)
  labelbgexpression = "if(@grid_number &gt; " + str(mapmargins[0]) + " AND @grid_number &lt; if(@grid_axis = 'x', " + ','.join(map(lambda n, m: str(args.box * n + m), nboxes, mapmargins)) + "),  'l', '')"
  lrlabelbgoptions = 'uuid="{' + getid() + '}" gridStyle="3" showAnnotation="1" annotationFontColor="' + bluestring + ',255" frameAnnotationDistance="' + str(mapmargins[0] - 10) + '" annotationFormat="8" annotationExpression="' + labelbgexpression + '"'
  tblabelbgoptions = 'uuid="{' + getid() + '}" gridStyle="3" showAnnotation="1" annotationFontColor="' + bluestring + ',255" frameAnnotationDistance="' + str(mapmargins[1] - 10) + '" annotationFormat="8" annotationExpression="' + labelbgexpression + '"'
  labelbgspec = '<annotationFontProperties description="Wingdings,30,-1,5,50,0,0,0,0,0,Regular" style="Regular"/>'

  labelindices = list(map(lambda m: 'round((@grid_number - ' + str(m) + ') / ' + str(args.box) + ')', mapmargins))
  labelexpression = "if(@grid_number &lt; " + str(mapmargins[0]) + ", '', if(@grid_axis = 'x', if(@grid_number &lt; " + str(args.box * nboxes[0] + mapmargins[0]) + ", char(64 + " + labelindices[0] + "), ''), if(@grid_number &lt; " + str(args.box * nboxes[1] + mapmargins[1]) + ", " + str(nboxes[1] + 1) + " - " + labelindices[1] + ", '')))"
  lrlabeloptions = 'uuid="{' + getid() + '}" gridStyle="3" showAnnotation="1" annotationFontColor="255,255,255,255" frameAnnotationDistance="' + str(mapmargins[0] - 7.3) + '" annotationFormat="8" annotationExpression="' + labelexpression + '"'
  tblabeloptions = 'uuid="{' + getid() + '}" gridStyle="3" showAnnotation="1" annotationFontColor="255,255,255,255" frameAnnotationDistance="' + str(mapmargins[1] - 7.5) + '" annotationFormat="8" annotationExpression="' + labelexpression + '"'
  labelspec = '<annotationFontProperties description="Al Bayan,10,-1,5,75,0,0,0,0,0,Bold" style="Bold"/>'

  yellowborderoptions = 'uuid="{' + getid() + '}" blendMode="16"'
  yellowborderspec = '''
        <lineStyle>
          <symbol name="" force_rhr="0" clip_to_extent="1" alpha="1" type="line">
            <layer locked="0" class="SimpleLine" pass="0" enabled="1">
              <prop v="255,255,195,255" k="line_color"/>
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
        gridspec = getgrid(layoutname + ' blue grid', [args.box, args.box], [0, 0] if inner else mapmargins, bluegridoptions, bluegridspec)
        labeloffset = list(map(lambda m: m + args.box / 2, mapmargins))
#        gridspec += getgrid(layoutname + ' label backgrounds', [args.box, args.box], labeloffset, labelbgoptions, labelbgspec, True)
        gridspec += getgrid(layoutname + ' labels backgrounds LR', [args.box, args.box], labeloffset, lrlabelbgoptions, labelbgspec, True, ['top', 'bottom'])
        gridspec += getgrid(layoutname + ' labels backgrounds TB', [args.box, args.box], labeloffset, tblabelbgoptions, labelbgspec, True, ['left', 'right'])
        gridspec += getgrid(layoutname + ' labels LR', [args.box, args.box], labeloffset, lrlabeloptions, labelspec, True, ['top', 'bottom'])
        gridspec += getgrid(layoutname + ' labels TB', [args.box, args.box], labeloffset, tblabeloptions, labelspec, True, ['left', 'right'])
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
    if 'magnification' in config['map']:
      customproperties = '<LayoutObject><customproperties><property key="variableNames" value="baseline_scale"/><property key="variableValues" value="' + str(round(20000 / config['map'].getfloat('magnification'))) + '"/></customproperties></LayoutObject>'

    return ('''<LayoutItem size="''' + size + ''',mm" mapFlags="''' + str(0 if inner else 1) + '''" blendMode="''' + str(5 if inner else 0) + '''" followPreset="true" position="''' + offset + ''',mm" zValue="''' + str(zindex) + '''" positionOnPage="''' + offset + ''',mm" outlineWidthM="13,mm" type="65639" followPresetName="''' + theme + '''" visibility="1" id="''' + name + '''">''' +
      customproperties +
      '''<Extent xmin="''' + extent[0][0] + '''" xmax="''' + extent[0][1] + '''" ymin="''' + extent[1][0] + '''" ymax="''' + extent[1][1] + '''"/>
      <crs>
        <spatialrefsys>
          <proj4>''' + proj4 + '''</proj4>
        </spatialrefsys>
      </crs>
      ''' + gridspec + '''
      <AtlasMap margin="0" scalingMode="0" atlasDriven="1"/>
      <labelBlockingItems/>
    </LayoutItem>''')

  print(getmap(False, 'blank', 2, True))
  print(getmap(True, 'coloring', 1))
  print(getmap(False, 'mono', 0))

  extent = list(map(lambda center, size: [str(center - size / 2), str(center + size / 2)], crscenter, scaledtotalmapsize))
  mn = towgs.transform(extent[0][0], extent[1][0])
  mx = towgs.transform(extent[0][1], extent[1][1])
  return '  <bookmark><id>' + getid() + '</id><name>' + layoutname + '</name><project></project><xmin>' + str(mn[0]) + '</xmin><xmax>' + str(mx[0]) + '</xmax><ymin>' + str(mn[1]) + '</ymin><ymax>' + str(mx[1]) + '</ymax><sr_id>3452</sr_id></bookmark>\n'


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
print('''



  <Layout name="''' + layoutname + '''" printResolution="''' + str(args.dpi) + '''" units="mm">
    <Grid resUnits="mm" offsetY="0" offsetUnits="mm" offsetX="0" resolution="10"/>
    <PageCollection>''')

for i in range(npages):
  print('''      <LayoutItem size="''' + papersizespec + ''',mm" position="0,''' + str(i * (args.papersize[1] + 10)) + ''',mm" zValue="0" positionOnPage="0,0,mm" blendMode="0" outlineWidthM="0.3,mm" type="65638" visibility="1" id="" background="true">
        <FrameColor green="0" blue="0" alpha="255" red="0"/>
        <BackgroundColor green="255" blue="255" alpha="255" red="255"/>
      </LayoutItem>''')
print('</PageCollection>')

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
  bookmarks += getmaplayout(layoutname, config, outermapoffset)

if atlasbooklet:
  print('''
    <customproperties>
      <property key="atlasRasterFormat" value="jpg"/>
      <property key="forceVector" value="0"/>
      <property key="pdfDisableRasterTiles" value="0"/>
      <property key="pdfIncludeMetadata" value="1"/>
      <property key="pdfTextFormat" value="0"/>
      <property key="rasterize" value="true"/>
      <property key="singleFile" value="true"/>
    </customproperties>
    <Atlas coverageLayer="atlas_atlas_a19a9d12_8916_4d71_8d76_84bb05359f57" coverageLayerProvider="ogr" coverageLayerSource="/Users/kevin/ZA/atlas.geojson|layername=atlas|subset=&quot;type&quot; = 'atlaspage'|geometrytype=Point" pageNameExpression="&quot;page&quot;" filterFeatures="0" coverageLayerName="atlaspage features" sortFeatures="0" hideCoverage="0" filenamePattern="'output_'||@atlas_featurenumber" enabled="1"/>
  ''')
print('  </Layout>')

if not atlasbooklet:
  print("multi-map layout, skipping creation of atlas.geojson file. Here's QGIS bookmarks for the atlas's center pages instead:")
  print(bookmarks)
