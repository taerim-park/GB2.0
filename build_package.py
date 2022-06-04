import requests
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
