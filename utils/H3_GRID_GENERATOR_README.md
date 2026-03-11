# H3 Grid Generator

A Python script that creates Uber H3 hexagonal grids for a variable grid size and given input geometry. The resulting grid is saved as a geopackage file.

## Features

- **Variable Grid Resolution**: Support for H3 resolution levels 0-15
- **Multiple Input Formats**: Accepts geometries as WKT strings, GeoJSON files, Shapefiles, or bounding boxes
- **Geopackage Output**: Saves results in standard geopackage format
- **Buffer Support**: Optional buffer distance to expand input geometries
- **Command Line Interface**: Easy-to-use CLI with comprehensive options
- **Comprehensive Testing**: Full unit test coverage

## Installation

This project uses [pixi](https://pixi.sh/) for environment and dependency management. The script requires the following dependencies:
- `h3` - Uber's H3 hexagonal hierarchical spatial index
- `geopandas` - Geospatial data manipulation
- `shapely` - Geometric objects and operations

### Prerequisites

1. Install pixi by following the [official installation guide](https://pixi.sh/installation/):
   ```bash
   # On macOS/Linux
   curl -fsSL https://pixi.sh/install.sh | bash
   
   # On Windows
   powershell -c "irm https://pixi.sh/install.ps1 | iex"
   ```

### Environment Setup

1. Clone the repository and navigate to the project directory:
   ```bash
   git clone <repository-url>
   cd capturing_peak_flood_conditions_project
   ```

2. Install dependencies using pixi:
   ```bash
   pixi install
   ```

3. Activate the environment:
   ```bash
   pixi shell
   ```

## Usage

### Command Line Interface

#### Basic Usage
```bash
pixi run python utils/h3_grid_generator.py --geometry "POLYGON((-74.0 40.7, -73.9 40.7, -73.9 40.8, -74.0 40.8, -74.0 40.7))" --output grid.gpkg
```

#### Using Bounding Box
```bash
pixi run python utils/h3_grid_generator.py --bounds 40.7 -74.0 40.8 -73.9 --resolution 8 --output grid.gpkg
```

#### Using Geometry File
```bash
pixi run python utils/h3_grid_generator.py --geometry input.geojson --resolution 6 --output grid.gpkg --layer-name my_grid
```

#### With Buffer
```bash
pixi run python utils/h3_grid_generator.py --geometry "POLYGON(...)" --buffer 0.01 --output grid.gpkg
```

#### Command Line Options
- `--geometry`: Input geometry as WKT string or path to GeoJSON/Shapefile
- `--bounds`: Bounding box coordinates (min_lat min_lon max_lat max_lon)
- `--resolution`: H3 resolution level (0-15, default: 6)
- `--output`: Output geopackage file path (required)
- `--layer-name`: Layer name in geopackage (default: h3_grid)
- `--buffer`: Buffer distance in degrees to expand geometry (default: 0.0)
- `--verbose`: Enable verbose logging

### Programmatic Usage

```python
from h3_grid_generator import H3GridGenerator
from shapely.geometry import Polygon

# Create generator with resolution 6
generator = H3GridGenerator(resolution=6)

# Define input geometry
polygon = Polygon([
    (-74.0, 40.7),
    (-73.9, 40.7),
    (-73.9, 40.8),
    (-74.0, 40.8),
    (-74.0, 40.7)
])

# Generate H3 grid
result_gdf = generator.create_h3_grid_from_geometry(polygon)

# Save to geopackage
generator.save_to_geopackage(result_gdf, "output.gpkg", "my_grid")
```

### Using WKT Geometry
```python
wkt_geometry = "POLYGON((-97.5 32.0, -96.0 32.0, -96.0 33.5, -96.0 33.5, -97.5 32.0))"
result_gdf = generator.create_h3_grid_from_geometry(wkt_geometry)
```

### Using Bounding Box
```python
result_gdf = generator.create_h3_grid_from_bounds(
    min_lat=40.7, min_lon=-74.0, max_lat=40.8, max_lon=-73.9
)
```

## H3 Resolution Levels

H3 resolution levels determine the size of hexagons:
- **Level 0**: ~4,250,546.8 km² (largest hexagons)
- **Level 6**: ~36.1 km² (default)
- **Level 15**: ~0.9 m² (smallest hexagons)

Higher resolution numbers create smaller, more detailed hexagons.

## Output Format

The generated geopackage contains the following columns:
- `h3_id`: Unique H3 hexagon identifier
- `geometry`: Hexagon polygon geometry
- `center_lat`: Latitude of hexagon center
- `center_lon`: Longitude of hexagon center
- `area_km2`: Approximate area in square kilometers
- `resolution`: H3 resolution level used

## Testing

Run the comprehensive test suite:
```bash
pixi run test
```

Or run tests directly:
```bash
pixi run python unit_tests/run_tests.py
```

Run example usage demonstrations:
```bash
pixi run python unit_tests/example_usage.py
```

## Examples

The `unit_tests/example_usage.py` script demonstrates various usage patterns:
- Basic geometry input
- Different resolution levels
- Bounding box usage
- WKT geometry input
- Buffer functionality

## File Structure

```
├── utils/
│   └── h3_grid_generator.py          # Main script
├── unit_tests/
│   ├── test_h3_grid_generator.py      # Core functionality tests
│   ├── test_h3_grid_generator_cli.py   # CLI tests
│   ├── run_tests.py                   # Test runner
│   └── example_usage.py                # Usage examples
├── pixi.toml                          # Pixi environment configuration
└── H3_GRID_GENERATOR_README.md        # This file
```

## Error Handling

The script includes comprehensive error handling for:
- Invalid H3 resolution levels
- Malformed geometry inputs
- File I/O errors
- Missing required parameters

## Performance Notes

- Higher resolution levels generate more hexagons and take longer to process
- Large geometries may require significant memory and processing time
- The algorithm efficiently filters hexagons to only include those intersecting the input geometry

## License

This script is part of the solutions-tasking project.
