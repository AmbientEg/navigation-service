"""
Coordinate Reference System (CRS) transformation and validation utilities.

This module provides functions for:
- Converting between WGS84 (EPSG:4326) and UTM coordinate systems
- Detecting and validating coordinate systems
- Normalizing coordinates for database storage

Policy:
- All geometries persisted to DB use WGS84 (EPSG:4326) with SRID=4326.
- Pipeline operations can work in UTM (EPSG:32636) for metric accuracy.
- Edge distances are stored in meters.
- Runtime inputs must be in WGS84 (lat/lng).
"""

from typing import Tuple, Literal, Optional, Any
import logging

try:
    from pyproj import Transformer, CRS
    PYPROJ_AVAILABLE = True
except ImportError:
    # Keep symbols defined so runtime type annotations do not fail at import time.
    Transformer = Any
    CRS = Any
    PYPROJ_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# CRS Constants
# ============================================================================
WGS84_EPSG = 4326
WGS84_PROJ = "EPSG:4326"

# Default UTM zone for project location (East Africa region)
DEFAULT_UTM_ZONE = 36
UTM_EPSG_TEMPLATE = 32600 + DEFAULT_UTM_ZONE  # EPSG:32636
UTM_PROJ_TEMPLATE = f"EPSG:{UTM_EPSG_TEMPLATE}"

# Valid WGS84 ranges
WGS84_LAT_MIN, WGS84_LAT_MAX = -90.0, 90.0
WGS84_LNG_MIN, WGS84_LNG_MAX = -180.0, 180.0

# UTM coordinate ranges for zone 36 (approximate bounds for East Africa)
# Zone 36 covers ~30°E to 36°E longitude
UTM_X_MIN, UTM_X_MAX = 166000.0, 833000.0  # Typical UTM easting bounds
UTM_Y_MIN, UTM_Y_MAX = -2_000_000.0, 10_000_000.0  # Very wide range for y


# ============================================================================
# Transformer Cache
# ============================================================================
_transformer_utm_to_wgs84: Optional[Transformer] = None
_transformer_wgs84_to_utm: Optional[Transformer] = None


def _get_utm_to_wgs84_transformer() -> Transformer:
    """
    Get cached transformer for UTM → WGS84.
    Lazy initialization to defer pyproj import errors.
    """
    global _transformer_utm_to_wgs84
    if _transformer_utm_to_wgs84 is None:
        if not PYPROJ_AVAILABLE:
            raise ImportError("pyproj is required for CRS transformations. Install: pip install pyproj")
        _transformer_utm_to_wgs84 = Transformer.from_crs(
            CRS.from_epsg(UTM_EPSG_TEMPLATE),
            CRS.from_epsg(WGS84_EPSG),
            always_xy=True  # Always return (x, y) = (lng, lat) order
        )
    return _transformer_utm_to_wgs84


def _get_wgs84_to_utm_transformer() -> Transformer:
    """
    Get cached transformer for WGS84 → UTM.
    Lazy initialization to defer pyproj import errors.
    """
    global _transformer_wgs84_to_utm
    if _transformer_wgs84_to_utm is None:
        if not PYPROJ_AVAILABLE:
            raise ImportError("pyproj is required for CRS transformations. Install: pip install pyproj")
        _transformer_wgs84_to_utm = Transformer.from_crs(
            CRS.from_epsg(WGS84_EPSG),
            CRS.from_epsg(UTM_EPSG_TEMPLATE),
            always_xy=True  # Always return (x, y) = (lng, lat) order
        )
    return _transformer_wgs84_to_utm


# ============================================================================
# Validation Functions
# ============================================================================
def looks_like_wgs84(x: float, y: float) -> bool:
    """
    Simple heuristic to detect if coordinates are likely WGS84 (lat/lng).

    WGS84 ranges: longitude [-180, 180], latitude [-90, 90].
    Returns True if both x and y fall within valid WGS84 ranges.

    Args:
        x: First coordinate (typically longitude/easting)
        y: Second coordinate (typically latitude/northing)

    Returns:
        bool: True if coordinates look like WGS84, False otherwise
    """
    try:
        x_float = float(x)
        y_float = float(y)
        is_wgs84 = (
            WGS84_LNG_MIN <= x_float <= WGS84_LNG_MAX and
            WGS84_LAT_MIN <= y_float <= WGS84_LAT_MAX
        )
        return is_wgs84
    except (TypeError, ValueError):
        return False


def looks_like_utm(x: float, y: float) -> bool:
    """
    Simple heuristic to detect if coordinates are likely UTM (easting/northing).

    UTM coordinates are typically much larger than WGS84 (e.g., 500000-700000 range).
    Returns True if x is out of WGS84 range, suggesting UTM.

    Args:
        x: First coordinate (typically easting)
        y: Second coordinate (typically northing)

    Returns:
        bool: True if coordinates look like UTM, False otherwise
    """
    try:
        x_float = float(x)
        return abs(x_float) > 180.0  # UTM x-coords are much larger
    except (TypeError, ValueError):
        return False


