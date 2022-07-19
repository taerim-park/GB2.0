# Client_Data_Saving.py
# 소켓 서버로 'CAPTURE' 명령어를 1초에 1번 보내, 센서 데이터값을 받습니다.
# 받은 데이터를 센서 별로 분리해 각각 다른 디렉토리에 저장합니다.
# 현재 mqtt 전송도 이 프로그램에서 담당하고 있습니다.
VERSION='20220718_V1.45'
print('\n===========')
print(f'Verion {VERSION}')

from encodings import utf_8
from threading import Timer, Thread
import random
from typing import Type
import requests
import json
import os
import sys
import time
import re
import signal
from datetime import datetime, timedelta
from time import process_time
from paho.mqtt import client as mqtt
from events import Events
from RepeatedTimer import RepeatedTimer
from graph import mygraph
import myserial

import logging
from flask import Flask, request, json, make_response, send_file
app= Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


import create  #for Mobius resource
import versionup
import make_oneM2M_resource
import savedData
import state
import camera

from conf import csename, memory, ae, slack, port, host as broker, boardTime, supported_sensors, root, TOPIC_list
dev_busy=0

# head insert point  tail removing point

schedule={}
    # schedule{aename: {   
        #'config':{},
        #'status':{}
        #'measure':{}
    # }

TOPIC_callback=f'/oneM2M/req/{csename}/#'
TOPIC_response=f'/oneM2M/resp/{csename}'
mqttc=""
command=""
m10={} # 매 10분단위 숫자

# key==aename
trigger_activated={}

# single value for all ae
gotBoardTime = False
doneFirstShoot={}

# 다중 데이터의 경우, 어떤 data를 저장할지 결정해야한다
acc_axis = "x" # x, y, z중 택1
deg_axis = "x" # x, y, z중 택1
str_axis = "x" # x, y, z중 택1
dis_channel = "ch4" # ch4, ch5중 택1

def sigint_handler(signal, frame):
    print()
    print()
    print('got restart command.  exiting...')
    os._exit(0)
signal.signal(signal.SIGINT, sigint_handler)

def sensor_type(aename):
    return aename.split('-')[1][0:2]


make_oneM2M_resource.makeit()
print('done any necessary Mobius resource creation')

# dict jsonCreate(dataTyep, timeData, realData)
# 받은 인자를 통해 딕셔너리를 생성합니다.
def jsonCreate(dataType, timeData, realData):
    data = {
        "type":dataType,
        "time":timeData,
        "data":realData
        }
    return data


# void jsonSave(path, jsonFile)
# 받은 dict를 json으로 변환한 후, 지정된 path에 저장합니다.
# 파일명은 기본적으로 날짜

def jsonSave(aename, jsonFile):
    global memory 
    mymemory = memory[aename]
    # remove microsec 2022-05-30 03:20:01.477113
    now_time = datetime.strptime(jsonFile['time'].split('.')[0],'%Y-%m-%d %H:%M:%S')
    if mymemory["head"] == "": 
        mymemory["head"] = now_time - timedelta(seconds=1)
        mymemory["tail"]= now_time

    sec = int((now_time - mymemory["head"]).total_seconds())
    if sec>30:
        print(f'sec too big {sec} limiting to 30 sensor_time= {now_time} head= {mymemory["head"]}')
        sec=10
    while sec>0:
        mymemory["head"] = mymemory["head"] + timedelta(seconds=1)
        mymemory["file"][mymemory["head"].strftime('%Y-%m-%d-%H%M%S')]=jsonFile
        if sec>1: print(f'{aename} json cover missing one by adding key={mymemory["head"].strftime("%Y-%m-%d-%H%M%S")} len={len(mymemory["file"])}')
        else: 
            rpitime = datetime.now()
            if len(mymemory["file"])%60 ==0: print(f'{aename} json add {mymemory["head"].strftime("%Y-%m-%d-%H%M%S")} len= {len(mymemory["file"])} board= {boardTime.strftime("%H:%M:%S")} rpi= {rpitime.strftime("%H:%M:%S")} diff= +{(boardTime-rpitime).total_seconds():.1f}s (next measure= {schedule[aename]["measure"].strftime("%Y-%m-%d %H:%M:%S")} state= {schedule[aename]["state"].strftime("%Y-%m-%d %H:%M:%S")})')
        sec -= 1
    
    while len(mymemory["file"])>660:
        try:
            del mymemory["file"][mymemory["tail"].strftime('%Y-%m-%d-%H%M%S')]
            print(f'{aename} removing extra json > 600  {mymemory["tail"].strftime("%Y-%m-%d-%H%M%S")}')
        except:
            print(f'{aename} tried to remove ghost {mymemory["tail"].strftime("%Y-%m-%d-%H%M%S")}')
            
        mymemory["tail"] = mymemory["tail"] + timedelta(seconds=1)


def save_conf(aename):
    with open(F"{root}/{aename}.conf","w") as f: f.write(json.dumps(ae[aename], ensure_ascii=False,indent=4))
    print(f"wrote {aename}.conf")

