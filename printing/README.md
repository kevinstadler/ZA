## paper

* binding margin = 4-5mm

effective page size is (123.75+4mm = 127.8mm * 191mm) = .0244sqm per page

Glasgow has 256 pages = 128 printed A5 leaves + 2x cardboard A5 + glue, weighs 269g
* A5 area = .03108*128 = 3.978sqm paper + .06126+ sqm cardboard // 269g / 4sqm = 67g/sqm
* exact area = .0244*128 = 3.12sqm paper + .05 sqm cardboard // 269g / 3.2sqm = 84g/sqm
<!-- Siang paper: 100xA4 = .297*.210 * 100: 60G: 274G, 70G: 436G, 80G: 499g -->
<!-- 100 page bag was 455g, 30 pages was 135g, so paper I bought is JUST OVER 70G! -->

## map page layout (excluding 4-5mm gutter for binding)

* the *printed area* of one double page is 24.75cm wide, 19.1cm high
* it is made up of 8*6 boxes of 2.75x2.75cm each, so 2.75 (1.375+1.375) horizontal margin and 2.6cm (1.3+1.3cm) vertical margin

* page index labels are 5.5mm circles, centered 5.5mm from the map border
* page number labels are 7mm tall rectangles, width depends on size of number (max is 9.5mm). inner side is aligned with map but 2mm above the top, so the center is 5.5mm above the top
* neighbour page links are 2.5mm from map border, 3mm tall and 6.5mm wide (NO MATTER SIZE LABEL), text is rotated outwards
* 2.5mm gap -- 3mm box -- 1mm gap -- 2.5mm triangle (same 6.5mm base max)

CP1515N print margin is .14in = 3.6mm

## cover leaf

* height: 19.1cm
* width: 12.8cm front + 1cm ridge (for 256 pages) + 12.8cm front = 26.6cm

### Fonts

via https://www.myfonts.com/WhatTheFont/

* blue title+subtitles (perfectly vertical edges of round characters like G and O)
  * SG Europa Grotesk SH Bold Condensed
  * Helvetica Black Condensed: http://fonts3.com/fonts/h/Helvetica-Condensed-Black.html
  * Antarctican Headline Bold
* regular town listing (old Manchester): https://fontsgeek.com/fonts/Industrial-Gothic-Banner-Std-Regular (write all lower caps!)
* italics town listing: no luck

### booklet creation pipeline

see [booklet.sh]

Most important was to *avoid* using GhostScript (and tools that use it, like `croppdf`) because it re-encodes everything. `mutool` (for cutting), `pdfjam` (for adding margin) and `pdfbook2` (with `--no-crop`) are 'lossless' in that way!

possible improvement: only add blue grid afterwards (to avoid cutting right on it)?

* https://stackoverflow.com/questions/56708765/using-ghostscript-how-do-i-put-page-numbers-on-combined-pdf-files
* https://stackoverflow.com/questions/12243044/is-it-possible-in-ghostscript-to-add-watermark-to-every-page-in-pdf

### filesize

|                 | 300 dpi | 400 dpi |
| --------------- |--------:| -------:|
| 3 double pages  | 8.6MB   | ? |
| 25 double pages | 79MB    | ? |

### colors

|                 | National Geographic | secondary |
| --------------- | ------------------- | --------- |
| motorway | | |
| primary | 255,178,0 | |
| secondary | 248,255,0 | |
| pedestrian | 255,151,202 | |
| blue/locked | 152,162,209| |
| water | 146,229,247 | |
| grass/greenspace | 238,250,163 | |
| built-up | 248,192,146 | |
| bldg: blue (public) | 18,102,255 | |
| bldg: pink (POI) | 255,70-80,122 | |
| bldg: purple (shop) | 191,139,255 | |
| bldg: orange (edu) | 255,163,36(!) | |
| icon: red | 255,0,0 | |
| icon: blue | 29,0,142 | |
| text: blue | ~60,0,220 | |

* saturation of buildings and roads 100% (except locked areas 38%)
* saturation of greenspace/builtup ~ 90%, water 86%

* https://www.nationalgeographic.com/content/dam/news/2017/06/22/london-map-blog-post/01-london-maps-charing-cross.adapt.1900.1.jpg
* https://www.nationalgeographic.com/content/dam/news/2017/06/22/london-map-blog-post/03-london-maps-birmingham.adapt.352.1.jpg
* https://www.nationalgeographic.com/content/dam/news/2017/06/22/london-map-blog-post/04-london-maps-st-paul-cathedral.adapt.352.1.jpg
