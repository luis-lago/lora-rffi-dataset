LoRa RF Fingerprinting: Capture & Dataset Pipeline

This repository contains the pipeline for capturing raw LoRa IQ signals via SDR, extracting the complex preambles, and formatting the data. 

Prerequisites & Environment Setup

1. GNU Radio (Radioconda)

For MacOS, we use Radioconda to manage the GNU Radio environment and necessary SDR drivers. Follow the installation and configuration guide at the official repository: https://github.com/radioconda/radioconda-installer

2. Python Dependencies

Once your radioconda environment is installed, you must install the Python dependencies into that same environment and specified in requirements.txt

Execution Pipeline

Ensure the SDR and LoRa HAT are connected via a USB port of the computer and configured. If the LoRa HAT has not been previosuly configured, set the device in configuration mode and use config_lora.py Python script for HAT configuration. Run the following scripts in the exact order listed below to record and process a single session:
1. In a terminal, run transmit_loop.py
2. In another terminal, run run_session.py to initiate the 60 seconds capture and extract preambles.
3. Verify the capture and preamble extraction.
4. Repeat the procedure for different LoRa HAT devices and sessions per device. 

