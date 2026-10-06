from dataclasses import dataclass


@dataclass(frozen=True)
class Params:
    # Shortest straight stroke kept, px; stable from 12 to 20 on samples, breaks below 12.
    # TODO(prod): scale line_length with the typical box size in a second pass
    line_length: int = 12
    # Extension at each stroke end, px; closes corners of thin or grey borders.
    corner_gap: int = 2
    # Minimum hole area relative to its bounding box area.
    rectangularity: float = 0.85
    # Maximum outward growth per side, px; thickest printed border seen is 4 px.
    max_border: int = 8
    # Minimum outer box side, px.
    min_side: int = 12
    # Maximum outer box side, px.
    max_side: int = 120
    # Minimum width / height; sample boxes range from 1.0 to 1.25.
    min_aspect: float = 0.6
    # Maximum width / height.
    max_aspect: float = 1.8
    # Minimum inner side / outer side.
    min_interior: float = 0.7
    # Relative size difference; most sensitive parameter, constrained only by sample1.
    size_tolerance: float = 0.15
    # Share of each side skipped when measuring interior ink.
    interior_inset: float = 0.20
    # Checked above this fill ratio; same result from 0.02 to 0.10 on samples.
    # Empty boxes measure 0.000; the faintest mark measures 0.156.
    checked_threshold: float = 0.08
