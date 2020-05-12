#!/usr/local/bin/python3

# ./layout.py -papersize 420 297 -box 27.5 -outermargin 10 data/{Moulsford,Kunming,Oxford,Nunhead}.atlas

import argparse
import configparser
import ast
import time
import os

from math import ceil, sqrt
from pyproj import CRS, Transformer
from geojson import Point, Polygon, Feature, FeatureCollection, dump

parser = argparse.ArgumentParser(description='Built a geojson feature file to be used as the basis of a QGIS atlas.')
parser.add_argument('atlas', nargs='*', default='data/Kunming.atlas', help='atlas specification file')
parser.add_argument('--startpage', type=int, default=4, help='first page for page numbering')
parser.add_argument('-o', default='atlas.geojson', help='output filename')

parser.add_argument('-box', type=float, default=27.5, help='in mm')
#parser.add_argument('-y', type=float, default=0, help='global y offset (for spreading pages)')
parser.add_argument('-papersize', type=float, nargs=2, default=(247.5, 191), metavar=('width', 'height'), help='in mm')
parser.add_argument('-dpi', type=int, default=300)
parser.add_argument('-bleed', type=float, default=0, help='in mm') # TODO make 10 instead
parser.add_argument('-outermargin', type=float, default=10, help='in mm')
args = parser.parse_args()

nmaps = len(args.atlas)

xmaps = ceil(sqrt(nmaps))
mapsperaxis = [ xmaps, ceil(nmaps / xmaps) ]

printareasize = list(map(lambda l: l - 2 * args.outermargin, args.papersize))
desiredmapsize = list(map(lambda s, n: s / n, printareasize, mapsperaxis))

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

