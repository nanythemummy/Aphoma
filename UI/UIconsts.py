from util.util import MaskingOptions
class UIConsts():
    MASKOPTIONS = {"No Masks":MaskingOptions.NOMASKS,
            "Context-Aware Select Droplet":MaskingOptions.MASK_CONTEXT_AWARE_DROPLET,
            "Magic Wand Droplet":MaskingOptions.MASK_MAGIC_WAND_DROPLET,
            "Otsu Thresholding":MaskingOptions.MASK_CANNY,
            "Binary Thresholding":MaskingOptions.MASK_THRESHOLDING,
            "Pot Inference":MaskingOptions.MASK_AI}