# ============================================================================
# Transformation Functions
# ============================================================================
def utm_to_wgs84(x: float, y: float, utm_zone: int = DEFAULT_UTM_ZONE) -> Tuple[float, float]:
    """
    Convert UTM coordinates to WGS84 (lat/lng).

    Args:
        x: UTM easting coordinate
        y: UTM northing coordinate
        utm_zone: UTM zone (default: 36 for East Africa)

    Returns:
        Tuple[float, float]: (longitude, latitude) in WGS84

    Raises:
        ImportError: If pyproj is not installed
        ValueError: If transformation fails
    """
    try:
        transformer = _get_utm_to_wgs84_transformer()
        lng, lat = transformer.transform(x, y)
        return (lng, lat)
    except Exception as e:
        logger.error(f"Failed to convert UTM ({x}, {y}) to WGS84: {e}")
        raise ValueError(f"CRS transformation failed: {e}") from e


def wgs84_to_utm(lng: float, lat: float, utm_zone: int = DEFAULT_UTM_ZONE) -> Tuple[float, float, int]:
    """
    Convert WGS84 (lat/lng) coordinates to UTM.

    Args:
        lng: Longitude in WGS84
        lat: Latitude in WGS84
        utm_zone: UTM zone (default: 36 for East Africa)

    Returns:
        Tuple[float, float, int]: (easting, northing, zone) in UTM

    Raises:
        ImportError: If pyproj is not installed
        ValueError: If transformation fails
    """
    try:
        transformer = _get_wgs84_to_utm_transformer()
        x, y = transformer.transform(lng, lat)
        return (x, y, utm_zone)
    except Exception as e:
        logger.error(f"Failed to convert WGS84 ({lng}, {lat}) to UTM: {e}")
        raise ValueError(f"CRS transformation failed: {e}") from e


# ============================================================================
# Normalization Functions
# ============================================================================
def normalize_point_for_db(
    x: float,
    y: float,
    source_crs: Literal["WGS84", "UTM"] = "UTM",
    target_crs: Literal["WGS84"] = "WGS84"
) -> Tuple[float, float]:
    """
    Normalize a coordinate point to target CRS, auto-detecting source if needed.

    This function intelligently detects the source CRS if "auto" is specified,
    then transforms coordinates to the target CRS (typically WGS84 for DB storage).

    Args:
        x: X coordinate (easting or longitude)
        y: Y coordinate (northing or latitude)
        source_crs: Source CRS - "WGS84", "UTM", or auto-detected if omitted
        target_crs: Target CRS (default: "WGS84" for database storage)

    Returns:
        Tuple[float, float]: Normalized (x, y) in target CRS

    Raises:
        ValueError: If coordinates are invalid or transformation fails
    """
    try:
        x_float = float(x)
        y_float = float(y)

        # Auto-detect source CRS if not explicitly specified
        if source_crs == "UTM" and looks_like_wgs84(x_float, y_float):
            logger.warning(
                f"Coordinates ({x_float}, {y_float}) look like WGS84 but UTM was specified. "
                "Auto-detecting as WGS84."
            )
            source_crs = "WGS84"
        elif source_crs == "WGS84" and looks_like_utm(x_float, y_float):
            logger.warning(
                f"Coordinates ({x_float}, {y_float}) look like UTM but WGS84 was specified. "
                "Auto-detecting as UTM."
            )
            source_crs = "UTM"

        # If already in target CRS, return as-is
        if source_crs == target_crs:
            return (x_float, y_float)

        # Transform from source to target
        if source_crs == "UTM" and target_crs == "WGS84":
            lng, lat = utm_to_wgs84(x_float, y_float)
            logger.debug(f"Converted UTM ({x_float}, {y_float}) → WGS84 ({lng}, {lat})")
            return (lng, lat)

        elif source_crs == "WGS84" and target_crs == "UTM":
            x_utm, y_utm, _ = wgs84_to_utm(x_float, y_float)
            logger.debug(f"Converted WGS84 ({x_float}, {y_float}) → UTM ({x_utm}, {y_utm})")
            return (x_utm, y_utm)

        else:
            raise ValueError(f"Unsupported CRS conversion: {source_crs} → {target_crs}")

    except (TypeError, ValueError) as e:
        logger.error(f"Failed to normalize point ({x}, {y}): {e}")
        raise ValueError(f"Invalid coordinate normalization: {e}") from e


def validate_wgs84_coordinates(lng: float, lat: float) -> bool:
    """
    Validate that coordinates are within valid WGS84 ranges.

    Args:
        lng: Longitude
        lat: Latitude

    Returns:
        bool: True if valid WGS84 coordinates, False otherwise
    """
    try:
        lng_float = float(lng)
        lat_float = float(lat)
        is_valid = (
            WGS84_LNG_MIN <= lng_float <= WGS84_LNG_MAX and
            WGS84_LAT_MIN <= lat_float <= WGS84_LAT_MAX
        )
        if not is_valid:
            logger.warning(f"Invalid WGS84 coordinates: lng={lng_float}, lat={lat_float}")
        return is_valid
    except (TypeError, ValueError):
        logger.warning(f"Could not validate coordinates: lng={lng}, lat={lat}")
        return False
