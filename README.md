## `remap` QGIS

[remap](https://thiswasyouridea.com/remap/) styles and scripts for QGIS

### usage of the `baseline_scale` magnification factor

Line and stroke widths are specified in map units (which are typically meters, e.g. 72m for a primary road), and each get multiplied by the current map scale divided by the `baseline_scale` parameter, i.e.:

`effective size (m) = size * map_scale / baseline_scale`

*Same `baseline_scale`s lead to same size of elements on paper*: if left at the default (`baseline_scale = 20.000`), the line will always be rendered at a width of `72m / 20.000 = 3.6mm` on paper, no matter the resolution of the map.

* increasing the `baseline_scale` will *reduce* the size of rendered features, e.g. at a value of 30.000 the primary road will only be 2.4mm wide, and any labels correspondingly less legible.
* decreasing the `baseline_scale` will *increase* the size of rendered features, e.g. at a value of 15.000 the primary road will be 48mm wide, with lines thicker and labels more clear.

Leaving the `baseline_scale` at its default produces consistent rendering of individual features, but it alters the overall look of the map due to its effects on the spacing between features: at 1:20.000, 3.6mm correspond to 72m on the map, but on a 1:10.000 map with default baseline scale the same 3.6mm only make up 36m, at 1:40.000 the 3.6mm will take up 144m of the underlying map space.

*Same `map_scale / baseline_scale` ratio leads to same relative spacing of line features relative to each other and the surrounding space*:

* if `map_scale < baseline_scale`, then the rendering of line features is relatively *smaller*, so the spacing between them is *increased*. (This is what happens when the `map_scale` is *decreased* without compensating for it.)
* if `map_scale > baseline_scale`, then the rendering of line features is relatively *bigger*, so the spacing between them is *decreased*, leading to *more overlap*. (This is what happens when the `map_scale` is *increased* without compensating for it.)
* if `map_scale = baseline_scale`, then the relative spacing of features remains intact. Therefore, *if a 'magnified' rendition of the originally spaced map is desired, the `map_scale` and `baseline_scale` should be changed in unison*: a 4x magnified version of the default map will have a `baseline_scale` of 80.000 (for 4x as large feature renditions) renderred at a map scale of 1:80.000 (to take up 4x the amount of space). A magnified version of the (more spacious) 1:10.000 map can be achieved by increasing both scales at the same factor, i.e. the same `baseline_scale` of 80.000 used together with a 1:40.000 map.

<!-- Changing the map resolution without changing the `baseline_scale` therefore changes  -->

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

## TODOs/FIXMEs

* add support for *map rotation* (requires funny center points for atlas)
