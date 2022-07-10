import serial
import time
from datetime import datetime


def read():
    #print("write port")
    ser = serial.Serial('/dev/ttyACM0', timeout=2)
    ser.write(b'at*skt*level=0\r\n')
    while True:
        line = ser.readline().decode('euckr')
        if line=='': break
        line = line.replace("\r\n", "")
        if line.startswith("*SKT*LEVEL"): 
            return line
    ser.close()
