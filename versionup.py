import requests
import json
import os
import sys
import create
import state
from datetime import datetime
from conf import ae

def versionup(aename, url):
    # url= http://damoa.io/upload/20220102.BIN
    com = url.split('/')[-1][:-4]
    bfile = com+ '.BIN'
    file = com+ '.tar'
    print(f'bfile= {bfile}  file={file}')

    if os.path.exists(com):
        print(f'dup name rejected: {com}')
        ae[aename]['state']["abflag"]="Y"
        ae[aename]['state']["abtime"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ae[aename]['state']["abdesc"]=f"{url} rejected due to duplicated firmware update."
        state.report(aename)
        return
        

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
