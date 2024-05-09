# -*- coding: utf-8 -*-
"""
Remove "blobs" from model prior to texturing. 
Created on Weds April 17 19:02:27 2024
For Metsahape 2.1 Python Library 

Created on Weds April 17 19:03:21 2024
For Metsahape 2.1 Python Library 
@authors: JP Brown 
"""

import Metashape, math, sys

# initial setup
doc = Metashape.app.document # specifies open document
chunk = doc.chunk # specifies active chunk

model = chunk.model
if model is None or len(model.faces) == 0:
    exit(0)
	
threshold = int(len(model.faces) * 0.6)
model.removeComponents(threshold)
