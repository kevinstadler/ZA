#!/bin/sh

# create empty A4 page:
#gs -sDEVICE=pdfwrite -o empty.pdf -g5950x8420 -c showpage
# A5:
#gs -sDEVICE=pdfwrite -o empty.pdf -g4210x5950 -c showpage

# gotta take that .5cm (14.17pt) out from the width to make margins work properly
#gs -sDEVICE=pdfwrite -o empty.pdf -g4068x5950 -c showpage

# 1. original file needs to be 1cm too narrow
# 2. split
mutool poster -x 2 "$1" tmp.pdf
mutool merge -o tmp.pdf empty.pdf tmp.pdf
#pdf180 tmp.pdf
#mv tmp-rotated180.pdf tmp.pdf

# 3. make booklet with no auto scale and add inner margin
pdfjam --noautoscale true --paper a5paper --twoside --offset '.5cm 0cm 0cm 0cm' tmp.pdf # output 148x210

# this one uses auto scale if we use the default mode which zooms, but can avoid this with --no-crop
pdfbook2 --no-crop --paper=a4paper tmp-pdfjam.pdf
open tmp-pdfjam-book.pdf

# this one works but reencodes at twice the size: pdfcrop --margins '0 0 14 0' --noclip tmp.pdf out.pdf

# these files are now each .5cm less then a5 wide

# pdfjam FORCES output sizes, so better way to add the gutter is using ghostscript, but also needs to have correct output device size...

# 5mm = 14.17pt
# A4 is 842x595pt, A5 595x421
# add gutter instructions: https://superuser.com/questions/904332/add-gutter-binding-margin-to-existing-pdf-file

# this one re-encodes at half the density apparently...
# gs -q -sDEVICE=pdfwrite -dBATCH -dNOPAUSE -sOutputFile=padded.pdf \
#   -dDEVICEWIDTHPOINTS=421 -dDEVICEHEIGHTPOINTS=595 -dFIXEDMEDIA \
#   -c "<< /CurrPageNum 1 def /Install { /CurrPageNum CurrPageNum 1 add def
#    CurrPageNum 2 mod 1 eq {14.17 0 translate} {-14.17 0 translate} ifelse } bind  >> setpagedevice" \
#   -f "tmp.pdf"

#gs -q -sDEVICE=pdfwrite -dBATCH -dNOPAUSE -sOutputFile=padded.pdf -c "<< /BeginPage { 2 mod 1 eq {-14.17 0 translate} {14.17 0 translate} ifelse } bind  >> setpagedevice" -f tmp.pdf

#open padded.pdf
#pdfjam --noautoscale true --booklet true --landscape padded.pdf

# --no-crop is best but needs to have smaller than a4/a5 page size then
#pdfbook2 --inner-margin=50 --paper=a4paper tmp-rotated180.pdf

#4. add blue grid afterwards: https://stackoverflow.com/questions/56708765/using-ghostscript-how-do-i-put-page-numbers-on-combined-pdf-files https://stackoverflow.com/questions/12243044/is-it-possible-in-ghostscript-to-add-watermark-to-every-page-in-pdf
