import sys
import os
import psutil
from datetime import datetime, timedelta
import time
import json
import create

import conf
ae = conf.ae
boardTime = conf.boardTime

def report(aename):
    global ae, boardTime
    state = ae[aename]['state']

    state['cpu']=psutil.cpu_percent()
    memory = psutil.virtual_memory()
    m2=f'{100*(memory.total-memory.available)/memory.total:.1f}'
    state['memory']=float(m2)
    state['disk']= float(f"{psutil.disk_usage('/')[3]:.1f}")
    if boardTime=="":
        state['time']= datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    else:
        state['time']= boardTime.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    sec = time.time() - psutil.boot_time()
    days=int(sec/86400)
    sec=sec%86400
    hours=int(sec/3600)
    sec=sec%3600
    mins=int(sec/60)
    sec=int(sec%60)

    state['uptime']= f'{days}days, {hours}:{mins}:{sec}'

    print('update', state)
    create.ci(aename, 'state', '')
