from enum import Enum

class ErrorCodes(Enum):
    """Class containing possible error codes for the task queue tasks"""
    NONE=0
    UNKNOWN=1
    INVALID_FILE=2
    NO_CHUNK=3
    UNALIGNED_CAMERAS = 4
    NO_TIEPOINTS = 5
    NO_MARKERS_FOUND=6
    NO_SCALEBARS_FOUND=7
    METASHAPE_FILE_LOCKED=8
    UNSUPPORTED_ALIGNMENT_TYPE=9
    NO_MODEL_FOUND = 10
    NO_TEXTURES_FOUND = 11
    NO_AXES = 12
    EXPORT_FAILURE_MODEL = 13
    NO_ORTHOMOSAIC =14
    EXPORT_FAILURE_ORTHOMOSAIC = 15
    MISSING_MARKER = 16
    MISSING_TARGET_CHUNK = 17
    BBOX_SIZE_MISMATCH = 18
    REPLACE_IMAGES_FAILURE=19
    FAILURE_TO_REMOVE_FILE = 20

    @classmethod
    def getFriendlyStrings(cls):
        return ["None", 
                "Unknown",
                "Missing or inproper files.",
                "No Chunk",
                "There are unaligned cameras.",
                "No tiepoints found",
                "No Markers Found",
                "No Scalebars Found",
                "File Locked",
                "Unsupported alignment type for configured palette.",
                "No model found",
                "No texture found",
                "Failed to find axes from markers",
                "Failed to export model.",
                "No Orthomosaic found",
                "Failed to export orthomosaic",
                "Expected marker not found.",
                "Invalid chunk specified for multichunk operation.",
                "Bounding box size mismatch.",
                "Failure to replace images in chunk.",
                "Failure to remove file or folder."]
    @classmethod
    def numToFriendlyString(cls, num): 
        if isinstance(num, ErrorCodes):
            num = num.value
        return ErrorCodes.getFriendlyStrings()[num]
    @classmethod 
    def friendlyToEnum(cls, searchstring:str):
        friendly = ErrorCodes.getFriendlyStrings()
        for i,fr in enumerate(friendly):
            if fr is searchstring:
                return ErrorCodes(i)
        return 0
    