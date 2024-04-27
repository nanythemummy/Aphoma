# -*- coding: utf-8 -*-
"""
Moves the center of the model to (0,0,0) of the chunk

Created on Sat Jan 27 15:00:04 2024
For Metsahape 2.1 Python Library 
@authors:  Alexey Pasumansky, JP Brown
See: https://www.agisoft.com/forum/index.php?topic=9240.msg66513#msg66513 for original code
"""
import Metashape, math, sys

import Metashape

def model_to_region_center(chunk):
	model = chunk.model
	if not model:
		print("No model in chunk, script aborted")
		return 0
	vertices = model.vertices
	T = chunk.transform.matrix
	s = chunk.transform.matrix.scale()
	step = int(min(1E4, len(vertices)) / 1E4) + 1
	
	sum = Metashape.Vector([0,0,0])
	N = 0
	for i in range(0, len(vertices), step):
		sum += vertices[i].coord
		N += 1
	avg = sum / N
	chunk.region.center = avg
	
	M = Metashape.Matrix().Diag([s,s,s,1])
	origin = (-1) * M.mulp(chunk.region.center)
	chunk.transform.matrix  = Metashape.Matrix().Translation(origin) * (s * Metashape.Matrix().Rotation(T.rotation()))
	return 1


doc = Metashape.app.document
chunk = doc.chunk
model_to_region_center(chunk)

