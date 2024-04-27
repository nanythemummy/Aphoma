# -*- coding: utf-8 -*-
"""
Detect markers
This process should be classed *after* RefineSparseCloud.py has been called.

Created on Sat Jan 27 15:00:04 2024
For Metsahape 2.1 Python Library 
@authors:  JP Brown

"""
import Metashape, math, sys

def detect_12bit_markers(chunk):
    # set accuracy values for markers and scale bars in the chunk
    chunk.tiepoint_accuracy = 0.25 # pixels
    chunk.marker_projection_accuracy = 0.5 # pixels
    chunk.marker_location_accuracy = Metashape.Vector( (5.0e-5, 5.0e-5, 5.0e-5) ) # meters (= 0.05 mm)

    # remove any existing markers from this chunk
    if len(chunk.markers):
        chunk.remove(chunk.markers)
    
    print("Detecting and assigning 12-bit targets")
    # detect markers using defaults (12-bit markers, tolerance: 50, filter_mask: False, etc.)
    chunk.detectMarkers() 

    # bale if we have no markers
    if len(chunk.markers) ==  0:
        print("- no markers detected")
        exit(0)
    else:
        print(f"- found {len(chunk.markers)} markers")
    # update markers
    chunk.refineMarkers()

# start main program
doc = Metashape.app.document
chunk = doc.chunk
detect_12bit_markers(chunk)