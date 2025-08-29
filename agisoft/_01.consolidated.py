# -*- coding: utf-8 -*-
"""
Import images from the .\input folder to correct chunks in an existing Metashape project file and generate orthomosaics

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
- To install packages:  (e.g. cv2)
	> %PROGRAM_FILES%\Agisoft\Metashape\python\python.exe -m pip install python_module_name (e.g., opencv-python)
		[if Metashape is active, restart it to make sure the dependency has been added ]
"""
import Metashape, math, sys, os, cv2
import numpy as np 

# numpy color channel constants
NUMPY_BLUE = 0 
NUMPY_GREEN = 1
NUMPY_RED = 2 
RGB = 4  # special code for RGB images

# fraction of least good points to be removed on each iteration of refine_tiepoints. 
# Value is on  a scale of 0-1 (here we remove 0.1 which is equivalent to 10% of the total points)
DISCARD_FRACTION = 0.1

doc: Metashape.Document
input_folder: str
ntp_start = 0



#  Holds information on the known distance between points for different scale bars
class ScaleBarInfo:

    # Constructor
    #     target1_marker_num: number of the first target
    #     target2_marker_num: number of the second target
    #     distance_in_meters: the length of the marker in meters

    def __init__(self, target1_marker_num, target2_marker_num, distance_in_meters):
        self.target1_name = "target " + str(target1_marker_num)
        self.target2_name = "target " + str(target2_marker_num)
        self.distance_in_meters = distance_in_meters
    
    # stringify this ScaleBarInfo
    def __str__(self):
        return  f"{self.target1_name}_{self.target2_name}: {self.distance_in_meters}  m"
    
    # return the scale bar's label
    def label(self):
        return  f"{self.target1_name}_{self.target2_name}"
        

# List of known scale bars
class ScaleBarList:

    # Constructor
    # Initializes the known_scale_bars list
    def __init__(self):
        # list of ScaleBarInfo items representing our known scale bars
        self._known_scale_bars = []        
        # make list of known scale distances on our coded scale bars
        #self._known_scale_bars.append(ScaleBarInfo(1, 3, 1.000023))
        self._known_scale_bars.append(ScaleBarInfo(4, 6, 0.50013))
        self._known_scale_bars.append(ScaleBarInfo(7, 8, 0.25004))
        #self._known_scale_bars.append(ScaleBarInfo(9, 11, 1.000016))
        #self._known_scale_bars.append(ScaleBarInfo(12, 14, 0.50000))
        self._known_scale_bars.append(ScaleBarInfo(15, 16, 0.24989))
        #self._known_scale_bars.append(ScaleBarInfo(15, 50, 0.16109))
    
    # return a scale bar (if we know of one) that starts with first_target_label
    #     first_target_label: the Metashape.marker.label we are trying to match
    #    returns: the matching ScaleBarInfo object, or 'None' if no match is found
    def getScaleBarStartingWith(self, first_target_label):
        # look for first target label (or 'None' if we can't find a match)
        info = next( (x for x in self._known_scale_bars if x.target1_name == first_target_label), None)
        return info

def initialize():
	global doc, input_folder
	
	doc = Metashape.app.document
	doc_folder = os.path.dirname(doc.path)
	input_folder = os.path.join(doc_folder, "_input")
	
	if not os.path.exists(input_folder):
		raise Exception("=== no input folder ===")
	
	doc.remove(doc.chunks)  # remove any existing chunks

def check_photos_counts():
	
	# check that there are the same number of photos for each camera position where we took multiple images

	cameras_with_same_band = { "BackUvUv": "BackUvVis", # BackUvUv should be at the same position as BackUvVis
							  "BackVisIr": "BackVisVis", # ditto for BackVisIr and BackVisVis
							  "FrontUvUv": "FrontUvVis", # ditto for FrontUvUv and FrontUvVis
							  "FrontVisIr": "FrontVisVis", # ditto for FrontVisIr and FrontVisVis
							}

	for band1_name in cameras_with_same_band.keys():
		band1_filenames_contain = f"{band1_name}0"
		band1_files = [f for f in os.listdir(input_folder) if band1_filenames_contain in f]
		band1_files_count = len(band1_files)

		band2_name = cameras_with_same_band[band1_name]
		band2_filenames_contain = f"{band2_name}0"
		band2_files = [f for f in os.listdir(input_folder) if band2_filenames_contain in f]
		band2_files_count = len(band2_files)

		print(f"{band1_name}: {band1_files_count} images | {band2_name}: {band2_files_count} images")

		if band2_files_count != band1_files_count:
			err_msg = f"check_photos_counts(): image counts do not match for [{band1_name}] and [{band2_name}]\n\n" \
			 f"- [{band1_name}] has {band1_files_count} images, while [{band2_name}] has {band2_files_count} image."
			raise Exception(err_msg)

