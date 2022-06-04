# Client_Data_Saving.py
# 소켓 서버로 'CAPTURE' 명령어를 1초에 1번 보내, 센서 데이터값을 받습니다.
# 받은 데이터를 센서 별로 분리해 각각 다른 디렉토리에 저장합니다.
# 현재 mqtt 전송도 이 프로그램에서 담당하고 있습니다.
VERSION='20220604_V1.11'
print('\n===========')
print(f'Verion {VERSION}')

from encodings import utf_8
from threading import Timer, Thread
import random
import requests
import json
from socket import *
import select
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

import create  #for Mobius resource
import versionup
import make_oneM2M_resource
import savedData
import state

from conf import csename, memory, ae, slack, port, host as broker, boardTime, supported_sensors, root, TOPIC_list

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

# 다중 데이터의 경우, 어떤 data를 저장할지 결정해야한다
acc_axis = "x" # x, y, z중 택1
deg_axis = "x" # x, y, z중 택1
str_axis = "z" # x, y, z중 택1
dis_channel = "ch4" # ch4, ch5중 택1

def sigint_handler(signal, frame):
    print()
    print()
    print('got restart command.  exiting...')
    os._exit(0)
signal.signal(signal.SIGINT, sigint_handler)

def sensor_type(aename):
    return aename.split('-')[1][0:2]

client_socket=""

def connect():
    global client_socket
    if client_socket=="":
        client_socket= socket(AF_INET, SOCK_STREAM)
        client_socket.settimeout(5)
        try:
            client_socket.connect(('127.0.0.1', 50000))
        except:
            print('got no connection')
            return 'no'
        print("socket pi연결에 성공했습니다.")
    return "yes"

if connect()=='no':
    os._exit(0)

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
    global memory, boardTime, schedule
    mymemory = memory[aename]
    # remove microsec 2022-05-30 03:20:01.477113
    now_time = datetime.strptime(jsonFile['time'].split('.')[0],'%Y-%m-%d %H:%M:%S')
    if mymemory["head"] == "": 
        mymemory["head"] = now_time - timedelta(seconds=1)
        mymemory["tail"]= now_time

    sec = int((now_time - mymemory["head"]).total_seconds())
    if sec>30:
        print(f'sec too big {sec} limiting to 30')
        sec=10
    while sec>0:
        mymemory["head"] = mymemory["head"] + timedelta(seconds=1)
        mymemory["file"][mymemory["head"].strftime('%Y-%m-%d-%H%M%S')]=jsonFile
        if sec>1: print(f'{aename} json add {mymemory["head"].strftime("%Y-%m-%d-%H%M%S")} len= {len(mymemory["file"])} extra')
        else: 
            rpitime = datetime.now()
            if len(mymemory["file"])%60 ==0: print(f'{aename} json add {mymemory["head"].strftime("%Y-%m-%d-%H%M%S")} len= {len(mymemory["file"])} board= {boardTime.strftime("%H:%M:%S")} rpi= {rpitime.strftime("%H:%M:%S")} diff= {(rpitime - boardTime).total_seconds():.1f}s (next measure= {schedule[aename]["measure"].strftime("%H:%M:%S")} state= {schedule[aename]["state"].strftime("%H:%M:%S")})')
        sec -= 1
    
    while len(mymemory["file"])>660:
        try:
            del mymemory["file"][mymemory["tail"].strftime('%Y-%m-%d-%H%M%S')]
            print(f'{aename} removing extra json > 600  {mymemory["tail"].strftime("%Y-%m-%d-%H%M%S")}')
        except:
            print(f'{aename} tried to remove ghost {mymemory["tail"].strftime("%Y-%m-%d-%H%M%S")}')
            
        mymemory["tail"] = mymemory["tail"] + timedelta(seconds=1)


