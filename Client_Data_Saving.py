# Client_Data_Saving.py
# 소켓 서버로 'CAPTURE' 명령어를 1초에 1번 보내, 센서 데이터값을 받습니다.
# 받은 데이터를 센서 별로 분리해 각각 다른 디렉토리에 저장합니다.
# 현재 mqtt 전송도 이 프로그램에서 담당하고 있습니다.
VERSION='20220921_V1.54'
print('\n===========')
print(f'Verion {VERSION}')

from encodings import utf_8
from threading import Timer, Thread
import random
from typing import Type
import requests
import json
import os
import math
import sys
import time
import re
import signal
from datetime import datetime, timedelta
from time import process_time
from paho.mqtt import client as mqtt
from RepeatedTimer import RepeatedTimer
from graph import mygraph
import myserial

import logging
from flask import Flask, request, json, make_response, send_file
app= Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
counter=1

import create  #for Mobius resource
import versionup
import make_oneM2M_resource
import savedData
import state
import camera
import ssh_patch

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

def sensor_type(aename):
    return aename.split('-')[1][0:2]

'''
# 다중 데이터의 경우, 어떤 data를 저장할지 결정해야한다
acc_axis = "z" # x, y, z중 택1
deg_axis = "x" # x, y, z중 택1
str_axis = "x" # x, y, z중 택1
dis_channel = "ch4" # ch4, ch5중 택1
아래 펑션으로 대체
'''

def is_inverted(aename):
    if 'axis' in ae[aename]['local']:
        if "-" in ae[aename]['local']['axis']: return True
        else: return False
    else: return False

def invertC(aename):
    if sensor_type(aename) not in {"AC", "TI"}:
        return 1 # DS, DI, TP는 축 방향에 따라 양음수가 바뀌지 않는다
    if 'axis' in ae[aename]['local']:
        if "-" in ae[aename]['local']['axis']: return -1
        else: return 1
    else: return 1   

def acc_axis(aename):
    if 'axis' in ae[aename]['local']:
        return ae[aename]['local']['axis'].replace("-", "") # 마이너스를 제거하고 return
    #설정된 축이 없다면 AE명에서 그대로 따온다
    return aename[-1].lower()

def deg_axis(aename):
    return acc_axis(aename)

def str_axis(aename):
    return acc_axis(aename)

def dis_channel(aename):
    if acc_axis(aename)=='x': return 'ch4'
    elif acc_axis(aename)=='y': return 'ch5'
    else:
        print(f'Format error in aename {aename}')
        print(f'DI type sensor supports X or Y only')
        os._exit(0)


def sigint_handler(signal, frame):
    print()
    print()
    print('got restart command.  exiting...')
    os._exit(0)
signal.signal(signal.SIGINT, sigint_handler)



make_oneM2M_resource.makeit()
print('done any necessary Mobius resource creation')