def getmaplayout(atlasfile, outermapoffset):
  layoutname = os.path.basename(atlasfile).split('.')[0]

  config = configparser.ConfigParser()
  config.read(atlasfile)
  crs = CRS.from_user_input(config['map']['proj'])
  wgs = CRS.from_epsg(4326)

  # always use longlat
  fromwgs = Transformer.from_crs(wgs, crs, always_xy=True)
  towgs = Transformer.from_crs(crs, wgs, always_xy=True)

  center = ast.literal_eval(config['map']['center'])
  crscenter = fromwgs.transform(center[0], center[1])

  scale = float(config['map']['scale'])
  # TODO merge both argument specs by calling defaultsdict.update(overridedict)?

  scaledinnermapsize = list(map(lambda d: d * scale / 1000, innermapsize))
  scaledtotalmapsize = list(map(lambda d: d * scale / 1000, outermapsize))

  # TODO add overbleed and offset from spacing maps
  outermapoffsetspec = ','.join(map(str, outermapoffset))

  innermapoffset = map(lambda a, b: a + b, mapmargins, outermapoffset)
  innermapoffsetspec = ','.join(map(str, innermapoffset))

  totalmarginspec = ','.join(map(str, mapmargins))
  innermapsizespec = ','.join(map(str, innermapsize))

  def getid():
    return str(int(time.time() * 1000))

  # needs arrays!
  def getgrid(name, intervals, offsets, options, markerspec): # position="3" 
    return '<ComposerMapGrid show="1" unit="1" name="' + name + '" bottomAnnotationPosition="1" leftAnnotationPosition="1" topAnnotationPosition="1" rightAnnotationPosition="1" intervalY="' + str(intervals[1]) + '" topAnnotationDisplay="0" leftAnnotationDirection="0" gridFrameWidth="2" offsetX="' + str(offsets[0]) + '" intervalX="' + str(intervals[0]) + '" offsetY="' + str(offsets[1]) + '" ' + options + '>' + markerspec + '</ComposerMapGrid>'

  bluegridoptions = 'uuid="{' + getid() + '}"'
  bluegridspec = '''
      <lineStyle>
        <symbol name="" force_rhr="0" clip_to_extent="1" alpha="1" type="line">
          <layer locked="0" class="SimpleLine" pass="0" enabled="1">
            <prop v="0,86,208,255" k="line_color"/>
            <prop v="solid" k="line_style"/>
            <prop v="0.3" k="line_width"/>
            <prop v="MM" k="line_width_unit"/>
          </layer>
        </symbol>
      </lineStyle>'''

  labelbgoptions = 'uuid="{' + getid() + '}" gridStyle="3" showAnnotation="1" annotationFontColor="0,86,208,255" frameAnnotationDistance="3.7" annotationFormat="8" annotationExpression="if(@grid_number &lt; ' + str(nboxes[0] * args.box) + ', \'l\', \'\')"'
  labelbgspec = '<annotationFontProperties description="Wingdings,22,-1,5,50,0,0,0,0,0,Regular" style="Regular"/>'

  labeloptions = 'uuid="{' + getid() + '}" gridStyle="3" showAnnotation="1" annotationFontColor="255,255,255,255" frameAnnotationDistance="5.5" annotationFormat="8" annotationExpression="CASE &#xa;WHEN @grid_axis = \'x\'&#xa;THEN substr(\' ABCDEFGHIJ \', 1 + (@grid_number) / ' + str(args.box) + ' , 1) &#xa;WHEN @grid_axis = \'y\' AND @grid_number > 0&#xa;THEN ' + str(nboxes[1]) + ' + 0.5 - @grid_number / ' + str(args.box) + '&#xa;END"'
  labelspec = '<annotationFontProperties description="Al Bayan,9,-1,5,75,0,0,0,0,0,Bold" style="Bold"/>'

  yellowborderoptions = 'uuid="{' + getid() + '}" blendMode="16"'
  yellowborderspec = '''
        <lineStyle>
          <symbol name="" force_rhr="0" clip_to_extent="1" alpha="1" type="line">
            <layer locked="0" class="SimpleLine" pass="0" enabled="1">
              <prop v="253,255,122,255" k="line_color"/>
              <prop v="solid" k="line_style"/>
              <prop v="''' + str(yellowborderwidth) + '''" k="line_width"/>
              <prop v="MM" k="line_width_unit"/>
            </layer>
          </symbol>
        </lineStyle>'''

  def getmap(inner):
    name = layoutname + ' ' + ('inner map' if inner else 'Outer (monochrome) map')
    size = innermapsizespec if inner else outermapsizespec
    offset = innermapoffsetspec if inner else outermapoffsetspec
    preset = 'AZ' if inner else 'AZ monochrome'
    z = '2' if inner else '0'

    if inner:
      labeloffsets = [args.box / 2, args.box / 2]
      grids = getgrid(layoutname + ' label backgrounds', [args.box, args.box], labeloffsets, labelbgoptions, labelbgspec) + getgrid('Labels', [args.box, args.box], labeloffsets, labeloptions, labelspec)
    else:
      grids = getgrid(layoutname + ' yellow border', yellowframeinterval, yellowborderoffset, yellowborderoptions, yellowborderspec)

    grids += getgrid(layoutname + ' blue grid', [args.box, args.box], [0, 0] if inner else mapmargins, bluegridoptions, bluegridspec)

    # use scale and crs to calculate extent
    extent = list(map(lambda center, size: [str(center - size / 2), str(center + size / 2)], crscenter, scaledinnermapsize if inner else scaledtotalmapsize))

    # TODO that offset should get extra on the y axis if we're not on the first page....
    return '''
    <LayoutItem size="''' + size + ''',mm" followPreset="true" position="''' + offset + ''',mm" zValue="''' + z + '''" positionOnPage="''' + offset + ''',mm" outlineWidthM="13,mm" type="65639" followPresetName="''' + preset + '''" visibility="1" id="''' + name + '''" background="false">
      <Extent xmin="''' + extent[0][0] + '''" xmax="''' + extent[0][1] + '''" ymin="''' + extent[1][0] + '''" ymax="''' + extent[1][1] + '''"/>
      <crs>
        <spatialrefsys>
          <!-- let QGIS figure it out... -->
          <proj4>''' + crs.to_proj4() + '''</proj4>
        </spatialrefsys>
      </crs>
      ''' + grids + '''
      <AtlasMap margin="0" scalingMode="0" atlasDriven="1"/>
      <labelBlockingItems/>
    </LayoutItem>'''

  return getmap(True) + '''
    <!-- cover rectangle -->
    <LayoutItem zValue="1" type="65643" shapeType="1" positionOnPage="''' + innermapoffsetspec + ''',mm" position="''' + innermapoffsetspec + ''',mm" size="''' + innermapsizespec + ''',mm" id="''' + getid() + '''">
      <symbol alpha="1" type="fill" clip_to_extent="1">
        <layer class="SimpleFill" enabled="1">
          <prop k="color" v="255,255,255,255"/>
          <prop k="outline_style" v="no"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
    </LayoutItem>

    ''' + getmap(False)

maps = ''
i = 0
for atlas in args.atlas:
  # TODO calculate offset, print
  offsets = [i % mapsperaxis[0], i // mapsperaxis[0]]
  maps += getmaplayout(atlas, list(map(lambda o, s: args.outermargin + o * s, offsets, outermapsize)))
  i += 1

layoutname = os.path.basename(args.atlas[0]).split('.')[0]
print('''
  <Layout name="''' + layoutname + '''" printResolution="''' + str(args.dpi) + '''" units="mm">
    <Snapper snapToGrid="0" snapToGuides="1" snapToItems="1" tolerance="5"/>
    <Grid resUnits="mm" offsetY="0" offsetUnits="mm" offsetX="0" resolution="10"/>
    <PageCollection>
      <LayoutItem size="''' + papersizespec + ''',mm" position="0,0,mm" zValue="0" positionOnPage="0,0,mm" blendMode="0" outlineWidthM="0.3,mm" type="65638" visibility="1" id="" background="true">
        <FrameColor green="0" blue="0" alpha="255" red="0"/>
        <BackgroundColor green="255" blue="255" alpha="255" red="255"/>
      </LayoutItem>
    </PageCollection>''')
print(maps)
if nmaps == 1:
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

if nmaps > 1:
  print("multi-map layout, skipping creation of atlas.geojson file")
else:
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