def save_conf(aename):
    global ae, root
    with open(F"{root}/{aename}.conf","w") as f: f.write(json.dumps(ae[aename], ensure_ascii=False,indent=4))
    print(f"wrote {aename}.conf")

def do_user_command(aename, jcmd):
    global ae, schedule, root, boardTime
    print(f'got command= {jcmd}')
    cmd=jcmd['cmd']
    if 'reset' in cmd:
        file=f"{root}/{aename}.conf"
        if os.path.exists(file): 
            os.remove(file)
            print(f'removed {aename}.conf')
        else:
            print(f'no {aename}.conf to delete')
        os.system("sudo reboot")
    elif 'reboot' in cmd:
        os.system("sudo reboot")
    elif cmd in {'synctime'}:
        print('nothing to sync time')
    elif cmd in {'fwupdate'}:
        url= f'{jcmd["protocol"]}://{jcmd["ip"]}:{jcmd["port"]}{jcmd["path"]}'
        versionup.versionup(url)
    elif cmd in {'realstart'}:
        print('start mqtt real tx')
        ae[aename]['local']['realstart']='Y'
    elif cmd in {'realstop'}:
        print('stop mqtt real tx')
        ae[aename]['local']['realstart']='N'
    elif cmd in {'reqstate'}:
        # 얘는 board에서 읽어오는 부분이있다. 
        #do_capture('STATUS')
        schedule[aename]['reqstate']=aename
        print(f"schedule do_capture({aename}:{schedule[aename]})")

    elif cmd in {'measurestart'}:
        ae[aename]['config']['cmeasure']['measurestate']='measuring'
        #create.ci(aename, 'config', 'cmeasure')
        t1 = Thread(target=create.ci, args=(aename, 'config', 'cmeasure'))
        t1.start()
    elif cmd in {'measurestop'}:
        ae[aename]['config']['cmeasure']['measurestate']='stopped'
        #create.ci(aename, 'config', 'cmeasure')
        t1 = Thread(target=create.ci, args=(aename, 'config', 'cmeasure'))
        t1.start()
    elif cmd in {'settrigger', 'setmeasure'}:
        ckey = cmd.replace('set','c')  # ctrigger, cmeasure
        k1=set(jcmd[ckey]) - {'use','mode','st1high','st1low','bfsec','afsec'}
        if ckey=="ctrigger" and len(k1)>0:
            ae[aename]['state']["abflag"]="Y"
            ae[aename]['state']["abtime"]=boardTime.strftime("%Y-%m-%d %H:%M:%S")
            ae[aename]['state']["abdesc"]="Invlid key in ctrigger command: "
            for x in k1: ae[aename]['state']["abdesc"] += f" {x}"
            print(f"Invalid ctrigger command: {ckey} {k1}")
            state.report(aename)
            return

        k1=set(jcmd[ckey]) - {'sensitivity','offset','measureperiod','stateperiod','usefft'}
        if ckey=="cmeasure" and len(k1)>0:
            ae[aename]['state']["abflag"]="Y"
            ae[aename]['state']["abtime"]=boardTime.strftime("%Y-%m-%d %H:%M:%S")
            ae[aename]['state']["abdesc"]="Invlid key in cmeasure command: "
            for x in k1: ae[aename]['state']["abdesc"] += f" {x}"
            print(f"Invalid ctrigger command: {ckey} {k1}")
            state.report(aename)
            return

        for k in jcmd[ckey]: ae[aename]['config'][ckey][k]=jcmd[ckey][k]

        if 'measureperiod' in jcmd[ckey]: 
            if not isinstance(jcmd[ckey]["measureperiod"],int):
                ae[aename]['state']["abflag"]="Y"
                ae[aename]['state']["abtime"]=boardTime.strftime("%Y-%m-%d %H:%M:%S")
                ae[aename]['state']["abdesc"]="measureperiod must be integer. defaulted to 600"
                state.report(aename)
                jcmd[ckey]['measureperiod']=600
            elif jcmd[ckey]["measureperiod"] < 600:
                ae[aename]['state']["abflag"]="Y"
                ae[aename]['state']["abtime"]=boardTime.strftime("%Y-%m-%d %H:%M:%S")
                ae[aename]['state']["abdesc"]="measureperiod must be bigger than 600. defaulted to 600"
                state.report(aename)
                jcmd[ckey]['measureperiod']=600
                return
            elif jcmd[ckey]["measureperiod"]%600 != 0:
                ae[aename]['state']["abflag"]="Y"
                ae[aename]['state']["abtime"]=boardTime.strftime("%Y-%m-%d %H:%M:%S")
                ae[aename]['state']["abdesc"]=f"measureperiod must be multiples of 600. modified to {v} and accepted"
                state.report(aename)
                jcmd[ckey]['measureperiod']= int(jcmd[ckey][x]/600)*600

            ae[aename]['config']['cmeasure']['measureperiod'] = v

        for k in jcmd[ckey]: ae[aename]['config'][ckey][k] = jcmd[ckey][k]   
        setboard=False
        if ckey=='cmeasure' and 'offset' in jcmd[ckey]: 
            #print(f" {aename} {ckey} will write to board")
            setboard=True
        if ckey=='ctrigger' and len({'use','st1high', 'st1low'} & jcmd[ckey].keys()) !=0: 
            #print(f" {aename} {ckey} will write to board")
            setboard=True
        if setboard:
            # 얘는 board에 설정하는 부분이 있다.
            schedule[aename]['config']='doit'
            print(f"set {schedule[aename]['config']}")
        save_conf(aename)
        #create.ci(aename, 'config', ckey)
        t1 = Thread(target=create.ci, args=(aename, 'config', ckey))
        t1.start()

    elif cmd in {'settime'}:
        print(f'set time= {jcmd["time"]}')
        ae[aename]["config"]["time"]= jcmd["time"]
        save_conf(aename)
        #create.ci(aename, 'config', 'time')
        t1 = Thread(target=create.ci, args=(aename, 'config', 'time'))
        t1.start()
    elif cmd in {'setconnect'}:
        print(f'set {aename}/connect= {jcmd["connect"]}')
        for x in jcmd["connect"]:
            ae[aename]['config']["connect"][x]=jcmd["connect"][x]
        #create.ci(aename, 'config', 'connect')
        t1 = Thread(target=create.ci, args=(aename, 'config', 'connect'))
        t1.start()
        save_conf(aename)
    elif cmd == 'inoon':
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
        print(f'invalid cmd {jcmd}')
        

