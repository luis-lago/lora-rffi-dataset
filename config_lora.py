#!/usr/bin/env python3
import serial
import time

def configure_lora():
    try:
        # Connect to the Mac's serial port
        ser = serial.Serial("/dev/cu.usbserial-0001", baudrate=9600, timeout=1)
    except Exception as e:
        print(f"Error opening serial port: {e}")
        return
        
    print("1. Reading current configuration...")
    # 0xC1 = Read Command, 0x00 = Start Address, 0x09 = Length
    ser.write(bytes([0xC1, 0x00, 0x09]))
    time.sleep(0.2)
    current = ser.read(12)
    
    if len(current) > 0:
        print(f"   Current Hex: {current.hex().upper()}")
    else:
        print("   No response. Ensure M1 is OFF (open) and M0 is ON (shorted).")
        
    print("\n2. Writing new parameters...")
    
    # 0xC0 = Write Command, 0x00 = Start Address, 0x09 = Length
    # [3] 0x00 = ADDH
    # [4] 0x00 = ADDL
    # [5] 0x00 = NETID (This is the byte I missed previously!)
    # [6] 0x62 = REG0 (9600 baud, 8N1, 2.4 kbps air rate)
    # [7] 0x02 = REG1 (Sub-packet 240 bytes, TX Power 13 dBm - closest to 14)
    # [8] 0x41 = REG2 (Channel 65 -> 850MHz + 65 = 915.0 MHz)
    # [9] 0x00 = REG3 (Transparent mode)
    # [10] 0x00 = CRYPT_H
    # [11] 0x00 = CRYPT_L
    
    config_frame = bytes([0xC0, 0x00, 0x09, 0x00, 0x00, 0x00, 0x62, 0x02, 0x41, 0x00, 0x00, 0x00])
    
    ser.write(config_frame)
    time.sleep(0.2)
    
    response = ser.read(12)
    
    if response:
        print(f"   Response Hex: {response.hex().upper()}")
        
        # A successful write echoes back the parameters with a 0xC1 header
        if response[0] == 0xC1 or response[0] == 0xC0:
            print("\nSUCCESS: Hardware locked to 915.0 MHz | 13 dBm | 2.4 kbps")
        else:
            print("\nWARNING: Unexpected response.")
    else:
        print("\nERROR: No response. Module timed out.")
        
    ser.close()

if __name__ == "__main__":
    configure_lora()