def optimize_cameras(chunk:Metashape.Chunk, isFinal=False):

	# Put the camera optimization in a block, because it is unwieldy
	# isFinal: boolean value for some of the less important fitting variables (set this value to True on the last optimization) 

	r = chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=isFinal, fit_b2=isFinal, fit_k1=True,
							  fit_k2=True, fit_k3=True, fit_k4=isFinal, fit_p1=True, fit_p2=True, fit_p3=isFinal,
							  fit_p4=isFinal, adaptive_fitting=False, tiepoint_covariance=False)

def optimize_tiepoints(chunk:Metashape.Chunk, filter_type, while_value, desired_value):

	# Ooptimizes tie points.
	#    chunk: the Metashape.Chunk we are operating on
	#	 filter type: one of the Metashape.TiePoints.Filter criterion values
	#    while_value: fraction of the ntp_start points below which we are are not willing to go.
	#    desired_value: the criterion threshold (we want to reduce the value for this filter type <= this value)

	global ntp_start
	
	tp = chunk.tie_points
	ntp_remaining = ntp_start 
	f = Metashape.TiePoints.Filter() # global filter for TiePoints object
	
	while(ntp_remaining > while_value * ntp_start):
		
		
		f.init(tp, filter_type)
		
		values = f.values.copy()
		values.sort(reverse=True)
		
		print("- filter max value:", values[0])
		
		# exit the while loop if the filter value < desired_value
		if values[0] <= desired_value:
			break
		
		thresh = values[int(len(values)*DISCARD_FRACTION)]
		
		f.selectPoints(thresh)
		
		tp.removeSelectedPoints()
		
		ntp_remaining = len(tp.points)
		print("- remaining points:", ntp_remaining)
		
		# camera optimization after point deletion
		optimize_cameras(chunk, False)

def get_chunk(label:str)->Metashape.Chunk:
	
	# get a chunk by its label name

	global doc

	for chunk in doc.chunks:
		if chunk.label == label:
			return chunk
	return None
	
# from Aphoma.photogrammetry.ModelHelpers.py by Kea Johnston
def set_chunk_accuracy(chunk):

    """sets the acuracy value for the chunk. This code is derived from JP Brown's script for detecting 12 bit markers. def detect_12bit_markers.
    Parameters:
    -----------
    chunk: the Metashape.chunk with scalebars & markers.
    """
     # set accuracy values for markers and scale bars in the chunk
    chunk.tiepoint_accuracy = 0.25 # pixels 
    chunk.marker_projection_accuracy = 0.5 # pixels
    chunk.marker_location_accuracy = Metashape.Vector( (1.0e-5, 1.0e-5, 1.0e-5) ) # meters (= 0.01 mm)
	


# from Aphoma.photogrammetry.ModelHelpers.py by Kea Johnston
def getNumberedTarget(targetnumber:int, chunk)->Metashape.Marker:
    name = f"target {targetnumber}"
    desiredmarker = None
    for marker in chunk.markers:
        if marker.label ==name:
            desiredmarker = marker
            break
    return desiredmarker

# from Aphoma.photogrammetry.util.py by Kea Johnston
def load_palettes():
    """Loads MarkerPalettes.json and returns a dictionary of different palettes.
    Different marker palettes may be used while doing photo capture in order to perform various calculations at the 
    model building stage. The palette used is specified in config.json->photogrammetry-> palette, which is used as a key to locate
    the specific data needed for each palette. This data is stored in MarkerPalettes.json
    """

    #going to hardcode this path for now. Maybe come back and configure it.
    palette = {}
    with open(Path(Path(__file__).parent,"MarkerPalettes.json"), encoding = "utf-8") as f:
        palette = json.load(f)
    return palette["palettes"]