def got_callback(topic, msg):
    global mqttc
    aename=topic[4] 
    if aename in ae:
        #print(topic, aename,  msg)
        try:
            j=json.loads(msg)
        except:
            print(f"json error {msg}")
            return
        jcmd=j["pc"]["m2m:sgn"]["nev"]["rep"]["m2m:cin"]["con"]
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


    client_id = f'python-mqtt-{random.randint(0, 1000)}'
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
    global csename, boardTime, mqttc
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

    setting={ 'AC':{'select':0x0100,'use':'N','st1high':0,'st1low':0, 'offset':0},
                'DI':{'select':0x0800,'use':'N','st1high':0,'st1low':0, 'offset':0},
                'TI':{'select':0x0200,'use':'N','st1high':0,'st1low':0, 'offset':0},
                'TP':{'select':0x1000,'use':'N','st1high':0,'st1low':0, 'offset':0}}
    for aename in ae:
        cmeasure = ae[aename]['config']['cmeasure']
        if 'offset' in cmeasure:
            setting[sensor_type(aename)]['offset'] = cmeasure['offset']
        ctrigger = ae[aename]['config']['ctrigger']
        if 'use' in ctrigger:
            setting[sensor_type(aename)]['use'] = ctrigger['use']
            if 'st1high' in ctrigger: setting[sensor_type(aename)]['st1high']= ctrigger['st1high']
            if 'st1low' in ctrigger: setting[sensor_type(aename)]['st1low']= ctrigger['st1low']
    #print(f"do_config board seting= {setting}")

    if connect() == 'no': 
        print('do_config: connect() failed. return.')
        return
    try:
        client_socket.sendall(("CONFIG"+json.dumps(setting, ensure_ascii=False)).encode())
    except OSError as msg:
        print(f"socket error {msg} exiting..")
        os._exit(0)

