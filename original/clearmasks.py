#!/usr/local/bin/python3

from xml.etree.ElementTree import fromstring, parse

projectdoc = parse('ZA2.qgs')
masks = projectdoc.findall(".//text-mask")
for mask in masks:
  mask.set("maskedSymbolLayers", "")

print('All cleared, writing')
projectdoc.write('ZA2.qgs')