def do_user_command(aename, jcmd):
    global ae, schedule

    # boolean type_check(value, type)
    # value가 입력된 자료형인지 검사합니다. 같을시 True, 틀릴시 False를 반환합니다.
    # 예외로, double이 입력된 경우 float나 int 중 하나라면 True를 반환합니다. double value에 정수가 들어갈 수 있기 때문입니다.
    def type_check(value, _type):
        _int = 1
        _double = 1.12 # 파이썬에서는 float
        _string = "test"
        _array = [1, 2, 3] # 파이썬에서는 list
        if _type == "int":
            return type(_int)==type(value)
        elif _type == "double":
            return (type(_double)==type(value) or type(_int)==type(value))
        elif _type == "string":
            return type(_string)==type(value)
        elif _type == "array":
            return type(_array)==type(value)
        else: # type명이 틀린 경우, 일단 False를 반환
            print("ERROR : inavailable type")
            return False

    
    # keyword별 type 검사를 위한 딕셔너리
    type_dict = {
        ### ctrigger 시작###
        "use":"string", 
        "mode":"int", # time에도 존재. 같은 type이기에 따로 분리하지 않음
        "st1high":"double",
        "st1low":"double",
        "bfsec":"int",
        "afsec":"int",
        ### ctrigger 끝, cmeasure 시작 ###
        "formula":"string",
        "sensitivity":"double",
        "samplerate":"string",
        "offset":"double",
        "measureperiod":"int", #measureperiod의 유효성은 하단에서 검사하나, key error 방지를 위해 dict에는 기입
        "stateperiod":"int",
        "rawperiod":"int",
        "usefft":"string",
        "st1min":"double",
        "st1max":"double",
        "st2min":"double",
        "st2max":"double",
        "st3min":"double",
        "st3max":"double",
        "st4min":"double",
        "st4max":"double",
        "st5min":"double",
        "st5max":"double",
        "st6min":"double",
        "st6max":"double",
        "st7min":"double",
        "st7max":"double",
        "st8min":"double",
        "st8max":"double",
        "st9min":"double",
        "st9max":"double",
        "st10min":"double",
        "st10max":"double",
        ### cmeasure 끝, connect 시작 ###
        "cseip":"string",
        "cseport":"int",
        "csename":"string",
        "cseid":"string",
        "mqttip":"string",
        "mqttport":"int",
        "uploadip":"string",
        "uploadport":"int",
        ### connect 끝, time 시작 ###
        "zone":"string",
        "ip":"string",
        "port":"int",
        "period":"int"
        ### time 끝 ###
    }

    def warn_state(msg):
        global ae
        ae[aename]['state']["abflag"]="Y"
        ae[aename]['state']["abtime"]=boardTime.strftime("%Y-%m-%d %H:%M:%S")
        ae[aename]['state']["abdesc"]=msg
        print(msg)
        state.report(aename)
    
    print(f'got command= {jcmd}')
    if "cmd" not in jcmd: # 명령어에 키워드 "cmd"가 없는 경우, 오류 report
        warn_state(F"there is no keyword: {cmd}")
        return

    cmd=jcmd['cmd']
    if 'reset' in cmd:
        file=f"{root}/{aename}.conf"
        if os.path.exists(file): 
            os.remove(file)
            print(f'removed {aename}.conf')
        else:
            print(f'no {aename}.conf to delete')
        os.system("sudo reboot")
        return

    if 'reboot' in cmd:
        os.system("sudo reboot")

    if cmd in {'synctime'}:
        do_timesync()
        return 

    if cmd in {'fwupdate'}:
        url= f'{jcmd["protocol"]}://{jcmd["ip"]}:{jcmd["port"]}{jcmd["path"]}'
        versionup.versionup(aename, url)
        #will restart too
        return

    if cmd in {'realstart'}:
        if sensor_type(aename) == "CM":
            warn_state(F"type CM does not support command : {cmd}")
        else:
            print('start mqtt real tx')
            ae[aename]['local']['realstart']='Y'
        return

    if cmd in {'realstop'}:
        if sensor_type(aename) == "CM":
            warn_state(F"type CM does not support command : {cmd}")
        else:
            print('stop mqtt real tx')
            ae[aename]['local']['realstart']='N'
        return

    if cmd in {'reqstate'}:
        # 얘는 board에서 읽어오는 부분이있다. 
        do_status()
        ae[aename]['state']["abflag"]="N"
        state.report(aename)
        return

    if cmd in {'measurestart'}:
        ae[aename]['config']['cmeasure']['measurestate']='measuring'
        create.ci(aename, 'config', 'cmeasure')
        save_conf(aename)
        return

    if cmd in {'measurestop'}:
        ae[aename]['config']['cmeasure']['measurestate']='stopped'
        create.ci(aename, 'config', 'cmeasure')
        save_conf(aename)
        return

        ### 여기까지가 type check 필요없는 명령어들 ###

    if cmd in {'settrigger', 'setmeasure'}: # 220620갱신 : 본문에 바로 명령어가 작성된다는 점에 주의
        if 'settrigger' in cmd:
            if sensor_type(aename) == "CM": # 카메라는 trigger 설정을 지원하지 않음
                warn_state(F"type CM does not support command : {cmd}")
                return
            
            command_key = 'settrigger'
        elif 'setmeasure' in cmd:
            command_key = 'setmeasure'

        del jcmd["cmd"] # 검사 이전에 명령어만을 제외한다

        ckey = cmd.replace('set','c')  # ctrigger, cmeasure
        k1=set(jcmd) - {'use','mode','st1high','st1low','bfsec','afsec'} #ctrigger 명령어의 키워드 유효성 검사
        if command_key == 'settrigger' and len(k1)>0:
            m="Invalid key in settrigger command: "
            for x in k1: m += f" {x}"
            warn_state(m)
            return

        #cmeasure 명령어의 키워드 유효성 검사
        k1=set(jcmd) - {'sensitivity','offset','measureperiod','stateperiod', 'rawperiod', 'usefft', 'st1max', 'st1min', 'st2max', 'st2min', 'st3max', 'st3min', 'st4max', 'st4min', 'st5max', 'st5min', 'st6max', 'st6min', 'st7max', 'st7min', 'st8max', 'st8min', 'st9max', 'st9min', 'st10max', 'st10min','formula', 'samplerate'}
        if command_key == 'setmeasure' and len(k1)>0:
            m="Invalid key in setmeasure command: "
            for x in k1: m += f" {x}"
            warn_state(m)
            return

        if 'measureperiod' in jcmd: 
            if not isinstance(jcmd["measureperiod"],int):
                warn_state("measureperiod must be integer. defaulted to 600")
                jcmd['measureperiod']=600
            elif jcmd["measureperiod"] < 600:
                warn_state("measureperiod must be bigger than 600. defaulted to 600")
                jcmd['measureperiod']=600
                return
            elif jcmd["measureperiod"]%600 != 0:
                warn_state(f"measureperiod must be multiples of 600. modified to {int(jcmd[x]/600)*600} and accepted")
                jcmd['measureperiod']= int(jcmd[x]/600)*600
        
        isTypeWrong = False
        TypeWrongMessage = "type error : "
        for k in jcmd: # keyword를 적용하기 전에 type이 옳은지 검사한다
            if not type_check(jcmd[k], type_dict[k]): 
                isTypeWrong = True
                TypeWrongMessage += F"\n {k} must be {type_dict[k]}"
        # 하나라도 False가 나오면, 검사는 실패로 돌아가며 state에 error report를 시행
        if isTypeWrong:
            warn_state(TypeWrongMessage)
            return

        for k in jcmd:
            ae[aename]['config'][ckey][k] = jcmd[k] # type check를 통과한 경우에만 새로운 설정값을 입력해넣는다
        setboard=False
        if ckey=='cmeasure' and 'offset' in jcmd: 
            #print(f" {aename} {ckey} will write to board")
            setboard=True
        if ckey=='ctrigger' and len({'use','st1high', 'st1low'} & jcmd.keys()) !=0: 
            #print(f" {aename} {ckey} will write to board")
            setboard=True
        if setboard:
            # 얘는 board에 설정하는 부분이 있다.
            do_config()
        save_conf(aename)
        create.ci(aename, 'config', ckey)
        if 'stateperiod' in jcmd:
            ae[aename]['state']["abflag"]="N"
            state.report(aename)
        return

    if cmd in {'settime'}:
        del jcmd["cmd"]
        k1=set(jcmd) - {'ip', 'mode', 'period', 'port', 'zone'} #time 명령어의 키워드 유효성 검사
        if len(k1)>0:
            m=f"Invalid key in time command: {k1}"
            for x in k1: m += f" {x}"
            warn_state(m)
            return

        print(f'set time= {jcmd}')
        isTypeWrong = False
        TypeWrongMessage = "type error : "
        for k in jcmd: # keyword를 적용하기 전에 type이 옳은지 검사한다
            if not type_check(jcmd[k], type_dict[k]): 
                isTypeWrong = True
                TypeWrongMessage += F"\n {k} must be {type_dict[k]}"
        # 하나라도 False가 나오면, 검사는 실패로 돌아가며 state에 error report를 시행
        if isTypeWrong:
            warn_state(TypeWrongMessage)
            return
        for x in jcmd: # type 검사에 성공했다면 설정값 입력
            ae[aename]["config"]["time"][x]= jcmd[x]
        save_conf(aename)
        create.ci(aename, 'config', 'time')
        return

    if cmd in {'setconnect'}:
        del jcmd["cmd"]
        k1=set(jcmd) - {'cseid', 'cseip', 'csename', 'cseport', 'mqttip', 'mqttport', 'uploadip', 'uploadport'} #connect 명령어의 키워드 유효성 검사
        if len(k1)>0:
            m="Invalid key in connect command: "
            for x in k1: m += f" {x}"
            warn_state(m)
            return

        print(f'set {aename}/connect= {jcmd}')
        isTypeWrong = False
        TypeWrongMessage = "type error : "
        for k in jcmd: # keyword를 적용하기 전에 type이 옳은지 검사한다
            if not type_check(jcmd[k], type_dict[k]): 
                isTypeWrong = True
                TypeWrongMessage += F"\n {k} must be {type_dict[k]}"
        # 하나라도 False가 나오면, 검사는 실패로 돌아가며 state에 error report를 시행
        if isTypeWrong:
            warn_state(TypeWrongMessage)
            return
        for x in jcmd: # type 검사에 성공했다면 설정값 입력
            ae[aename]['config']["connect"][x]=jcmd[x]
        create.ci(aename, 'config', 'connect')
        save_conf(aename)
        return

    if cmd == 'takepicture':
        if sensor_type(aename) == "CM":
            camera.take_picture_command(boardTime, aename) # 사진을 찍어 올린다
        else:
            warn_state(F"type {sensor_type(aename)} does not support such command : takepicture")
        return

    if cmd in 'autossh':
        print("autossh ON")
        os.system("sudo systemctl start autossh")
        return

    if cmd == 'inoon':
        cmd2=jcmd['cmd2']
        if cmd2=="ae": 
            slack(aename, json.dumps(ae[aename], indent=4))
            print(json.dumps(ae, indent=4))
        elif cmd2=="slack":
            ae[aename]['local']['slack']=jcmd['slack']
            print(f"activated slack monitoring: {ae[aename]['local']['slack']}")
            save_conf(aename)
        elif cmd2=="noslack":
            del ae[aename]['local']['slack']
            print(f"deactivated slack monitoring")
            save_conf(aename)
        elif cmd2=='setting':
            msg="aename measurestate measureperiod stateperiod use mode bfsec afsec realstart\n"
            for n in ae: msg+=f"{n} {ae[n]['config']['cmeasure']['measurestate']} {ae[n]['config']['cmeasure']['measureperiod']} {ae[n]['config']['cmeasure']['stateperiod']} {ae[n]['config']['ctrigger']['use']} {ae[n]['config']['ctrigger']['mode']} {ae[n]['config']['ctrigger']['bfsec']} {ae[n]['config']['ctrigger']['afsec']} {ae[n]['local']['realstart']}\n"
            slack(aename, msg)
    else:
        warn_state(f'invalid cmd {jcmd}')
        

