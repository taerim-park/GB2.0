import requests
import json
import os
import sys
from datetime import datetime
from subprocess import PIPE, Popen, STDOUT

if len(sys.argv)<2:
    print('Usage: python  build_package.py [FILES]||[conf.py]')
    print()
    print(' 예1) python  build_package.py  conf.py')
    print('         -- conf.py만 넣어서 빌드합니다. 이렇게 하면 AE specific ')
    print(' 예2) python  build_package.py ')
    print('         -- generic한 버전')
    print()
    print(' 빌드는 generic한 것을 만드세요.   필요시 conf.py 만 따로 별도로 updatge 하는 방식으로 갑니다')
    print(' FILES 안의 화일들은 자동으로 포함됩니다.')
    print()
    sys.exit(0)

dstr = datetime.now().strftime('%Y%m%d_%H%M%S')
ifile=f'{dstr}.tar'
ofile=f'{dstr}.BIN'
cmd = f'tar cf {ifile}'


if sys.argv[1]=='conf.py':
    cmd += ' conf.py'
elif sys.argv[1]=='FILES':
    files=os.popen('cat FILES').read().split('\n')
    for x in files: 
        if x !="": cmd += f" {x}"

print('files=', cmd)

os.system(cmd)
#print('OPENSSL로암호화를 해야하는데...   어쩔수없이 손으로입력해야 합니다,   dlshdhschlrh(이노온최고)   두번입력. 바꾸면 안됩니다')
x=f'openssl aes-256-cbc -pbkdf2 -in {ifile} -out {ofile} -pass pass:dlshdhschlrh'
p=Popen(x.split(' '), stdout=PIPE, stdin=PIPE, stderr=PIPE)
print(f'openssl aes-256-cbc -pbkdf2 -in {ifile} -out {ofile}')
print(f"created {ofile}")
print(f"mail {ofile} to 건기원  담당자")

#for internal test only
#print("아래는 내부 테스트용일 뿐")
#print(f'rcp {ofile} ubuntu@damoa.io:Web/public/update')
#os.system(f'rcp {ofile} ubuntu@damoa.io:Web/public/update')
#x=f'"cmd":"fwupdate","protocol":"HTTP","ip":"damoa.io","port":80,"path":"/update/{ofile}"'
#print(f"python3 actuate.py  AE  '{{{x}}}'")
