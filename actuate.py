build_package.py                                                                                    0000644 0001750 0001750 00000003300 14246612552 012007  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     import requests
import json
import os
import sys
from datetime import datetime

if len(sys.argv)<2:
    print('Usage: python  build_package.py  build_file_name  [conf.py]')
    print()
    print(' 예1) python  build_package.py  ae.99998888-AC_S1M_01_X__0604_1522  conf.py')
    print('         -- conf.py를 넣어서 빌드합니다. 이렇게 하면 AE specific 주의: .은 자동으로 _로 변환 ')
    print(' 예2) python  build_package.py  0604_1522')
    print('         -- generic한 버전')
    print()
    print(' build_file_name  AE별로 따로할지 generic할지에 따라 결정하세요. 그저 build화일 명칭을 지정할 뿐입니다. conf.py는 generic할때는 절대 넣으면 안되겠네요')
    print(' FILES 안의 화일들은 자동으로 포함됩니다.')
    print()
    sys.exit(0)

#print(sys.argv)
ifile=f'{sys.argv[1]}.tar'
ofile=f'{sys.argv[1]}.BIN'
cmd = f'tar cf {ifile}'

files=os.popen('cat FILES').read().split('\n')
for x in files: 
    if x !="": cmd += f" {x}"

os.system(cmd)
print('OPENSSL로암호화를 해야하는데...   어쩔수없이 손으로입력해야 합니다,   dlshdhschlrh(이노온최고)   두번입력. 바꾸면 안됩니다')
os.system(f'openssl aes-256-cbc -pbkdf2 -in {ifile} -out {ofile}')
print(f'openssl aes-256-cbc -pbkdf2 -in {ifile} -out {ofile}')
print(f"created {ofile}")
print(f"mail {ofile} to 건기원  담당자")

#for internal test only
print("아래는 내부 테스트용일 뿐")
print(f'rcp {ofile} ubuntu@damoa.io:Web/public/update')
os.system(f'rcp {ofile} ubuntu@damoa.io:Web/public/update')
x=f'"cmd":"fwupdate","protocol":"HTTP","ip":"damoa.io","port":80,"path":"/update/{ofile}"'
print(f"python3 actuate.py  AE  '{{{x}}}'")
                                                                                                                                                                                                                                                                                                                                Client_Data_Saving.py                                                                               0000644 0001750 0001750 00000104525 14247344567 012737  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     # Client_Data_Saving.py
# 소켓 서버로 'CAPTURE' 명령어를 1초에 1번 보내, 센서 데이터값을 받습니다.
# 받은 데이터를 센서 별로 분리해 각각 다른 디렉토리에 저장합니다.
# 현재 mqtt 전송도 이 프로그램에서 담당하고 있습니다.
VERSION='20220604_V1.1111'
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
    global memory 
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
    with open(F"{root}/{aename}.conf","w") as f: f.write(json.dumps(ae[aename], ensure_ascii=False,indent=4))
    print(f"wrote {aename}.conf")

def do_user_command(aename, jcmd):
    global ae, schedule
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
        create.ci(aename, 'config', 'cmeasure')
    elif cmd in {'measurestop'}:
        ae[aename]['config']['cmeasure']['measurestate']='stopped'
        create.ci(aename, 'config', 'cmeasure')
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
        create.ci(aename, 'config', ckey)
        if 'stateperiod' in jcmd[ckey]: state.report(aename)

    elif cmd in {'settime'}:
        print(f'set time= {jcmd["time"]}')
        ae[aename]["config"]["time"]= jcmd["time"]
        save_conf(aename)
        create.ci(aename, 'config', 'time')
    elif cmd in {'setconnect'}:
        print(f'set {aename}/connect= {jcmd["connect"]}')
        for x in jcmd["connect"]:
            ae[aename]['config']["connect"][x]=jcmd["connect"][x]
        create.ci(aename, 'config', 'connect')
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
        return 'error',0,0

    if not 'Timestamp' in j:
        print(f"no Timestamp {j} at {datetime.now().strftime('%H:%M:%S')}")
        return 'err',0,0

    
    t1_msg += f' - server2client - {process_time()-t1_start:.1f}s' 

    global dev_busy
    dev_busy=0
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
            
            ''' 서버에서 계산합니다.
            print(f"정적데이타offset연산  offset= {cmeasure['offset']}")
            if sensor_type(aename) == "DI": data = j["DI"][dis_channel]+cmeasure['offset']
            elif sensor_type(aename) == "TP": data = j["TP"]+cmeasure['offset']
            elif sensor_type(aename) == "TI": data = j["TI"][deg_axis]+cmeasure['offset'] # offset이 있는 경우, 합쳐주어야한다
            else: data = "nope"
            '''

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

        #print(raw_json[stype]["time"])
        global doneFirstShoot
        if not aename in doneFirstShoot: doneFirstShoot[aename]=1
        if doneFirstShoot[aename]>0:
            doneFirstShoot[aename] -= 1
            dmeasure = {}
            dmeasure['val'] = raw_json[stype]["data"]
            dmeasure['time'] = raw_json[stype]["time"]
            dmeasure['type'] = "S"
            ae[aename]['data']['dmeasure'] = dmeasure
            #Timer(delay, create.ci, [aename, 'data', 'dmeasure']).start()
            #print(f" creat data/dmeasure ci for {aename} to demonstrate communication success {doneFirstShoot[aename]}")
            create.ci(aename, 'data', 'dmeasure')

    t1_msg += f' - doneSaving - {process_time()-t1_start:.1f}s' 
    #if process_time()-t1_start>0.5:
    #print(f'TIME {t1_msg}')
    return 'ok', t1_start, t1_msg


def do_tick():
    global schedule, ae

    stat, t1_start, t1_msg = do_capture('CAPTURE')
    if stat == 'error':
        global dev_busy
        dev_busy+=1
        #print('device not ready')
        if dev_busy>3:
            print(f'*** {dev_busy} consecuitive dev busy is not normal.')
        return

    once=True
    for aename in schedule:

        if 'config' in schedule[aename]: 
            do_config()
            del schedule[aename]['config']

        elif 'reqstate' in schedule[aename]:
            if once:
                once=False
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
                print(f'got this error: boardTime= {boardTime}')
                print(f'schedule.keys()= {schedule.keys()}')
                #print(ae)

    if stat=='ok' and process_time()-t1_start>0.3:
        t1_msg += f' - doneChores - {process_time()-t1_start:.1f}s'
        print(t1_msg)
        

def startup():
    global ae, schedule

    #this need once for one board
    do_config()

    print('create ci at boot')
    once=True
    for aename in ae:
        ae[aename]['info']['manufacture']['fwver']=VERSION
        create.allci(aename, {'config','info'})
        schedule[aename]['reqstate']=aename



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
        onehour1 = twohour[:-5]+'00:00'
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
        schedule[aename]['state']= datetime.strptime(sbtime1, '%Y-%m-%d %H:%M:%S')
        print(f'{aename} set first schedule for measure, state at {boardTime} -> {schedule[aename]["state"]}')
        #slack(aename, json.dumps(ae[aename]))
        #print(ae[aename])

for aename in ae:
    memory[aename]={"file":{}, "head":"","tail":""}
    trigger_activated[aename]=-1
    schedule[aename]={}
    ae[aename]['local']['upTime']=datetime.now().strftime('%Y-%m-%d %H:%M:%S')

print('Ready')
startup()
RepeatedTimer(0.9, do_tick)
                                                                                                                                                                           conf.py                                                                                             0000644 0001750 0001750 00000005537 14247340542 010176  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     import os