def got_callback(topic, msg):
    aename=topic[4] 
    if aename in ae:
        #print(topic, aename,  msg)
        try:
            j=json.loads(msg)
        except:
            print(f"json error {msg}")
            return
        try:
            jcmd=j["pc"]["m2m:sgn"]["nev"]["rep"]["m2m:cin"]["con"]
        except KeyError as msg:
            print(F"not available json : {j}")
            return
        print(f" ==> {aename} {jcmd}")
        do_user_command(aename, jcmd)

        resp_topic=f'{TOPIC_response}/{aename}/json'
        r = {}
        r['m2m:rsp'] = {}
        r['m2m:rsp']["rsc"] = 2001
        r['m2m:rsp']["to"] = ''
        r['m2m:rsp']["fr"] = aename
        r['m2m:rsp']["rqi"] = j["rqi"]
        r['m2m:rsp']["pc"] = ''
        mqttc.publish(resp_topic, json.dumps(r, ensure_ascii=False))
        print(f'response {resp_topic} {j["rqi"]}')

    else:
        #print(' ==> not for me', topic, msg[:20],'...')
        pass





def connect_mqtt():
    global mqttc
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to {broker} via MQTT")
            client.subscribe(TOPIC_callback)
            print(f"subscribed to {TOPIC_callback}")
        else:
            print("Failed to connect, return code %d\n", rc)

    def on_disconnect(client, userdata, rc):
        print("Disconnected from MQTT server!")

    def on_message(client, _topic, _msg):
        topic=_msg.topic.split('/')
        msg=_msg.payload.decode('utf8')
        got_callback(topic, msg)


    client_id = f'python-mqtt-{random.randint(0, 1000000)}'
    mqttc = mqtt.Client(client_id)
    mqttc.on_connect = on_connect
    mqttc.on_disconnect = on_disconnect
    mqttc.on_message = on_message
    mqttc.connect(broker, port)
    return mqttc

