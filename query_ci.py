import requests
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
