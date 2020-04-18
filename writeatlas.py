#!/usr/local/bin/python3

from pyproj import CRS, Transformer
from geojson import Point, Polygon, Feature, FeatureCollection, dump

import argparse
import configparser
import ast

import os

parser = argparse.ArgumentParser(description='Built a geojson feature file to be used as the basis of a QGIS atlas.')
parser.add_argument('atlas', nargs='+', help='atlas specification file(s)')
parser.add_argument('--startpage', type=int, default=4, help='first page for page numbering')
args = parser.parse_args()

def addpage(featurelist, towgs, crscenter, x, y, xoffset, yoffset, pagenum):
	pagecenter = [ crscenter[0] + x * xoffset, crscenter[1] + y * yoffset ]
	featurelist.append(Feature(geometry=Point(towgs.transform(pagecenter[0], pagecenter[1])), properties={"type": "atlaspage", "page": page}))
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
	return pagenum+2

config = configparser.ConfigParser()

for atlasfile in args.atlas:
	config.read(atlasfile)

	crs = CRS.from_user_input(config['map']['proj'])
	#print(crs)
	#print(crs.geodetic_crs)
	wgs = CRS.from_epsg(4326)

	# always use longlat
	fromwgs = Transformer.from_crs(wgs, crs, always_xy=True)
	towgs = Transformer.from_crs(crs, wgs, always_xy=True)

	center = ast.literal_eval(config['map']['center'])
	print("center is", center)
	crscenter = fromwgs.transform(center[0], center[1])
	print("center is", crscenter)

	pagesize = ast.literal_eval(config['map']['pagesize'])
	scale = float(config['map']['scale'])
	# pagesize is in mm, crs will be in meters, so scale down
	xoffset = pagesize[0] * scale / 1000
	yoffset = pagesize[1] * scale / 1000
	print("Creating atlas index with " + str(xoffset) + "x" + str(yoffset) + " meters per page")

	pagefeatures = []

	page = args.startpage
	for yspec in config['pages']:
		y = int(yspec)
		# FIXME ignore whitespace everywhere?
		for xspec in config['pages'][yspec].split(', '):
			split = xspec.find('-', 1)
			if split > 0:
				# loop through spec
				for x in range(int(xspec[:split]), int(xspec[split+1:])):
					page = addpage(pagefeatures, towgs, crscenter, x, y, xoffset, yoffset, page)
			else:
				page = addpage(pagefeatures, towgs, crscenter, int(xspec), y, xoffset, yoffset, page)

	feature_collection = FeatureCollection(pagefeatures)

	geojson = atlasfile + '.geojson'
	with open(geojson, 'w') as f:
	   dump(feature_collection, f)

#shapefile = atlasfile + '.shp'
# destination, source
# -t_srs ....
#os.system('ogr2ogr -overwrite ' + shapefile + ' ' + geojson)