import json
import requests

# 아래 설정값은 최소 1회만 읽어가고 외부명령어로 값 설정이 있을 경우, 그 뒤부터는 'config.dat' 에 저장시켜두고 그것을 사용한다.
# ctrl command 로 reset 을 실행하거나, config.dat 를 삭제하면 다시 아래값을 1회 읽어간다.

csename='cse-gnrb-mon'
#host="m.damoa.io"  #이노온 테스트 사이트
host="218.232.234.232"  #건교부 테스트 사이트
port=1883

uploadhost='m.damoa.io'
uploadport=2883
from default import make_ae, ae, TOPIC_list, supported_sensors

#bridge = 80061056 #placecode 설정을 위해 변수로 재설정
#bridge = 42345141 #placecode 설정을 위해 변수로 재설정
#bridge = 32345141 #placecode 설정을 위해 변수로 재설정
#bridge = 80062056 #placecode 설정을 위해 변수로 재설정
#bridge = 11001100 # 개인 테스트용
bridge = 99998877

install= {"date":"2022-04-25","place":"금남2교(하)","placecode":F"{bridge}","location":"6.7m(P2~P3)","section":"최우측 거더","latitude":"37.657248","longitude":"127.359962","aetype":"D"}
#connect={"cseip":host,"cseport":7579,"csename":csename,"cseid":csename,"mqttip":host,"mqttport":port,"uploadip":uploadhost,"uploadport":uploadport}
connect={"cseip":host,"cseport":7579,"csename":csename,"cseid":csename,"mqttip":host,"mqttport":port,"uploadip":uploadhost,"uploadport":uploadport}

# AC X,Y,Z can't coexist in current conf
make_ae(F'ae.{bridge}-AC_S1M_01_X', csename, install, connect)
#make_ae(F'ae.{bridge}-AC_S1M_02_X', csename, install, connect)
#make_ae(F'ae.{bridge}-AC_S1M_03_X', csename, install, connect)
#make_ae(F'ae.{bridge}-DI_S1M_01_X', csename, install, connect)
#make_ae(F'ae.{bridge}-TP_S1M_01_X', csename, install, connect)
#make_ae(F'ae.{bridge}-TI_S1M_01_X', csename, install, connect)

root='/home/pi/GB'
for aename in ae:
    if os.path.exists(F"{root}/{aename}.conf"): 
        print(f'read {aename} from {aename}.conf')
        with open(F"{root}/{aename}.conf") as f:
            try:
                ae1 = json.load(f)
                ae[aename]=ae1
            except ValueError as e:
                print(e)
                print(f'wrong {aename}.conf')
    else:
        print(f'read {aename} from conf.py')

memory={}
boardTime=""
upTime=""

def slack(aename, msg):
    if os.path.exists('slackkey.txt'):
        if not 'slack' in ae[aename]["local"]:
            with open("slackkey.txt") as f: ae[aename]['local']['slack']=f.read()
            print(f'activate slack alarm {ae[aename]["local"]["slack"]}')

    if 'slack' in ae[aename]["local"]:
        url2=f'http://damoa.io:8999/?msg={msg}&channel={ae[aename]["local"]["slack"]}'
        try:
            #print(f'for {aename} {msg}')
            r = requests.get(url2)
        except requests.exceptions.RequestException as e:
            print(f'failed to slack {e}')


if __name__ == "__main__":
    print(ae)
                                                                                                                                                                 create.py                                                                                           0000644 0001750 0001750 00000003600 14247114270 010476  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     # start.py
# date : 2022-05-06
# 리소스 생성

from encodings import utf_8
import requests
import json
import sys
import os
from datetime import datetime
from conf import csename, ae, slack

def ci(aename, cnt, subcnt):
    global ae, csename
    c=ae[aename]['config']['connect']
    h={
        "Accept": "application/json",
        "X-M2M-RI": "12345",
        "X-M2M-Origin": "S",
        "Host": F"{c['cseip']}",
        "Content-Type":"application/vnd.onem2m-res+json;ty=4"
    }
    body={
        "m2m:cin":
        {
            "con": { }
        }
    }
    if cnt in {'config','info','data'}:
        url = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}/{cnt}/{subcnt}"
        body["m2m:cin"]["con"] = ae[aename][cnt][subcnt]
    else:
        url = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}/{cnt}"
        body["m2m:cin"]["con"] = ae[aename][cnt]
    #print(f'{url} {json.dumps(body)[:50]}...')
    #print(f'{url}')
              
    gotok=False
    try:
        r = requests.post(url, data=json.dumps(body), headers=h)
        r.raise_for_status()
        if "m2m:dbg" in r.json():
            print(f'got error {r.json}')
        else:
            if subcnt == "": x=''
            else: x=f'/{subcnt}'
            print(f'  created ci {aename}/{cnt}{x}/{r.json()["m2m:cin"]["rn"]} {json.dumps(r.json()["m2m:cin"]["con"], ensure_ascii=False)[:100]}...')
            slack(aename, f'created {url}/{r.json()["m2m:cin"]["rn"]}')
            gotok=True
    except requests.exceptions.RequestException as e:
        print(f'failed to ci {e}')


# (ae.323376-TP_A1_01_X, {'info','config'})
def allci(aei, all):
    #print(f'create ci for containers= {all}')
    for cnti in ae[aei]:
        for subcnti in ae[aei][cnti]:
            if cnti in all:
                #print(f'allci {aei}/{cnti}/{subcnti}')
                ci(aei, cnti, subcnti)

if __name__== "__main__":
    doit()
                                                                                                                                default.py                                                                                          0000644 0001750 0001750 00000015142 14247120756 010671  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     #####################################################################
#                   AC:Accelerator 가속도, DI:Displacement 변위, Temperature, TI:Degree 경사, DS:Distortion 변형률
supported_sensors = {'AC', 'DI', 'TP', 'TI', 'DS'}

#####################################################################
#### 다음 섹션은 센서별 generic factory 초기설정값
#####################################################################
config_ctrigger={}
#                                                                           30s          60s
config_ctrigger["AC"]={"use":"Y","mode":1,"st1high":200,"st1low":-2000,"bfsec":30,"afsec":60}
config_ctrigger["DI"]={"use":"N","mode":3,"st1high":700,"st1low":100,"bfsec":0,"afsec":1}
config_ctrigger["TP"]={"use":"N","mode":3,"st1high":60,"st1low":-20,"bfsec":0,"afsec":1}
config_ctrigger["TI"]={"use":"N","mode":3,"st1high":5,"st1low":-5,"bfsec":0,"afsec":1}
# saved for copy just in case
#{"use":"Y","mode":1,"st1high":200,"st1low":-2000,"st2high":"","st2low":"","st3high":"","st4low":"","lt4high":"","st5low":"","st5high":"","st5low":"","bfsec":30,"afsec":60}

config_cmeasure={}                                                         #measuring  stopped   
config_cmeasure['AC']={'sensitivity':20,'samplerate':"100",'usefft':'Y','measurestate':'measuring'}
config_cmeasure['DI']={'sensitivity':24,'samplerate':"1/3600",'usefft':'N','measurestate':'measuring'}
config_cmeasure['TP']={'sensitivity':16,'samplerate':"1/3600",'usefft':'N','measurestate':'measuring'}
config_cmeasure['TI']={'sensitivity':20,'samplerate':"1/3600",'usefft':'N','measurestate':'measuring'}