def do_trigger_followup(aename):
    global ae,memory

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
    i=0
    dtrigger['data']='mobius can handle up to 6500 items. so data0, data1 are provided'
    for i in range(len(data)):
        if i*5000+5000>len(data): break
        dtrigger[f'data{i}']=data[i*5000:i*5000+5000]
    dtrigger[f'data{i}']=data[i*5000:]
    dtrigger["start"] = start.strftime("%Y-%m-%d %H:%M:%S")
    #create.ci(aename, 'data', 'dtrigger')
    t1 = Thread(target=create.ci, args=(aename, 'data', 'dtrigger'))
    t1.start()
    print(f"comiled trigger data: {len(data)} bytes for bfsec+afsec= {ctrigger['bfsec']+ctrigger['afsec']}")

session_active = False
def watchdog():
    global session_active
    if not session_active:
        print('found server capture session freeze, exiting..')
        os._exit(0)
    session_active = False
RepeatedTimer(60, watchdog)


def do_capture(target):
    global client_socket, mqtt_measure, time_old
    global trigger_activated, session_active
    global ae
    global boardTime, gotBoardTime, schedule

    t1_start=process_time()
    t1_msg="0s"
    #print('do capture')
    if connect() == 'no':
        return 'err',0,0
    try:
        client_socket.sendall(target.encode()) # deice server로 'CAPTURE' 명령어를 송신합니다.
        rData = client_socket.recv(20000)
    except OSError as msg:
        print(f"socket error {msg} exiting..")
        os._exit(0)

    rData = rData.decode('utf_8')
    try:
        j = json.loads(rData) # j : 서버로부터 받은 json file을 dict 형식으로 변환한 것
    except ValueError:
        print(f"no json: skip. rData={rData}")
        return 'err',0,0

    session_active=True

    if not 'Origin' in j:
        print(f'No Origin  {j}')
        return 'err',0,0

    if j['Origin']=='STATUS' and j['Status']=='Ok':
        #print(f'got STATUS return ok')
        for aename in ae:
            ae[aename]['state']['battery']=j['battery']
        return 'err',0,0

    if 'Origin' in j and j['Origin'] in {'RESYNC','STATUS','CONFIG'}:
        print(f'got result {j}')
        return 'err',0,0

    if j['Origin'] == 'CAPTURE' and j['Status'] == 'False':
        #print(f'device not ready {j}')
        return 'err',0,0

    if not 'Timestamp' in j:
        print(f"no Timestamp {j} at {datetime.now().strftime('%H:%M:%S')}")
        return 'err',0,0

    
    t1_msg += f' - server2client - {process_time()-t1_start:.1f}s' 

    boardTime = datetime.strptime(j['Timestamp'],'%Y-%m-%d %H:%M:%S')
    if not gotBoardTime:
        gotBoardTime = True
        schedule_first()

    #print(f"trigger= {j['trigger']}")

    for aename in ae:

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
            tmsg +=  f" not-for-me-{aename}-skip"
            #print(tmsg)
            continue

        # skip if not measuring
        if cmeasure['measurestate'] != 'measuring':
            tmsg += f" not-measuring-{aename}-skip"
            print(tmsg)
            continue

        # skip if not enabled
        if ctrigger['use'] not in {'Y','y'}:
            tmsg+= f" not-enabled-{aename}-skip"
            print(tmsg)
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
        else:
            # 정적 데이터의 경우, 트리거 발생 당시의 데이터를 전송한다
            print(f"got non-AC trigger {aename}  bfsec= {ctrigger['bfsec']}  afsec= {ctrigger['afsec']}")
            dtrigger['start']=boardTime.strftime("%Y-%m-%d %H:%M:%S")
            dtrigger['count'] = 1
            
            if sensor_type(aename) == "DI": data = j["DI"][dis_channel]+cmeasure['offset']
            elif sensor_type(aename) == "TP": data = j["TP"]+cmeasure['offset']
            elif sensor_type(aename) == "TI": data = j["TI"][deg_axis]+cmeasure['offset'] # offset이 있는 경우, 합쳐주어야한다
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
        if sensor_type(aename) == "AC":
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
        "TI":0
    }

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

    Time_data = j["Timestamp"]
    Temperature_data = j["TP"] + offset_dict["TP"]
    Displacement_data = j["DI"][dis_channel] + offset_dict["DI"]
    
    acc_list = list()
    str_list = list()
    
    for i in range(len(j["AC"])):
        acc_list.append(j["AC"][i][acc_axis] + offset_dict["AC"])
    for i in range(len(j["DS"])):
        str_list.append(j["DS"][i][str_axis]) #offset 기능 구현되어있지 않음
        
    #print(F"acc : {acc_list}")
    #samplerate에 따라 파일에 저장되는 data 조정
    #현재 가속도 센서에만 적용중
    for aename in ae:
        # acceleration의 경우, samplerate가 100이 아닌 경우에 대처한다
        if sensor_type(aename)=="AC":
            ae_samplerate = float(ae[aename]["config"]["cmeasure"]["samplerate"])
            if ae_samplerate != 100:
                if 100%ae_samplerate != 0:
                    #100의 약수가 아닌 samplerate가 설정되어있는 경우, 오류가 발생한다
                    print("wrong samplerate config")
                    print("apply standard samplerate = 100")
                    ae_samplerate = 100
                new_acc_list = list()
                merged_value = 0
                merge_count = 0
                sample_number = 100//ae_samplerate
                for i in range(len(acc_list)):
                    merged_value += acc_list[i]
                    merge_count += 1
                    if merge_count == sample_number:
                        new_acc_list.append(round(merged_value/sample_number, 2))
                        merge_count = 0
                        merged_value = 0
                acc_list = new_acc_list
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
    if aename not in m10: m10[aename]=""
    if m10[aename]=="": m10[aename] = f'{boardTime.minute}'.zfill(2)[0]  # do not run at first, run first when we get new 10 minute
    if m10[aename] != f'{boardTime.minute}'.zfill(2)[0]:  # we got new 10 minute
        m10[aename] = f'{boardTime.minute}'.zfill(2)[0]
        print(f'GOT 10s minutes')
        time.sleep(0.001)
        # resync board clock first
        if connect() == 'no':
            return 'err',0,0
        try:
            client_socket.sendall("RESYNC".encode()) # deice server로 "RESYNC" 명령어를 송신합니다.
        except OSError as msg:
            print(f"socket error {msg} exiting..")
            os._exit(0)

        for aename in ae:
            # skip if not measuring
            if ae[aename]['config']['cmeasure']['measurestate'] != 'measuring': continue

            if schedule[aename]['measure'] <= boardTime:
                # savedJaon() 에서 정적데이타는 아직 hold하고 있는 정시데이타를 보내야 한다. 그래서 j 공급  
                stat, t1_start, t1_msg = savedData.savedJson(aename, raw_json, t1_start, t1_msg)
                schedule_measureperiod(aename)
            else:
                print(f"no work now.  time to next measure= {(schedule[aename]['measure'] - boardTime).total_seconds()/60}min. clear 10 minute long data.")
                memory[aename]['file']={}
    # 데이타 전송처리 끝
    t1_msg += f' - doneSendData - {process_time()-t1_start:.1f}s' 


    
    # mqtt 전송을 시행하기로 했다면 mqtt 전송 시행
    # 내 device의 ae에 지정된 sensor type 정보만을 전송
    for aename in ae:
        # skip if not measuring
        if ae[aename]['config']['cmeasure']['measurestate'] != 'measuring': continue

        # stype 은 'AC' 와 같은 부분
        stype = sensor_type(aename)
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
        jsonSave(aename, raw_json[stype])

    t1_msg += f' - doneSaving - {process_time()-t1_start:.1f}s' 
    #if process_time()-t1_start>0.5:
    #print(f'TIME {t1_msg}')
    return 'ok', t1_start, t1_msg


