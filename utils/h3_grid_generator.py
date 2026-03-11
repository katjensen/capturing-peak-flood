#!/usr/bin/env python3
"""
H3 Grid Generator

A Python script that creates Uber H3 grids for a variable grid size and given input geometry.
The resulting grid is saved as a geopackage file.

Author: AI Assistant
"""

import argparse
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Union, List, Optional, Dict, Any, Tuple

import geopandas as gpd
import h3
import pandas as pd
from shapely.geometry import Polygon, Point
from shapely.wkt import loads as wkt_loads


class H3GridGenerator:
    """
    A class to generate H3 hexagonal grids for given geometries.
    """
    
    # Constants for efficiency
    DEGREES_PER_KM = 1.0 / 111.0  # Approximate conversion factor
    HEXAGON_AREA_FACTOR = 2 / (3 * math.sqrt(3))  # For area to edge length conversion
    
    def __init__(self, resolution: int = 6):
        """
        Initialize the H3GridGenerator.
        
        Args:
            resolution (int): H3 resolution level (0-15). Higher values create smaller hexagons.
        """
        if not 0 <= resolution <= 15:
            raise ValueError("H3 resolution must be between 0 and 15")
        
        self.resolution = resolution
        self.logger = logging.getLogger(__name__)
        
        # Pre-calculate hexagon properties for efficiency
        self._hex_area_km2 = None
        self._edge_length_deg = None
        self._sample_spacing = None
    
    def _get_hexagon_properties(self, reference_lat: float = 0.0) -> Tuple[float, float, float]:
        """
        Calculate hexagon properties for the current resolution.
        
        Args:
            reference_lat: Reference latitude for area calculation
            
        Returns:
            Tuple of (area_km2, edge_length_deg, sample_spacing_deg)
        """
        if self._hex_area_km2 is None:
            # Use a reference point to calculate hexagon area
            sample_hex_id = h3.latlng_to_cell(reference_lat, 0.0, self.resolution)
            self._hex_area_km2 = h3.cell_area(sample_hex_id, unit='km^2')
            
            # Calculate edge length from area
            edge_length_km = math.sqrt(self._hex_area_km2 * self.HEXAGON_AREA_FACTOR)
            self._edge_length_deg = edge_length_km * self.DEGREES_PER_KM
            
            # Sample spacing is 1/3 of edge length for complete coverage
            self._sample_spacing = self._edge_length_deg / 3.0
        
        return self._hex_area_km2, self._edge_length_deg, self._sample_spacing
    
    def create_h3_grid_from_geometry(
        self, 
        geometry: Union[Polygon, str], 
        buffer_distance: float = 0.0,
        output_dir: Optional[Union[str, Path]] = None
    ) -> gpd.GeoDataFrame:
        """
        Create an H3 grid that covers the given geometry.
        
        Args:
            geometry: Input geometry as Shapely Polygon or WKT string
            buffer_distance: Buffer distance in degrees to expand the geometry
            output_dir: Directory to save output files (default: ./output/)
            
        Returns:
            GeoDataFrame containing H3 hexagons as polygons
        """
        # Parse and validate geometry
        geometry = self._parse_geometry(geometry)
        if buffer_distance > 0:
            geometry = geometry.buffer(buffer_distance)
        
        # Get bounding box
        min_lon, min_lat, max_lon, max_lat = geometry.bounds
        
        # Generate H3 hexagons with systematic sampling
        h3_hexagons = self._generate_hexagons_systematic(
            min_lat, min_lon, max_lat, max_lon, geometry
        )
        
        # Convert to GeoDataFrame
        result_gdf = self._hexagons_to_geodataframe(h3_hexagons)
        
        # Verify coverage and add stats
        coverage_stats = self.verify_coverage(geometry, h3_hexagons)
        result_gdf.attrs['coverage_stats'] = coverage_stats
        self.logger.info(f"Coverage verification: {coverage_stats['message']}")
        
        # Save to output directory if specified
        if output_dir is not None:
            self._save_result_to_output_dir(result_gdf, output_dir)
        
        return result_gdf
    
    def _parse_geometry(self, geometry: Union[Polygon, str]) -> Polygon:
        """Parse and validate input geometry."""
        if isinstance(geometry, str):
            try:
                geometry = wkt_loads(geometry)
            except Exception as e:
                raise ValueError(f"Invalid WKT geometry: {e}")
        
        if not isinstance(geometry, Polygon):
            raise ValueError("Geometry must be a Polygon")
        
        return geometry
    
    def create_h3_grid_from_bounds(
        self, 
        min_lat: float, 
        min_lon: float, 
        max_lat: float, 
        max_lon: float
    ) -> gpd.GeoDataFrame:
        """
        Create an H3 grid covering the given bounding box.
        
        Args:
            min_lat: Minimum latitude
            min_lon: Minimum longitude  
            max_lat: Maximum latitude
            max_lon: Maximum longitude
            
        Returns:
            GeoDataFrame containing H3 hexagons as polygons
        """
        # Create bounding box polygon
        bounds_polygon = Polygon([
            (min_lon, min_lat),
            (max_lon, min_lat), 
            (max_lon, max_lat),
            (min_lon, max_lat)
        ])
        
        h3_hexagons = self._generate_hexagons_systematic(
            min_lat, min_lon, max_lat, max_lon, bounds_polygon
        )
        
        return self._hexagons_to_geodataframe(h3_hexagons)
    
    def _generate_hexagons_systematic(
        self, 
        min_lat: float, 
        min_lon: float, 
        max_lat: float, 
        max_lon: float,
        geometry: Polygon
    ) -> List[str]:
        """
        Generate H3 hexagons using systematic sampling for complete coverage.
        
        Args:
            min_lat: Minimum latitude
            min_lon: Minimum longitude
            max_lat: Maximum latitude  
            max_lon: Maximum longitude
            geometry: Target geometry for intersection testing
            
        Returns:
            List of H3 hexagon IDs that intersect with the geometry
        """
        # Get hexagon properties
        _, _, sample_spacing = self._get_hexagon_properties(min_lat)
        
        # Generate systematic sampling points
        lat_points = self._generate_sample_points(min_lat, max_lat, sample_spacing)
        lon_points = self._generate_sample_points(min_lon, max_lon, sample_spacing)
        
        # Collect all unique hexagons from sampling points
        all_hexagons = set()
        for lat in lat_points:
            for lon in lon_points:
                try:
                    hex_id = h3.latlng_to_cell(lat, lon, self.resolution)
                    all_hexagons.add(hex_id)
                except Exception:
                    continue
        
        # Expand to include neighbors for complete coverage
        expanded_hexagons = self._expand_hexagon_set(all_hexagons)
        
        # Filter hexagons that intersect with the geometry
        return self._filter_intersecting_hexagons(expanded_hexagons, geometry)
    
    def _generate_sample_points(self, min_val: float, max_val: float, spacing: float) -> List[float]:
        """Generate systematic sample points between min and max values."""
        points = []
        current = min_val
        while current <= max_val:
            points.append(current)
            current += spacing
        
        # Ensure we include the maximum value
        if points[-1] < max_val:
            points.append(max_val)
        
        return points
    
    def _expand_hexagon_set(self, hexagons: set) -> set:
        """Expand hexagon set to include neighbors for complete coverage."""
        expanded = set(hexagons)
        for hex_id in hexagons:
            try:
                neighbors = h3.grid_disk(hex_id, 1)
                expanded.update(neighbors)
            except Exception:
                continue
        return expanded
    
    def _filter_intersecting_hexagons(self, hexagons: set, geometry: Polygon) -> List[str]:
        """Filter hexagons that intersect with the target geometry."""
        intersecting = []
        bounds_polygon = Polygon([
            (geometry.bounds[0], geometry.bounds[1]),
            (geometry.bounds[2], geometry.bounds[1]), 
            (geometry.bounds[2], geometry.bounds[3]),
            (geometry.bounds[0], geometry.bounds[3])
        ])
        
        for hex_id in hexagons:
            try:
                hex_boundary = h3.cell_to_boundary(hex_id)
                hex_polygon = Polygon([(lon, lat) for lat, lon in hex_boundary])
                
                # Check intersection with both bounds and target geometry
                if (hex_polygon.intersects(bounds_polygon) and 
                    self._hexagon_intersects_geometry(hex_polygon, geometry)):
                    intersecting.append(hex_id)
            except Exception:
                continue
        
        return intersecting
    
    def _hexagon_intersects_geometry(self, hex_polygon: Polygon, geometry: Polygon) -> bool:
        """Check if hexagon intersects with geometry using multiple criteria."""
        return (hex_polygon.intersects(geometry) or 
                hex_polygon.within(geometry) or 
                geometry.intersects(hex_polygon) or
                geometry.within(hex_polygon) or
                hex_polygon.overlaps(geometry))
    
    
    def verify_coverage(
        self, 
        geometry: Polygon, 
        hexagons: List[str], 
        tolerance: float = 0.01
    ) -> Dict[str, Any]:
        """
        Verify that the H3 hexagons provide adequate coverage of the input geometry.
        
        Args:
            geometry: Input polygon geometry
            hexagons: List of H3 hexagon IDs
            tolerance: Tolerance for coverage verification (default: 0.01 = 1%)
            
        Returns:
            Dictionary with coverage statistics
        """
        if not hexagons:
            return self._create_coverage_stats(False, 0.0, 0, 0, 0.0, 0.0, 'No hexagons provided')
        
        total_geometry_area = geometry.area
        total_covered_area = 0.0
        valid_hexagons = 0
        
        # Use union operation for more efficient area calculation
        try:
            # Create a union of all hexagons for faster intersection calculation
            hex_polygons = []
            for hex_id in hexagons:
                try:
                    hex_boundary = h3.cell_to_boundary(hex_id)
                    hex_polygon = Polygon([(lon, lat) for lat, lon in hex_boundary])
                    hex_polygons.append(hex_polygon)
                    valid_hexagons += 1
                except Exception:
                    continue
            
            if hex_polygons:
                # Calculate intersection with union of hexagons
                from shapely.ops import unary_union
                hex_union = unary_union(hex_polygons)
                intersection = hex_union.intersection(geometry)
                total_covered_area = intersection.area if hasattr(intersection, 'area') else 0.0
                
        except Exception:
            # Fallback to individual calculation if union fails
            for hex_id in hexagons:
                try:
                    hex_boundary = h3.cell_to_boundary(hex_id)
                    hex_polygon = Polygon([(lon, lat) for lat, lon in hex_boundary])
                    intersection = hex_polygon.intersection(geometry)
                    if hasattr(intersection, 'area'):
                        total_covered_area += intersection.area
                        valid_hexagons += 1
                except Exception:
                    continue
        
        coverage_percentage = (total_covered_area / total_geometry_area) * 100 if total_geometry_area > 0 else 0
        adequate_coverage = coverage_percentage >= (100 - tolerance * 100)
        
        return self._create_coverage_stats(
            adequate_coverage, coverage_percentage, len(hexagons), valid_hexagons,
            total_geometry_area, total_covered_area
        )
    
    def _create_coverage_stats(
        self, covered: bool, coverage_percentage: float, total_hexagons: int,
        valid_hexagons: int, geometry_area: float, covered_area: float,
        custom_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create coverage statistics dictionary."""
        message = custom_message or f'Coverage: {coverage_percentage:.2f}% ({'Adequate' if covered else 'Inadequate'})'
        
        return {
            'covered': covered,
            'coverage_percentage': coverage_percentage,
            'total_hexagons': total_hexagons,
            'valid_hexagons': valid_hexagons,
            'geometry_area': geometry_area,
            'covered_area': covered_area,
            'message': message
        }
    
    def _hexagons_to_geodataframe(self, hexagons: List[str]) -> gpd.GeoDataFrame:
        """
        Convert H3 hexagon IDs to a GeoDataFrame efficiently.
        
        Args:
            hexagons: List of H3 hexagon IDs
            
        Returns:
            GeoDataFrame with hexagon geometries and metadata
        """
        if not hexagons:
            return gpd.GeoDataFrame([], crs='EPSG:4326')
        
        # Pre-calculate area for efficiency
        area_km2 = self._get_hexagon_properties()[0]
        
        data = []
        for hex_id in hexagons:
            try:
                # Get hexagon boundary and center efficiently
                hex_boundary = h3.cell_to_boundary(hex_id)
                hex_polygon = Polygon([(lon, lat) for lat, lon in hex_boundary])
                center_lat, center_lon = h3.cell_to_latlng(hex_id)
                
                data.append({
                    'h3_id': hex_id,
                    'geometry': hex_polygon,
                    'center_lat': center_lat,
                    'center_lon': center_lon,
                    'area_km2': area_km2,
                    'resolution': self.resolution
                })
            except Exception:
                continue
        
        return gpd.GeoDataFrame(data, crs='EPSG:4326')
    
    def _save_result_to_output_dir(
        self, 
        gdf: gpd.GeoDataFrame, 
        output_dir: Union[str, Path]
    ) -> None:
        """
        Save the GeoDataFrame to the output directory with automatic filename generation.
        
        Args:
            gdf: GeoDataFrame to save
            output_dir: Directory to save the output files
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp and resolution
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"h3_grid_res_{self.resolution}_{timestamp}.gpkg"
        output_path = output_dir / filename
        
        # Save geopackage
        gdf.to_file(output_path, driver='GPKG', layer='h3_grid')
        self.logger.info(f"Auto-saved H3 grid to {output_path} with {len(gdf)} hexagons")
        
        # Also save as CSV for easy viewing
        csv_filename = f"h3_grid_res_{self.resolution}_{timestamp}.csv"
        csv_path = output_dir / csv_filename
        
        # Create CSV with hexagon metadata (excluding geometry)
        csv_data = gdf.drop(columns=['geometry']).copy()
        csv_data.to_csv(csv_path, index=False)
        self.logger.info(f"Auto-saved H3 grid metadata to {csv_path}")
    
    def save_to_geopackage(
        self, 
        gdf: gpd.GeoDataFrame, 
        output_path: Union[str, Path],
        layer_name: str = 'h3_grid'
    ) -> None:
        """
        Save the GeoDataFrame to a geopackage file.
        
        Args:
            gdf: GeoDataFrame to save
            output_path: Path to output geopackage file
            layer_name: Name of the layer in the geopackage
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        gdf.to_file(output_path, driver='GPKG', layer=layer_name)
        self.logger.info(f"Saved H3 grid to {output_path} with {len(gdf)} hexagons")
    
    def get_coverage_stats(self, gdf: gpd.GeoDataFrame) -> Optional[Dict[str, Any]]:
        """
        Get coverage statistics from a GeoDataFrame that was created by this generator.
        
        Args:
            gdf: GeoDataFrame created by create_h3_grid_from_geometry
            
        Returns:
            Coverage statistics dictionary or None if not available
        """
        return gdf.attrs.get('coverage_stats', None)


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Generate H3 hexagonal grid for a given geometry"
    )
    
    parser.add_argument(
        '--geometry', 
        type=str,
        help='Input geometry as WKT string or path to GeoJSON/Shapefile'
    )
    
    parser.add_argument(
        '--bounds',
        nargs=4,
        type=float,
        metavar=('MIN_LAT', 'MIN_LON', 'MAX_LAT', 'MAX_LON'),
        help='Bounding box coordinates (min_lat min_lon max_lat max_lon)'
    )
    
    parser.add_argument(
        '--resolution',
        type=int,
        default=6,
        help='H3 resolution level (0-15, default: 6)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Output geopackage file path'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./output/',
        help='Output directory for auto-generated files (default: ./output/)'
    )
    
    parser.add_argument(
        '--layer-name',
        type=str,
        default='h3_grid',
        help='Layer name in geopackage (default: h3_grid)'
    )
    
    parser.add_argument(
        '--buffer',
        type=float,
        default=0.0,
        help='Buffer distance in degrees to expand geometry (default: 0.0)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create H3 grid generator
        generator = H3GridGenerator(resolution=args.resolution)
        if args.geometry:
            # Load geometry from file or use as WKT
            if Path(args.geometry).exists():
                gdf_input = gpd.read_file(args.geometry)
                if len(gdf_input) == 0:
                    raise ValueError("Input geometry file is empty")
                geometry = gdf_input.geometry.iloc[0]
            else:
                geometry = args.geometry
            
            # Generate grid
            result_gdf = generator.create_h3_grid_from_geometry(
                geometry, buffer_distance=args.buffer, output_dir=args.output_dir
            )
            
        elif args.bounds:
            # Generate grid from bounds
            min_lat, min_lon, max_lat, max_lon = args.bounds
            result_gdf = generator.create_h3_grid_from_bounds(
                min_lat, min_lon, max_lat, max_lon
            )
            
        else:
            raise ValueError("Either --geometry or --bounds must be specified")
        
        # Save to geopackage (if output file specified)
        if args.output:
            generator.save_to_geopackage(
                result_gdf, 
                args.output, 
                args.layer_name
            )
            print(f"Successfully created H3 grid with {len(result_gdf)} hexagons")
            print(f"Resolution: {args.resolution}")
            print(f"Output saved to: {args.output}")
        else:
            print(f"Successfully created H3 grid with {len(result_gdf)} hexagons")
            print(f"Resolution: {args.resolution}")
            print(f"Auto-saved to output directory: {args.output_dir}")
        
    except Exception as e:
        logging.error(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