#                                    sec 600          min 60           min 60
cmeasure2={'offset':33,'measureperiod':3600,'stateperiod':60,'rawperiod':60,
        'st1min':2.1, 'st1max':2.6, 'st2min':3.01, 'st2max':4.01, 'st3min':5.01, 'st3max':6.01, 'st4min':7.01, 'st4max':8.01,
        'st5min':9.01, 'st5max':10.01, 'st6min':11.01, 'st6max':12.01, 'st7min':13.01, 'st7max':14.01, 'st8min':15.01, 'st8max':16.01,
        'st9min':17.01, 'st9max':18.01, 'st10min':19.01, 'st10max':20.01,'formula':'센서값*Factor+Offset'}
config_cmeasure['AC'].update(cmeasure2)  #deep copy
config_cmeasure['DI'].update(cmeasure2)  #deep copy
config_cmeasure['TP'].update(cmeasure2)  #deep copy
config_cmeasure['TI'].update(cmeasure2)  #deep copy


info_manufacture={}
info_manufacture['AC']={'serial':'T0000001','manufacturer':'Ino-on. Inc.','phonenumber':'02-336-2050','website':'http://www.ino-on.com','model':'mgi-1000',
    'sensortype':'MEMS','sensitivity':'20bit','opertemp':'-20~60℃','manufacturedate':'2022-04-19','fwver':'1.0','hwver':'1.0','hwtype':'D','mac':'e45f014b363b'}
info_manufacture['DI']={'serial':'T0000002','manufacturer':'Ino-on. Inc.','phonenumber':'02-336-2050','website':'http://www.ino-on.com','model':'mgi-1000',
    'sensortype':'Wire-strain','sensitivity':'24bit','opertemp':'-20~60℃','manufacturedate':'2022-04-19','fwver':'1.0','hwver':'1.0','hwtype':'D','mac':'e45f014b363b'}
info_manufacture['TP']={'serial':'T0000003','manufacturer':'Ino-on. Inc.','phonenumber':'02-336-2050','website':'http://www.ino-on.com','model':'mgi-1000',
    'sensortype':'CMOS','sensitivity':'12bit','opertemp':'-20~60℃','manufacturedate':'2022-04-19','fwver':'1.0','hwver':'1.0','hwtype':'D','mac':'e45f014b363b'}
info_manufacture['TI']={'serial':'T0000004','manufacturer':'Ino-on. Inc.','phonenumber':'02-336-2050','website':'http://www.ino-on.com','model':'mgi-1000',
    'sensortype':'MEMS','sensitivity':'0.01º','opertemp':'-20~60℃','manufacturedate':'2022-04-19','fwver':'1.0','hwver':'1.0','hwtype':'D','mac':'e45f014b363b'}


info_imeasure={}
info_imeasure['AC']={'mode':'D','type':'AC','item':'가속도','range':'+-2G','precision':'0.01','accuracy':'0.01','meaunit':'mg','conunit':'mg','direction':'X'}
info_imeasure['DI']={'mode':'D','type':'DI','item':'변위','range':'0-500','precision':'1','accuracy':'3','meaunit':'ustrain','conunit':'mm','direction':'X'}
info_imeasure['TP']={'mode':'D','type':'TP','item':'온도','range':'-40~+120','precision':'0.01','accuracy':'0.01','meaunit':'C degree','conunit':'C degree','direction':'X'}
info_imeasure['TI']={'mode':'D','type':'TI','item':'경사(각도)','range':'0~90','precision':'0.01','accuracy':'0.01','meaunit':'degree','conunit':'degree','direction':'X'}

data_dtrigger={"time":"","step":"","mode":"","sthigh":"","stlow":"","val":"","start":"","samplerate":"","count":"","data":""}
data_fft={"start":"","end":"","st1hz":"","st2hz":"","st3hz":"","st4hz":"","st5hz":"","st6hz":"","st7hz":"","st8hz":"","st9hz":"","st10hz":""}
data_dmeasure={"type":"","time":"","temp":"","hum":"","val":"","min":"","max":"","avg":"","std":"","rms":"","peak":""}

config_time={'zone':'GMT+9','mode':3,'ip':'time.nist.gov','port':80,'period':600} #600sec
#state={'battery':4,'memory':10,'disk':10,'cpu':20,'time':'2022-05-16 09:01:01.0000','uptime':'0 days, 13:29:34','abflag':'N','abtime':'','abdesc':'','solarinputvolt':0,'solarinputamp':0,'solarchargevolt':0,'powersupply':0}
state={}

ae={}
TOPIC_list = {}

def make_ae(aename, csename, install, config_connect):
    global TOPIC_list, ae
    global config_ctrigger, config_time, config_cmeasure, info_manufacture, info_imeasure, state, data_dtrigger, data_fft, data_dmeasure
    sensor_id= aename.split('-')[1]
    sensor_type = sensor_id[0:2]
    if not sensor_type in supported_sensors:
        print('unknown sensor definition')
        return

    ae[aename]= {
        'config':{'ctrigger':{}, 'time':{}, 'cmeasure':{}, 'connect':{}},
        'info':{'manufacture':{}, 'install':{},'imeasure':{}},
        'data':{'dtrigger':{},'fft':{},'dmeasure':{}},
        'state':state,
        'ctrl':{"cmd":"","targetid":""}
    }
    ae[aename]['config']['ctrigger'].update(config_ctrigger[sensor_type])
    ae[aename]['config']['time'].update(config_time)
    ae[aename]['config']['cmeasure'].update(config_cmeasure[sensor_type])
    ae[aename]['config']['connect'].update(config_connect)
    ae[aename]['info']['manufacture'].update(info_manufacture[sensor_type])
    ae[aename]['info']['install'].update(install)
    ae[aename]['info']['install']['sensorid']=sensor_id
    ae[aename]['info']['imeasure'].update(info_imeasure[sensor_type])
    ae[aename]['data']['dtrigger'].update(data_dtrigger)
    ae[aename]['data']['fft'].update(data_fft)
    ae[aename]['data']['dmeasure'].update(data_dmeasure)
    ae[aename]['local']={'printtick':'N', 'realstart':'Y', 'name':aename, 'upTime':""}
    TOPIC_list[aename]=F'/{csename}/{aename}/realtime'

ctrl={'cmd':''}
# 'reset','reboot  synctime','fwupdate','realstart','realstop','reqstate','settrigger','settime','setmeasure','setconnect','measurestart','meaurestop'
                                                                                                                                                                                                                                                                                                                                                                                                                              make_oneM2M_resource.py                                                                             0000644 0001750 0001750 00000010304 14246612552 013240  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     import requests
import json
import sys
import create

from conf import csename, ae
verify_only=False

def create_sub(aename):
    global csename, ae
    c=ae[aename]['config']['connect']
    h={
        "Accept": "application/json",
        "X-M2M-RI": "12345",
        "X-M2M-Origin": "S",
        "Host": F"{c['cseip']}",
        "Content-Type":"application/vnd.onem2m-res+json;ty=23"
    }
    body={
      "m2m:sub": {
        "rn": "sub",
        "enc": {
          "net": [3]
        },
        "nu": [F"mqtt://{c['cseip']}/{aename}?ct=json"],
        "exc": 10
      }
    }
    
    url = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}/ctrl?ct=json"
    if not verify_only:
        r = requests.post(url, data=json.dumps(body), headers=h)
        print('created m2m:sub', r.json()["m2m:sub"]["rn"])
        if "m2m:dbg" in r.json(): sys.exit(0)

