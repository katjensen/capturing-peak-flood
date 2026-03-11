# capturing_peak_flood

## Installation

This project uses [pixi](https://pixi.sh/) for environment and dependency management. The project includes a `pixi.toml` configuration file that defines all dependencies and tasks.

### Prerequisites

1. Install pixi by following the [official installation guide](https://pixi.sh/installation/):
   ```bash
   # On macOS/Linux
   curl -fsSL https://pixi.sh/install.sh | bash
   
   # On Windows
   powershell -c "irm https://pixi.sh/install.ps1 | iex"
   ```

### Environment Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd capturing_peak_flood_conditions_project
   ```

2. Install dependencies using the pixi.toml configuration:
   ```bash
   pixi install
   ```

3. Activate the environment:
   ```bash
   pixi shell
   ```

### Available Tasks

The project includes several predefined tasks in `pixi.toml`:

- **Run tests**: `pixi run test`
- **Start Jupyter**: `pixi run notebook`
- **Lint code**: `pixi run lint`
- **Format code**: `pixi run format`

### Running the Project

Once the environment is activated, you can run the various components:

- Jupyter notebooks: `jupyter notebook`
- Python scripts: `python scripts/your_script.py`
- Unit tests: `python unit_tests/run_tests.py`

### Development

For development, you can add new dependencies using:
```bash
pixi add <package-name>
```

Or add development dependencies:
```bash
pixi add --dev <package-name>
```
