# **Building a LoRa IQ Capture Setup with GNU Radio and USRP**

### **1\. Overview**

We are building a receive-only GNU Radio flowgraph to capture raw IQ samples from LoRa devices transmitting on the 915 MHz band. The goal of this system is to collect high-fidelity RF fingerprint data for device authentication research. The final output is a raw .iq file (complex64 format) containing exactly 60 seconds of continuous RF capture.

### 

### **2\. Prerequisites**

Before opening GNU Radio, ensure your hardware and software are ready:

1. **Hardware:** A USRP B210 (or equivalent SDR) and a LoRa transmitter (such as the Waveshare SX126X HAT connected to a Raspberry Pi).  
2. **Software:** GNU Radio 3.10 or newer, with the UHD drivers properly installed.  
3. **Quick Verification:** Open your terminal and run the command uhd\_find\_devices. Confirm that your system detects the USRP before proceeding to the flowgraph.

### 

### **3\. Building the Flowgraph**

Open GNU Radio Companion (GRC) and create a new flowgraph. You will need to add and connect the following blocks.  
**Connection Diagram:**  
\[UHD: USRP Source\] \---\> \[Head\] \---\> \[File Sink\]  
       |  
       \+---\> \[QT GUI Time Sink\]

**Step-by-Step Block Configuration:**

1. **Variable Block:** Double-click the default samp\_rate variable block and ensure the value is set to 1e6 (1 MHz).  
2. **UHD: USRP Source:** Add this block to interface with your SDR.  
   * Center Freq: 915e6 (915 MHz)  
   * Sample Rate: samp\_rate  
   * Ch0: Gain Value: 28 (dB)  
   * Ch0: Antenna: "RX2"  
3. **Head:** Add this block to limit the capture duration.  
   * Num Items: int(samp\_rate \* 60\) (This stops the flowgraph after exactly 60 million samples, equaling 60 seconds).  
4. **File Sink:** Add this block to save the data to disk.  
   * File: capture.iq (or passed as a parameter)  
   * Input Type: Complex Float32  
5. **QT GUI Time Sink (Optional):** Add this for real-time visualization.  
   * Type: Complex Float32  
6. **Connections:** Wire the out port of the **USRP Source** to the in port of the **Head** block. Wire the out port of the **Head** block to the in port of the **File Sink**. Wire a second connection from the out port of the **USRP Source** to the in port of the **QT GUI Time Sink**.

### 

### **4\. Generating and Customizing the Python Script**

Once the flowgraph is complete, we need to convert it into a usable Python script.

1. **Generate the Code:** In GRC, click **Build → Generate** (or press F5) in the top menu. This creates a Python file in your directory.  
2. **The Generated Class:** GRC wraps your flowgraph in a Python class (e.g., lora\_receiver). The constructor of this class will accept any parameters you defined, such as samp\_rate, gain, and filepath.  
3. **Running from a Script:** You can now import and trigger this flowgraph from your own custom Python scripts:  
   from lora\_receiver import lora\_receiver

   \# Initialize the flowgraph with parameters  
   tb \= lora\_receiver(samp\_rate=1e6, gain=28, filepath="capture.iq")

   \# Start the capture  
   tb.start()

4. **The Event Loop:** The generated script uses a PyQt5 event loop to display the GUI sink. Because we included the Head block, the flowgraph will automatically terminate data collection and cleanly exit the loop once the 60 seconds of samples are collected.

### 

### **5\. Integration with the Capture Pipeline**

This GRC flowgraph is designed to be the first stage of a larger automated pipeline, typically managed by a master script like run\_session.py.

1. **Phase 1 (Capture):** The pipeline imports the generated GRC Python class, activates the USRP, and saves 60 seconds of raw IQ data directly to disk.  
2. **Phase 2 (Extraction):** An offline Python script loads the saved .iq file into memory. It uses frequency-based chirp boundary detection to find and isolate individual LoRa packets from the continuous capture.  
3. **Phase 3 (Verification):** The pipeline generates visual plots of the extracted preambles to verify the signal is clean and ready for machine learning.
