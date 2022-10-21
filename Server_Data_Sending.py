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
from threading import Thread, Lock
import threading
mutex=threading.Lock()

# board LED, power setting

import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(22, GPIO.OUT)   # 15, nRST
GPIO.setup(5, GPIO.OUT)    # 29, self en
GPIO.setup(24, GPIO.OUT)    # 18, LED_G
GPIO.setup(25, GPIO.OUT)    # 22, LED_R
GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP) # 16, RPI_EN

GPIO.output(22, True)
GPIO.output(24, True)
GPIO.output(25, True)
GPIO.output(5,  False)


'''
def callback_i1(channel):
    os.system("sudo shutdown now")
    #GPIO.output(5,  False)

GPIO.add_event_detect(23, GPIO.FALLING, callback=callback_i1)
'''

app= Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

            #counter      #시간
Time_Stamp={"TimeOffset":0,"BaseTime":datetime.now()}

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

#flush buffer first
spi.xfer2([0x41])
print('Flushing board buffer')

#하드웨어 보드의 설정상태 저장
board_fw = 0.03
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
    c_delta = stamp - Time_Stamp["TimeOffset"]
    return Time_Stamp["BaseTime"] + timedelta(milliseconds = c_delta)

def status_conversion(solar, battery, vdd):
    """
    solar   = 0.003013 * solar + 1.2824
    battery = battery / 4096 * 100  # 12-bit
    vdd     = vdd / 4096 * 100      # 12-bit
    """
    if solar >65000 :
        solar = 0
    else :
        #solar   = (solar*0.003809)/14.7*100        # linear voltage %, not capacity %
        solar   = (solar*0.003809)                  # linear voltage

    battery = (battery*0.001222)/4.2* 100      # linear voltage %, not capacity %
    vdd     = (vdd*0.000879)/ 3.3 * 100        # % 

    return solar, battery, vdd

def sync_time():
    global Time_Stamp
    
    spi.xfer2([0x27])
    time.sleep(ds)  
    s = spi.xfer2([0x0]*14)
   
    timeoffset = Time_Stamp["TimeOffset"] = (s[3] << 24 | s[2] << 16 | s[1] << 8 | s[0]) - TimeCorrection

    if timeoffset < 0:
        print(f"sync_time: invalid timeoffset= {timeoffset} skip ")
        return

    Time_Stamp["BaseTime"]=datetime.now()
    print(f"sync_time BaseTime= {Time_Stamp['BaseTime'].strftime('%Y-%m-%d %H:%M:%S.%f')}  Time_Stamp['TimeOffset']= {Time_Stamp['TimeOffset']}")
    return Time_Stamp["BaseTime"]

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
    # per request fro Park CEO  07/23
    #result = (result-16339000)/699.6956*(1.01)
    result = result*0.001444961 +500
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
    
    if board_fw < 0.03:
        result_int = Twos_Complement(result_str, 2)
        result = float(result_int)
        result /= 100
    else: 
        result_int = Twos_Complement(result_str, 4)
        result = float(result_int)
        result /= 10000
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

def strain_conversion(number_list):
    result_str = ''
    for i in reversed(range(len(number_list))):
        result_hex = hex(number_list[i])[2:]
        if len(result_hex)<2:
            result_hex = '0'+result_hex
        result_str += result_hex
    result = Twos_Complement(result_str, 4)
    # per request from Park CEO  07/23
    #result = result*0.00690750 # 단위는 microstrain
    #result = result*0.02889922 # half bridge 
    result =  result*0.0144496 # full bridge
    return result

def simpleLowPassFilter(prev_val, measured):
    
    tau = 3             # around 0.05Hz cut off
    filtered_value = (tau*prev_val + 1*measured)/(tau+1)

    return filtered_value

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

