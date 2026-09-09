"""ArUco detection utilities package for the mixed media utility POC."""

from .aruco import (
    AmbiguousMarkersError,
    DegeneratePageGeometryError,
    MissingMarkersError,
    PageGeometryError,
    ScanFrameExtractionError,
    UnsupportedScanDepthError,
    build_markers_document,
    compute_page_homography,
    detect_markers,
    detector_parameters,
    extract_scan_frames,
    marker_module_size_px,
    marker_modules_per_side,
    warp_page,
)

__all__ = [
    "AmbiguousMarkersError",
    "DegeneratePageGeometryError",
    "MissingMarkersError",
    "PageGeometryError",
    "ScanFrameExtractionError",
    "UnsupportedScanDepthError",
    "build_markers_document",
    "compute_page_homography",
    "detect_markers",
    "detector_parameters",
    "extract_scan_frames",
    "marker_module_size_px",
    "marker_modules_per_side",
    "warp_page",
]
