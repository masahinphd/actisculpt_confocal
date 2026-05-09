# ActiSculpt Confocal Viewer

**Author:** Mehmet Akif Sahin (akif.sahin@tum.de)

This is a Streamlit-based GUI tool for visualizing and analyzing confocal microscopy images (TIFF stacks), originally developed for the ActiSculpt research project.

## Quick Start

Use the launcher for your operating system:

- Windows: double-click `run_app.bat`
- macOS: double-click `run_app.command`
- Linux: run `bash run_app.sh` or execute `python run_app.py`

The launcher creates a local virtual environment if needed, installs the packages from `requirements.txt`, checks the environment, and starts the Streamlit app.

## Demo

![App Demo](assets/demo.gif)

## Features
- Load and visualize 3D TIFF stacks.
- Interactive YZ and XY cross-sectional views.
- Video generation of slicing through the stack.
- Intensity profile analysis.

## Installation

1.  Clone this repository or download the files.
2.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Or use the bundled launcher scripts, which handle environment setup automatically.

## Usage

1.  Run the application using Streamlit:
    ```bash
    python run_app.py
    ```
2.  Use the sidebar to navigate to your directory containing `.tif` or `.tiff` files.
3.  Adjust visualization parameters in the sidebar and explore the tabs.

If you prefer to skip the launcher, you can still run the app directly with `streamlit run confocal_gui.py` once the dependencies are installed.

## License
MIT License

## Citation
If you use this tool in your research, please cite our corresponding paper:
M. A. Sahin et al., "ActiSculpt: Active flow sculpting" (2026).