# dict data_receiving()
# 센서로부터 data bit를 받아, 그것을 적절한 int값으로 변환합니다.
# return value는 모든 센서 데이터를 포함하고 있는 dictionary 데이터입니다.
PrevXdeg =0
PrevYdeg =0
PrevZdeg =0
PrevCh4 = 0
PrevCh5 = 0

def data_receiving():
    global Offset
    global Time_Stamp
    global PrevXdeg
    global PrevYdeg
    global PrevZdeg
    global PrevCh4
    global PrevCh5
    #print("s:0x24")        # request header
    rcv1 = spi.xfer2([0x24])
    #print("header data signal")
    time.sleep(ds)

    #print("s:0x40")
    rcv2 = spi.xfer2([0x40]*8) # follow up action
    time.sleep(ds)
    #print(rcv2)
    #print(F"got {len(rcv2)}B {rcv2[0:20]}...")
    
    if rcv2[0] == 216 and rcv2[1] == 216:
        isReady = True
        json_data = {}
        #print("data is ready")
        status = basic_conversion(rcv2[2:4]) #status info save
        time_counter = int(basic_conversion(rcv2[4:8]),16)
        json_data["sensorTime"] = time_conversion(time_counter).strftime('%Y-%m-%d %H:%M:%S.%f') #timestamp info save.

        #print("trigger status : ", status_trigger_return(status)) #trigger 작동여부 출력 테스트 코드
        json_data["trigger"] = status_trigger_return(status)
    else:
        isReady = False
        fail_data = {"Status":"False"}
        return fail_data
        
    if isReady: #only send data if data is ready
        #print("s:"+ "0x26")        # request static
        rcv3 = spi.xfer2([0x26])
        #print(rcv3)
        #print("static sensor data signal")
        time.sleep(ds)

            #print("s:"+ "0x40")
        if board_fw <0.03 :
            rcv4 = spi.xfer2([0x40]*16) # follow up action
            #print(rcv4)
            degreeX = deg_conversion(rcv4[0:2]) + Offset['TI'] 
            degreeY = deg_conversion(rcv4[2:4]) + Offset['TI'] 
            degreeZ = deg_conversion(rcv4[4:6]) + Offset['TI'] 
            Temperature = tem_conversion(rcv4[6:8]) + Offset['TP']
            # 식을 dis_conversion으로 변경하여 해결하였음
            Displacement_ch4 = dis_conversion(rcv4[8:12]) + Offset['DI']
            Displacement_ch5 = dis_conversion(rcv4[12:]) + Offset['DI']
        else: 
            #print("s:"+ "0x40")
            rcv4 = spi.xfer2([0x40]*24) # follow up action
            #print(rcv4)
            degreeX = deg_conversion(rcv4[0:4]) + Offset['TI'] 
            degreeY = deg_conversion(rcv4[4:8]) + Offset['TI'] 
            degreeZ = deg_conversion(rcv4[8:12]) + Offset['TI'] 

            degreeX = simpleLowPassFilter(PrevXdeg,degreeX)
            degreeY = simpleLowPassFilter(PrevYdeg,degreeY)
            degreeZ = simpleLowPassFilter(PrevZdeg,degreeZ)

            PrevXdeg = degreeX
            PrevYdeg = degreeY
            PrevZdeg = degreeZ
            
            Temperature = tem_conversion(rcv4[12:14]) + Offset['TP']
            # 14~15 is skipped by mcu compiler!
            # 식을 dis_conversion으로 변경하여 해결하였음
            Displacement_ch4 = dis_conversion(rcv4[16:20]) + Offset['DI']
            Displacement_ch5 = dis_conversion(rcv4[20:]) + Offset['DI']

            Displacement_ch4 = simpleLowPassFilter(PrevCh4, Displacement_ch4)
            Displacement_ch5 = simpleLowPassFilter(PrevCh5, Displacement_ch5)

            PrevCh4 = Displacement_ch4
            PrevCh5 = Displacement_ch5

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
            sx = strain_conversion(rcv6[12+cycle:16+cycle])
            sy = strain_conversion(rcv6[16+cycle:20+cycle])
            sz = strain_conversion(rcv6[20+cycle:24+cycle])
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
        return json_data

