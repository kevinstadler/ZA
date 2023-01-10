## paper

* binding margin = 4-5mm

effective page size is (123.75+4mm = 127.8mm * 191mm) = .0244sqm per page

Glasgow has 256 pages = 128 printed A5 leaves + 2x cardboard A5 + glue, weighs 269g
* A5 area = .03108*128 = 3.978sqm paper + .06126+ sqm cardboard // 269g / 4sqm = 67g/sqm
* exact area = .0244*128 = 3.12sqm paper + .05 sqm cardboard // 269g / 3.2sqm = 84g/sqm
<!-- Siang paper: 100xA4 = .297*.210 * 100: 60G: 274G, 70G: 436G, 80G: 499g -->
<!-- 100 page bag was 455g, 30 pages was 135g, so paper I bought is JUST OVER 70G! -->

## crop mark positions on double-page print

printed area of both sides together is 24.75cm wide, 19.1cm high.

crop marks should be `24.75cm + 2 * binding margin` apart *once binding margin is added*. On the QGIS export, crop marks just show the desired printed area. Moving QGIS crop marks inward would:

1. keep the booklet format size intact at the cost of:
2. *reducing* the size of the horizontal margin (13-14mm yellow, 4mm from the page number label box)

In practice:

* original ZA has 4mm binding margin, crop mark distance on paper: `25.55cm`, resulting in a booklet width of `12.9cm`
* first book print accidentally had 7.35mm binding margin, so the cropmark distance was `26.22cm`. Together with wider glue that let to a booklet width of `13.4cm` (2+mm could've been cut off as is)
* intentionally choose 8mm binding margin on 2nd print to make central bits more accessible?

## leaflet layout

First print assumed 26.6cm print area (12.8cm + 12.8cm + 1cm ridge), and added .775cm left and 1.025cm right bleed + 2*.65cm crop marks to get to `29.7cm` (=A4).

## map page layout (excluding 4-5mm gutter for binding)

* the *printed area* of one double page is 24.75cm wide, 19.1cm high
* it is made up of 8*6 boxes of 2.75x2.75cm each, so 2.75 (1.375+1.375) horizontal margin and 2.6cm (1.3+1.3cm) vertical margin

* page index labels are 5.5mm circles, centered 5.5mm from the map border
* page number labels are 7mm tall rectangles, width depends on size of number (max is 9.5mm). inner side is aligned with map but 2mm above the top, so the center is 5.5mm above the top
* neighbour page links are 2.5mm from map border, 3mm tall and 6.5mm wide (NO MATTER SIZE LABEL), text is rotated outwards
* 2.5mm gap -- 3mm box -- 1mm gap -- 2.5mm triangle (same 6.5mm base max)

CP1515N print margin is .14in = 3.6mm

### map fonts

* station names are DIN

* pagelabel numbers (*very* vertical 0/5/6/9 -- too wide is a no-no because 3-digit page numbers don't fit in box anymore)

|                              | height/tallness | weight    | 1/4/7/6/9 rendering |
| ---------------------------- | --------------- | --------- | ------------------- |
| D-Din Condensed Regular 20pt | super nice      | bit too thin | 6+9 not swung, G no hook |
| DIN Alternate Bold 14pt      | too wide        |           | 4 disconnected, G no hook, 7 hooked |
| Helvetica Neue Condensed Bold 15pt | bit too wide | too black |                  |
| Avenir Next Condensed Medium | too round       |           | 6+9 not swung, C/G too simple |
| DIN Engschrift LT Alternate Regular |          | too black | 4 disconnected, 7 hooked |
| DIN Condensed Bold           |                 | too black | 4 disconnected, 7 hooked, 6+9 not swung, D no hook |

Even though the 6/9-curving really suggests a Helvetica-like font, for the page label the condensed DIN fonts work much better. That kind of locks us into adopting similarly wrong fonts for the smaller labels on the page:

* page grid indices are not *quite* as condensed, in particular the 6 and 9 have curved sides, and the 2 has a turning point, so has a curved middle line that swings back to the bottom line
** to match the 6/9 style of D-Din Condensed: use *D-DIN DIN-Bold* 12pt
** DIN Alternate Bold 12pt is VERY close except numbers are relatively too narrow (flat sides) while letters too wide, and a disconnected 4
** DINEnglischrift LT Alternate Regular *13pt* is too narrow

* page link labels: *Helvetica Neue Condensed Bold* 8pt (even it's a bit too black actually)

## cover leaf

* height: 19.1cm
* width: 12.8cm front + 1cm ridge (for 256 pages) + 12.8cm front = 26.6cm

in order to correctly align the front (including the cropmarks), use the following dimensions:

* the crop marks are 19.75mm from the right margin (the bleed goes to at least 16.75 from the margin)

So cropmark length (can only be defined once!) + right bleed need to add up to 16.75 (not 19.75 for some reason?)

do cropmarklength: 6.5

`a4 width = 2*cropmarklength + pagewidth + leftbleed + rightbleed`
`a4 height = 2*cropmarklength + pageheight + topbleed + bottombleed`

`297 = 13 + 266 + 7.75 + 10.25`
`210 = 13 + 191 + 3 + 3`

* bleed: `7.75, 10.25, 3, 3`
* margin (to indicate where the ridge is): `128, 128, 0, 0`

Scribus export settings:

[X] Crop marks
  * Length: 6.5mm
  * Offset: 0
[X] Use document bleeds

The dimensions of the document output by Scribus only cover the area that is actually printed on, which needs to be made to match A4 by having cropmarks which extend all the way to the edge of the document.

### Colors

* blue (based on home on thin paper): `220d, 92%, 92-100%` = #135EF2
* red (based on print shop): `5d, 97%, 92%` = #EB1A07
* light blue (based on home): `234d, 20% 100%` = #CCD1FF
* yellow (based on home thin paper): `63d, 84%, 88%` = #D7E024?? (looks well dark to me)

conclusions of the PROPER print shop test:
blue: 244deg, 100% s, <69% v == #0C00B0 (looks v purple on screen??) in QGIS: #0b00b0
red: 358deg, 95+-3% s, 100% v == #FF0D15
backblue: 220deg, 8+-2% s, 69% v == #9EA4B0 (choose 10 saturation because otherwise completely gray)
FIRST TO SECOND PRINT CHANGES
blue goes from 19,94,242 to 12,0,176
red goes from 235,26,7 to 255,13,21
backblue goes from 204,209,255 to 158,164,176 (don't think that can be right???)

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

## duplex printing

***sucky approach because ends up with wrong page order:***

1st run: 3-* even pages only
2nd run: 3-*: odd pages only + reverse pages (also reverse page feature not actually working the same way with Preview print, just blocks)

***better approach***

