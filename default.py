import os
#####################################################################
#                   AC:Accelerator 가속도, DI:Displacement 변위, Temperature, TI:Degree 경사, DS:Distortion 변형률, CM:Camera 카메라, IF:Information 설치 이전의 임시 AE 타입
supported_sensors = {'AC', 'DI', 'TP', 'TI', 'DS', 'CM', 'IF'}

#####################################################################
#### 다음 섹션은 센서별 generic factory 초기설정값
#####################################################################
config_ctrigger={}
#                                                                           30s          60s
config_ctrigger["AC"]={"use":"N","mode":1,"st1high":200,"st1low":-2000,"bfsec":30,"afsec":60}
config_ctrigger["DS"]={"use":"N","mode":1,"st1high":200,"st1low":-2000,"bfsec":30,"afsec":60}
config_ctrigger["DI"]={"use":"N","mode":3,"st1high":700,"st1low":100,"bfsec":0,"afsec":1}
config_ctrigger["TP"]={"use":"N","mode":3,"st1high":60,"st1low":-20,"bfsec":0,"afsec":1}
config_ctrigger["TI"]={"use":"N","mode":3,"st1high":5,"st1low":-5,"bfsec":0,"afsec":1}
config_ctrigger["CM"]={} # CM은 ctrigger를 사용하지 않음
config_ctrigger["IF"]={} # IF는 ctrigger를 사용하지 않음
# saved for copy just in case
#{"use":"Y","mode":1,"st1high":200,"st1low":-2000,"st2high":"","st2low":"","st3high":"","st4low":"","lt4high":"","st5low":"","st5high":"","st5low":"","bfsec":30,"afsec":60}

config_cmeasure={}                                                         #measuring  stopped   
config_cmeasure['AC']={'sensitivity':20,'samplerate':"100",'usefft':'N','measurestate':'measuring'}
config_cmeasure['DS']={'sensitivity':20,'samplerate':"100",'usefft':'N','measurestate':'measuring'}
config_cmeasure['DI']={'sensitivity':24,'samplerate':"1/3600",'usefft':'N','measurestate':'measuring'}
config_cmeasure['TP']={'sensitivity':16,'samplerate':"1/3600",'usefft':'N','measurestate':'measuring'}
config_cmeasure['TI']={'sensitivity':20,'samplerate':"1/3600",'usefft':'N','measurestate':'measuring'}
config_cmeasure["CM"]={'measurestate':'measuring'} # CM은 cmeasure의 일부 스테이터스만 사용함.
config_cmeasure["IF"]={'measurestate':'stopped'} # IF 자체는 측정을 시행하지 않음

#                                     sec 3600          min 60           min 60
cmeasure2={'offset':0,'measureperiod':3600,'stateperiod':60,'rawperiod':60, 'st1min':2.1, 'st1max':2.6, 'formula':'지원하지 않음'}
config_cmeasure['AC'].update(cmeasure2)  #deep copy
config_cmeasure['DS'].update(cmeasure2)  #deep copy
config_cmeasure['DI'].update(cmeasure2)  #deep copy
config_cmeasure['TP'].update(cmeasure2)  #deep copy
config_cmeasure['TI'].update(cmeasure2)  #deep copy
config_cmeasure['CM'].update(cmeasure2)  #deep copy
config_cmeasure['IF'].update(cmeasure2)  #혹시 몰라 deep copy


info_manufacture={}
info_manufacture['AC']={'serial':'T0000001','manufacturer':'Ino-on. Inc.','phonenumber':'02-336-2050','website':'http://www.ino-on.com','model':'mgi-1000',
    'sensortype':'MEMS','sensitivity':'20bit','opertemp':'-20~60℃','manufacturedate':'2022-04-19','fwver':'1.0','hwver':'1.0','hwtype':'D','mac':'e45f014b363b'}
info_manufacture['DS']={'serial':'T0000006','manufacturer':'Ino-on. Inc.','phonenumber':'02-336-2050','website':'http://www.ino-on.com','model':'mgi-1000',
    'sensortype':'MEMS','sensitivity':'20bit','opertemp':'-20~60℃','manufacturedate':'2022-04-19','fwver':'1.0','hwver':'1.0','hwtype':'D','mac':'e45f014b363b'}
info_manufacture['DI']={'serial':'T0000002','manufacturer':'Ino-on. Inc.','phonenumber':'02-336-2050','website':'http://www.ino-on.com','model':'mgi-1000',
    'sensortype':'Wire-strain','sensitivity':'24bit','opertemp':'-20~60℃','manufacturedate':'2022-04-19','fwver':'1.0','hwver':'1.0','hwtype':'D','mac':'e45f014b363b'}
info_manufacture['TP']={'serial':'T0000003','manufacturer':'Ino-on. Inc.','phonenumber':'02-336-2050','website':'http://www.ino-on.com','model':'mgi-1000',
    'sensortype':'CMOS','sensitivity':'12bit','opertemp':'-20~60℃','manufacturedate':'2022-04-19','fwver':'1.0','hwver':'1.0','hwtype':'D','mac':'e45f014b363b'}
info_manufacture['TI']={'serial':'T0000004','manufacturer':'Ino-on. Inc.','phonenumber':'02-336-2050','website':'http://www.ino-on.com','model':'mgi-1000',
    'sensortype':'MEMS','sensitivity':'0.01º','opertemp':'-20~60℃','manufacturedate':'2022-04-19','fwver':'1.0','hwver':'1.0','hwtype':'D','mac':'e45f014b363b'}
