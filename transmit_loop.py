#!/usr/bin/env python3
"""transmit_loop.py — Hardware-locked periodic transmission"""

import serial
import time

# Initialize Serial Connection
ser = serial.Serial("/dev/cu.usbserial-0001", baudrate=9600, timeout=2)

# Standard 58-byte payload
payload = b'\xAA' * 58
count = 0

print("Transmitting continuously. Press Ctrl+C to stop.")

try:
    while True:
        # The HAT is hardware-locked to the correct parameters. 
        ser.write(payload)
        count += 1
        print(f"  TX #{count}", end="\r")
        
        # 2-second sleep
        time.sleep(2)
        
except KeyboardInterrupt:
    ser.close()
    print(f"\nStopped after {count} transmissions.")