# **Building a LoRa IQ Capture Setup with GNU Radio and USRP**

### **1\. Overview**

We are building a receive-only GNU Radio flowgraph to capture raw IQ samples from LoRa devices transmitting on the 915 MHz band. The goal of this system is to collect high-fidelity RF fingerprint data for device authentication research. The final output is a raw `.iq` file (`complex64` format) containing exactly 60 seconds of continuous RF capture.

### 

### **2\. Prerequisites**

Before opening GNU Radio, ensure your hardware and software are ready:

1. **Hardware:** A USRP B210 and a LoRa HAT transmitter (such as the Waveshare SX126X HAT).  
2. **Software:** GNU Radio 3.10 or newer, with the UHD drivers properly installed.  
3. **Quick Verification:** Open your terminal and run the command `uhd_find_devices`. Confirm that your system detects the USRP before proceeding to the flowgraph.

### 

### **3\. Building the Flowgraph**

Open GNU Radio Companion (GRC) and create a new flowgraph. You will need to add and connect the following blocks.  
**Connection Diagram:**  
```
[UHD: USRP Source] ---> [Head] ---> [File Sink]  
         
[UHD: USRP Source] ---> [QT GUI Waterfall Sink]
```
**Step-by-Step Blocks Configuration:**

1. **Parameter Blocks:** Add four **Parameter Blocks**--one for each parameter sample rate, gain, I/Q data storage, and capture time-- Double-click each block and ensure the attribute **ID** is set to the corresponding ID (`samp_rate`, `gain`, `filepath`, and `capture_time`) while the correct data type and value is correctly set in each case. For instance, the default `samp_rate` parameter value is set to 1e6 (1 MHz), type `Float`, and `Value` to 60 for 60 seconds default capturing duration.  
2. **UHD: USRP Source:** Add this block to interface with your SDR.  
   * Center Freq: 915e6 (915 MHz)  
   * Sample Rate: `samp_rate`  
   * Ch0: Gain Value: 28 (dB)  
   * Ch0: Antenna: "RX2"  
3. **Head:** Add this block to limit the capture duration.  
   * Num Items: `int(samp_rate * capture_time)` (This stops the flowgraph after exactly `capture_time` million samples for `samp_rate` = 1e6, `capture_time` = 60).  
4. **File Sink:** Add this block to save the data to disk.  
   * File: `filepath`  
   * Input Type: Complex Float32  
5. **QT GUI Waterfall Sink (Optional):** Add this for real-time visualization.  
   * Type: Complex Float32  
6. **Connections:** Wire the out port of the **USRP Source** to the in port of the **Head** block. Wire the out port of the **Head** block to the in port of the **File Sink**. Wire a second connection from the out port of the **USRP Source** to the in port of the **QT GUI Waterfall Sink**.

### 

### **4\. Generating and Customizing the Python Script**

Once the flowgraph is complete, we need to convert it into a usable Python script.

1. **Generate the Code:** In GRC, click **Build → Generate** in the top menu. This creates a Python file in your directory.  
2. **The Generated Class:** GRC wraps your flowgraph in a Python class (e.g., lora\_receiver). The constructor of this class will accept any parameters you defined, such as `samp_rate`, `gain`, `capture_duration`, and `filepath`.  
3. **Running from a Script:** You can now import and trigger this flowgraph from your own custom Python scripts:  
   ```
   from lora_receiver import lora_receiver

   # Initialize the flowgraph with parameters  
   tb = lora_receiver(samp_rate=1e6, gain=28, capture_time = 60, filepath="capture.iq")

   # Start the capture  
   tb.start()
   ```

4. **The Event Loop:** The generated script uses a PyQt5 event loop to display the GUI sink. Because we included the Head block, the flowgraph will automatically terminate data collection and cleanly exit the loop once the the time specified in `capture_time` is reached.

### 

### **5\. Integration with the Capture Pipeline**

This GRC flowgraph is designed to be the first stage of a larger automated pipeline managed by a master script--like run\_session.py in this repository.

1. **Phase 1 (Capture):** The pipeline imports the generated GRC Python class, activates the USRP, and saves 60 seconds by defaults of raw IQ data directly to disk.  
2. **Phase 2 (Extraction):** An offline Python script loads the saved `.iq` file into memory. It uses frequency--based chirp boundary detection to find and isolate individual LoRa packets from the raw capture.  
3. **Phase 3 (Verification):** The pipeline generates visual plots of the extracted preambles--8 preambles by defaulst--to verify the signal is clean and suitable for RF fingerprint processing.