def makeit():
    global ae, csename

    for aename in ae:
        c=ae[aename]['config']['connect']
        print('Using ', f"{c['cseip']}:{c['cseport']}")
        print('Query CB:')
        h={
            "Accept": "application/json",
            "X-M2M-RI": "12345",
            "X-M2M-Origin": "S",
            "Host": F"{c['cseip']}"
        }
        url = F"http://{c['cseip']}:{c['cseport']}/{csename}"
        r = requests.get(url, headers=h)
        print('found', 'm2m:cb', r.json()["m2m:cb"]["rn"])
        # once is enough for a board
        break
    
    print('Query AE: ')
    found=False
    for aename in ae:
        url = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}"
        r = requests.get(url, headers=h)
        j=r.json()
        if "m2m:ae" in j:
            print('found', r.json()["m2m:ae"]["rn"])
            found = True
    if found:
        return
    
    for aename in ae:
        print('Found no AE. Create fresh one')
        c=ae[aename]['config']['connect']
        h={
            "Accept": "application/json",
            "X-M2M-RI": "12345",
            "X-M2M-Origin": "S",
            "Host": F"{c['cseip']}",
            "Content-Type":"application/vnd.onem2m-res+json;ty=2"
        }
        body={
            "m2m:ae" : {
                "rn": "",
                "api": "0.0.1",
                "rr": True
                }
        }
        url = F"http://{c['cseip']}:{c['cseport']}/{csename}"
        body["m2m:ae"]["rn"]=aename
        body["m2m:ae"]["lbl"]=[aename]
        if not verify_only:
            r = requests.post(url, data=json.dumps(body), headers=h)
            print('created m2m:ae', r.json()["m2m:ae"]["rn"])
            if "m2m:dbg" in r.json(): sys.exit(0)
    
    
    print('\nCreate Container ')
    
    for aename in ae:
        c=ae[aename]['config']['connect']
        h={
            "Accept": "application/json",
            "X-M2M-RI": "12345",
            "X-M2M-Origin": "S",
            "Host": F"{c['cseip']}",
            "Content-Type":"application/vnd.onem2m-res+json;ty=3"
        }
        body={
            "m2m:cnt": {
                "rn": "",
                "lbl": []
            }
        }
        url = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}"
        for ct in ae[aename]:
            if ct == 'local':
                continue
            body["m2m:cnt"]["rn"]=ct
            body["m2m:cnt"]["lbl"]=[ct]
            if not verify_only:
                r = requests.post(url, data=json.dumps(body), headers=h)
                print(f'created m2m:cnt {aename}/{r.json()["m2m:cnt"]["rn"]}')
                if "m2m:dbg" in r.json(): 
                    print(f'error in creating ct {ct}')
                    sys.exit(0)
            if ct in {'config','info','data'}:
                url2 = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}/{ct}"
                for subct in ae[aename][ct]:
                    body["m2m:cnt"]["rn"]=subct
                    body["m2m:cnt"]["lbl"]=[subct]
                    if not verify_only:
                        r = requests.post(url2, data=json.dumps(body), headers=h)
                        print(f'created m2m:cnt {aename}/{ct}/{r.json()["m2m:cnt"]["rn"]}')
                        if "m2m:dbg" in r.json(): sys.exit(0)
                    
            if ct=='ctrl':
                create_sub(aename)


if __name__ == "__main__":
    makeit()
                                                                                                                                                                                                                                                                                                                            query_all_resource.py                                                                               0000644 0001750 0001750 00000002301 14246612552 013141  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     import requests
import json
import sys

import conf
host = conf.host
port = conf.port
cse = conf.cse
ae = conf.ae

root=conf.root

print('\n1. CB 조회', f'host= {host}')
h={
    "Accept": "application/json",
    "X-M2M-RI": "12345",
    "X-M2M-Origin": "S",
    "Host": F'{host}'
}
url = F"http://{host}:7579/{cse['name']}"
r = requests.get(url, headers=h)
print(f"{cse['name']}", json.dumps(r.json(),indent=4))

print('\n2. AE/Container 조회')

for k in ae:
    url2 = F"{url}/{k}"
    r = requests.get(url2, headers=h)
    #if "m2m:dbg" in r.json():
        #sys.exit()
    print(f'{k}', json.dumps(r.json(),indent=4))
    for ct in ae[k]:
        url3 = F"{url2}/{ct}"
        r = requests.get(url3, headers=h)
        #if "m2m:dbg" in r.json():
            #sys.exit()
        print(f' {k}/{ct}', json.dumps(r.json(),indent=4))
        if ct in {'ctrigger', 'time', 'cmeasure', 'connect', 'info','install','imeasure'}:
            for subct in ae[k][ct]:
                url4 = F"{url3}/{subct}"
                r = requests.get(url4, headers=h)
                #if "m2m:dbg" in r.json():
                    #sys.exit()
                print(f'  {k}/{ct}/{subct}', json.dumps(r.json(),indent=4))
    print()
                                                                                                                                                                                                                                                                                                                               query_ci.py                                                                                         0000644 0001750 0001750 00000002037 14246612552 011063  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     import requests
import json
import sys
from datetime import datetime, timedelta

import conf
host = conf.host
port = conf.port
csename = conf.csename
ae = conf.ae

def query(aename, container):
    global host, port, csename
    url = F"http://{host}:{port}/{csename}/{aename}/{container}?fu=1"
    h={
        "Accept": "application/json",
        "X-M2M-RI": "12345",
        "X-M2M-Origin": "S",
        "Host": F'{host}'
    }
    
    print(f'url= {url}')
    r = requests.get(url, headers=h)
    if "m2m:dbg" in r.json():
        print('error', r.json())
        sys.exit()
    
    d=r.json()["m2m:uril"]
    d.sort(reverse=True)
    
    i=1
    for x in d:
        if 'MOBIUS' in x: continue
        t=x.split('/')[-1]
        time = datetime.strptime(t, '4-%Y%m%d%H%M%S%f') + timedelta(hours=9)
        print(_ae, time)
        print(f'  http://{host}:{port}/{x}')
        i += 1
        if i>1: return

container = 'data/dmeasure'
#container = 'state'
#container = 'info/manufacture'

for aename in ae:
    query(aename, container)
    print()
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 read_resource.py                                                                                    0000644 0001750 0001750 00000000526 14246612552 012066  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     import requests
import json
import sys

if len(sys.argv)<1:
    print('Usage pkython3 read_resource.py http://.......')
    sys.exit()

h={
    "Accept": "application/json",
    "X-M2M-RI": "12345",
    "X-M2M-Origin": "S"
}
url = sys.argv[1]
print('Resource url=', url)
r = requests.get(url, headers=h)
print(json.dumps(r.json(), indent=4))
                                                                                                                                                                          RepeatedTimer.py                                                                                    0000644 0001750 0001750 00000001364 14246612552 011777  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     import time
from threading import Event, Thread

class RepeatedTimer:

    """Repeat `function` every `interval` seconds."""

    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.start = time.time()
        self.event = Event()
        self.thread = Thread(target=self._target)
        self.thread.start()

    def _target(self):
        while not self.event.wait(self._time):
            self.function(*self.args, **self.kwargs)

    @property
    def _time(self):
        return self.interval - ((time.time() - self.start) % self.interval)

    def stop(self):
        self.event.set()
        self.thread.join()
                                                                                                                                                                                                                                                                            savedData.py                                                                                        0000644 0001750 0001750 00000020252 14246612552 011136  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     # 작성자 : ino-on, 주수아
# 정해진 주기마다 가속도 데이터의 통계를 내, 모비우스 규약에 기반한 컨텐트인스턴스를 생성합니다.
# FFT 연산을 사용하는 경우, FFT 연산 후 peak값에 해당하는 hrz를 반환하고, data->FFT 컨텐트인스턴스를 생성합니다.

