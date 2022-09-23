import requests
import json
import os
import sys
import create
import state
import re
from datetime import datetime
from conf import ae, boardTime
from subprocess import PIPE, run


def versionup(aename, url):
    global ae

    def warn_state(msg):
        global ae
        ae[aename]['state']["abflag"]="Y"
        ae[aename]['state']["abtime"]=boardTime.strftime("%Y-%m-%d %H:%M:%S")
        ae[aename]['state']["abdesc"]=msg
        print(msg)
        state.report(aename)

    # url= HTTP://damoa.io:80/update/20220512_0241.BIN

    if not re.match(r'^http://', url, re.IGNORECASE) or not re.match(r'.*/\d{8}_\d{6}\.BIN$', url):
        warn_state(f'inappropriate url with firmware file {url}')
        return

    com = url.split('/')[-1][:-4]
    bfile = com+ '.BIN'
    file = com+ '.tar'
    print(f'bfile= {bfile}  file={file}  url={url}')

    if os.path.exists(com):
        warn_state(f"Already done same firmware update. {bfile}")
        return

    try:
        r = requests.get(url, timeout=20)
        if not r.status_code == 200:
            print(f'got {r.status_code} for {url}')
            return
    except:
        print('***** update url failed')
        warn_state("fwupdate has failed : no reply")
        return 

    os.makedirs(com)
    os.chdir(f'/home/pi/GB/{com}')
    print(f'cd {com}')
    open(f'{bfile}', "wb").write(r.content)
    s=os.path.getsize(f'{bfile}')
    print(f"created {bfile} {s}B")
    
    
    # tar cbf package20020512.tar a.py b.py...
    # openssl aes-256-cbc -pbkdf2 -in package20020512.tar -out 20200512.BIN
    # rcp 20200512.BIN ubuntu@damoa.io:Web/public/update
    print(f"openssl aes-256-cbc -pbkdf2 -d -in {bfile} -out {file} -pass pass:dlshdhschlrh")

    r= run(f"openssl aes-256-cbc -pbkdf2 -d -in {bfile} -out {file} -pass pass:dlshdhschlrh", shell=True, capture_output=True)
    if r.returncode != 0:
        warn_state(f'decoding failed {bfile}')
        return

    r= run(f"tar xf {file}", shell=True, capture_output=True)
    if r.returncode != 0:
        warn_state(f'decoding failed {bfile}')
        return

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