def set_config_data(jdata):
    global Offset
    # set offset, already defauled to 0
    '''
    if '-AC_' in aename: Offset['ac'] = config['cmeasure']['offset']  
    if '-DI_' in aename: Offset['di'] = config['cmeasure']['offset']  
    if '-TI_' in aename: Offset['ti'] = config['cmeasure']['offset']  
    if '-TP_' in aename: Offset['tp'] = config['cmeasure']['offset']  


    sel_sensor=0
    for stype in jdata:
        Offset[stype]=jdata[stype]['offset']
        if jdata[stype]['use']=='Y': 
            sel_sensor += jdata[stype]['select']
        
    
    # making triger_seltect

    ttp = tdi = tti = tac = 0
    tp1h = tp1l = di1h = di1l = ti1h = ti1l = ac1h = 0

    if '-AC_' in aename and 'use' in config['ctrigger'] and config['ctrigger']['use'] in {'Y','y'}: 
        tac = int(0x0100)
        if 'st1high' in config['ctrigger'] and str(config['ctrigger']['st1high']).isnumeric(): ac1h = int(config['ctrigger']['st1high'])
    if '-DI_' in aename and 'use' in config['ctrigger'] and config['ctrigger']['use'] in {'Y','y'}:
        tdi = int(0x0800)
        if 'st1high' in config['ctrigger'] and str(config['ctrigger']['st1high']).isnumeric(): di1h = int(config['ctrigger']['st1high'])
        if 'st1low' in config['ctrigger'] and str(config['ctrigger']['st1high']).isnumeric(): di1l = int(config['ctrigger']['st1low'])
        di1l = config['ctrigger']['st1low']
    if '-TI_' in aename and 'use' in config['ctrigger'] and config['ctrigger']['use'] in {'Y','y'}:
        tti = int(0x0200)
        if 'st1high' in config['ctrigger'] and str(config['ctrigger']['st1high']).isnumeric(): ti1h = int(config['ctrigger']['st1high'])
        if 'st1low' in config['ctrigger'] and str(config['ctrigger']['st1high']).isnumeric(): ti1l = int(config['ctrigger']['st1low'])
    if '-TP_' in aename and 'use' in config['ctrigger'] and config['ctrigger']['use'] in {'Y','y'}:
        ttp = int(0x1000)
        if 'st1high' in config['ctrigger'] and str(config['ctrigger']['st1high']).isnumeric(): tp1h = int(config['ctrigger']['st1high'])
        if 'st1low' in config['ctrigger'] and str(config['ctrigger']['st1high']).isnumeric(): tp1l = int(config['ctrigger']['st1low'])
    '''

    # formatting for GBC data structure and tranmisssion (two bytes) 
    # Revise latter!!!
    global board_setting
    board_setting['samplingRate'] =   int(np.uint16(100))           # hw fix 5/9
    board_setting['sensingDuration'] = int(np.uint16(12*60*60))     # hw fix 5/9
    board_setting['measurePeriod'] =  int(np.uint16(1))             # SC support 5/9 
    board_setting['uploadPeriod'] =   int(np.uint16(6))             # hSC support 5/9
    #board_setting['sensorSelect'] =   int(np.uint16(ttp|tdi|tti|tac))
    board_setting['sensorSelect'] =   int(np.uint16(0x0100))
    board_setting['highTemp'] =       int(np.int16(jdata['TP']['st1high']*100))
    board_setting['lowTemp'] =        int(np.int16(jdata['TP']['st1low']*100))


    # per req from Park CEO 07/23
    #board_setting['highDisp'] =       int(np.uint16((jdata['DI']['st1high']*692.9678+16339000)/1024))
    #board_setting['lowDisp'] =        int(np.uint16((jdata['DI']['st1low']*692.9678+16339000)/1024))
    #old equations. to enable triggering in GBC, revise this
    board_setting['highDisp'] =       int(np.uint16(0))
    board_setting['lowDisp'] =        int(np.uint16(0))

    ###############
    board_setting['highStrain'] =     int(np.int16(0)) # strain의 보드 설정을 위한 코드 수정 필요
    board_setting['lowStrain'] =      int(np.int16(0))
    ###############

    board_setting['highTilt'] =       int(np.int16(jdata['TI']['st1high']*100))
    board_setting['lowTilt'] =        int(np.int16(jdata['TI']['st1low']*100))
    board_setting['highAcc'] =        int(np.uint16(jdata['AC']['st1high']/0.0039/16))
    board_setting['lowAcc'] =         int(np.int16(0))       # hw fix 5/9
    # end of formatting 
    return board_setting 