mqttc = connect_mqtt()
mqttc.loop_start()
print("mqtt 연결에 성공했습니다.")

        
# void mqtt_sending(aename, data)
# mqtt 전송을 수행합니다. 단, mqtt 전송을 사용하지 않기로 한 센서라면, 수행하지 않습니다.
# 센서에 따라 다른 TOPIC에 mqtt 메시지를 publish합니다.
def mqtt_sending(aename, data):   
    if mqttc=="":
        connect_mqtt()

    now = datetime.now()
    test_list = list()
    if type(data) == type(test_list):
        count = len(data)
        BODY = {
            "start":boardTime.strftime("%Y-%m-%d %H:%M:%S"),
            "samplerate":ae[aename]["config"]["cmeasure"]['samplerate'],
            "count":count,
            "data":data
        }
    else:
        array_data = list()
        array_data.append(data)
        count = 1
        BODY = {
            "start":boardTime.strftime("%Y-%m-%d %H:%M:%S"),
            "samplerate":ae[aename]["config"]["cmeasure"]['samplerate'],
            "count":count,
            "data":array_data
            }

    mqttc.publish(F'/{csename}/{aename}/realtime', json.dumps(BODY, ensure_ascii=False))
    


time_old=datetime.now()

def do_config():
    print(f'do_config()')

    setting={ 'AC':{'use':'N','st1high':0,'st1low':0, 'offset':0},
                'DI':{'use':'N','st1high':0,'st1low':0, 'offset':0},
                'TI':{'use':'N','st1high':0,'st1low':0, 'offset':0},
                'DS':{'use':'N','st1high':0,'st1low':0, 'offset':0},
                'TP':{'use':'N','st1high':0,'st1low':0, 'offset':0}}
    for aename in ae:
        if sensor_type(aename) != 'CM':
            cmeasure = ae[aename]['config']['cmeasure']
            if 'offset' in cmeasure:
                setting[sensor_type(aename)]['offset'] = cmeasure['offset']
            ctrigger = ae[aename]['config']['ctrigger']
            if 'use' in ctrigger:
                setting[sensor_type(aename)]['use'] = ctrigger['use']
                if 'st1high' in ctrigger: setting[sensor_type(aename)]['st1high']= ctrigger['st1high']
                if 'st1low' in ctrigger: setting[sensor_type(aename)]['st1low']= ctrigger['st1low']
        #print(f"do_config board seting= {setting}")

    try:
        r = requests.post('http://localhost:5000/config', json=setting)
        if not r.status_code==200:
            print(F"got do_config {r.status_code} skip")
            return
        j= r.json()
        print(f"got j={j}")
    except requests.exceptions.RequestException as err:
        print(f"error in requests {err}")
        return


def do_trigger_followup(aename):
    global ae

    #print(f'trigger_followup {aename}')
    dtrigger=ae[aename]['data']['dtrigger']
    ctrigger = ae[aename]['config']['ctrigger']
    trigger = datetime.strptime(dtrigger['time'],'%Y-%m-%d %H:%M:%S')

    stype = sensor_type(aename)
    mymemory=memory[aename]

    data = list()
    start=""
    for i in range(-ctrigger['bfsec'],ctrigger['afsec']):
        key = datetime.strftime(trigger + timedelta(seconds=i), "%Y-%m-%d-%H%M%S")
        try:
            json_data = mymemory["file"][key]
            if start=="": start= datetime.strptime(key,'%Y-%m-%d-%H%M%S')
        except:
            print(f' skip i={i}', end='')
            continue
        if isinstance(json_data['data'], list): data.extend(json_data["data"])
        else: data.append(json_data["data"]) 
    
    #print(f'found {len(data_path_list)} files')

    dtrigger['count']=len(data)
    dtrigger['data']= data #data를 나누어 넣던 것을 원래대로 돌려놓았음
    dtrigger["start"] = start.strftime("%Y-%m-%d %H:%M:%S")
    #create.ci(aename, 'data', 'dtrigger')
    t1 = Thread(target=create.ci, args=(aename, 'data', 'dtrigger'))
    t1.start()
    print(f"comiled trigger data: {len(data)} bytes for bfsec+afsec= {ctrigger['bfsec']+ctrigger['afsec']}")

def do_timesync():
    try:
        r = requests.get('http://localhost:5000/sync')
        print(F"do_timesync {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {r.json()}")
    except requests.exceptions.RequestException as err:
        print(f"do_timesync {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} error in requests {err}")
        return


def do_status():
    try:
        r = requests.get('http://localhost:5000/status')
        if not r.status_code==200:
            print("got do_status {r.statue_code} skip")
            return
    except requests.exceptions.RequestException as err:
        print(f"error in requests {err}")
        return

    j= r.json()
    print(f"got j={j}")
    if not j['Status']=='Ok':
        print(f"got do_status error")
        return

    for aename in ae:
        ae[aename]['state']['battery']=j['battery']