# from Aphoma.photogrammetry.ModelHelpers.py by Kea Johnston
def find_axes_from_markers(chunk, palette:str):
    """Given a chunk with a model on it, and detected markers, use the palette definiton to try to figure out the x, y and z axes.
    
    Parameters:
    -------------
    chunk: the chunk on which we are operating.
    pallette: tha name of the palette we are using for this model. Get it from config.json.

    returns: a list of unit vectors corresponding to x,y, and z axes.
    """

    if not chunk.markers:
        print("No marker palette defined or markers detected. Cannot detect orientation from palette.")
        return []
    xaxis = []
    yaxis = []
    markers = chunk.markers
    markers.reverse() #generally higher numbers are on the inside, so search from inside out.
    for m in markers:
        if not m.position==None:
            lookforlabel = (int)(m.label.split()[1]) #get the number of the label to look for it in the list of axes.
            if lookforlabel in palette["axes"]["xpos"] or lookforlabel in palette["axes"]["xneg"]:
                xaxis.append(m.position)
            if lookforlabel in palette["axes"]["zpos"] or lookforlabel in palette["axes"]["zneg"]:
                zaxis.append(m.position)
            if len(xaxis)>=2 and len(zaxis)>=2:
                break
    if len(xaxis)<2 or len(zaxis) <2:
        print("Not enough data to determine x and z axes.")
        return []
    ux = (xaxis[1]-xaxis[0])
    uy = (zaxis[1]-zaxis[0])
    zaxis = Metashape.Vector.cross(uz,ux)
    ux.normalize()
    uy.normalize()
    zaxis.normalize()
    return [ux, uy, zaxis]

def import_alignment_images(chunk_label: str, img_from: str, make_grayscale: bool, color_channel: int, brightness=1.0):
	
	# Create chunk, set accuracy, create initial alignment images and copy to subfolders, and then assign the images from the subfolder to 
	# the specified chunk in the Metashape project.

	# NB:  the images we are importing are *alignment* images - images which will be used to create the sparse cloud alignment for the chunk. 
	# The alignment images may subsequently be over-written with different images (shot from the same camera position) for coloring the orthomosaic.
	
	# Parameters:
	# -----------
	# 	chunk_label: the label for the chunk to which we will import images 
	# 	img_from: the pattern for the files to import
	# 	make_grayscale: whether to make the alignment images are grayscale
	# 	color_channel: which color channel to write in the alignment images (NUMPY_BLUE, NUMPY_GREEN, or NUMPY_RED for 8-bit grayscale, RGB for rgb grayscale)
	# 	brightness: any modification of brightness for the pixel values. The brightness is expressed on a scale of 0.0 - 1.0 (default is 1.0)
	
	global input_folder, doc

	chunk = doc.addChunk()
	
	if not chunk:
		print(f"Chunk {chunk_label} not created.")
		return

	chunk.label = chunk_label
	set_chunk_accuracy(chunk)

	from_filenames_contain = f"{img_from}0"
	from_files = [f for f in os.listdir(input_folder) if from_filenames_contain in f]
	
	if not from_files:
		print(f"No files found for chunk {chunk.label}.")
		return
	
	# create folder for new files
	# to_folder = os.path.join(output_folder, chunk_label)
	to_folder = os.path.join(input_folder, chunk_label)
	if not os.path.exists(to_folder):
		os.makedirs(to_folder)

	# list of files to add to the chunk
	files_to_add = list()

	# open input files, modify them if neccesary, and copy them to the new folder
	for f in from_files:

		# open original RGB color image
		file_path_in = os.path.join(input_folder, f)
		img_in = cv2.imread(file_path_in)
		if img_in is None:
			print(f"Error reading image {file_path_in}. Skipping.")
			continue

		# if needed, convert image to single channel grayscale, or RGB grayscale
		img_out = img_in
		if make_grayscale:
			if color_channel == RGB:
				# convert color image to 3-channel grayscale
				# - we do it this way if we need a 3-channel RGB image for coloring

				# img_out = cv2.cvtColor(img_in, COLOR_BGR2GRAY) <- results are too dark
				blue_channel = img_in[:, :, NUMPY_BLUE] # create grayscale from just the blue channel
				img_out = np.zeros_like(img_in)
				img_out[:,:,0] = blue_channel
				img_out[:,:,1] = blue_channel
				img_out[:,:,2] = blue_channel
			else: 
				# single channel grayscale conversion
				img_out = img_in[:, :, color_channel]
		
		# if needed, modify brightness
		if( brightness != 1.0):
			#TODO: check if we need to control clipping
			img_out = cv2.multiply(img_out, brightness)

		#TODO: copy exif data to new image file. The following stackoverflow code looks promising...
		# https://stackoverflow.com/questions/72544252/python-copy-exif-data-from-one-image-to-other

		# create new file with correct (although currently spurious) file name
		to_file_name = f.replace(img_from, chunk_label)
		to_file_path = os.path.join(to_folder, to_file_name)
		cv2.imwrite(to_file_path, img_out)
		print(f"saved image to {to_file_path}")

		# add the new file to the list of files to add to the chunk
		if not os.path.exists(to_file_path):
			raise Exception(f"import_alignment_images(): error saving image {to_file_path}.")
			
		files_to_add.append(to_file_path)

		
	# add the accumulated images to the chunk
	chunk.addPhotos(files_to_add) # add the photos to the chunk
	print(f"Imported {len(files_to_add)} photos into chunk {chunk_label} from folder {to_folder}.")

	# update camera info
	for cam in chunk.cameras:
		cam.sensor.type = Metashape.Sensor.Type.Frame
		cam.sensor.label = "NIKON D610, 60.0 mm f/4.0 (60mm)"
		cam.sensor.pixel_height = 0.0059701 # mm
		cam.sensor.pixel_width = 0.0059701  # mm
		cam.sensor.focal_length = 60 # mm focal length 
		#cam.sensor.meta =  {'Exif/BodySerialNumber': '3000888', 'Exif/LensModel': '60.0 mm f/4.0', 'Exif/Make': 'NIKON CORPORATION', 'Exif/Model': 'NIKON D610', 'Exif/Software': 'Adobe Photoshop cam Raw 9.1.1 (Windows)'}
		cam.sensor.height = 4016 # pixels
		cam.sensor.width = 6016 # pixels

