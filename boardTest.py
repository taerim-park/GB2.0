# Server_Data_Sending.py
# date : 2022-05-06
# 초기 작성자 : ino-on, 주수아
# 소켓 클라이언트와 통신을 하며, 클라이언트가 명령어를 보낼 때마다 명령어에 따른 동작을 수행합니다.
# 현재 'CAPTURE' 명령어만이 활성화되어있습니다. 

#   5/6 변위식 수정. 추후 인하대쪽 코드와 통합할 예정입니다, 주수아
#   5/5 making robust를 위한 작업들, 김규호 
import spidev
import time
import numpy as np
import json
import math
import sys
from datetime import datetime
from datetime import timedelta
import re
import os
import logging
from flask import Flask, request, json
app= Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

            #counter            #counter          #시간
Time_Stamp={"TimeStamp":0,"OldTimeStamp":0, "BaseTime":0}

import signal
def sigint_handler(signal, frame):
    print()
    print()
    print('got restart command.  exiting...')
    os._exit(0)
signal.signal(signal.SIGINT, sigint_handler)

print('==================')
print('Version 1.0')

spi_bus = 0
spi_device = 0
spi = spidev.SpiDev()
spi.open(spi_bus, spi_device)
spi.max_speed_hz = 100000 #100MHz

#하드웨어 보드의 설정상태 저장
board_setting = {} 

rq_cmd = [0x01]*6
CMD_A = [0x10]*6
CMD_B = [0x20]*6


def request_cmd() :
    RXD = spi.xfer2(rq_cmd)
    #print(f'RXD= {RXD}')
    if   RXD == [0x2, 0x3, 0x4, 0x5, 0x6, 0x7] : # ACK
        return 1
    else : 
        return 0

def send_data(cmd) : 
    RXD = spi.xfer3(cmd)
    #print(f'RXD= {RXD}')
    return RXD


def time_conversion(stamp):
    global Time_Stamp

    if Time_Stamp["TimeStamp"]==0:
        # Time_Stamp={"TimeStamp":0,"OldTimeStamp":0, "BaseTime":0}
        x=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        Time_Stamp["BaseTime"]=datetime.strptime(x, "%Y-%m-%d %H:%M:%S")
        Time_Stamp["TimeStamp"]=stamp
        Time_Stamp["OldTimeStamp"]=stamp-1000

    c_delta = stamp - Time_Stamp["TimeStamp"]
    return (Time_Stamp["BaseTime"] + timedelta(milliseconds = c_delta)).strftime("%Y-%m-%d %H:%M:%S")

def status_conversion(solar, battery, vdd):
    solar   = 0.003013 * solar + 1.2824
    battery = battery / 4096 * 100  # 12-bit
    vdd     = vdd / 4096 * 100      # 12-bit

    return solar, battery, vdd

def sync_time():
    # DO NOTHING, time is broght from data packet
    pass

    global Time_Stamp
    
    for i in range(5):
        time.sleep(ds)  
        spi.xfer2([0x27])
        time.sleep(ds)  
        status_data_i_got = spi.xfer2([0x0]*14)
   
        Time_Stamp["TimeStamp"] = status_data_i_got[3] << 24 | status_data_i_got[2] << 16 | status_data_i_got[1] << 8 | status_data_i_got[0]  - TimeCorrection
        if Time_Stamp["TimeStamp"] > 0: break
        print(f'INVALID Time_Stamp["TimeStamp"]= {Time_Stamp["TimeStamp"]}  try again')
    
    x=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    Time_Stamp["BaseTime"]=datetime.strptime(x, "%Y-%m-%d %H:%M:%S")
    print(f"syc_time BaseTime= {Time_Stamp['BaseTime'].strftime('%H:%M:%S')}  Time_Stamp['TimeStamp']= {Time_Stamp['TimeStamp']}")
    return Time_Stamp["BaseTime"].strftime("%Y-%m-%d %H:%M:%S")

# int Twos_Complement(string data, int length)
# bit data를 int data로 바꾸어줍니다.
# first bit가 1이라면 보수 연산을 시행하며, 그렇지 않으면 보수 연산을 시행하지 않습니다.
def Twos_Complement(data, length):
    def convert(data):
        uintval = int(data, 16)
        bit = 4 * (len(data) - 2)
        if uintval >= math.pow(2,bit-1):
            uintval = int(0 - (math.pow(2, bit)-uintval))
        return uintval
    int_data = int(data, 16)
    bin_data = bin(int_data)
    if len(bin_data) == length*8+2:
        return convert('0x'+data)
    else:
        return int_data
    
    
# str basic_conversion(list number_list)
# convert whole bit data to demical
# 특별한 연산 없이 bit data를 원래 순서대로 뒤집어둡니다. 
def basic_conversion(number_list):
    result_str = ''
    for i in reversed(range(len(number_list))):
        result_hex = hex(number_list[i])[2:]
        if len(result_hex)<2:
            result_hex = '0'+result_hex
        result_str += result_hex
    return result_str

