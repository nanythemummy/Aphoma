# -*- coding: utf-8 -*-
"""
Created on Mon July 7, 2025 7:29 pm
For Metsahape 2.2 Python Library 
@authors: JP Brown, Kea Johnston

This script is designed to be run in the Metashape Python console.
Python: v3.11.7
Metashape: v2.2.0

Prerequisites:
- A Metashape project file saved with the correct filename (A3697_31760.x[-x]_Multiband.psx) where x[-x] is the subnumber [or the range of sub-numbers], for the item(s) imaged
- A folder named "_input" in the directory of the Metashape project file, containing images from multiband photography.
- 	Each image file should be named with the pattern "[Front|Back]][band][nnnn].jpg", where
		"band" is one of "IrIr", "UvUv", "UvVis"," VisIr" or "VisVis", 
		"nnnn" is a number starting from 1 (number is left-padded to four digits with zeros).

- To install python packages (e.g. cv2) in Metashape's python environment:  
    In Windows Command Prompt (or PowerShell terminal)
	> %PROGRAM_FILES%\Agisoft\Metashape\python\python.exe -m pip install python_module_name (e.g., opencv-python)
		[if Metashape is active, restart it to make sure the dependency has been added ]
"""
import Metashape, math, sys, os, copy, cv2, json
import numpy as np 

# numpy color channel constants
NUMPY_BLUE = 0 
NUMPY_GREEN = 1
NUMPY_RED = 2 
RGB = 4  # special code for RGB images

doc: Metashape.app.document
input_folder: str
output_folder: str

def get_chunk(label) -> Metashape.Chunk:
	# get a chunk by its label name

	global doc
	if doc is None:
		raise Exception(f"get_chunk(label): no document defined")
	
	for chunk in doc.chunks:
		if chunk.label == label:
			return chunk
	return None

def get_chunk_key(chunk_label) -> int: 
	# get the key of a chunk by its label

	global doc
	if doc is None:
		raise Exception("get_chunk_key(chunk_label): no document defined")
	
	for chunk in doc.chunks:
		if chunk.label == chunk_label:
			print(f"{chunk_label} key: {chunk.key}")
			return chunk.key

	return -1

def remove_models(chunk):
	# remove any models from a chunk 
	if chunk.models != None and len(chunk.models) > 0:
		chunk.remove(chunk.models)


def reset_transform(chunk):
	# reset the transform for a chunk
	if chunk is None:
		chunk.crs = None
		chunk.transform.matrix = None	


def get_output_stem() -> str:
	# get the output stem for filenames
	global doc 

	if doc is None:
		raise Exception (f"no document defined")

	return os.path.basename(doc.path).rsplit("_", 1)[0]

def initialize():
	# initialize global values
	global doc, input_folder, output_folder

	# assign globals
	doc = Metashape.app.document
	doc_folder = os.path.dirname(doc.path)
	input_folder = os.path.join(doc_folder, "_input")
	output_folder = os.path.join(doc_folder, "_output")

	# check that the input folder is present
	if not os.path.exists(input_folder):
		raise Exception("initialize(): no input folder")

	# create output folder if necessary
	if not os.path.exists(output_folder):
		os.mkdir(output_folder)
		print("created output folder")


# dictionary of chunks to create models for as keys, with a list of chunks to receive the model as the value.
chunks_to_model = {
				"BackVisVis": ["BackIrIr", "BackUvUv", "BackUvVis", "BackVisIr"],
				"FrontVisVis": ["FrontIrIr", "FrontUvUv", "FrontUvVis", "FrontVisIr"]
				}


def check_markers():
	# check for equal number of markers in the [Back|Front]VisVis chunk and the other [Back|Front] chunks that will be aligned to it.
	for vis_chunk_label in chunks_to_model.keys():
		vis_chunk = get_chunk(vis_chunk_label)
		vis_marker_count = len(vis_chunk.markers)
		for other_chunk_label in chunks_to_model[vis_chunk_label]:
			other_chunk = get_chunk(other_chunk_label)
			other_marker_count = len(other_chunk.markers)
			if other_marker_count != vis_marker_count:
				raise Exception(f"missing marker in {vis_chunk_label} or {other_chunk_label}")
			else:
				print(f"Markers OK for {vis_chunk_label} and {other_chunk_label}")


