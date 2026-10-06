import os

# OpenCV reads this once, when its native library is imported.
os.environ["OPENCV_IO_MAX_IMAGE_PIXELS"] = "40000000"