import json
import os
import sys
import time
from datetime import datetime, timedelta
from time import process_time
import numpy as np
import requests
from threading import Timer, Thread

import create
from conf import ae, root, memory

def sensor_type(aename):
    return aename.split('-')[1][0:2]

# double FFT(cmeasure, data_list)
# 리스트의 가장 오래된 1024개의 데이터를 받아, FFT 연산을 시행합니다.
# cmeasure에 기록된 st1min, st1max를 기반으로 peak을 찾아내어, peak에 해당하는 헤르츠를 찾아냅니다.
def FFT(cmeasure, data_list):
    FFT_fail = -1

    if len(data_list)<1024: # 데이터가 1024개 미만인 경우, 연산을 시행하지 않음
        print("no enough data")
        print("FFT calculation has failed")
        return FFT_fail # 마이너스값 return

    data_FFT_list = list()
    
    FFT_list = data_list[:1024] # select oldest 1024 data
    data_FFT_list_np = np.fft.fft(FFT_list)
    
    for i in range(len(data_FFT_list_np)):
        data_FFT_list.append(round(np.absolute(data_FFT_list_np[i]).item(),2))
    data_FFT_list[0] = 0
    #print(data_FFT_list)

    FFT_const = int(cmeasure["samplerate"])/1024
    data_FFT_X = np.arange(FFT_const, FFT_const*1025, FFT_const)
    data_peak_range = list()
    for i in range(len(data_FFT_X)):
        if data_FFT_X[i] >= cmeasure["st1min"] and data_FFT_X[i] <= cmeasure["st1max"]:
            data_peak_range.append(i)
        if data_FFT_X[i] > cmeasure["st1max"]: # 데이터가 범위를 벗어나기 시작했다면, 더이상 반복문을 수행하지 않음
            break
    # peak를 측정할 범위 내에 속하는 데이터가 전혀 없는 경우, FFT는 실패
    # 예 : st1min이 100, st1max가 1000.. 이런 식일 경우
    if len(data_peak_range) == 0: 
        print("data range error : there is no data in peak range")
        print("FFT calculation has failed")
        return FFT_fail

    peak = 0
    
    for i in range(len(data_peak_range)):
        if peak < data_FFT_list[data_peak_range[i]]:
            peak = data_FFT_list[data_peak_range[i]]

    return data_FFT_X[data_FFT_list.index(peak)]

# raw_json 은 file로 저장준비가된 모든 센서들 통합 데이타
def savedJson(aename,raw_json, t1_start, t1_msg):
    global root, ae, memory
    print(f'create ci for {aename}')
    cmeasure = ae[aename]['config']['cmeasure']
    save_path = F"{root}/merged_data/{sensor_type(aename)}"
    j = raw_json[sensor_type(aename)]
    boardTime = datetime.strptime(j['time'],'%Y-%m-%d %H:%M:%S')
    if not os.path.exists(save_path): os.makedirs(save_path)

    mymemory=memory[aename]
    point1 = process_time()
    print('measure time begin: 0')
    
    data_list = list()
    recent_data = ""
    print(f'{aename} processing {len(mymemory["file"])} records(sec)')

    # boardTime 기준으로, 아직 지금 이순간 1초 데이타는 hold되고있지, Json 으로 저정되어있지 않다. 그래서 1부터.
    print(f'boardTime= {boardTime} ')
    for i in range(1, 601): # 10분간 기간
        key = (boardTime - timedelta(seconds=i)).strftime("%Y-%m-%d-%H%M%S")
        # 가장 최근 데이터를 뽑아낸다, i=0이 정시 boardData 를 처리하기전으로 수정
        if recent_data == "":
            try:
                recent_data = mymemory["file"][key]
                print(f' got recent_data with {key}')
            except:
                print(f' failed recent_data len(mymemory["file"][{key}]= len(mymemory["file"][{key}])')
        # 데이타가 600개가 되지 않을 경우도 있다. 그래서 계속 값지정. 마지막에 지정된 값이 시작시간이 된다.
        start_time = boardTime - timedelta(seconds=i)

        if not key in mymemory["file"]:
            print(f'{aename} no key= {key} i= {i}')
            break
        json_data = mymemory["file"][key]
        if isinstance(json_data['data'], list): data_list.extend(json_data["data"])
        else: data_list.append(json_data["data"])

    t1_msg += f' - doneCollectData - {process_time()-t1_start:.1f}s'

    if sensor_type(aename) == "AC" or sensor_type(aename) == "DS": # 동적 데이터의 경우
        print(f"{aename} len(data)= {len(data_list)} elapsed= {process_time()-point1:.1f}")
        
        #print(f'len(data_list)= {len(data_list)}')
        #print(data_list)
        data_list_np = np.array(data_list)
        dmeasure = {}
        dmeasure['type'] = "D"
        dmeasure['time'] = start_time.strftime("%Y-%m-%d %H:%M:%S")   # spec에 의하면 10분 측정구간의 시작시간을 지정
        dmeasure['min'] = np.min(data_list_np)
        dmeasure['max']= np.max(data_list_np)
        dmeasure['avg'] = np.average(data_list_np)
        dmeasure['std'] = np.std(data_list_np)
        dmeasure['rms'] = np.sqrt(np.mean(data_list_np**2))
        ae[aename]['data']['dmeasure'] = dmeasure
        #create.ci(aename, 'data', 'dmeasure')
        print(f'TIMER: create.ci +1s')
        Timer(1, create.ci,[aename, 'data', 'dmeasure']).start()
        
        if cmeasure["usefft"] in {"Y", "y"}:
            hrz = FFT(cmeasure, data_list_np)
            if hrz != -1 : #FFT 연산에 성공한 경우에만 hrz 기록
                fft = {}
                fft["start"]=start_time.strftime("%Y-%m-%d %H:%M:%S")
                fft["end"]=recent_data['time']
                fft["st1hz"]=hrz
                ae[aename]['data']['fft']=fft
                #create.ci(aename, 'data', 'fft')
                t0=Thread(target=create.ci, args=(aename, 'data', 'fft'))
                t0.start()

    else: # 정적 데이터의 경우, 하나의 데이터만을 전송. FFT 설정에는 아예 반응하지 않는다
        dmeasure = {}
        dmeasure['val'] = j["data"]
        dmeasure['time'] = j["time"]
        dmeasure['type'] = "S"
        ae[aename]['data']['dmeasure'] = dmeasure
        #create.ci(aename, 'data', 'dmeasure')
        t1=Thread(target=create.ci, args=(aename, 'data', 'dmeasure')).start()

    t1_msg += f' - doneSendCi - {process_time()-t1_start:.1f}s'

    merged_file = { # 최종적으로 rawperiod간의 데이터가 저장될 json의 dict
        "starttime":start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "endtime":recent_data['time'],
        "count":len(data_list),
        "data":data_list
    }

    file_name = f'{save_path}/{start_time.strftime("%Y%m%d%H%M")}_{aename}.bin'

    # saved file의 이름은 끝나는 시간임 --> 시작시간으로 변경
    def savefile(merged_file):
        with open (file_name, "w") as f: json.dump(merged_file, f, indent=4)
        print(f'TIMER: saved')
    #savefile(aename, boardTime, f'{save_path}/{file_name}.bin')
    print(f'TIMER: savefile +2s')
    Timer(2, savefile, [merged_file]).start()


    t1_msg += f' - doneSaveFile - {process_time()-t1_start:.1f}s'

    def upload():
        host = ae[aename]['config']['connect']['uploadip']
        port = ae[aename]['config']['connect']['uploadport']
        url = F"http://{host}:{port}/upload"
        print(f'{aename} upload url= {url} {file_name}')
        try:
            r = requests.post(url, data = {"keyValue1":12345}, files = {"attachment":open(file_name, "rb")})
            print(f'TIMER: {aename} result= {r.text}')
        except:
            print(f'TIMER: fail-to-upload {aename} file={file_name}')

    #upload(aename, f'{save_path}/{file_name}.bin')
    print(f'TIMER: upload +3s')
    Timer(3, upload).start()
    #print(f'{aename} uploaded a file elapsed= {process_time()-point1:.1f}s')

    # reserve some data for trigger follow-up
    for i in range(60, 1000): # 전 1분간의 데이타를 save해둔다. 
        key = (boardTime - timedelta(seconds=i)).strftime("%Y-%m-%d-%H%M%S")
        if key in mymemory["file"]: del mymemory["file"][key]
        else:
            print(f'done removing break at {i} {key}')
            break

    t1_msg += f' - doneUploadFile - {process_time()-t1_start:.1f}s'

    print("RETURN from savedJson()")
    return 'ok', t1_start, t1_msg
                                                                                                                                                                                                                                                                                                                                                      Server_Data_Sending.py                                                                              0000644 0001750 0001750 00000046207 14246612552 013120  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     # Server_Data_Sending.py