def import_iniital_aligment_photos():

	# import initial alignment photos

	# params for alignment images to be generated
	alignment_image_params = {
					"BackIrIr": {"img_from":"BackIrIr", "make_grayscale":True, "color_channel":NUMPY_BLUE}, 
					"BackUvUv": {"img_from":"BackUvVis", "make_grayscale":True, "color_channel":NUMPY_BLUE, "brightness":1.9},
					"BackUvVis": {"img_from":"BackUvVis", "make_grayscale":True, "color_channel":RGB, "brightness":1.9},
					"BackVisIr": { "img_from":"BackVisVis", "make_grayscale":True, "color_channel":NUMPY_BLUE},
					"BackVisVis": {"img_from":"BackVisVis", "make_grayscale":False, "color_channel":RGB},
					"FrontIrIr": {"img_from":"FrontIrIr", "make_grayscale":True, "color_channel":NUMPY_BLUE},
					"FrontUvUv": {"img_from":"FrontUvVis", "make_grayscale":True, "color_channel":NUMPY_BLUE, "brightness":1.9},
					"FrontUvVis": {"img_from":"FrontUvVis", "make_grayscale":True, "color_channel":RGB, "brightness":1.9},
					"FrontVisIr": {"img_from":"FrontVisVis", "make_grayscale":True, "color_channel":NUMPY_BLUE},
					"FrontVisVis": {"img_from":"FrontVisVis", "make_grayscale":False, "color_channel":RGB}
					}

	for chunk_label in alignment_image_params.keys():
		params = alignment_image_params[chunk_label]
		img_from = params.get("img_from")
		make_grayscale = params.get("make_grayscale")
		color_channel = params.get("color_channel")
		brightness = params.get("brightness", 1.0)

		import_alignment_images(chunk_label, img_from, make_grayscale, color_channel, brightness)

def align_cameras():
	
	# align cameras
	
	global doc

	for chunk in doc.chunks:
		if len(chunk.cameras) == 0:
			continue
		chunk.matchPhotos(downscale=2, generic_preselection=True, reference_preselection=False, tiepoint_limit=20000, reset_matches=True)
		chunk.alignCameras()

def refine_alignment():
	
	# refine camera alignment
	
	global doc, ntp_start

	for chunk in doc.chunks:
		if len(chunk.cameras) == 0:
			continue
		optimize_cameras(chunk, False)

		ntp_start = len(chunk.tie_points.points)

		# optimize reconstruction uncertainty 
		# - do not continue if we are at 50% or less of the initial tie points.
		# - stop if the reconstruction uncertainty value is <= 10
		print("- Optimizing reconstruction uncertainty:")
		optimize_tiepoints(chunk, Metashape.TiePoints.Filter.ReconstructionUncertainty, 0.5, 10)

		# optimize the reprojection error
		# - do not continue if we are at 25% or less of the initial tie points.
		# - stop if the reprojection error is <= 0.3
		print("- Optimizing Reprojection Error:")
		optimize_tiepoints(chunk, Metashape.TiePoints.Filter.ReprojectionError, 0.25, 0.3)

		#final optimization
		optimize_cameras(chunk, True)