def do_capture():
    global mqtt_measure, time_old
    global trigger_activated
    global ae
    global boardTime, gotBoardTime, schedule

    t0_start=process_time()
    t1_start=process_time()
    t1_msg="0s"
    #print('do capture')

    try:
        r = requests.get('http://localhost:5000/capture')
        if not r.status_code==200:
            print("got do_capture {r.statue_code} skip")
            return
    except requests.exceptions.RequestException as err:
        print(f"error in requests {err}")
        return

    j= r.json()
    #print(f"got j={j}")

    global dev_busy
    if j['Status'] == 'False':
        dev_busy +=1
        if dev_busy > 1: print(f"rpiTime= {datetime.now().strftime('%H:%M:%S')} device-busy {dev_busy}")
        return 

    t1_msg += f' - server2client - {process_time()-t1_start:.1f}s' 

    # receive good data
    dev_busy=0
    boardTime = datetime.strptime(j['Timestamp'],'%Y-%m-%d %H:%M:%S')
    print(f"boardTime@capture= {boardTime.strftime('%H:%M:%S')} rpiTime= {datetime.now().strftime('%H:%M:%S')} counter={j['counter']} {(boardTime-datetime.now()).total_seconds():.1f}")
    if not gotBoardTime:
        gotBoardTime = True
        schedule_first()

    # print(f"trigger= {j['trigger']}"

    # start of trigger
    for aename in ae: 
        if sensor_type(aename) == "CM": # 카메라는 trigger동작을 하지 않기 때문에 넘긴다
            continue
        ctrigger=ae[aename]['config']['ctrigger']
        cmeasure=ae[aename]['config']['cmeasure']
        dtrigger=ae[aename]['data']['dtrigger']
        #print(f"aename= {aename} stype= {sensor_type(aename)} use= {ctrigger['use']}")

        def print_trigger(trig):
            msg =""
            for x in trig: 
                if msg != "": msg += " "
                if trig[x]=='1': msg+=f"{x}"
            return msg

        def all_trigger(trig):
            for x in trig: 
                if trig[x]=='1': return True
            return False

        # trigger counter가 살아있으면 -1  downcount
        if trigger_activated[aename] >0: 
            trigger_activated[aename] -= 1
            print(f" trigger-counting-afsec-{trigger_activated[aename]}")
            continue

        # aename에 트리거 이미 진행중인 경우 먼저 처리
        if trigger_activated[aename]==0:  # afsec 충족된 상태
            do_trigger_followup(aename)
            trigger_activated[aename]=-1  # -1 값이면 no trigger in progress
            continue

        tmsg=""
        # We do have (a) trigger(s)
        if all_trigger(j['trigger']):
            tmsg=f" got-trigger {print_trigger(j['trigger'])}"

        # skip if not for me
        if j['trigger'][sensor_type(aename)]=='0': 
            #tmsg +=  f" not-for-me-{aename}-skip"
            #print(tmsg)
            continue

        # skip if not measuring
        if cmeasure['measurestate'] != 'measuring':
            #tmsg += f" not-measuring-{aename}-skip"
            #print(tmsg)
            continue

        # skip if not enabled
        if ctrigger['use'] not in {'Y','y'}:
            #tmsg+= f" not-enabled-{aename}-skip"
            #print(tmsg)
            continue

        # 새로운 trigger 처리
        if sensor_type(aename) == "AC": # 동적 데이터의 경우, 트리거 전초와 후초를 고려해 전송 시행
            trigger_list = j["AC"]
            trigger_data = "unknown"
            for ac in trigger_list: # 트리거 조건을 충족시키는 가장 첫번째 값을 val에 저장하기 위해 일치하는 값을 찾으면 break
                if ctrigger['mode'] == 1 and ac[acc_axis] > ctrigger['st1high']:
                    trigger_data = ac[acc_axis]
                    break
                elif ctrigger['mode'] == 2 and ac[acc_axis] < ctrigger['st1low']:
                    trigger_data = ac[acc_axis]
                    break
                elif ctrigger['mode'] == 3:
                    if ac[acc_axis] > ctrigger['st1high'] and ac[acc_axis] < ctrigger['st1low']:
                        trigger_data = ac[acc_axis]
                        break
                elif ctrigger['mode'] == 4:
                    if ac[acc_axis] < ctrigger['st1high'] and ac[acc_axis] > ctrigger['st1low']:
                        trigger_data = ac[acc_axis]
                        break

            if trigger_data == "unknown":
                print(f" not-for-me-trig-condition-skip")
                continue
                
            dtrigger['val'] = trigger_data

            print(f" got-trigger-new-{aename}-bfsec={ctrigger['bfsec']}-afsec={ctrigger['afsec']}")
            if isinstance(ctrigger['afsec'],int) and ctrigger['afsec']>0: 
                trigger_activated[aename]=ctrigger['afsec']
            else: 
                trigger_activated[aename]=60  # value error, 60 instead

        
        elif sensor_type(aename) == "DS": # 동적 데이터의 경우, 트리거 전초와 후초를 고려해 전송 시행
            trigger_list = j["DS"]
            trigger_data = "unknown"
            for st in trigger_list: # 트리거 조건을 충족시키는 가장 첫번째 값을 val에 저장하기 위해 일치하는 값을 찾으면 break
                if ctrigger['mode'] == 1 and st[str_axis] > ctrigger['st1high']:
                    trigger_data = st[str_axis]
                    break
                elif ctrigger['mode'] == 2 and st[str_axis] < ctrigger['st1low']:
                    trigger_data = st[str_axis]
                    break
                elif ctrigger['mode'] == 3:
                    if st[str_axis] > ctrigger['st1high'] and st[str_axis]< ctrigger['st1low']:
                        trigger_data = st[str_axis]
                        break
                elif ctrigger['mode'] == 4:
                    if st[str_axis] < ctrigger['st1high'] and st[str_axis] > ctrigger['st1low']:
                        trigger_data = st[str_axis]
                        break

            
            if trigger_data == "unknown":
                print(f" not-for-me-trig-condition-skip")
                continue
                
            dtrigger['val'] = trigger_data

            print(f" got-trigger-new-{aename}-bfsec={ctrigger['bfsec']}-afsec={ctrigger['afsec']}")
            if isinstance(ctrigger['afsec'],int) and ctrigger['afsec']>0: 
                trigger_activated[aename]=ctrigger['afsec']
            else: 
                trigger_activated[aename]=60  # value error, 60 instead

        else:
            # 정적 데이터의 경우, 트리거 발생 당시의 데이터를 전송한다
            print(f"got non-AC trigger {aename}  bfsec= {ctrigger['bfsec']}  afsec= {ctrigger['afsec']}")
            dtrigger['start']=boardTime.strftime("%Y-%m-%d %H:%M:%S")
            dtrigger['count'] = 1
            
            # offset 은 서버에서 계산하다록 합니다. 현재는 클라이언트 2군데에서추가로 계산
            # 그런데 아래부분이  data를 만들기 때문에 삭제하면 에러가 발생.  그래서 data만 만들어지도록 둡니다.
            print(f"정적데이타offset연산  offset= {cmeasure['offset']}")

            '''
            if sensor_type(aename) == "DI": data = j["DI"][dis_channel]+cmeasure['offset']
            elif sensor_type(aename) == "TP": data = j["TP"]+cmeasure['offset']
            elif sensor_type(aename) == "TI": data = j["TI"][deg_axis]+cmeasure['offset'] # offset이 있는 경우, 합쳐주어야한다
            else: data = "nope"
            '''
            if sensor_type(aename) == "DI": data = j["DI"][dis_channel]
            elif sensor_type(aename) == "TP": data = j["TP"]
            elif sensor_type(aename) == "TI": data = j["TI"][deg_axis]
            else: data = "nope"

            #정말로 val값이 trigger를 만족시키는지 check해야함. 추후 추가.
            dtrigger['val'] = data

        dtrigger['time']=boardTime.strftime("%Y-%m-%d %H:%M:%S") # 트리거 신호가 발생한 당시의 시각
        dtrigger['mode']=ctrigger['mode']
        dtrigger['sthigh']=ctrigger['st1high']
        dtrigger['stlow']=ctrigger['st1low']
        dtrigger['step']=1
        dtrigger['samplerate']=cmeasure['samplerate']

        # AC need afsec
        if sensor_type(aename) == "AC" or sensor_type(aename) == "DS":
            #print("will process after afsec sec")
            pass
        else:
            #create.ci(aename, "data", "dtrigger") # 정적 트리거 전송은 따로 do_trigger_followup을 실행하지 않는다.
            t1 = Thread(target=create.ci, args=(aename, 'data', 'dtrigger'))
            t1.start()
            print("sent trigger for {aename}")

    t1_msg += f' - doneTrigger - {process_time()-t1_start:.1f}s' 

    # end of trigger            

    offset_dict = {
        "AC":0,
        "DI":0,
        "TP":0,
        "TI":0,
        "DS":0
    }

    '''
    for aename in ae:
        # skip if not measuring
        if ae[aename]['config']['cmeasure']['measurestate'] != 'measuring': continue

        cmeasure=ae[aename]['config']['cmeasure']
        type = sensor_type(aename)

        if type == 'TP' and 'offset' in cmeasure:
            offset_dict["TP"] = cmeasure['offset']
        elif type == 'DI' and 'offset' in cmeasure:
            offset_dict["DI"] = cmeasure['offset']
        elif type == "AC" and 'offset' in cmeasure:
            offset_dict["AC"] = cmeasure['offset']
        elif type == "TI" and 'offset' in cmeasure:
            offset_dict["TI"] = cmeasure['offset']
    '''

    Time_data = j["Timestamp"]
    Temperature_data = j["TP"] + offset_dict["TP"]
    Displacement_data = j["DI"][dis_channel] + offset_dict["DI"]
    
    acc_list = list()
    str_list = list()
    
    for i in range(len(j["AC"])):
        acc_list.append(j["AC"][i][acc_axis] + offset_dict["AC"])
    for i in range(len(j["DS"])):
        str_list.append(j["DS"][i][str_axis] + offset_dict["DS"]) #offset 기능 구현되어있지 않음
        
    #print(F"acc : {acc_list}")
    #samplerate에 따라 파일에 저장되는 data 조정
    #현재 가속도 센서와 변형률 센서에 적용중
    for aename in ae:
        # 동적 데이터의 경우, samplerate가 100이 아닌 경우에 대처한다
        if sensor_type(aename)=="AC" or sensor_type(aename)=="DS":
            ae_samplerate = float(ae[aename]["config"]["cmeasure"]["samplerate"])
            if ae_samplerate != 100:
                if 100%ae_samplerate != 0:
                    #100의 약수가 아닌 samplerate가 설정되어있는 경우, 오류가 발생한다
                    print("wrong samplerate config")
                    print("apply standard samplerate = 100")
                    ae_samplerate = 100
                merged_value = 0
                merge_count = 0
                sample_number = 100//ae_samplerate
                if sensor_type(aename)=="AC":
                    new_acc_list = list()
                    for i in range(len(acc_list)):
                        merged_value += acc_list[i]
                        merge_count += 1
                        if merge_count == sample_number:
                            new_acc_list.append(round(merged_value/sample_number, 2))
                            merge_count = 0
                            merged_value = 0
                    acc_list = new_acc_list
                else:
                    new_str_list = list()
                    for i in range(len(str_list)):
                        merged_value += str_list[i]
                        merge_count += 1
                        if merge_count == sample_number:
                            new_str_list.append(round(merged_value/sample_number, 2))
                            merge_count = 0
                            merged_value = 0
                    str_list = new_str_list
            #print("samplerate calculation end")
            #print(acc_list)
    Acceleration_data = acc_list
    Strain_data = str_list
    Degree_data = j["TI"][deg_axis]+ offset_dict["TI"]
    
    # 센서의 특성을 고려해 각 센서 별로 센서 data를 담은 dict 생성
    raw_json={}
    raw_json['TI'] = jsonCreate('TI', Time_data, Degree_data)
    raw_json['TP'] = jsonCreate('TP', Time_data, Temperature_data)
    raw_json['DI'] = jsonCreate('DI', Time_data, Displacement_data)
    raw_json['AC'] = jsonCreate('AC', Time_data, Acceleration_data)
    raw_json['DS'] = jsonCreate('DS', Time_data, Strain_data)
    

    # boardTime이 정시가딘것이  확인되면 먼저 데이타 전송  처리작업을 한다.  10분의 기간이 10:00 ~ 19:99 이기때문
    if gotBoardTime:
        if aename not in m10: m10[aename]=""
        if m10[aename]=="": m10[aename] = f'{boardTime.minute}'.zfill(2)[0]  # do not run at first, run first when we get new 10 minute
        if m10[aename] != f'{boardTime.minute}'.zfill(2)[0]:  # we got new 10 minute
            m10[aename] = f'{boardTime.minute}'.zfill(2)[0]
            print(f'GOT 10s minutes board= {boardTime.strftime("%H:%M:%S")} rpi= {datetime.now().strftime("%H:%M:%S")} {m10[aename]}0')
    
            timesync=False
            for aename in ae:
                # skip if not measuring
                if ae[aename]['config']['cmeasure']['measurestate'] != 'measuring': continue
    
                if schedule[aename]['measure'] <= boardTime:
                    # savedJaon() 에서 정적데이타는 아직 hold하고 있는 정시데이타를 보내야 한다. 그래서 j 공급  
                    if sensor_type(aename) != 'CM': # 카메라는 json Save를 하지 않는다. 대신 사진을 전송함
                        stat, t1_start, t1_msg = savedData.savedJson(aename, raw_json, t1_start, t1_msg)
                        timesync=True
                    else:
                        t1_start, t1_msg = camera.take_picture(boardTime, aename, t1_start, t1_msg) # 사진을 찍어 올린다
                    schedule_measureperiod(aename)
                else:
                    nsec = (schedule[aename]['measure'] - boardTime).total_seconds()
                    print(f"no work now.  time to next measure= {nsec/60:.1f}min.")
                    if nsec>ae[aename]['config']['cmeasure']['measureperiod']:
                        schedule_measureperiod(aename)
                        nsec = (schedule[aename]['measure'] - boardTime).total_seconds()
                        print(f"fixed wrong schedule time.  new time to next measure= {nsec/60:.1f}min.")
                    savedData.remove_old_data(aename, boardTime)
    
            # 매 데이타 처리후에만 sync 실시
            if timesync:
                print('At 10min time ', end='')
                do_timesync()
    else:
        print(f"skip scheduling with boardTime not ready")

    # 데이타 전송처리 끝
    t1_msg += f' - doneSendData - {process_time()-t1_start:.1f}s' 


    
    # mqtt 전송을 시행하기로 했다면 mqtt 전송 시행
    # 내 device의 ae에 지정된 sensor type 정보만을 전송
    for aename in ae:
        # skip if not measuring
        if ae[aename]['config']['cmeasure']['measurestate'] != 'measuring': continue

        # stype 은 'AC' 와 같은 부분
        stype = sensor_type(aename)
        if stype == 'CM' : continue # 카메라는 mqtt 전송을 시행하지 않음
        #print(f"mqtt {aename} {stype} {ae[aename]['local']['realstart']}")
        if ae[aename]['local']['realstart']=='Y':  # mqtt_realtime is controlled from remote user
            payload = raw_json[stype]["data"]
            mqtt_sending(aename, payload)
            #print(F'real mqtt /{csename}/{aename}/realtime')
        else:
            #print('reslstart==N, skip real time mqtt sending')
            pass

    t1_msg += f' - doneMQTT - {process_time()-t1_start:.1f}s' 

    # 센서별 json file 생성
    # 내 ae에 지정된 sensor type정보만을 저장
    for aename in ae:
        # skip if not measuring
        if ae[aename]['config']['cmeasure']['measurestate'] != 'measuring': continue

        stype = sensor_type(aename)
        if stype == 'CM' : continue # 카메라는 json 전송을 시행하지 않음
        jsonSave(aename, raw_json[stype])

        #print(raw_json[stype]["time"])
        global doneFirstShoot
        if not aename in doneFirstShoot: doneFirstShoot[aename]=1
        if doneFirstShoot[aename]>0:
            doneFirstShoot[aename] -= 1
            dmeasure = {}
            dmeasure['val'] = raw_json[stype]["data"]
            dmeasure['time'] = raw_json[stype]["time"]
            if stype == "AC" or stype == "DS":
                dmeasure['type'] = "D"
            else:
                dmeasure['type'] = "S"
            ae[aename]['data']['dmeasure'] = dmeasure
            #Timer(delay, create.ci, [aename, 'data', 'dmeasure']).start()
            #print(f" creat data/dmeasure ci for {aename} to demonstrate communication success {doneFirstShoot[aename]}")
            create.ci(aename, 'data', 'dmeasure')

    t1_msg += f' - doneSaving - {process_time()-t1_start:.1f}s' 
    if process_time()-t0_start>0.5:
        print(f'TIME do_capture elapsed= {process_time()-t0_start:.1f}s {t1_msg}')