def do_tick():
    global schedule, boardTime, ae
    stat, t1_start, t1_msg = do_capture('CAPTURE')

    for aename in schedule:
        if 'config' in schedule[aename]: 
            do_config()
            del schedule[aename]['config']

        elif 'reqstate' in schedule[aename]:
            do_capture('STATUS')

            ae[aename]['state']["abflag"]="N"
            if "abtime" in ae[aename]['state']: del ae[aename]['state']["abtime"]
            if "abdesc" in ae[aename]['state']: del ae[aename]['state']["abdesc"]

            state.report(aename)
            del schedule[aename]['reqstate']

        try:
            if schedule[aename]['state'] <= boardTime:
                state.report(aename)
                schedule_stateperiod(aename)
        except:
            print('got this error: boardTime= {boardTime}')
            print(f'schedule.keys()= {schedule.keys()}')
            print(ae)

    if stat=='ok' and process_time()-t1_start>0.3:
        t1_msg += f' - doneChores - {process_time()-t1_start:.1f}s'
        print(t1_msg)
        

def startup():
    global ae, schedule
    print('create ci at boot')
    for aename in ae:
        ae[aename]['info']['manufacture']['fwver']=VERSION
        create.allci(aename, {'config','info'})
        schedule[aename]['reqstate']=aename

    #this need once for one board
    do_config()