def align_chunks():
	
	# align other chunks with their [Back|Front]VisVis counterpart using marker 
	# - Backs aligned with BackVisVis
	# - Fronts aligned with FrontVisVis
	
	chunks_to_align = list()
	ref_chunk = 0
	i = 0

	for vis_chunk_label in chunks_to_model.keys():
		
		ref_chunk_key = get_chunk_key(vis_chunk_label)

		print(f"reference chunk: {vis_chunk_label} key: {ref_chunk_key}")

		chunks_to_align_keys = list()
		
		# add other chunk keys
		for other_chunk_label in chunks_to_model[vis_chunk_label]:
			other_chunk_key = get_chunk_key(other_chunk_label)
			chunks_to_align_keys.append(other_chunk_key)
		
		print(f"chunks to align: {chunks_to_align_keys}")

		# get markers
		ref_chunk = get_chunk(vis_chunk_label)
		vis_markers = list()
		for i in range(0, len(ref_chunk.markers)):
			vis_markers.append(i)
		print(f"marker indices: {vis_markers}")

		# do alignment
		for key in chunks_to_align_keys:
			key_list = list()
			key_list.append(key)
			# add reference chunk key
			key_list.append(ref_chunk_key)
			print(f"align {key} with {ref_chunk_key}")
			doc.alignChunks(chunks=key_list, reference=ref_chunk_key, method=1, markers=vis_markers, fit_scale=True)

def remove_model_blobs(chunk):
	
	# Remove "blobs" from model prior to texturing. 

	# Arguments:
	# 	chunk - the chunk from which to remove blobs
	
	model = chunk.model
	if model is None or len(model.faces) == 0:
		raise Exception("remove_model_blobs(chunk)): no model found")
		
		
	threshold = int(len(model.faces) * 0.6)
	model.removeComponents(threshold)

def build_and_distribute_models():
	# build models for [Back|Front]VisVis and import them to other [Back|Front] chunks

	output_stem = get_output_stem()
	
	for vis_chunk_label in chunks_to_model.keys():
		chunk = get_chunk(vis_chunk_label)
		
		#remove any existing models
		remove_models(chunk)

		chunk.buildDepthMaps(downscale=1)
		chunk.buildModel(
			face_count=Metashape.FaceCount.MediumFaceCount, 
			vertex_colors=False, 
			build_texture=False, 
			replace_asset=True)
		
		remove_model_blobs(chunk) 

		model_path = os.path.join(output_folder, f"{output_stem}_{vis_chunk_label}ScaledInMetersPly.ply")
		chunk.exportModel(path=model_path, format=Metashape.ModelFormat.ModelFormatPLY)
		
		for other_chunk_label in chunks_to_model[vis_chunk_label]:
			other_chunk = get_chunk(other_chunk_label)
			remove_models(other_chunk)
			other_chunk.importModel(path=model_path, format=Metashape.ModelFormat.ModelFormatPLY, replace_asset=True)

