# Install @ RPI
# Created on 2022.09.04 by Kyuho Kim ekyuho@gmail.com
#
# pm2 start agent.py --interpreter python3
# pm2 startup
# sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u pi --hp /home/pi
# pm2 save
#
import requests
import socket
import os
import subprocess
import urllib.parse
import threading
from datetime import datetime, timedelta
from RepeatedTimer import RepeatedTimer
gid=1
KEY=''

if KEY=='': with open("key.txt") as f: KEY=f.read()

serverAddressPort   = ("127.0.0.1", 8001)
UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
p=socket.gethostname()
print(f"I am {p}")


def do_it(id, cmd):
    print(f"{id} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} job= {cmd}")
    output = subprocess.check_output(cmd, shell=True).decode('utf8')
    print(f"{id} result= {len(output)}B {str(output[:32])}...")
    r=requests.get(f'http://ec2-13-209-74-216.ap-northeast-2.compute.amazonaws.com:8000/output?key={KEY}&p={p}&output={output}')
    if not r.status_code == 200:
        print(f"{id} got {r.status_code}")
        return


def do_tick():
    try:
        r=requests.get(f'http://ec2-13-209-74-216.ap-northeast-2.compute.amazonaws.com:8000/heartbeat?key={KEY}&p={p}')
        if not r.status_code == 200:
            print(f"got {r.status_code}")
            return
    except:
        print('server not available. skip http heart beat for now, but keep trying')
        return

    cmd = r.text
    if cmd.startswith('No'):
        print(f"{p} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {cmd}")
        return

    global gid
    threading.Thread(target=do_it, args=(gid, cmd)).start()
    gid+=1


print(f"=== begin at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
RepeatedTimer(5, do_tick)
