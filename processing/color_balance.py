import cv2
import math
import numpy as np
import sys
import argparse
#This code is from DavidYKay at Github https://gist.github.com/DavidYKay/9dad6c4ab0d8d7dbf3dc#file-simple_cb-py-L14
#It is adapted from a c++ adaptation (https://www.morethantechnical.com/blog/2015/01/14/simplest-color-balance-with-opencv-wcode/) which follows the algorithm
#set forward by Jason Su at Stanford (https://web.archive.org/web/20151031210927/http://web.stanford.edu/~sujason/ColorBalancing/grayworld.html)

def apply_mask(matrix, mask, fill_value):
    masked = np.ma.array(matrix, mask=mask, fill_value=fill_value)
    return masked.filled()

def apply_threshold(matrix, low_value, high_value):
    low_mask = matrix < low_value
    matrix = apply_mask(matrix, low_mask, low_value)

    high_mask = matrix > high_value
    matrix = apply_mask(matrix, high_mask, high_value)

    return matrix

def simplest_cb(img, percent):
    assert img.shape[2] == 3
    assert percent > 0 and percent < 100

    half_percent = percent / 200.0

    channels = cv2.split(img)

    out_channels = []
    for channel in channels:
        assert len(channel.shape) == 2
        # find the low and high precentile values (based on the input percentile)
        height, width = channel.shape
        vec_size = width * height
        flat = channel.reshape(vec_size)

        assert len(flat.shape) == 1

        flat = np.sort(flat)

        n_cols = flat.shape[0]

        low_val  = flat[math.floor(n_cols * half_percent)]
        high_val = flat[math.ceil( n_cols * (1.0 - half_percent))]

        print(f"Lowval:  {low_val}")
        print(f"Highval: {high_val}")

        # saturate below the low percentile and above the high percentile
        thresholded = apply_threshold(channel, low_val, high_val)
        # scale the channel
        normalized = cv2.normalize(thresholded, thresholded.copy(), 0, 255, cv2.NORM_MINMAX)
        out_channels.append(normalized)

    return cv2.merge(out_channels)

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(prog="color_correct")
    parser.add_argument("inputstr", help="file to operate on",type=str)
    args =parser.parse_args()

    img = cv2.imread(args.inputstr)
    print(img)
    out = simplest_cb(img, 1)
    cv2.imshow("before", img)
    cv2.imshow("after", out)
    cv2.waitKey(0)