# date : 2022-05-06
# 초기 작성자 : ino-on, 주수아
# 소켓 클라이언트와 통신을 하며, 클라이언트가 명령어를 보낼 때마다 명령어에 따른 동작을 수행합니다.
# 현재 'CAPTURE' 명령어만이 활성화되어있습니다. 

#   5/6 변위식 수정. 추후 인하대쪽 코드와 통합할 예정입니다, 주수아
#   5/5 making robust를 위한 작업들, 김규호 
import spidev
import time
import numpy as np
import socket
import select
import json
import math
import sys
from datetime import datetime
from datetime import timedelta
import re
import os
from RepeatedTimer import RepeatedTimer

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
    global BaseTimeStamp
    global BaseTime
    #t_delta = BaseTimeStamp - stamp    

    #t_delta = stamp- BaseTimeStamp     
    #return str(BaseTime + timedelta(milliseconds = t_delta))

    c_delta = stamp - BaseTimeStamp
    return (BaseTime + timedelta(milliseconds = c_delta)).strftime("%Y-%m-%d %H:%M:%S")

def status_conversion(solar, battery, vdd):
    solar   = 0.003013 * solar + 1.2824
    battery = battery / 4096 * 100  # 12-bit
    vdd     = vdd / 4096 * 100      # 12-bit

    return solar, battery, vdd

def sync_time():
    global BaseTime
    global BaseTimeStamp
    
    for i in range(5):
        BaseTime = datetime.now()
        time.sleep(ds)  
        spi.xfer2([0x27])
        time.sleep(ds)  
        status_data_i_got = spi.xfer2([0x0]*14)

        BaseTimeStamp = status_data_i_got[3] << 24 | status_data_i_got[2] << 16 | status_data_i_got[1] << 8 | status_data_i_got[0]  - TimeCorrection
        if BaseTimeStamp > 0: break
        print(f'INVALID BaseTimeStamp= {BaseTimeStamp}  try again')

    print(f'syc_time BaseTime= {BaseTime}  BaseTimeStamp= {BaseTimeStamp}')
    return str(BaseTime)

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
BaseTimeStamp = 0
BaseTime = datetime.now()   # basetime , 처음 동작할 때 다시 초기화함
TimeCorrection = int(ds * 1000) # FIXME

# AE별 global offset value, defaulted to 0
Offset={'AC':0,'DI':0,'TI':0,'TP':0}

# dict data_receiving()
# 센서로부터 data bit를 받아, 그것을 적절한 int값으로 변환합니다.
# return value는 모든 센서 데이터를 포함하고 있는 dictionary 데이터입니다.
def data_receiving():
    global Offset
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
        timestamp = time_conversion(int(basic_conversion(rcv2[4:8]),16)) #timestamp info save.
        json_data["Timestamp"] = timestamp
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
        rcv4 = spi.xfer2([0x40]*16) # follow up action
        #print(rcv4)
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
        return json_data