info_manufacture['CM']={'serial':'T0000005','manufacturer':'Ino-on. Inc.','phonenumber':'02-336-2050','website':'http://www.ino-on.com','model':'mgi-1000',
    'sensortype':'CAM','sensitivity':'0.01º','opertemp':'-20~60℃','manufacturedate':'2022-04-19','fwver':'1.0','hwver':'1.0','hwtype':'D','mac':'e45f014b363b'}
info_manufacture['IF']={}
info_manufacture['IF'].update(info_manufacture['AC']) # IF의 디바이스별 info는 AC(x)를 따름


info_imeasure={}
info_imeasure['AC']={'mode':'D','type':'AC','item':'가속도','range':'+-2G','precision':'0.01','accuracy':'0.01','meaunit':'G','conunit':'G','direction':'X'}
info_imeasure['DS']={'mode':'D','type':'DS','item':'변형률','range':'?','precision':'0.01','accuracy':'0.01','meaunit':'microstrain','conunit':'microstrain','direction':'X'}
info_imeasure['DI']={'mode':'D','type':'DI','item':'변위','range':'0-500','precision':'1','accuracy':'3','meaunit':'ustrain','conunit':'mm','direction':'X'}
info_imeasure['TP']={'mode':'D','type':'TP','item':'온도','range':'-40~+120','precision':'0.01','accuracy':'0.01','meaunit':'C degree','conunit':'C degree','direction':'X'}
info_imeasure['TI']={'mode':'D','type':'TI','item':'경사(각도)','range':'0~90','precision':'0.01','accuracy':'0.01','meaunit':'degree','conunit':'degree','direction':'X'}
info_imeasure['CM']={'mode':'S','type':'CM','item':'사진','range':'1920*1080', 'meaunit':'pixel','conunit':'pixel','direction':'X'}
info_imeasure['IF']={}
info_imeasure['IF'].update(info_imeasure['AC']) # IF의 디바이스별 info는 AC(x)를 따름

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
    sensor_direction = aename[-2:]

    if not sensor_type in supported_sensors:
        print(f'unknown sensor definition {sensor_type}')
        print(f'supported sensor type= {supported_sensors}')
        os._exit(0)


    if not sensor_direction in {'_X', '_Y', '_Z'}:
        if sensor_type == "IF": #IF의 경우 방향정보가 있는지 검사하지 않는다
            pass
        else:
            print(f'Format error in AE near direction {aename}')
            print(f'direction must be any one of {{"_X", "_Y", "_Z"}}')
            os._exit(0)

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
    ae[aename]['info']['manufacture']['serial'] = getserial()
    ae[aename]['info']['install'].update(install)
    ae[aename]['info']['install']['sensorid']=sensor_id
    ae[aename]['info']['imeasure'].update(info_imeasure[sensor_type])
    if sensor_type != 'CM' and sensor_type != 'IF' : # 웹캠과 IF의 경우, data 컨테이너를 사용하지 않는다
        ae[aename]['data']['dtrigger'].update(data_dtrigger)
        ae[aename]['data']['fft'].update(data_fft)
        ae[aename]['data']['dmeasure'].update(data_dmeasure)
    ae[aename]['local']={'printtick':'N', 'realstart':'N', 'name':aename, 'upTime':"", 'serial': getserial(), 'mqtt':True, 'teststart':'N'}
    TOPIC_list[aename]=F'/{csename}/{aename}/realtime'

    if sensor_type == "IF": #IF인 경우, 모든 AE type에 대한 make_ae 실행
        bridge_code = aename.split("-")[0][3:]
        ae_list = [ # 모든 AE type을 담은 list 생성
            F"ae.{bridge_code}-AC_S1M_01_X", F"ae.{bridge_code}-AC_S1M_01_Y", F"ae.{bridge_code}-AC_S1M_01_Z",
            F"ae.{bridge_code}-DS_S1M_01_X", F"ae.{bridge_code}-DS_S1M_01_Y", F"ae.{bridge_code}-DS_S1M_01_Z",
            F"ae.{bridge_code}-TI_S1M_01_X", F"ae.{bridge_code}-TI_S1M_01_Y", F"ae.{bridge_code}-TI_S1M_01_Z",
            F"ae.{bridge_code}-DI_S1M_01_X", F"ae.{bridge_code}-DI_S1M_01_Y",
            F"ae.{bridge_code}-TP_S1M_01_X",
            F"ae.{bridge_code}-CM_S1M_01_X"
        ]
        for _aename in ae_list: # make_ae를 재귀적으로 시행
            make_ae(_aename, csename, install, config_connect)



def getserial():
  # Extract serial from cpuinfo file
  cpuserial = "0000000000000000"
  try:
    f = open('/proc/cpuinfo','r')
    for line in f:
      if line[0:6]=='Serial':
        cpuserial = line[10:26]
    f.close()
  except:
    cpuserial = "ERROR000000000"

  return cpuserial

ctrl={'cmd':''}
# 'reset','reboot  synctime','fwupdate','realstart','realstop','reqstate','settrigger','settime','setmeasure','setconnect','measurestart','meaurestop'
