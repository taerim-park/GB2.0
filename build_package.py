import requests
import json
import os
import sys
from datetime import datetime

ae=sys.argv[1]
if not ae.startswith('ae'):
    print('Usage: python  build_package.py  ae.32345141-AC_S1M_01_X 2022-05-22_2330 a.py b.py.....  `cat FILES`')
    sys.exit(0)
version=sys.argv[2]
ae = ae.replace('.','_')
file = f"{ae}__{version}.tar"
cmd=f'tar cf {file}'
for i in range(3,len(sys.argv)):
    f=sys.argv[i]
    cmd += f' {f}'
bfile = file.replace('.tar','.BIN')
print(f'ae= {ae}')
print(f'version= {version}')
print(f'out= {bfile}')
print(f'files= {cmd}')

os.system(cmd)
os.system(f'openssl aes-256-cbc -pbkdf2 -in {file} -out {bfile}')
print(f'openssl aes-256-cbc -pbkdf2 -in {file} -out {bfile}')
os.system(f'rcp {bfile} ubuntu@damoa.io:Web/public/update')
print(f'rcp {bfile} ubuntu@damoa.io:Web/public/update')
x=f'"cmd":"fwupdate","protocol":"HTTP","ip":"damoa.io","port":80,"path":"/update/{bfile}"'
print(f"python3 actuate.py {ae} '{{{x}}}'")