def get_status_data():
    spi.xfer2([0x27])
    time.sleep(ds)
    s = spi.xfer2([0x0]*14)

    timestamp   = (s[3]<<24 | s[2]<<16 | s[1]<<8 | s[0]) - TimeCorrection
    battery  = s[9]<<8 | s[8]   
    solar = s[7]<<8 | s[6]
    vdd = s[11]<<8 | s[10]

    #r=f'solar,battery,vdd= {solar},{battery},{vdd} ==> '
    solar, battery, vdd = status_conversion(solar, battery, vdd)
    #r+=f' {solar},{battery},{vdd}'
    #print(r)

    status_data={}
    status_data["time"] = time_conversion(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    status_data["battery"]   = float(f'{battery:.1f}') # internal battery %
    status_data["resetFlag"] = s[5]<<8 | s[4]   
    status_data["solar"]     = float(f'{solar:.1f}') # external battery %
    status_data["vdd"]       = float(f'{vdd:.1f}') # V
    status_data["errcode"]   = s[13]<<8 | s[12]  
    return(status_data)

    
@app.route('/sync')
def sync():
    sync_time()
    return {"Status":"Ok", "Origin":"sync", "BaseTime": Time_Stamp["BaseTime"].strftime('%Y-%m-%d %H:%M:%S.%f'), "TimeOffset":Time_Stamp["TimeOffset"]}

@app.route('/capture')
def capture():
    mutex.acquire(blocking=True, timeout=0.5)
    if not mutex.locked():
        print('data_capture: mutex failed')
        data={}
        data['Origin']='capture'
        data['Status']='False: mutex fail'
        return data
    data = data_receiving()
    mutex.release()
    data['Origin']='capture'
    return data

@app.route('/status')
def status():
    mutex.acquire(blocking=True, timeout=0.5)
    if not mutex.locked():
        print('status_capture: mutex failed')
        data={}
        data['Origin']='status'
        data['Status']='False: mutex fail'
        return data

    data=get_status_data()
    mutex.release()
    data["Status"]="Ok"
    data["Origin"]='status'
    return data

@app.route('/config', methods=['GET', 'POST'])
def config():
    mutex.acquire(blocking=True, timeout=0.5)
    if not mutex.locked():
        print('config: mutex failed')
        data={}
        data['Origin']='config'
        data['Status']='False: mutex fail'
        return data

    sending_config_data = [0x09]
    Config_data = set_config_data(request.json)
    print(f'CONFIG wrote to board')
    print(Config_data)

    # assuming all values are two bytes
    for tmp in Config_data.values():
        # convert order to GBC parsing
        #sending_config_data.append(tmp >> 8)
        #sending_config_data.append(tmp & 0xFF)
        sending_config_data.append(tmp & 0xff) 
        sending_config_data.append(tmp >> 8)
    rcv = spi.xfer2(sending_config_data)
    mutex.release()
    return {"Status":"Ok", "Origin":"config"}

if __name__ == '__main__':
    sync()
    app.run()
