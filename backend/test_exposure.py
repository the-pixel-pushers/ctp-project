
import cv2
import sys
from pathlib import Path
from detectors.exposure import detect_exposure


def main():
    if len(sys.argv) < 2:
        print("Usage: python backend/test_exposure.py <image_path>")
        return

    image_path = Path(sys.argv[1])

    if not image_path.is_file():
        print(f"Image not found: {image_path}")
        return

    image = cv2.imread(str(image_path))

    if image is None:
        print("Unable to read the image.")
        return

    result = detect_exposure(image)

    print("\n--- PhotoSort Exposure Detection ---")
    print(f"Image: {image_path.name}")
    print(f"Classification: {result['classification']}")
    print(f"Average brightness: {result['average_brightness']}")
    print(f"Highlight ratio: {result['highlight_ratio']:.2%}")
    print(f"Shadow ratio: {result['shadow_ratio']:.2%}")


if __name__ == "__main__":
    main()