# schedule measureperiod
def schedule_measureperiod(aename1):
    global ae, schedule, boardTime
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

        schedule[aename]['measure'] = boardTime+timedelta(seconds=cmeasure['measureperiod'])
        print(f'measure schedule[{aename}] at {schedule[aename]["measure"]}')

def schedule_stateperiod(aename1):
    global ae, schedule, boardTime
    for aename in ae:
        if aename1 != "" and aename != aename1: continue

        cmeasure=ae[aename]['config']['cmeasure']

        if not 'stateperiod' in cmeasure: cmeasure['stateperiod']=60 #min
        elif not isinstance(cmeasure['stateperiod'],int): cmeasure['stateperiod']=60
        print(f"cmeasure.stateperiod= {cmeasure['stateperiod']} min")

        schedule[aename]['state'] = boardTime+timedelta(minutes=cmeasure['stateperiod'])
        print(f'state schedule[{aename}] at {schedule[aename]["state"]}')

def schedule_first():
    global ae, schedule, boardTime
    for aename in ae:
        sbtime = (boardTime+timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
        sbtime1 = sbtime[:15]+'0:00'
        schedule[aename]['measure']= datetime.strptime(sbtime1, '%Y-%m-%d %H:%M:%S')
        schedule[aename]['state']= datetime.strptime(sbtime1, '%Y-%m-%d %H:%M:%S')
        print(f'{aename} set first schedule for measure, state at {boardTime} -> {schedule[aename]["state"]}')
        slack(aename, json.dumps(ae[aename]))
        #print(ae[aename])

for aename in ae:
    memory[aename]={"file":{}, "head":"","tail":""}
    trigger_activated[aename]=-1
    schedule[aename]={}

print('Ready')
Timer(3, startup).start()
RepeatedTimer(0.9, do_tick)