def do_tick():
    global ae

    do_capture()

    once=True
    for aename in schedule:
        if 'state' in schedule[aename] and schedule[aename]['state'] <= boardTime:
            if once:
                once=False
                do_status()
            ae[aename]['state']["abflag"]="N"         
            state.report(aename)
            schedule_stateperiod(aename)


def startup():
    global ae

    #this need once for one board
    do_config()
    print('create ci at boot')
    for aename in ae:
        #print(f"AE= {aename} RPI CPU Serial= {ae[aename]['local']['serial']}")
        ae[aename]['info']['manufacture']['fwver']=VERSION
        create.allci(aename, {'config','info'}) 
        ae[aename]['state']["abflag"]="N"
        state.report(aename) # boot이후 state를 전송해달라는 요구사항에 맞춤


# schedule measureperiod
def schedule_measureperiod(aename1):
    global ae, schedule
    for aename in ae:
        if aename1 != "" and aename != aename1: continue

        cmeasure=ae[aename]['config']['cmeasure']

        if not 'measureperiod' in cmeasure: cmeasure['measureperiod']=3600
        elif not isinstance(cmeasure['measureperiod'],int): cmeasure['measureperiod']=3600
        elif cmeasure['measureperiod']<600: cmeasure['measureperiod']=600
        cmeasure['measureperiod'] = int(cmeasure['measureperiod']/600)*600
        print(f"cmeasure.measureperiod= {cmeasure['measureperiod']} sec")
    
        cmeasure['rawperiod'] = int(cmeasure['measureperiod']/60)
        print(f"cmeasure.rawperiod= {cmeasure['rawperiod']} min")

        twohour = (datetime.strptime(ae[aename]['local']['upTime'], '%Y-%m-%d %H:%M:%S')+timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        twohour1 = twohour[:-5]+'00:00'
        twohour = datetime.strptime(twohour1, '%Y-%m-%d %H:%M:%S')
        if cmeasure['measureperiod'] == 3600 and boardTime < twohour:
            schedule[aename]['measure'] = boardTime+timedelta(seconds=600)
            print(f'measure schedule[{aename}] for first 2 hour special window at {schedule[aename]["measure"]}')
        else:
            schedule[aename]['measure'] = boardTime+timedelta(seconds=cmeasure['measureperiod'])
            print(f'measure schedule[{aename}] at {schedule[aename]["measure"]}')

def schedule_stateperiod(aename1):
    global ae, schedule
    for aename in ae:
        if aename1 != "" and aename != aename1: continue

        cmeasure=ae[aename]['config']['cmeasure']

        if not 'stateperiod' in cmeasure: cmeasure['stateperiod']=60 #min
        elif not isinstance(cmeasure['stateperiod'],int): cmeasure['stateperiod']=60
        print(f"cmeasure.stateperiod= {cmeasure['stateperiod']} min")

        onehour = (datetime.strptime(ae[aename]['local']['upTime'], '%Y-%m-%d %H:%M:%S')+timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        onehour1 = onehour[:-5]+'00:00'
        onehour = datetime.strptime(onehour1, '%Y-%m-%d %H:%M:%S')
        if cmeasure['stateperiod'] == 60 and boardTime < onehour:
            schedule[aename]['state'] = onehour
        else:
            schedule[aename]['state'] = boardTime+timedelta(minutes=cmeasure['stateperiod'])
            print(f'state schedule[{aename}] at {schedule[aename]["state"]}')

def schedule_first():
    global schedule
    for aename in ae:
        sbtime = (boardTime+timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
        sbtime1 = sbtime[:15]+'0:00'
        schedule[aename]['measure']= datetime.strptime(sbtime1, '%Y-%m-%d %H:%M:%S')
        schedule[aename]['state']= boardTime+timedelta(seconds=3)
        print(f"{aename} set first schedule for measure at {schedule[aename]['measure']}  state at {schedule[aename]['state']}")
        #slack(aename, json.dumps(ae[aename]))
        #print(ae[aename])

        if sensor_type(aename) == "CM": camera.take_picture_command(boardTime, aename)

for aename in ae:
    memory[aename]={"file":{}, "head":"","tail":""}
    trigger_activated[aename]=-1
    schedule[aename]={}
    ae[aename]['local']['upTime']=datetime.now().strftime('%Y-%m-%d %H:%M:%S')

@app.route('/')
def a_status():
    r='<H3>AE 설정 확인</H3>'
    for aename in ae: r+= f"<li><a href=/ae?aename={aename}>{aename}</a>"
    r+='<H3>최종 데이타 확인</H3>'
    for aename in ae: 
        print(aename, sensor_type(aename))
        if sensor_type(aename) != "CM": r+= f"<li><a href=/data?aename={aename}>{aename}</a>"
    r+='<H3>RSSI 확인</H3>'
    r+= f"<li><a href=/rssi>rssi 확인</a>"
    r+='<H3>카메라 영상  확인</H3>'
    r+= f"<li><a href=/camera>Camera 확인</a>"

    return r


@app.route('/ae')
def a_ae():
    aename = request.args.get('aename', '')
    if aename=='':
        return 'please add aename'
    r= make_response(json.dumps(ae[aename], indent=4, ensure_ascii=False), 200)
    r.mimetype='text/plain'
    return r

@app.route('/data')
def a_data():
    aename = request.args.get('aename', '')
    if aename=='': 
        return 'please add aename'

    mymemory = memory[aename]
    keys = sorted(mymemory['file'].keys())
    X=[]
    Y=[]

    for k in keys[-3:]:
        #print(f"k= {k}")
        #print(f"mymemory['file'][k]= {mymemory['file'][k]}")
        d=mymemory['file'][k]
        time=d["time"].split(' ')[1]
        if isinstance(d['data'], list): 
            X.extend([time]*len(d["data"]))
            Y.extend(d["data"])
        else: 
            X.append(time)
            Y.append(d["data"])

    r2='최종 데이타 확인'
    for aename in ae: 
        print(aename, sensor_type(aename))
        if sensor_type(aename) != "CM": r2+= f"<li><a href=/data?aename={aename}>{aename}</a>"
    r= make_response(mygraph(zip(X,Y))+r2, 200)
    return r

stat=[]

@app.route('/rssi')
def a_rssi():
    stat.insert(0, F"{datetime.now().strftime('%H:%M:%S')} {myserial.read()}")
    if len(stat)>10: del stat[10]
    r=''
    for i in range(len(stat)):
        r+=f"<li>{stat[i]}"
    r = f"<html><head><meta http-equiv=refresh content=1></head><body>{r}</body>"
    return r

@app.route('/camera')
def a_camera():
    global ae
    for aename in ae:
        if sensor_type(aename) == "CM":
            print(f" last_picture= {ae[aename]['local']['last_picture']}")
            if ae[aename]['local']['last_picture'] == "":
                return "no photo yet. wait for the first photo"
            else:
                return send_file(ae[aename]['local']['last_picture'], mimetype='image/jpg')
    return "no camera device found"

print(f"===== Begin at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
startup()
RepeatedTimer(0.9, do_tick)

app.run(host='0.0.0.0', port=8000)