def detect_markers():

	# create targets and scalebars in all chunks

	global doc

	for chunk in doc.chunks:
		
		# remove any old markers
		if chunk.markers is not None and len(chunk.markers):
			chunk.remove(chunk.markers)
		
		chunk.detectMarkers()
		
		# bail if we have no markers
		if len(chunk.markers) ==  0:
			raise Exception(f"detect_markers(): no markers detected in chunk {chunk.label}")
			
		else:
			print("== found markers ==")

		# update markers
		chunk.refineMarkers()


def assign_scalebars():

	# for the [Back|Front]VisVis chunks: iterate over the markers, looking for known scale bars with matching target names
	
	our_scalebars = ScaleBarList()
	for chunk_label in ["BackVisVis", "FrontVisVis"]:
		chunk = get_chunk(chunk_label)
		for count, m1 in enumerate(chunk.markers):
			
			print(f"- {m1}")
			
			# see if we have a known first marker target
			matching_scalebar = our_scalebars.getScaleBarStartingWith(m1.label) 
			
			# if we don't have a scale bar whose first target label == m1.label, continue to the next marker 
			if (matching_scalebar == None):
				continue
				
			# check for second marker target
			m2 = next( (x for x in chunk.markers if x.label == matching_scalebar.target2_name), None)  
			
			# if we can't find the end label for our scale bar, continue to the next marker 
			if (m2 == None):
				continue
			
			print(f"- - found scale bar {matching_scalebar.label}")
			
			# create scale bar
			new_scalebar = chunk.addScalebar(m1, m2)
			new_scalebar.reference.distance = matching_scalebar.distance_in_meters
			new_scalebar.reference.accuracy = 1.0e-5
			new_scalebar.reference.enabled = True

		# now we have scale bars, we should be able to rescale the sparse cloud
		optimize_cameras(chunk, True) # update to set the scale

initialize()
check_photos_counts()
import_iniital_aligment_photos()
align_cameras()
refine_alignment()
detect_markers()
assign_scalebars()

Metashape.app.update()
doc.save()

print("Now straighten FrontVisVis and align BackVisVis")


"""
#TODO: does not reliably straighten the chunk - currently not bad, but not great...
# straighten BackVisVis.

# from: https://www.agisoft.com/forum/index.php?topic=13561.0
def cross(a,b):
	result = Metashape.Vector([a.y*b.z - a.z*b.y, a.z*b.x - a.x*b.z, a.x*b.y - a.y *b.x])
	return result.normalized()

def get_marker(label):
	global chunk
	for marker in chunk.markers:
		if marker.label == label:
			return marker
	return None

# adapted from: https://www.agisoft.com/forum/index.php?topic=13561.0
def straighten_chunk(chunk):
	m1 = get_marker("target 8")  # m1 is origin
	m2 = get_marker("target 16") # m1 to m2 is x-axis (marker 8 to marker 16)
	m3 = get_marker("target 7")  # m1 to m3: y-axis (marker 8 to marker 7)

	if m1 is None or m2 is None or m3 is None:
		print("could not find one of the alignment markers: ")
		print(f" - check chunk {chunk.label} for  <target 7>, <target 8>, and <target 16>")

	X = (m2.position - m1.position).normalized()
	Y = (m3.position - m1.position).normalized()
	Z = cross(X,Y)
	Y1 = -cross(X,Z)
	T = Metashape.Matrix( [[X.x,Y1.x,Z.x,0],[X.y,Y1.y,Z.y,0],[X.z,Y1.z,Z.z,0],[0,0,0,1]] ).t()
	chunk.transform.matrix = T

# get the key of a chunk by its label
def get_chunk_key(chunk_label) -> int: 
	global doc
	if doc is None:
		raise Exception("get_chunk_key(chunk_label): no document defined")
		
	
	i = 0
	for chunk in doc.chunks:
		if chunk.label == chunk_label:
			print(f"{chunk_label} key: {chunk.key}")
			return chunk.key

	return -1

# straighten BackVisVis, and align FrontVisVis to it (using markers)
def align_visvis_chunks():
	global doc 

	#straighten BackVisVis
	backvisvis = get_chunk("BackVisVis")
	straighten_chunk(backvisvis)

	# align FrontVisVis to BackVisVis using markers
	frontvisvis = get_chunk("FrontVisVis")
	frontkey = get_chunk_key(frontvisvis.label)
	backkey = get_chunk_key(backvisvis.label)

	align_list = [ frontkey, backkey ]

	doc.alignChunks(chunks=align_list, reference=backkey, method=1, fit_scale=True) 

align_visvis_chunks()
"""




