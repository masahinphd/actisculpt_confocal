# ActiSculpt Confocal Viewer

**Author:** Mehmet Akif Sahin (akif.sahin@tum.de)

This repository contains the source code for the **ActiSculpt Confocal Viewer**, a Streamlit-based GUI for visualizing and analyzing confocal microscopy image stacks in Active Flow Sculpting experiments.

## Quick Start

**What it does:** A Streamlit-based GUI tool for visualizing and analyzing confocal microscopy images (TIFF stacks). It is designed for the ActiSculpt research project and includes bundled example data under `Fiber confocal scan examples/` so you can explore the workflow immediately.

**How to use:** Double-click the launcher script for your OS (`run_app.bat` on Windows, `run_app.command` on macOS, or `run_app.sh` on Linux) to start the interactive web interface. Then point the sidebar to a folder containing `.tif` or `.tiff` files, adjust the visualization settings, and explore the cross-sectional views and intensity analysis tabs.

---

## Setup

### Automatic Setup

The launcher creates a local virtual environment if needed, installs the packages from `requirements.txt`, checks the environment, and starts the Streamlit app.

## Demo

![App Demo](assets/demo.gif)

## Features
- Load and visualize 3D TIFF stacks.
- Interactive YZ and XY cross-sectional views.
- Video generation of slicing through the stack.
- Intensity profile analysis.

### Manual Setup

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

## Acknowledgments

The interactive GUI was developed with assistance from **GitHub Copilot**, an AI-powered code completion tool. Generative AI helped accelerate the development of the Streamlit interface and visualization components.