def replace_alignment_images_with_coloring_images(chunk_label: str, make_grayscale: bool, color_channel: int):
	
	# Creates images for *coloring* the orthomosaic in a specified chunk, and over-writes the alignment images in the input subfolder for that chunk. 
	# NB: 
	# - The subfolder for a particular chunk should be  .\_input\[chunk.label]
	# - Not all chunks need coloring images (VisVis and IrIr are fine with the images used for alignment)
	
	# Parameters:
	# -----------
	#   chunk_label: the label of the chunk for which we are creating new coloring images
	#   make_grayscale: whether to make the images  grayscale
	#   color_channel: which color channel to write in the coloring images (one of NUMPY_BLUE, NUMPY_GREEN, NUMPY_RED for 8-bit grayscale, RGB for rgb)
		
	global input_folder, doc 

	chunk = get_chunk(chunk_label)
	if not chunk:
		raise Exception(f"in chunk coloring: chunk {chunk_label} not found")

	# get input files
	from_filenames_contain = f"{chunk_label}0"
	from_files = [f for f in os.listdir(input_folder) if from_filenames_contain in f]
	
	# check that we have input files
	if not from_files:
		raise Exception(f"No files found for coloring chunk {chunk.label} at path '{input_folder}'.")
	
	# check that folder for new files exists
	folder_to = os.path.join(input_folder, chunk_label)
	if not os.path.exists(folder_to):
		raise Exception(f"could not find folder to write files: '{folder_to}'")

	# open input files, modify them, and save the results to the output folder
	for f in from_files:

		# figure out path to original RGB color image in .\_input folder
		from_file_path = os.path.join(input_folder, f)

		# open original RGB color image
		img_in = cv2.imread(from_file_path) 
		if img_in is None:
			raise Exception(f"Error reading image {from_file_path}.")

		# convert to grayscale if needed
		img_out = img_in
		if make_grayscale:
			if color_channel == RGB:
				# img_out = cv2.cvtColor(img_in, COLOR_BGR2GRAY) <- results are too dark
				blue_channel = img_in[:,:,NUMPY_BLUE]
				img_out = np.zeros_like(img_in)
				img_out[:,:,0] = blue_channel
				img_out[:,:,1] = blue_channel
				img_out[:,:,2] = blue_channel
			else:
				img_out = img_in[:, :, color_channel]
		
		#TODO: copy exif data to new image file. The following stackoverflow code looks promising...
		# https://stackoverflow.com/questions/72544252/python-copy-exif-data-from-one-image-to-other

		# create new file (this should overwrite an existing file)
		to_file_path = os.path.join(folder_to, f)
		cv2.imwrite(to_file_path, img_out)

		# check the file was written to the expected location
		if not os.path.exists(to_file_path):
			raise Exception(f"Error saving image {to_file_path}.")
			
		print(f"Updated image at {to_file_path}")
	
	print(f"updated {len(from_files)} photos in chunk {chunk_label} from folder {folder_to}.")

def import_coloring_images():
	
	# Create the images that we will use for coloring the orthomosaics, over-writing the 
	# images used for alignment where necessary (i.e., for the UvUv, UvVis, and VisIr chunks)

	coloring_import_params = {# nothing for [Back]IrIr - images are already good
					"BackUvUv": {"make_grayscale":True, "color_channel":NUMPY_RED},
					"BackUvVis": {"make_grayscale":False, "color_channel":RGB},
					"BackVisIr": {"make_grayscale":True, "color_channel":NUMPY_RED},
					# nothing for [Back]VisVis - images are already good
					# nothing for [Front]IrIr - images are already good
					"FrontUvUv": {"make_grayscale":True, "color_channel":NUMPY_RED},
					"FrontUvVis": {"make_grayscale":False, "color_channel":RGB},
					"FrontVisIr": {"make_grayscale":True, "color_channel":NUMPY_RED},
					# nothing for [Front]VisVis - images are already good
					}
	for chunk_label in coloring_import_params.keys():
		params = coloring_import_params[chunk_label]
		make_grayscale = params.get("make_grayscale")
		color_channel = params.get("color_channel")
		replace_alignment_images_with_coloring_images(chunk_label, make_grayscale, color_channel)

#TODO: force Metashape to update thumbnails


def build_orthmosaics():

	# Builds the orthomasics (all chunks)
	
	for chunk in doc.chunks:
		chunk.buildOrthomosaic(refine_seamlines=True)
		chunk.orthomosaic.label = f"{os.path.splitext(os.path.basename(doc.path))[0]}{chunk.label}"

def get_ortho_export_resolution(max_res)->float:
	
	# Calculates the resolution to use when exporting orthomosaics. Resolution is calculated as the ceiling of the fourth binary digit of
	# the max_res value.

	# NB: it is important for pixel alignment that all orthomosaics for a particular orientation use the exact same export resolution.

	# Returns:
	# 	The export resolution for all orthomosaics (in meters).
	
	shifted_number = max_res * (10**4)
	ceiling_shifted_number = math.ceil(shifted_number)
	export_resolution = ceiling_shifted_number / (10**4)
	return export_resolution

def get_max_ortho_resolution()->float:

	# get the largets resolution value for the orthmosaics in all the chunks.

	max_resolution = 0.0
	for chunk in doc.chunks:
		ortho_res = chunk.orthomosaic.resolution
		if(ortho_res > max_resolution):
			max_resolution = ortho_res
	return max_resolution

