from PIL import Image
from pathlib import Path
import sys
import argparse
import cv2
import numpy as np
#this was vibecoded with chatgpt and copilot. Clean it up before it goes anywhere real.
def boolean_intersection_bw(image_path1, image_path2, output_path):
    """
    Takes two image file paths, converts them to black and white, and creates a new image that is the boolean intersection of every pixel.
    If a pixel is white in both images, it will be white in the output; otherwise, it will be black.
     saves the result to output_path if provided.
    Returns the resulting PIL Image object.
    """
    # Open and convert both images to black and white (mode '1' or 'L')
    img1 = Image.open(image_path1).convert('1')
    img2 = Image.open(image_path2).convert('1')

    # Ensure both images are the same size
    if img1.size != img2.size:
        raise ValueError("Input images must have the same dimensions.")

    # Perform boolean intersection (logical AND)
    result = Image.new('1', img1.size)
    pixels1 = img1.load()
    pixels2 = img2.load()
    result_pixels = result.load()

    for y in range(img1.size[1]):
        for x in range(img1.size[0]):
            # Both must be white (255) to be white in output
            result_pixels[x, y] = 255 if (pixels1[x, y] == 255 and pixels2[x, y] == 255) else 0

    if output_path:
        result.save(Path(output_path))
    return result

def focus_mask(image_path, output_dir):
    """
    Takes a path to an image and a path to a folder to save the output image in.
    Selects the area of the image that is in focus (using a Laplacian-based focus measure),
    colors that area white, and the rest black. Saves the result in the output directory.
    """
    image_path = Path(image_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read image in grayscale
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Compute Laplacian (focus measure)
    laplacian = cv2.Laplacian(img, cv2.CV_64F)
    focus_map = np.abs(laplacian)

    # Threshold: pixels with high focus measure are in focus
    threshold = np.percentile(focus_map, 90)  # Top 10% most focused
    mask = (focus_map >= threshold).astype(np.uint8) * 255

    # Save mask as output (white=in focus, black=not in focus)
    output_path = output_dir / (image_path.stem + '.png')
    cv2.imwrite(str(output_path), mask)
    return output_path

def foreground_mask(input_path, output_path):
    """
    Takes an input image path and an output path. Selects the foreground of the image,
    colors it white, the background black, and saves the result as a PNG to output_path.
    """
    input_path = str(input_path)
    output_path = str(output_path)

    # Read image
    img = cv2.imread(input_path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {input_path}")

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Use Otsu's thresholding to separate foreground and background
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Optional: Invert mask if background is white and foreground is dark
    # If the mean of the mask is closer to 255, invert it
    if np.mean(mask) > 127:
        mask = cv2.bitwise_not(mask)

    # Save the mask as a PNG
    cv2.imwrite(output_path, mask)
    return output_path

def main():
    parser = argparse.ArgumentParser(description="Perform boolean intersection on pairs of black and white images from two folders.")
    parser.add_argument('images1_folder', help='Path to the first images folder')
    parser.add_argument('images2_folder', help='Path to the second images folder')
    parser.add_argument('output_folder', help='Path to the output folder')
    args = parser.parse_args()

    images1_folder = Path(args.images1_folder)
    images2_folder = Path(args.images2_folder)
    output_folder = Path(args.output_folder)

    output_folder.mkdir(parents=True, exist_ok=True)

    files1 = sorted([f for f in images1_folder.iterdir() if f.is_file()])
    files2 = sorted([f for f in images2_folder.iterdir() if f.is_file()])


    if len(files1) != len(files2):
        print("Error: The two folders must have the same number of files.")
        sys.exit(1)

    for i, file1 in enumerate(files1):
        if files2[i].stem != file1.stem:
            print(f"Error: File {file1.stem} not found in both folders.")
            sys.exit(1)
        file2 = files2[i]
        output_path = output_folder / f"{file1.stem}.png"
        boolean_intersection_bw(str(file1), str(file2), str(output_path))
        print(f"Processed {file1.name}")

def main_foreground_mask():
    parser = argparse.ArgumentParser(description="Create foreground masks for all JPG images in a folder.")
    parser.add_argument('input_folder', help='Path to the input folder containing JPG images')
    parser.add_argument('output_folder', help='Directory to save the output masks')
    args = parser.parse_args()

    input_folder = Path(args.input_folder)
    output_folder = Path(args.output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    jpg_files = sorted([f for f in input_folder.iterdir() if f.is_file() and f.suffix.lower() == '.jpg'])
    if not jpg_files:
        print(f"No JPG files found in {input_folder}")
        return

    for img_file in jpg_files:
        output_path = output_folder / (img_file.stem + '.png')
        foreground_mask(str(img_file), str(output_path))
        print(f"Foreground mask saved to {output_path}")

def main_focus_mask():
    parser = argparse.ArgumentParser(description="Create focus masks for all JPG images in a folder.")
    parser.add_argument('input_folder', help='Path to the input folder containing JPG images')
    parser.add_argument('output_folder', help='Directory to save the output masks')
    args = parser.parse_args()

    input_folder = Path(args.input_folder)
    output_folder = Path(args.output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    jpg_files = sorted([f for f in input_folder.iterdir() if f.is_file() and f.suffix.lower() == '.jpg'])
    if not jpg_files:
        print(f"No JPG files found in {input_folder}")
        return

    for img_file in jpg_files:
        output_path = output_folder / (img_file.stem + '.png')
        focus_mask(str(img_file), str(output_folder))
        print(f"Focus mask saved to {output_path}")

if __name__ == "__main__":
    main()
