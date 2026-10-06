"""Shared helpers for the exploration scripts. Not part of the service."""

import json
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "experiments" / "output"
SAMPLES = {
    "sample1": "sample1.png",
    "sample2": "sample2.jpg",
    "sample3": "sample3.png",
    "sample4": "sample4.png",
}


def load_image(sample):
    return cv2.imread(str(ROOT / "samples" / SAMPLES[sample]), cv2.IMREAD_COLOR)


def load_truth(sample):
    path = ROOT / "eval" / "ground_truth" / f"{sample}.json"
    return json.loads(path.read_text())["boxes"]