def export_orthomsaics():

	
	# Writes the orthomosaics (all chunks) with approprariate raster transforms where necessary
	
	raster_transform_params = {
				 "BackIrIr": {"transform": Metashape.RasterTransformType.RasterTransformNone},
				 "BackUvUv": {"transform": Metashape.RasterTransformType.RasterTransformPalette,
				 				"formula":["B1*2.6"], 
								"LUT": "Gray", 
								"range":(100.0, 600.0)},
				 "BackUvVis": {"transform": Metashape.RasterTransformType.RasterTransformPalette,
								"formula":["B1/3"], 
								"LUT": "Gray", 								
								"range":(0.0, 70.0)},
				 "BackUvVis": {"transform": Metashape.RasterTransformType.RasterTransformPalette,
				 				"formula":["(B1*.6)/256", "(B2*.6)/256", "(B1*.3)/256"], 
								"LUT": "False Color", 
								"range":(0.0, 0.3)}, 
				 "BackVisIr": {"transform": Metashape.RasterTransformType.RasterTransformPalette,
				 				"formula":["B1*2.5"], 
				 				"LUT": "Gray", 
								"range":(66.0, 600)},
				 "BackVisVis": {"transform": Metashape.RasterTransformType.RasterTransformNone},
				 "FrontIrIr": {"transform": Metashape.RasterTransformType.RasterTransformNone},
				 "FrontUvUv": {"transform": Metashape.RasterTransformType.RasterTransformPalette,
				 				"formula":["B1*2.6"], 
								"LUT": "Gray", 
								"range":(100.0, 600.0)},
				 "FrontUvVis": {"transform": Metashape.RasterTransformType.RasterTransformPalette,
								"formula":["B1/3"], 
								"LUT": "Gray", 								
								"range":(0.0, 70.0)},
				 "FrontUvVis": {"transform": Metashape.RasterTransformType.RasterTransformPalette,
				 				"formula":["(B1*.6)/256", "(B2*.6)/256", "(B1*.3)/256"], 
								"LUT": "False Color", 
								"range":(0.0, 0.3)}, 
				 "FrontVisIr": {"transform": Metashape.RasterTransformType.RasterTransformPalette,
				 				"formula":["B1*2.5"], 
				 				"LUT": "Gray", 
								"range":(66.0, 600.0)},
				 "FrontVisVis": {"transform": Metashape.RasterTransformType.RasterTransformNone}
				 } 

	max_ortho_res = get_max_ortho_resolution()
	export_res = get_ortho_export_resolution(max_ortho_res)

	# set compression values
	compression = Metashape.ImageCompression()
	compression.jpeg_quality = 99
	compression.tiff_compression = Metashape.ImageCompression.TiffCompression.TiffCompressionLZW

	#export all the orthomosaics
	for chunk in doc.chunks:
		
		ortho_path = os.path.join(output_folder, f"{chunk.orthomosaic.label}.tif")

		# get the export params
		params =  raster_transform_params.get(chunk.label, None)
		if params is None:
			raise Exception("no transform params for chunk {chunk.label}")

		# set the transform type from params
		transform_type = params.get("transform", Metashape.RasterTransformType.RasterTransformNone)


		if transform_type == Metashape.RasterTransformType.RasterTransformNone:
			chunk.raster_transform.enabled = False
		else:
			chunk.raster_transform.formula = params["formula"]
			chunk.raster_transform.range = params["range"]
			if params["LUT"] == "False Color":
				chunk.raster_transform.false_color = [0,1,2]
			else:
				chunk.raster_transform.palette = {0.0: (0, 0, 0), 1.0: (255, 255, 255)}
			chunk.raster_transform.interpolation = True 
			chunk.raster_transform.enabled = True

		print(f"writing ortho: {chunk.orthomosaic.label} to {ortho_path}")
		chunk.exportRaster(path=ortho_path, 
							source_data=Metashape.DataSource.OrthomosaicData,
							image_format=Metashape.ImageFormat.ImageFormatTIFF, 
							image_compression=compression, 
							resolution = export_res,
							raster_transform=transform_type,
							save_alpha=False, 
							white_background=False)


initialize()
check_markers()
align_chunks()
build_and_distribute_models()
import_coloring_images()
build_orthmosaics()
export_orthomsaics()

doc.save()