# dict status_trigger_return(hex_data)
# status bit를 분석하여 trigger가 발동된 센서가 있는지 표기합니다.
# trigger가 발동되었다면 1을, 그렇지 않았다면 0을 저장하고 있습니다.
def status_trigger_return(hex_data):
    #print("hex data :", hex_data)
    int_data = int(hex_data[:2], 16)
    #print("int_data :", int_data)
    bin_data = bin(int_data)[2:]
    #print(f'bin_data= {bin_data}')
    if len(bin_data) < 5:
        gap = 5-len(bin_data)
        for i in range(gap):
            bin_data = "0"+bin_data
    #print("bin_data :", bin_data)
    tem_bit = bin_data[0]
    dis_bit = bin_data[1]
    str_bit = bin_data[2]
    deg_bit = bin_data[3]
    acc_bit = bin_data[4]

    is_triggered = {
        "TP":tem_bit,
        "DI":dis_bit,
        "DS":str_bit,
        "TI":deg_bit,
        "AC":acc_bit
    }

    return is_triggered

# int dis_conversion(list number_list)
# convert whole displacement bit data to demical
# if first bit is '1', it calculates minus value according to Two's Complement
def dis_conversion(number_list):
    result_str = ''
    for i in reversed(range(len(number_list))):
        result_hex = hex(number_list[i])[2:]
        if len(result_hex)<2:
            result_hex = '0'+result_hex
        result_str += result_hex
    result = Twos_Complement(result_str, 4)
    result = (result-16339000)/699.6956*(1.01)
    return result

# float acc_conversion(list number_list)
# convert whole acceleration bit data to acc data
# if first bit is '1', it calculates minus value according to Two's Complement
def acc_conversion(number_list):
    result_str = ''
    for i in reversed(range(len(number_list))):
        result_hex = hex(number_list[i])[2:]
        if len(result_hex)<2:
            result_hex = '0'+result_hex
        result_str += result_hex
    result_int = Twos_Complement(result_str, 4)
    result = float(result_int)
    result *= 0.0039
    result = round(result, 2)
    return result

# float deg_conversion(list number_list)
# convert whole degree bit data to deg data
# if first bit is '1', it calculates minus value according to Two's Complement
def deg_conversion(number_list):
    result_str = ''
    for i in reversed(range(len(number_list))):
        result_hex = hex(number_list[i])[2:]
        if len(result_hex)<2:
            result_hex = '0'+result_hex
        result_str += result_hex
    result_int = Twos_Complement(result_str, 2)
    result = float(result_int)
    result /= 100
    return result

# float tem_conversion(list number_list)
# convert whole temperature bit data to tem data
# if first bit is '1', it calculates minus value according to Two's Complement
def tem_conversion(number_list):
    result_str = ''
    for i in reversed(range(len(number_list))):
        result_hex = hex(number_list[i])[2:]
        if len(result_hex)<2:
            result_hex = '0'+result_hex
        result_str += result_hex
    #result_str = result_str[::-1] # invert string
    result_int = Twos_Complement(result_str, 2)
    result = float(result_int)
    result /= 100
    return result

# 220506 갱신 : 변위 변환 수식 수정 완료


i =0
d = 1
ds = 0.01
d2 = 0.1
n = 2400

TimeCorrection = int(ds * 1000) # FIXME

isReady = False

upload_HEADER = ["Timestamp", "Temperature", "Displacement"]
capture_HEADER = ["Timestamp", "Temperature", "Displacement", "samplerate"]
ctrigger_CONFIG = ["use", "mode", "st1high", "st1low", "bfsec"]
cmeasure_CONFIG = ["sensitivity", "samplerate", "measureperiod", "stateperiod", "rawperiod"]
STATUS = ["ibattery", "ebattery", "count", "abflag", "abtime", "abdesc"]
num_of_DATA = 2

Config_datas = {}        # config data 담을 dict
Status_datas = {}        # status data 담을 dict

TimeCorrection = int(ds * 1000) # FIXME

# AE별 global offset value, defaulted to 0
Offset={'AC':0,'DI':0,'TI':0,'TP':0}
old=datetime.now()