# dict jsonCreate(dataTyep, timeData, realData)
# 받은 인자를 통해 딕셔너리를 생성합니다.
def jsonCreate(dataType, timeData, realData):
    data = {
        "type":dataType,
        "time":timeData.strftime('%Y-%m-%d %H:%M:%S'),
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
    now_time = datetime.strptime(jsonFile['time'], "%Y-%m-%d %H:%M:%S")
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
            rpitime = datetime.now().replace(microsecond=0)
            if len(mymemory["file"])%60 ==0: print(f'{aename} json add {mymemory["head"].strftime("%Y-%m-%d-%H%M%S")} len= {len(mymemory["file"])} board= {boardTime} rpi= {rpitime} diff= {(boardTime-rpitime).total_seconds():.1f}s (next measure= {schedule[aename]["measure"].strftime("%Y-%m-%d %H:%M:%S")} state= {schedule[aename]["state"].strftime("%Y-%m-%d %H:%M:%S")})')
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
        # 형식 검사 코드 필요할듯
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
        if "mode" in jcmd:
            if not jcmd["mode"] in {1, 2, 3, 4}: # mode는 오로지 숫자 1, 2, 3, 4만을 입력으로 받는다 #테스트요망
                warn_state("ctrigger->mode must be 1 or 2 or 3 or 4")
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
        print("autossh Restart")
        os.system("sudo systemctl restart autossh")
        return

    if cmd in 'gitupdate':
        print("update software via Github")
        os.system("rm -rf ../GB2.0")
        os.system("mkdir ../GB2.0")
        os.system("git clone https://github.com/ekyuho/GB2.0.git ../GB2.0")
        os.system("cp ../GB2.0/COPY.sh .")
        os.system("sh COPY.sh")
        os.system("pm2 restart all")
        return

    if cmd in 'teststart':
        if sensor_type(aename) == "CM":
            warn_state(F"type CM does not support command : {cmd}")
        else:
            print('start test mode saving')
            schedule_test(aename)
            ae[aename]['local']['teststart']='Y'
        return

    if cmd in 'teststop':
        if sensor_type(aename) == "CM":
            warn_state(F"type CM does not support command : {cmd}")
        else:
            print('stop test mode saving')
            ae[aename]['local']['teststart']='N'
        return

    if cmd in 'cntcheck':
        print("start container check in 2 seconds")
        Timer(2, make_oneM2M_resource.container_search).start()
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
        warn_state(f'invalid cmd - {cmd}')
        

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
    global mqttc, mqttc_failed_at
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to {broker} via MQTT")
            client.subscribe(TOPIC_callback)
            print(f"subscribed to {TOPIC_callback}")
        else:
            print("Failed to connect, return code %d\n", rc)

    def on_disconnect(client, userdata, rc):
        print("Disconnected from MQTT server!")
        mqttc_failed_at=datetime.now() # 연결이 해제된 경우 연결이 해제된 시점의 시간을 저장

    def on_message(client, _topic, _msg):
        topic=_msg.topic.split('/')
        msg=_msg.payload.decode('utf8')
        got_callback(topic, msg)


    client_id = f'python-mqtt-{random.randint(0, 1000000)}'
    mqttc = mqtt.Client(client_id)
    mqttc.on_connect = on_connect
    mqttc.on_disconnect = on_disconnect
    mqttc.on_message = on_message
    try:
        mqttc.connect(broker, port)
    except:
        return ""
    return mqttc

mqttc = connect_mqtt()
mqttc_failed_at=''
if mqttc == "":
    print("***** mqtt 연결실패. mqtt 스킵합니다.")
    mqttc_failed_at=datetime.now()
else:    
    mqttc.loop_start()
    print("mqtt 연결에 성공했습니다.")


# void mqtt_retry()
# mqtt 연결이 끊겨있으며, 마지막으로 mqtt 연결 재시도를 한지 10분 이상이 지났다면 mqtt 구독을 재시도합니다.

def mqtt_retry():
    global mqttc, mqttc_failed_at
    if mqttc=="" and (datetime.now() - mqttc_failed_at).total_seconds()>600: # mqtt가 끊겨있으며 마지막 재연결 시도 이후 10분이 지났으면 재연결 시도
        print("MQTT connection has failed before over 10 minutes. reconnecting...")
        mqttc = connect_mqtt()
        if mqttc=="":
            print('***** failed to connect mqtt again. will try in 10 minutes')
            mqttc_failed_at=datetime.now() # 또 실패했으므로 실패 시점의 시간을 저장
        else:
            print("success to connect mqtt again.")
            mqttc.loop_start()

# void mqtt_sending(aename, data)
# mqtt 전송을 수행합니다. 단, mqtt 전송을 사용하지 않기로 한 센서라면, 수행하지 않습니다.
# 센서에 따라 다른 TOPIC에 mqtt 메시지를 publish합니다.
def mqtt_sending(aename, data):
    if mqttc=="":
        print("no MQTT connection. skip mqtt data sending...")
        return # mqtt 연결이 되어있지 않은 경우 스킵
    ''' 
    global mqttc, mqttc_failed_at
    if mqttc=="" and (datetime.now() - mqttc_failed_at).total_seconds()>600:
        mqttc = connect_mqtt()
        #연결을 시도했음에도 불구하고 연결이 되지 않았다면 mqtt 전송을 스킵 #테스트요망
        if mqttc=="":
            print('mqtt_sending: not conneccted. skip sending...')
            return
        else:
            mqttc.loop_start()
    '''  
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
        state=ae[aename]['state']
        state['battery']=j['battery']
        state['solarchargevolt']=j['solar']
        state['time']=j['time']
        #state['vdd']=j['vdd']
        #state['resetFlag']=j['resetFlag']
        #state['errcode']=j['errcode']


def do_capture():
    global mqtt_measure, time_old
    global trigger_activated
    global ae
    global boardTime, gotBoardTime, schedule

    t0_start=datetime.now()
    t1_start=datetime.now()
    t1_msg="0s"
    #print('do capture')

    def elapsed(base):
        return (datetime.now()-base).total_seconds()

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
    if j['Status'].startswith('False'):
        dev_busy +=1
        if dev_busy > 1: print(f"rpiTime= {datetime.now().strftime('%H:%M:%S')} device-busy {dev_busy}")
        return 'busy'

    t1_msg += f' - server2client - {elapsed(t1_start):.1f}s' 

    # receive good data
    dev_busy=0
    # boardTiem is actually 센서데이타 측정시간
    boardTime = datetime.strptime(j['sensorTime'], "%Y-%m-%d %H:%M:%S.%f").replace(microsecond=0)
    rpiTime = datetime.now().replace(microsecond=0)
    global counter
    if counter<180:
        print(f"{counter} boardTime@capture= boardTime= {boardTime} rpiTime= {rpiTime} {(boardTime-rpiTime).total_seconds():.1f}s")
    if counter==180:
        print(f"print per-second-logs for first 3 minutes")
    counter+=1
    if not gotBoardTime:
        gotBoardTime = True
        schedule_first()

    # print(f"trigger= {j['trigger']}"

    '''
    보드에서는 모든 센서 데이타를 한방에 다 가져온다.
    이미, j 변수에는 그 값이 담겨져 있다.
    conf.py 에 설정된 aename 각각 루프를 돌면서 필요한 값을 처리하는 형식.
    '''

    # 캡쳐해온 data를 captured_data라는 dict에 따로 가공하여 저장한다.
    captured_data = {}
    for aename in ae:
        capture_offset = ae[aename]['config']['cmeasure']['offset']
        capture_invert = invertC(aename)
        stype = sensor_type(aename)
        #이하 부분에서 offset, 자릿수 변경, 부호 변경, 유효숫자 관리 모두 시행함
        if stype == "AC" :
            captured_data[aename] = list()
            for d in j[stype]:
                captured_data[aename].append(round((d[acc_axis(aename)] + capture_offset) * capture_invert * 0.001, 5))# AC 단위를 mG가 아닌 G로 변경한 후, 소숫점 5자리까지 표기
        elif stype == "DS":
            captured_data[aename] = list()
            for d in j[stype]:
                captured_data[aename].append(round(d[str_axis(aename)] + capture_offset, 2))
        elif stype == "DI":
            captured_data[aename] = j[stype][dis_channel(aename)] + capture_offset
        elif stype == "TP":
            captured_data[aename] = j[stype] + capture_offset
        elif stype == "TI":
            captured_data[aename] = round((j[stype][deg_axis(aename)] + capture_offset) * capture_invert , 4)

    # start of trigger
    for aename in ae: 
        ctrigger=ae[aename]['config']['ctrigger']
        cmeasure=ae[aename]['config']['cmeasure']
        dtrigger=ae[aename]['data']['dtrigger']
        local=ae[aename]['local']
        stype = sensor_type(aename)

        # skip if not measuring
        if cmeasure['measurestate'] != 'measuring': continue

        # 카메라('CM')외 센서들만 해당
        if stype in {'AC','DS','DI','TP','TI'}:  
            #print(f"aename= {aename} stype= {stype} use= {ctrigger['use']}")

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
            if j['trigger'][stype]=='0': 
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
            if stype == "AC": # 동적 데이터의 경우, 트리거 전초와 후초를 고려해 전송 시행
                trigger_list = captured_data[aename]
                trigger_data = "unknown"
                for ac in trigger_list: # 트리거 조건을 충족시키는 가장 첫번째 값을 val에 저장하기 위해 일치하는 값을 찾으면 break
                    if ac > ctrigger['st1high']: #220908 : 트리거는 무조건 상한으로만 동작하도록 변경
                        trigger_data = ac
                    '''
                    if ctrigger['mode'] == 1 and acctrig_value > ctrigger['st1high']:
                        trigger_data = acctrig_value
                        break
                    elif ctrigger['mode'] == 2 and acctrig_value < ctrigger['st1low']:
                        trigger_data = acctrig_value
                        break
                    elif ctrigger['mode'] == 3:
                        if acctrig_value > ctrigger['st1high'] or acctrig_value < ctrigger['st1low']:
                            trigger_data = acctrig_value
                            break
                    elif ctrigger['mode'] == 4:
                        if acctrig_value < ctrigger['st1high'] and acctrig_value > ctrigger['st1low']:
                            trigger_data = acctrig_value
                            break
                    '''
    
                if trigger_data == "unknown":
                    #print(f" not-for-me-trig-condition-skip")
                    continue
                    
                dtrigger['val'] = trigger_data
    
                print(f" got-trigger-new-{aename}-bfsec={ctrigger['bfsec']}-afsec={ctrigger['afsec']}")
                if isinstance(ctrigger['afsec'],int) and ctrigger['afsec']>0: 
                    trigger_activated[aename]=ctrigger['afsec']
                else: 
                    trigger_activated[aename]=60  # value error, 60 instead
    
            
            elif stype == "DS": # 동적 데이터의 경우, 트리거 전초와 후초를 고려해 전송 시행
                trigger_list = captured_data[aename]
                trigger_data = "unknown"
                for st in trigger_list: # 트리거 조건을 충족시키는 가장 첫번째 값을 val에 저장하기 위해 일치하는 값을 찾으면 break
                    if ctrigger['mode'] == 1 and st > ctrigger['st1high']:
                        trigger_data = st
                        break
                    elif ctrigger['mode'] == 2 and st < ctrigger['st1low']:
                        trigger_data = st
                        break
                    elif ctrigger['mode'] == 3:
                        if st > ctrigger['st1high'] and st < ctrigger['st1low']:
                            trigger_data = st
                            break
                    elif ctrigger['mode'] == 4:
                        if st < ctrigger['st1high'] and st > ctrigger['st1low']:
                            trigger_data = st
                            break
                
                if trigger_data == "unknown":
                    #print(f" not-for-me-trig-condition-skip")
                    continue
                    
                dtrigger['val'] = trigger_data
    
                print(f" got-trigger-new-{aename}-bfsec={ctrigger['bfsec']}-afsec={ctrigger['afsec']}")
                if isinstance(ctrigger['afsec'],int) and ctrigger['afsec']>0: 
                    trigger_activated[aename]=ctrigger['afsec']
                else: 
                    trigger_activated[aename]=60  # value error, 60 instead
    
            else: # stype이 DI, TP, TI인 경우
                # 정적 데이터의 경우, 트리거 발생 당시의 데이터를 전송한다
                print(f"got non-AC trigger {aename}  bfsec= {ctrigger['bfsec']}  afsec= {ctrigger['afsec']}")
                dtrigger['start']=boardTime.strftime("%Y-%m-%d %H:%M:%S")
                dtrigger['count'] = 1
                
                print(f"정적데이타offset연산  offset= {cmeasure['offset']}")
    
                dtrigger['val'] = captured_data[aename] 

                #정말로 val값이 trigger를 만족시키는지 check해야함. 추후 추가.
    
            dtrigger['time']=boardTime.strftime("%Y-%m-%d %H:%M:%S") # 트리거 신호가 발생한 당시의 시각
            dtrigger['mode']=ctrigger['mode']
            dtrigger['sthigh']=ctrigger['st1high']
            dtrigger['stlow']=ctrigger['st1low']
            dtrigger['step']=1
            dtrigger['samplerate']=cmeasure['samplerate']
    
            # AC need afsec
            if stype == "AC" or stype == "DS":
                #print("will process after afsec sec")
                pass
            else:
                #create.ci(aename, "data", "dtrigger") # 정적 트리거 전송은 따로 do_trigger_followup을 실행하지 않는다.
                t1 = Thread(target=create.ci, args=(aename, 'data', 'dtrigger'))
                t1.start()
                print("sent trigger for {aename}")
    
            t1_msg += f' - doneTrigger - {elapsed(t1_start):.1f}s' 
    
    # end of trigger            

    # data를 메모리에 저장하는 프로세스 시작
    for aename in ae: 
        ctrigger=ae[aename]['config']['ctrigger']
        cmeasure=ae[aename]['config']['cmeasure']
        dtrigger=ae[aename]['data']['dtrigger']
        local=ae[aename]['local']
        stype = sensor_type(aename)

        # skip if not measuring
        if cmeasure['measurestate'] != 'measuring': continue

        '''
        offset_dict = {
            "AC":0,
            "DI":0,
            "TP":0,
            "TI":0,
            "DS":0
        }

        if stype == 'TP' and 'offset' in cmeasure: offset_dict["TP"] = cmeasure['offset']
        elif stype == 'DI' and 'offset' in cmeasure: offset_dict["DI"] = cmeasure['offset']
        elif stype == "AC" and 'offset' in cmeasure: offset_dict["AC"] = cmeasure['offset']
        elif stype == "TI" and 'offset' in cmeasure: offset_dict["TI"] = cmeasure['offset']
        elif stype == "DS" and 'offset' in cmeasure: offset_dict["DS"] = cmeasure['offset']

        if stype=='AC':
            acc_list = list()
            for i in range(len(j["AC"])): 
                acc_value = round(j["AC"][i][acc_axis(aename)] + offset_dict["AC"],2)*invertC(aename)
                acc_list.append(acc_value)
        elif stype=='DS':
            str_list = list()
            for i in range(len(j["DS"])):
                str_value = round(j["DS"][i][str_axis(aename)] + offset_dict["DS"],2)*invertC(aename)
                str_list.append(str_value)

        '''
        
        #samplerate에 따라 파일에 저장되는 data 조정
        #현재 가속도 센서와 변형률 센서에 적용중
        if stype=="AC" or stype=="DS":
            round_num = {} # 가공할 자릿수를 뽑아낼 dict
            round_num["AC"] = 5
            round_num["DS"] = 2
            ae_samplerate = float(cmeasure["samplerate"])
            if ae_samplerate != 100:
                if 100%ae_samplerate != 0:
                    #100의 약수가 아닌 samplerate가 설정되어있는 경우, 오류가 발생한다
                    print("wrong samplerate config")
                    print("apply standard samplerate = 100")
                    ae_samplerate = 100
                merged_value = 0
                merge_count = 0
                sample_number = 100//ae_samplerate
                new_list = list()
                for i in range(len(captured_data[aename])):
                    merged_value += captured_data[aename][i]
                    merge_count += 1
                    if merge_count == sample_number:
                        new_list.append(round(merged_value/sample_number, round_num[stype]))
                        merge_count = 0
                        merged_value = 0
                captured_data[aename] = new_list

        # 센서의 특성을 고려해 각 센서 별로 센서 data를 담은 dict 생성
        raw_json={}

        if stype=='TI': raw_json[aename] = jsonCreate('TI', boardTime, captured_data[aename])
        elif stype=='TP': raw_json[aename] = jsonCreate('TP', boardTime, captured_data[aename])
        elif stype=='DI':raw_json[aename] = jsonCreate('DI', boardTime, captured_data[aename])
        elif stype=='AC':raw_json[aename] = jsonCreate('AC', boardTime, captured_data[aename])
        elif stype=='DS':raw_json[aename] = jsonCreate('DS', boardTime, captured_data[aename])

        # boardTime이 정시가딘것이  확인되면 먼저 데이타 전송  처리작업을 한다.  10분의 기간이 10:00 ~ 19:99 이기때문
        if gotBoardTime:
            if aename not in m10: m10[aename]=""
            if m10[aename]=="": m10[aename] = f'{boardTime.minute}'.zfill(2)[0]  # do not run at first, run first when we get new 10 minute
            if m10[aename] != f'{boardTime.minute}'.zfill(2)[0]:  # we got new 10 minute
                m10[aename] = f'{boardTime.minute}'.zfill(2)[0]
                print(f'GOT 10s minutes board= {boardTime} rpi= {datetime.now().strftime("%H:%M:%S")} {m10[aename]}0')
    
                timesync=False
    
                if schedule[aename]['measure'] <= boardTime:
                    # savedJaon() 에서 정적데이타는 아직 hold하고 있는 정시데이타를 보내야 한다. 그래서 j 공급  
                    if stype != 'CM': # 카메라는 json Save를 하지 않는다. 대신 사진을 전송함
                        stat, tx_start, tx_msg = savedData.savedJson(aename, raw_json, t1_start, t1_msg)
                        timesync=True
                    else:
                        tx_start, tx_msg = camera.take_picture(boardTime, aename, t1_start, t1_msg) # 사진을 찍어 올린다
                    schedule_measureperiod(aename)
                else:
                    nsec = (schedule[aename]['measure'] - boardTime).total_seconds()
                    print(f"no work now.  time to next measure= {nsec/60:.1f}min.")
                    if nsec>cmeasure['measureperiod']:
                        schedule_measureperiod(aename)
                        nsec = (schedule[aename]['measure'] - boardTime).total_seconds()
                        print(f"fixed wrong schedule time.  new time to next measure= {nsec/60:.1f}min.")
                    savedData.remove_old_data(aename, boardTime)
    
                # 매 데이타 처리후에만 sync 실시
                if timesync:
                    print('At 10min time ', end='')
                    do_timesync()

            if ae[aename]['local']['teststart'] == "Y": # 테스트 중이라면 n분 00초인지도 확인한다
                if sensor_type(aename) == "CM":pass
                elif schedule[aename]['test'] <= boardTime:
                    savedData.testOneMinuteData(aename, raw_json)
                    schedule_test(aename)
        else:
            print(f"skip scheduling with boardTime not ready")

        # 데이타 전송처리 끝
        t1_msg += f' - doneSendData - {elapsed(t1_start):.1f}s' 


    
        # mqtt 전송을 시행하기로 했다면 mqtt 전송 시행
        # 내 device의 ae에 지정된 sensor type 정보만을 전송

        # stype 은 'AC' 와 같은 부분
        if stype == 'CM' : continue # 카메라는 mqtt 전송을 시행하지 않음
        #print(f"mqtt {aename} {stype} {local['realstart']}")
        if local['realstart']=='Y':  # mqtt_realtime is controlled from remote user
            payload = raw_json[aename]["data"]
            mqtt_sending(aename, payload)
            #print(F'real mqtt /{csename}/{aename}/realtime')
        else:
            #print('reslstart==N, skip real time mqtt sending')
            pass

        t1_msg += f' - doneMQTT - {elapsed(t1_start):.1f}s' 

        # 센서별 json file 생성
        # 내 ae에 지정된 sensor type정보만을 저장

        if stype == 'CM' : continue # 카메라는 json 전송을 시행하지 않음
        jsonSave(aename, raw_json[aename])

        #print(raw_json[aename]["time"])

        #최초 1회 data 수신시 data ci를 생성시킵니다.
        global doneFirstShoot
        if not aename in doneFirstShoot: doneFirstShoot[aename]=1
        if doneFirstShoot[aename]>0:
            doneFirstShoot[aename] -= 1
            dmeasure = {}
            dmeasure['val'] = raw_json[aename]["data"]
            dmeasure['time'] = raw_json[aename]["time"]
            if stype == "AC" or stype == "DS":
                dmeasure['type'] = "D"
            else:
                dmeasure['type'] = "S"
            ae[aename]['data']['dmeasure'] = dmeasure
            #Timer(delay, create.ci, [aename, 'data', 'dmeasure']).start()
            #print(f" create data/dmeasure ci for {aename} to demonstrate communication success {doneFirstShoot[aename]}")
            create.ci(aename, 'data', 'dmeasure')

        t1_msg += f' - doneSaving - {elapsed(t1_start):.1f}s' 

    if elapsed(t0_start)>0.7:
        print(f'do_capture elapsed= {elapsed(t0_start):.1f}s {t1_msg}')

    return 'ok'

def do_tick():
    global ae

    r = do_capture()

    once=True
    for aename in schedule:
        if aename == "ping": continue
        if 'state' in schedule[aename] and schedule[aename]['state'] <= boardTime:
            if once:
                once=False
                do_status()
            ae[aename]['state']["abflag"]="N"         
            state.report(aename)
            schedule_stateperiod(aename)

    if schedule["ping"] <= boardTime:
        addr = 'google.com'
        cmdstring = F'ping -c1 {addr} 1>/dev/null'
        res = os.system(cmdstring)
        if res == 0:
            print("ICMP : responding well.")
        else:
            print("ICMP : not responding. do modem reset...")
            myserial.modem_reset()
        schedule_ping()


    global counter
    if counter>100000: counter=300
    mqtt_retry()

def startup():
    global ae
    ssh_need = ssh_patch.service_file_change()
    if ssh_need:ssh_patch.ssh_init()
    #this need once for one board
    do_config()
    print('create ci at boot')
    for aename in ae:
        #print(f"AE= {aename} RPI CPU Serial= {ae[aename]['local']['serial']}")
        ae[aename]['info']['manufacture']['fwver']=VERSION
        create.allci(aename, {'config','info'}) 
        do_status()
        ae[aename]['state']["abflag"]="N"
        state.report(aename) # boot이후 state를 전송해달라는 요구사항에 맞춤
        if sensor_type(aename) == "CM": camera.take_picture_command(boardTime, aename)
        print(f"MAP {aename} --> using Sensor {acc_axis(aename)}")
        if sensor_type(aename) != "CM" and ae[aename]['local']['teststart'] == "Y":
            schedule_test(aename)
    os.system("sudo systemctl restart autossh") #초기 autossh start 커맨드


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
        #print(f"cmeasure.measureperiod= {cmeasure['measureperiod']} sec")
    
        cmeasure['rawperiod'] = int(cmeasure['measureperiod']/60)
        #print(f"cmeasure.rawperiod= {cmeasure['rawperiod']} min")

        if cmeasure['measureperiod'] == 3600:
            t1 = boardTime.strftime('%Y-%m-%d %H:00:00')
            t2 = datetime.strptime(t1, '%Y-%m-%d %H:%M:%S')   # boardTime에서 분아래 제거하고 1시간 + 하여 다가오는 00분 정시성확보
            schedule[aename]['measure'] = t2+ timedelta(hours=1)
        else:
            t1 = boardTime.strftime('%Y-%m-%d %H:%M')[:-1]+'0:00'
            t2 = datetime.strptime(t1, '%Y-%m-%d %H:%M:%S')   # boardTime에서 분아래 제거하고 1시간 + 하여 다가오는 00분 정시성확보
            schedule[aename]['measure'] = t2+ timedelta(minutes=cmeasure['measureperiod']/60)
        print(f'next measure schedule[{aename}] at {schedule[aename]["measure"]} +{cmeasure["measureperiod"]}')

def schedule_stateperiod(aename1):
    global ae, schedule
    for aename in ae:
        if aename1 != "" and aename != aename1: continue

        cmeasure=ae[aename]['config']['cmeasure']

        if not 'stateperiod' in cmeasure: cmeasure['stateperiod']=60 #min
        elif not isinstance(cmeasure['stateperiod'],int): cmeasure['stateperiod']=60
        #print(f"cmeasure.stateperiod= {cmeasure['stateperiod']} min")

        if cmeasure['stateperiod'] == 60:
            t1 = boardTime.strftime('%Y-%m-%d %H:01:00')
            t2 = datetime.strptime(t1, '%Y-%m-%d %H:%M:%S')   # boardTime에서 분아래 제거하고 1시간 + 하여 다가오는 00분 정시성확보
            schedule[aename]['state'] = t2 + timedelta(hours=1)
        else:
            t1 = boardTime.strftime('%Y-%m-%d %H:%M')[:-1]+'1:00'
            t2 = datetime.strptime(t1, '%Y-%m-%d %H:%M:%S')
            schedule[aename]['state'] = t2+timedelta(minutes=cmeasure['stateperiod'])
        print(f'next state schedule[{aename}] at {schedule[aename]["state"]} +{cmeasure["stateperiod"]}')
        '''
        onehour = (datetime.strptime(ae[aename]['local']['upTime'], '%Y-%m-%d %H:%M:%S')+timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        onehour1 = onehour[:-5]+'00:00'
        onehour = datetime.strptime(onehour1, '%Y-%m-%d %H:%M:%S')
        if cmeasure['stateperiod'] == 60 and boardTime < onehour:
            schedule[aename]['state'] = onehour
        else:
            schedule[aename]['state'] = boardTime+timedelta(minutes=cmeasure['stateperiod'])
            print(f'state schedule[{aename}] at {schedule[aename]["state"]}')
        '''
# void schedule_ping()
# 정시+2분마다 인터넷 상태를 체크하고, 인터넷 연결이 되지 않으면 모뎀 리셋 명령어를 보냅니다.
def schedule_ping():
    global schedule
    t1 = boardTime.strftime('%Y-%m-%d %H:02:00')
    t2 = datetime.strptime(t1, '%Y-%m-%d %H:%M:%S')   # boardTime에서 분아래 제거하고 1시간 + 하여 다가오는 02분 정시성확보. state 전송이나 주기적 전송에 영향받지 않도록 함
    schedule["ping"] = t2 + timedelta(hours=1)
    print(f'next internet check schedule at {schedule["ping"]} + 3600')

# void schedule_ping(string aename)
# teststart가 Y인 경우 시행합니다. 매 n분 0초마다 1분치 데이터를 따로 저장합니다.
def schedule_test(aename):
    global schedule
    t1 = boardTime.strftime('%Y-%m-%d %H:%M:00')
    t2 = datetime.strptime(t1, '%Y-%m-%d %H:%M:%S') # boardTime에서 초 아래 제거하고 1분 +하여 다가오는 00초 정시성 확보.
    schedule[aename]["test"] = t2 + timedelta(minutes=1)
    print(f'next test data save schedule at {schedule[aename]["test"]} + 60')


#  첫번째 데이타 수신
def schedule_first():
    for aename in ae:
        cmeasure=ae[aename]['config']['cmeasure']
        #schedule_measureperiod(aename)   첫번재 10분 정시에 1회만
        t1 = boardTime.strftime('%Y-%m-%d %H:%M')[:-1]+'0:00'
        t2 = datetime.strptime(t1, '%Y-%m-%d %H:%M:%S')   # boardTime에서 분아래 제거하고 1시간 + 하여 다가오는 00분 정시성확보
        schedule[aename]['measure'] = t2+ timedelta(minutes=10)
        print(f'next measure schedule[{aename}] at 10s {schedule[aename]["measure"]} +{cmeasure["measureperiod"]}')
        schedule_stateperiod(aename)    # 정상적 다음 일정
        schedule_ping() # ping 스케줄링도 함께 시행
        '''
        schedule[aename]['measure']= boardTime
        schedule[aename]['state']= boardTime+timedelta(seconds=1)
        #slack(aename, json.dumps(ae[aename]))
        #print(ae[aename])
        '''

for aename in ae:
    memory[aename]={"file":{}, "head":"","tail":""}
    trigger_activated[aename]=-1
    schedule[aename]={}
    ae[aename]['local']['upTime']=datetime.now().strftime('%Y-%m-%d %H:%M:%S')

@app.route('/')
def a_status():
    """
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
    r+='<H3>Device Info</H3>'
    r+= f"<li><a href=/deviceInfo>Device Info</a>"
    """

    r='<H1>Ino-Vibe GB</H1>'
    r+='<hr>'
    r+='<H2>AE 설정 확인</H2>'
    for aename in ae: r+= f"<li><a href=/ae?aename={aename} style='text-decoration:none;'>{aename}</a>"
    r+='<hr>'
    r+='<H2>최종 데이타 확인</H2>'
    for aename in ae: 
        print(aename, sensor_type(aename))
        if sensor_type(aename) != "CM": r+= f"<li><a href=/data?aename={aename} style='text-decoration:none;'>{aename}</a>"
    r+='<hr>'
    r+='<H2>RSSI 확인</H2>'
    r+= f"<li><a href=/rssi style='text-decoration:none;'>rssi 확인</a>"
    r+='<hr>'
    r+='<H2>카메라 영상  확인</H2>'
    r+= f"<li><a href=/camera style='text-decoration:none;'>Camera 확인</a>"
    r+='<hr>'
    r+='<H2>인터넷 연결 확인</H2>'
    r+= f"<li><a href=/connection style='text-decoration:none;'>인터넷 연결 확인</a>"
    r+='<hr>'
    r+='<H3>모뎀 리셋</H3>'
    r+= f"<li><a href=/modem style='text-decoration:none;'>모뎀 리셋</a>"
    r+='<hr>'
    r+='<H3>Device Info</H3>'
    r+= f"<li><a href=/deviceInfo>Device Info</a>"
    r+='<hr>'
    r+= f"Copyrightⓒ2022. Ino-on Inc. All Rights Reserved."

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

    r0=f"<H3>{aename}</H3>"

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
    r= make_response(r0+mygraph(zip(X,Y))+r2, 200)
    return r

stat=[]

@app.route('/rssi')
def a_rssi():
    stat.insert(0, F"{datetime.now().strftime('%H:%M:%S')} RSSI value : {myserial.read().split(',')[2]}")
    if len(stat)>10: del stat[10]
    r=''
    for i in range(len(stat)):
        r+=f"<li>{stat[i]}"
    r = f"<html><head><meta http-equiv=refresh content=1></head><body>{r}</body>"
    return r

@app.route('/deviceInfo')
def a_dinfo():
    # RSSI, 태양광, 내부 배터리 전원
    # 1차: 쓸 값만 - 가속도, 기울기, 변위, 변형률, 온도
    # 시리얼, 펌웨어, 모뎀 정보 
    do_status()
    r=''
    for aename in ae:
        #r+=f'battery: {ae[aename]['state']['battery']}'
        #solar =float(list({ae[aename]['state']['solarchargevolt']})[0])*14.7/100
        solar =float(list({ae[aename]['state']['solarchargevolt']})[0])
        battery =float(list({ae[aename]['state']['battery']})[0])*4.2/100
        r+=f'External battery: {solar:.2f} V <br>'
        r+=f'Internal battery: {battery:.2f} V <br>'
        r+=f'<br>'
        r+=f'Version : {VERSION}'
        print(r)
        break
        
    r = f"<html><head><meta http-equiv=refresh content=3></head><body>{r}</body>"
    #r = f"<html><body>{r}</body>"
    return r

@app.route('/camera')
def a_camera():
    for aename in ae:
        if sensor_type(aename) == "CM":
            print(f" last_picture= {ae[aename]['local']['last_picture']}")
            camera.take_picture_command(boardTime,aename)
            if ae[aename]['local']['last_picture'] == "":
                return "no photo yet. wait for the first photo"
            else:
                return send_file(ae[aename]['local']['last_picture'], mimetype='image/jpg')
    return "no camera device found"

conne = []
# /connection
# 인터넷 연결 상태를 확인합니다. 페이지는 1초마다 갱신됩니다.
# pingmsg : ICMP를 이용해 인터넷이 연결되어있는지 확인한 결과입니다. 
# mqttmsg : mqtt 구독여부를 변수 mqttc를 통해 확인한 결과입니다.
@app.route('/connection') 
def a_connection():
    addr = 'google.com'
    cmdstring = F'ping -c1 {addr} 1>/dev/null'
    res = os.system(cmdstring)
    if res == 0:
        pingmsg = "OK - 인터넷이 연결되어있습니다."
    else:
        pingmsg = "NG - 인터넷이 연결되어있지 않습니다."
    if mqttc=="":
        mqttmsg = "MQTT 중지 상태."
    else:
        mqttmsg = "MQTT 정상 작동 중."
    conne.insert(0, F"{datetime.now().strftime('%H:%M:%S')} : {pingmsg} {mqttmsg}")
    if len(conne)>10: del conne[10]
    r=''
    for msg in conne:
        r+=f"<li>{msg}"
    r = f"<html><head><meta http-equiv=refresh content=1></head><body>{r}</body>"
    return r

# /modem
# 페이지에 접속하면 모뎀 리셋 명령어를 전송합니다.
@app.route('/modem')
def a_modem():
    r=''
    myserial.modem_reset()
    r=f"모뎀을 리셋하였습니다. 몇 초 후 인터넷 상태를 재확인해주세요."
    r = f"<html><head></head><body>{r}</body>"
    return r


print(f"===== Begin at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
startup()
RepeatedTimer(0.9, do_tick)
Timer(2, make_oneM2M_resource.container_search).start()

app.run(host='0.0.0.0', port=8000)