def set_config_data(config_data):
    jdata = json.loads(config_data)

    print(f'CONFIG wrote to board')
    for x in jdata: print(x, jdata[x])

    global Offset
    # set offset, already defauled to 0
    '''
    if '-AC_' in aename: Offset['ac'] = config['cmeasure']['offset']  
    if '-DI_' in aename: Offset['di'] = config['cmeasure']['offset']  
    if '-TI_' in aename: Offset['ti'] = config['cmeasure']['offset']  
    if '-TP_' in aename: Offset['tp'] = config['cmeasure']['offset']  
    '''

    sel_sensor=0
    for stype in jdata:
        Offset[stype]=jdata[stype]['offset']
        if jdata[stype]['use']=='Y': 
            sel_sensor += jdata[stype]['select']
        
    
    # making triger_seltect
    '''
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
    board_setting['sensorSelect'] =   int(np.uint16(sel_sensor))
    board_setting['highTemp'] =       int(np.int16(jdata['TP']['st1high']*100))
    board_setting['lowTemp'] =        int(np.int16(jdata['TP']['st1low']*100))
    board_setting['highDisp'] =       int(np.uint16((jdata['DI']['st1high']*692.9678+16339000)/1024))
    board_setting['lowDisp'] =        int(np.uint16((jdata['DI']['st1low']*692.9678+16339000)/1024))
    board_setting['highStrain'] =     int(np.int16(0))
    board_setting['lowStrain'] =      int(np.int16(0))
    board_setting['highTilt'] =       int(np.int16(jdata['TI']['st1high']*100))
    board_setting['lowTilt'] =        int(np.int16(jdata['TI']['st1low']*100))
    board_setting['highAcc'] =        int(np.uint16(jdata['AC']['st1high']/0.0039/16))
    board_setting['lowAcc'] =         int(np.int16(0))       # hw fix 5/9
    # end of formatting 
    return board_setting 


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
    return(status_data)

    
def do_command(command, param):

    # init
    flag = True
    data = {}
    
    # main
    if command=="RESYNC":
        ok_data = {"Status":"Ok", "Timestamp": sync_time()}
        ok_data['Origin'] = command
        #sending_data = json.dumps(ok_data, ensure_ascii=False)
        print(f'sync {ok_data["Timestamp"]}')
        flag = False

    elif command=="START":
        flag = False
    elif command == "STOP":
        flag = False
    elif command=="RESET":
        flag = False
    
    elif command=="CAPTURE":
        # CAPTURE 명령어를 받으면, 센서 데이터를 포함한 json file을 client에 넘깁니다.
        data = data_receiving()
        data['Origin']=command
        sending_data = json.dumps(data, ensure_ascii=False) 

    elif command=="STATUS":
        d=get_status_data()
        d["Status"]="Ok"
        d["Origin"]=command
        sending_data = json.dumps(d, ensure_ascii=False)
        #print('query board with state info')

    elif command=="CONFIG":
        sending_config_data = [0x09]
        Config_data = set_config_data(param)
        #print(Config_data)

        # assuming all values are two bytes
        for tmp in Config_data.values():
            # convert order to GBC parsing
            #sending_config_data.append(tmp >> 8)
            #sending_config_data.append(tmp & 0xFF)
            sending_config_data.append(tmp & 0xff) 
            sending_config_data.append(tmp >> 8)
        rcv = spi.xfer2(sending_config_data)
        ok_data = {"Status":"Ok"}
        ok_data['Origin'] = command
        sending_data = json.dumps(ok_data, ensure_ascii=False)
        flag = False
    else:
        print('WRONG COMMAND: ', command)
        fail_data = {"Status":"False","Reason":"Wrong Command"}
        sending_data = json.dumps(fail_data, ensure_ascii=False)
        flag=Falseflag = False
    
    if flag:
        #sending_data += '\n\n'
        client_socket.sendall(sending_data.encode()) # encode UTF-8
        #print("Server -> Client :  ", sending_data)
    
#
# Handing socket and commands
#

HOST = ''     # allow all
PORT = 50000  # Use PORT 50000

# Server socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.settimeout(10)
server_socket.listen(1)
while True:
    try:
        client_socket,addr = server_socket.accept()
        print("Socket ready to listen")
        break
    except OSError as msg:
        print('got found no client connection. keep waiting..')
        continue

#client_socket.setblocking(False)

# 소켓 클라이언트와 연결

session_active = False

def watchdog():
    global session_active
    if not session_active:
        print('found session freeze, exiting..')
        os._exit(0)
    session_active = False

RepeatedTimer(60, watchdog)

time_old=datetime.now()
sync_time()
while(1) :
    # read Command
    if select.select([client_socket], [], [], 0.01)[0]: #ready? return in 0.01 sec
        try:
            data = client_socket.recv(1024).decode().strip()
            if not data:
                print('socket troubled. exiting..')
                os._exit(0)
        except:
            print('socket raised exception. exiting..')
            os._exit(0)
        m=re.match("(\w+)(.*)", data)
        #print(m.groups())
        if m:
            cmd=m.groups()[0]
            if len(m.groups())>1:
                param=m.groups()[1]
        else:
            continue
        session_active = True

        if not cmd.startswith('CAPTURE'): print(f'got {cmd} at {datetime.now().strftime("%H:%M:%S")}')
        do_command(cmd, param)
                                                                                                                                                                                                                                                                                                                                                                                         state.py                                                                                            0000644 0001750 0001750 00000001632 14247121547 010363  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     import sys
import os
import psutil
from datetime import datetime, timedelta
import time
import json
import create

from conf import ae, boardTime

def report(aename):
    global ae
    state = ae[aename]['state']

    state['cpu']=psutil.cpu_percent()
    memory = psutil.virtual_memory()
    m2=f'{100*(memory.total-memory.available)/memory.total:.1f}'
    state['memory']=float(m2)
    state['disk']= float(f"{psutil.disk_usage('/')[3]:.1f}")
    state['time']= ae[aename]['local']['upTime']

    sec = time.time() - psutil.boot_time()
    days=int(sec/86400)
    sec=sec%86400
    hours=int(sec/3600)
    sec=sec%3600
    mins=int(sec/60)
    sec=int(sec%60)

    state['uptime']= f'{days}days, {hours:02}:{mins:02}:{sec:02}'

    #print('update', state)
    # board에서 가져온 battery는 이미 ae값에 저장되어 여기서 사용
    #print(f"state= {ae[aename]['state']}")
    create.ci(aename, 'state', '')
                                                                                                      versionup.py                                                                                        0000644 0001750 0001750 00000002604 14246612552 011275  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     import requests
import json
import os
import sys
from datetime import datetime

def versionup(url):
    # url= http://damoa.io/upload/20220102.BIN
    com = url.split('/')[-1][:-4]
    bfile = com+ '.BIN'
    file = com+ '.tar'
    print(f'bfile= {bfile}  file={file}')

    r = requests.get(url)
    if not r.status_code == 200:
        print(f'got {r.code}')
        sys.exit()
    
    os.makedirs(com)
    os.chdir(com)
    print(f'cd {com}')
    open(bfile, "wb").write(r.content)
    print(f"created {bfile} {os.path.getsize(bfile)}")
    
    
    # tar cbf package20020512.tar a.py b.py...
    # openssl aes-256-cbc -pbkdf2 -in package20020512.tar -out 20200512.BIN
    # rcp 20200512.BIN ubuntu@damoa.io:Web/public/update
    print(f"openssl aes-256-cbc -pbkdf2 -d -in {bfile} -out {file} -pass pass:dlshdhschlrh")
    os.system(f"openssl aes-256-cbc -pbkdf2 -d -in {bfile} -out {file} -pass pass:dlshdhschlrh")
    os.system(f"tar xf {file}")
    files=os.listdir('.')
    
    os.makedirs('backup')
    for f in files:
        if f in {f'{bfile}', f'{file}', 'backup'}: continue
        os.system(f'mv ../{f} backup/{f}')
        print(f'mv ../{f} backup/{f}', end=' ')
        os.system(f'cp {f} ../{f}')
        print(f'cp {f} ../{f}')
    
    print('pm2 restart all')
    os.system('pm2 restart all')
    
if __name__ == '__main__':
    versionup("HTTP://damoa.io:80/update/20220512_0241.BIN")   
                                                                                                                            x.py                                                                                                0000644 0001750 0001750 00000023116 14246612552 007513  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     import json

a='{"Timestamp": "2022-06-03 02:20:01", "trigger": {"TP": "0", "DI": "0", "DS": "0", "TI": "0", "AC": "0"}, "TI": {"x": -0.61, "y": -0.02, "z": 0.61}, "TP": 0.0, "DI": {"ch4": 632.4224705714886, "ch5": 632.4224705714886}, "AC": [{"x": 11.33, "y": -0.78, "z": 995.81}, {"x": 11.39, "y": -1.05, "z": 995.16}, {"x": 11.48, "y": -1.05, "z": 995.63}, {"x": 11.31, "y": -0.81, "z": 995.41}, {"x": 10.93, "y": -0.78, "z": 995.57}, {"x": 11.13, "y": -1.45, "z": 995.62}, {"x": 11.14, "y": -0.9, "z": 995.12}, {"x": 11.35, "y": -0.95, "z": 995.69}, {"x": 11.43, "y": -1.12, "z": 994.96}, {"x": 11.25, "y": -1.15, "z": 995.56}, {"x": 11.28, "y": -0.95, "z": 995.35}, {"x": 11.12, "y": -0.28, "z": 995.4}, {"x": 10.77, "y": -0.82, "z": 995.49}, {"x": 10.87, "y": -1.01, "z": 995.3}, {"x": 11.15, "y": -0.7, "z": 995.56}, {"x": 11.06, "y": -0.96, "z": 995.16}, {"x": 10.71, "y": -1.07, "z": 995.6}, {"x": 11.37, "y": -0.86, "z": 995.16}, {"x": 10.9, "y": -0.79, "z": 995.66}, {"x": 11.17, "y": -0.69, "z": 995.07}, {"x": 10.98, "y": -1.02, "z": 995.03}, {"x": 10.75, "y": -0.85, "z": 995.52}, {"x": 11.17, "y": -0.99, "z": 995.84}, {"x": 11.33, "y": -1.03, "z": 994.71}, {"x": 11.11, "y": -0.78, "z": 995.3}, {"x": 11.28, "y": -0.92, "z": 994.41}, {"x": 11.03, "y": -0.71, "z": 995.28}, {"x": 10.78, "y": -0.64, "z": 995.02}, {"x": 11.03, "y": -0.88, "z": 995.38}, {"x": 11.31, "y": -0.77, "z": 995.49}, {"x": 11.31, "y": -0.96, "z": 995.19}, {"x": 11.07, "y": -0.73, "z": 995.58}, {"x": 10.98, "y": -0.67, "z": 995.49}, {"x": 11.01, "y": -0.68, "z": 995.52}, {"x": 11.05, "y": -0.92, "z": 995.4}, {"x": 11.35, "y": -0.94, "z": 995.3}, {"x": 11.29, "y": -0.91, "z": 995.56}, {"x": 10.85, "y": -0.97, "z": 995.53}, {"x": 11.42, "y": -0.51, "z": 995.41}, {"x": 11.3, "y": -0.7, "z": 995.33}, {"x": 10.85, "y": -0.5, "z": 995.37}, {"x": 11.42, "y": -0.81, "z": 995.47}, {"x": 11.19, "y": -0.8, "z": 995.21}, {"x": 11.32, "y": -0.97, "z": 995.43}, {"x": 11.31, "y": -1.06, "z": 995.47}, {"x": 11.28, "y": -1.33, "z": 995.55}, {"x": 11.48, "y": -1.21, "z": 995.19}, {"x": 10.92, "y": -0.79, "z": 995.24}, {"x": 11.23, "y": -1.0, "z": 995.49}, {"x": 11.03, "y": -0.52, "z": 995.1}, {"x": 11.05, "y": -1.12, "z": 995.63}, {"x": 10.78, "y": -0.65, "z": 995.92}, {"x": 10.95, "y": -1.11, "z": 996.27}, {"x": 11.03, "y": -0.41, "z": 995.75}, {"x": 11.45, "y": -0.67, "z": 995.08}, {"x": 10.64, "y": -0.9, "z": 994.45}, {"x": 10.83, "y": -0.88, "z": 995.26}, {"x": 11.04, "y": -1.02, "z": 995.03}, {"x": 11.58, "y": -1.0, "z": 995.05}, {"x": 11.27, "y": -1.24, "z": 995.38}, {"x": 10.93, "y": -0.94, "z": 995.23}, {"x": 11.14, "y": -1.29, "z": 994.94}, {"x": 10.96, "y": -1.15, "z": 995.51}, {"x": 11.11, "y": -0.99, "z": 995.55}, {"x": 11.48, "y": -0.53, "z": 995.29}, {"x": 10.93, "y": -0.68, "z": 995.2}, {"x": 11.0, "y": -0.4, "z": 995.69}, {"x": 11.26, "y": -1.06, "z": 995.04}, {"x": 11.52, "y": -1.12, "z": 995.28}, {"x": 11.28, "y": -1.19, "z": 995.21}, {"x": 10.75, "y": -0.73, "z": 994.75}, {"x": 11.15, "y": -0.77, "z": 995.25}, {"x": 11.24, "y": -0.89, "z": 995.15}, {"x": 11.01, "y": -0.89, "z": 995.18}, {"x": 11.4, "y": -0.84, "z": 995.49}, {"x": 11.33, "y": -1.05, "z": 995.12}, {"x": 11.12, "y": -1.15, "z": 995.51}, {"x": 11.15, "y": -0.97, "z": 995.43}, {"x": 10.91, "y": -1.07, "z": 995.55}, {"x": 11.47, "y": -1.03, "z": 994.79}, {"x": 10.9, "y": -0.59, "z": 995.23}, {"x": 11.33, "y": -1.16, "z": 995.47}, {"x": 11.4, "y": -1.25, "z": 995.29}, {"x": 11.31, "y": -1.2, "z": 995.2}, {"x": 11.08, "y": -0.95, "z": 994.64}, {"x": 11.35, "y": -1.02, "z": 994.91}, {"x": 10.84, "y": -1.12, "z": 995.17}, {"x": 11.22, "y": -0.71, "z": 994.46}, {"x": 11.54, "y": -1.12, "z": 995.31}, {"x": 11.1, "y": -0.9, "z": 995.89}, {"x": 10.85, "y": -1.13, "z": 995.16}, {"x": 10.73, "y": -0.87, "z": 994.93}, {"x": 11.36, "y": -1.21, "z": 995.63}, {"x": 11.09, "y": -0.8, "z": 995.45}, {"x": 10.92, "y": -0.91, "z": 995.7}, {"x": 11.19, "y": -0.84, "z": 995.55}, {"x": 11.04, "y": -0.79, "z": 995.06}, {"x": 11.21, "y": -0.86, "z": 995.22}, {"x": 11.4, "y": -0.78, "z": 995.7}, {"x": 11.31, "y": -0.79, "z": 995.41}], "DS": [{"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}], "Status": "Ok", "Origin": "CAPTURE"}{"Status": "Ok", "Timestamp": "2022-06-03 02:20:06.272169", "Origin": "RESYNC"}'



def extract(a):
    c=0
    data=[]

    s=0
    for i in range(len(a)):
        if  a[i]=='{': c+=1
        if  a[i]=='}': c-=1
        if c==0: 
            data.append(json.loads(a[s:i+1]))
            s=i+1
    return data

d=extract(a)
for x in d:
    print(x)
                                                                                                                                                                                                                                                                                                                                                                                                                                                  testsuite.sh                                                                                        0000755 0001750 0001750 00000003276 14246612446 011271  0                                                                                                    ustar   pi                              pi                                                                                                                                                                                                                     #!/usr/bin/bash
ae=('ae.99998888-AC_S1M_01_X'  'ae.99998888-TI_S1M_01_X'  'ae.99998888-DI_S1M_01_X'  'ae.99998888-TP_S1M_01_X')
ae=('ae.99998888-AC_S1M_01_X')

for aename in ${ae[@]}; do 
    echo ==== Session starts for $aename
    echo; echo 1. setmeasure
    python3 actuate.py  ${aename} '{"cmd":"setmeasure","cmeasure":{"measureperiod":600, "stateperiod":10}}'
    sleep 2
    
    python3 actuate.py  ${aename} '{"cmd":"setmeasure","cmeasure":{"measureperiod":3600, "stateperiod":60}}'
    sleep 2

    echo; echo 2. measure stop/start
    python3 actuate.py  ${aename} '{"cmd":"measurestop"}'
    sleep 2
    
    python3 actuate.py  ${aename} '{"cmd":"measurestart"}'
    sleep 2

    echo; echo 3. real stop/start
    python3 actuate.py  ${aename} '{"cmd":"realstop"}'
    sleep 2
    
    python3 actuate.py  ${aename} '{"cmd":"realstart"}'
    sleep 2

    echo; echo 4. reqstate
    python3 actuate.py  ${aename} '{"cmd":"reqstate"}'

    if [[ ${aename} =~ "AC" ]]; then
        echo; echo 5. setrigger use st1high
        python3 actuate.py  ${aename}  '{"cmd":"settrigger","ctrigger":{"use":"N"}}'
        sleep 2
    
        python3 actuate.py  ${aename}  '{"cmd":"settrigger","ctrigger":{"use":"Y","st1high":200}}'
        sleep 2

        echo; echo 6. cmeasure offset
        python3 actuate.py  ${aename}  '{"cmd":"setmeasure","cmeasure":{"usefft":"N"}}'
        sleep 2
    
        python3 actuate.py  ${aename}  '{"cmd":"setmeasure","cmeasure":{"usefft":"Y", "offset":11}}'
        sleep 2
    fi

    echo '다음음 firmware update 명령예시'
    echo  python3 actuate.py  ${aename}   '{"cmd":"fwupdate","protocol":"HTTP","ip":"damoa.io","port":80,"path":"/update/20220512_0324.BIN"}'
    
done


                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  