# dict data_receiving()
# 센서로부터 data bit를 받아, 그것을 적절한 int값으로 변환합니다.
# return value는 모든 센서 데이터를 포함하고 있는 dictionary 데이터입니다.
def data_receiving():
    global Offset
    global Time_Stamp
    #print("s:0x24")        # request header
    rcv1 = spi.xfer2([0x24])
    #print("header data signal")
    time.sleep(ds)

    #print("s:0x40")
    rcv2 = spi.xfer2([0x40]*8) # follow up action
    time.sleep(ds)
    #print(rcv2)
    
    if rcv2[0] == 216 and rcv2[1] == 216:
        global old
        print(F"\n{datetime.now().strftime('%H:%M:%S')} +{(datetime.now()-old).total_seconds()}s got {len(rcv2)}B {rcv2[0:2]}", end=' ')
        old=datetime.now()
        isReady = True
        json_data = {}
        #print("data is ready")
        print(f"status= {rcv2[2:4]}", end=' ')
        status = basic_conversion(rcv2[2:4]) #status info save
        time_counter = int(basic_conversion(rcv2[4:8]),16)
        print(f"counter= {rcv2[4:8]} {time_counter}", end=' ')

        # board not err 발생시 time_counter가 리셋되어 10이 온다.
        timestamp = time_conversion(time_counter) #timestamp info save.

        json_data["Timestamp"] = timestamp
        json_data["count"] = time_counter - Time_Stamp["OldTimeStamp"]
        json_data["counter"] = time_counter

        Time_Stamp["OldTimeStamp"] = time_counter
        #print("trigger status : ", status_trigger_return(status)) #trigger 작동여부 출력 테스트 코드
        json_data["trigger"] = status_trigger_return(status)
    else:
        isReady = False
        fail_data = {"Status":"False"}
        return fail_data
        
    if isReady: #only send data if data is ready
        #print("s:"+ "0x26")        # request static
        rcv3 = spi.xfer2([0x26])
        print(rcv3, end=' ')
        #print("static sensor data signal")
        time.sleep(ds)

        #print("s:"+ "0x40")
        rcv4 = spi.xfer2([0x40]*16) # follow up action
        print(f"XYZ= {rcv4[0:6]} Temp= {rcv4[6:8]} Di4_5= {rcv4[8:]}", end=' ')
        degreeX = deg_conversion(rcv4[0:2]) + Offset['TI'] 
        degreeY = deg_conversion(rcv4[2:4]) + Offset['TI'] 
        degreeZ = deg_conversion(rcv4[4:6]) + Offset['TI'] 
        Temperature = tem_conversion(rcv4[6:8]) + Offset['TP'] 
        Displacement_ch4 = dis_conversion(rcv4[8:12]) + Offset['DI']
        # 식을 dis_conversion으로 변경하여 해결하였음
        Displacement_ch5 = dis_conversion(rcv4[12:]) + Offset['DI']
        json_data["TI"] = {"x":degreeX, "y":degreeY, "z":degreeZ}
        json_data["TP"] = Temperature
        json_data["DI"] = {"ch4":Displacement_ch4, "ch5":Displacement_ch5}
        time.sleep(ds)
 
        #print("s:"+ "0x25")        # request data    
        rcv5 = spi.xfer2([0x25])
        #print(rcv5)
        #print("Dynamic sensor data signal")
        time.sleep(ds)

        #print("s:"+ "0x40")
        rcv6 = spi.xfer2([0x40]*n)
        #print(rcv6)
        acc_list = list()
        strain_list = list()
        for i in range(100):
            cycle = i*24
            ax = acc_conversion(rcv6[0+cycle:4+cycle]) + Offset['AC'] 
            ay = acc_conversion(rcv6[4+cycle:8+cycle]) + Offset['AC'] 
            az = acc_conversion(rcv6[8+cycle:12+cycle]) + Offset['AC'] 
            acc_list.append({"x":ax, "y":ay, "z":az})
            #acc_list.append([ax, ay, az])
            """
            ax = acc_conversion(rcv6[0+cycle:4+cycle])
            ay = acc_conversion(rcv6[4+cycle:8+cycle])
            az = acc_conversion(rcv6[8+cycle:12+cycle])
            """
            sx = basic_conversion(rcv6[12+cycle:16+cycle])
            sy = basic_conversion(rcv6[16+cycle:20+cycle])
            sz = basic_conversion(rcv6[20+cycle:24+cycle])
            strain_list.append({"x":sx, "y":sy, "z":sz})
            #strain_list.append([sx, sy, sz])           

        json_data["AC"] = acc_list
        #print(acc_list)
        json_data["DS"] = strain_list
        time.sleep(d2)
        s1 = 'trigger='
        for x in json_data['trigger']:
            if  json_data['trigger'][x]=='1': s1 += f' {x}:1'
        json_data["Status"]="Ok"
        #print(json_data)
        return json_data

def get_status_data():
    global BaseTime

    spi.xfer2([0x27])
    time.sleep(ds)
    status_data_i_got = spi.xfer2([0x0]*14)

    timestamp   = status_data_i_got[3]  << 24 | status_data_i_got[2] << 16 | status_data_i_got[1] << 8 | status_data_i_got[0] - TimeCorrection
    solar   = status_data_i_got[7]  << 8  | status_data_i_got[6]
    battery  = status_data_i_got[9]  << 8  | status_data_i_got[8]
    vdd     = status_data_i_got[11] << 8  | status_data_i_got[10]

    solar, battery, vdd = status_conversion(solar, battery, vdd)

    status_data={}
    status_data["Timestamp"] = time_conversion( timestamp ) # board uptime
    status_data["resetFlag"] = status_data_i_got[5]  << 8  | status_data_i_got[4]
    status_data["solar"]     = solar #
    status_data["battery"]   = float(f'{battery:.1f}') #battery %
    status_data["vdd"]       = vdd
    status_data["errcode"]   = status_data_i_got[13] << 8  | status_data_i_got[12]
    print(status_data)
    return(status_data)


while True:
    j=get_status_data()
    j=data_receiving() 
