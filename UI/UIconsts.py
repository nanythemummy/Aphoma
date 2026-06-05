from util.util import MaskingOptions
class UIConsts():
    MASKOPTIONS = {"No Masks":MaskingOptions.NOMASKS,
            "Context-Aware Select Droplet":MaskingOptions.MASK_CONTEXT_AWARE_DROPLET,
            "Binary Thresholding":MaskingOptions.MASK_THRESHOLDING,
            "Pot Inference":MaskingOptions.MASK_AI}