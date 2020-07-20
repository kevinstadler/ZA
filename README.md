## `remap` QGIS

[remap](https://thiswasyouridea.com/remap/) styles and scripts for QGIS

### generate atlas (processed by `layout.py`)

Specify atlas pages config like:

```
[map]
center: [long, lat]
proj: 3857
scale: 20000
pagesize: 456, 123 // in mm, not including margin!
magnification: 1.2 // adjust font+geometry scaling away from 1:20.000 basis

[pages]
-1: -5-5
0: -1-3, 5
1: -1, 1, 3-5
```

`layout.py` workings:

1. calculate page size in projection coordinates based on input projection, scale and pagesize
2. for every page specified in above format, calculate the center of the page (converting from projection coordinates back to WGS84 if necessary)
3. generate atlas geojson output file with points on the center of every full-page (back in WGS84!)
4. generate page number geojson output file with points on every half-page that have atlas page number attribute (back in WGS84!)

### atlas export pipeline

for future booklet production:

1. export atlas as SVG, stroke and coloring layer *separate*
2. crop to page using `inkscape --export-area-page`
3. create composite SVG using `feBlend` spec
4. render to raster?

prepare for print? https://unix.stackexchange.com/questions/405610/how-can-i-split-each-pdf-page-into-two-pages-using-the-command-line
