# ActiSculpt Confocal Viewer

**Author:** Mehmet Akif Sahin (akif.sahin@tum.de)

This is a Streamlit-based GUI tool for visualizing and analyzing confocal microscopy images (TIFF stacks), originally developed for the ActiSculpt research project.

## Demo

https://github.com/masahin720/actisculpt_confocal/raw/main/assets/demo.mp4

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

## Usage

1.  Run the application using Streamlit:
    ```bash
    streamlit run confocal_gui.py
    ```
2.  Use the sidebar to navigate to your directory containing `.tif` or `.tiff` files.
3.  Adjust visualization parameters in the sidebar and explore the tabs.

## License
MIT License

## Citation
If you use this tool in your research, please cite our corresponding paper:
M. A. Sahin et al., "ActiSculpt: Active flow sculpting" (2026).

