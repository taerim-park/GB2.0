#####################################################################
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
cmeasure2={'offset':0,'measureperiod':3600,'stateperiod':60,'rawperiod':60,
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
    ae[aename]['local']={'printtick':'N', 'realstart':'Y', 'name':aename}
    TOPIC_list[aename]=F'/{csename}/{aename}/realtime'

ctrl={'cmd':''}
# 'reset','reboot  synctime','fwupdate','realstart','realstop','reqstate','settrigger','settime','setmeasure','setconnect','measurestart','meaurestop'
