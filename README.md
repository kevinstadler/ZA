## `remap` QGIS

`remap` styles and scripts for QGIS

### dimensions

```

      W
\^^^^^^^^^^^\
\+----+----+\
\|XXXX|XXXX|\
\|XXXX|XXXX|\
\|XXXX|XXXX|\ H
\|XXXX|XXXX|\
\|XXXX|XXXX|\
\|XXXX|XXXX|\
\^^^^^^^^^^^\
```

lengths in `mm`:

    |   AZ  |   A5  | derivation
--- | ----- | ----- | ----------
`X` |  27.5 |  23.25 |
`\` |  13.75 | 12 |
`W` | 247.5 |  <210 | `8*X + 2*\`
`^` |  13   |  4.25  |
`H` | 191   |  <148 | `6*X + 2*^`
X label offset (X)  |    6.875 | | `\ / 2`
Y label offset (Y)  |    6.5  | | `^ / 2`
border thickness |   13.75 | | `max(width(\), height(^)) / 2`
X border spacing | 233.75 | | `8 * X + border thickness`
X border offset  |   6.875 | | `\ - border thickness / 2`
Y border spacing | 178.75 | | `6 * X + border thickness`
Y border offset  |   6.125 | | `^ - border thickness / 2`

Grid order:

* labels are *frame & annotations*
* label backgrounds are *frame & annotations*
* grid is *solid* (thickness < 1pt)
* border is *solid* (thickness `border thickness`)

`distance to map frame` is 7.5mm for the 9pt bold labels, 5.7mm for 22pt wingding backgrounds

#### Label rule

```
CASE
WHEN @grid_axis = 'x'
THEN substr(' ABCDEFGH ', 1 + (@grid_number) / 27.5 , 1) 
WHEN @grid_axis = 'y' AND @grid_number > 0
THEN 7 - @grid_number / 27.5
END
```

#### Label background rule (Wingdings)

```
if(@grid_number > 0 AND @grid_number < 9 * 27.5, 'l', '')
```

### generate atlas (`writeatlas.py`)

Specify atlas pages config like:

```
[map]
center: [long, lat]
proj: 3857
scale: 20000
pagesize: 456, 123 // in mm, not including margin!
[pages]
-1: -5-5
0: -1-3, 5
1: -1, 1, 3-5
```

1. calculate page size in projection coordinates based on input projection, scale and pagesize
2. for every page specified in above format, calculate the center of the page (converting from projection coordinates back to WGS84 if necessary)
3. generate atlas geojson output file with points on the center of every full-page (back in WGS84!)
4. generate page number geojson output file with points on every half-page that have atlas page number attribute (back in WGS84!)
