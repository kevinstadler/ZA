#!/bin/sh

# this should only be called with files in the parent directory (because it will overwrite)
NAME=`basename "$1" .pdf`


# 1. split into A5, and merge in one extra empty A5 page for the front
echo "Splitting pages through the middle..."
# first, adjust teeny amount to the RIGHT so that the split cuts the middle blue line in half
pdfjam -q --noautoscale true --paper a4paper --offset '0mm 0cm' -o "$NAME.pdf" "$1"
mutool poster -x 2 "$1" "$NAME.pdf"
#gs -sDEVICE=pdfwrite -o empty.pdf -g4210x5950 -c showpage
mutool merge -o "$NAME.pdf" empty.pdf "$NAME.pdf"

# 2. make booklet with no auto scale and add inner margin (this is actually just a rendering offset, not a margin!)
echo "Adding binding margin offset..."
pdfjam -q --noautoscale true --paper a5paper --twoside --offset '8mm 0cm' -o "$NAME.pdf" "$NAME.pdf" # output 148x210

# this one uses auto scale if we use the default mode which zooms, but can avoid this with --no-crop
echo "Creating A4 pages for booklet printing..."
# --inner-margin only works when cropping is on (which re-encodes the file...)
pdfbook2 --no-crop --paper=a4paper "$NAME.pdf"
open "$NAME-book.pdf"

#echo "Splitting page sets for duplex printing..."
#echo "...odd pages..."
#pdftk tmp-pdfjam-book.pdf cat odd output "$1-odd.pdf"
#open "$1-odd.pdf"
#echo "...even pages (in reverse order)..."
#pdftk tmp-pdfjam-book.pdf cat end-1even output "$1-even-reversed.pdf"
#echo "Done."

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

#4. add blue grid afterwards: https://stackoverflow.com/questions/56708765/using-ghostscript-how-do-i-put-page-numbers-on-combined-pdf-files https://stackoverflow.com/questions/12243044/is-it-possible-in-ghostscript-to-add-watermark-to-every-page-in-pdf
