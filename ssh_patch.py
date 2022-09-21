import os

def service_file_change():
    new_service = ""
    service_route = "/etc/systemd/system/autossh.service"
    os.system(f"sudo chmod 777 {service_route}")
    with open(service_route, 'r', encoding='UTF8') as f:
        lines = f.readlines() #autossh.service 파일을 한줄씩 읽어내려간다. 이때 lines은 줄 맨끝의 개행문자(\n)을 포함하고 있음에 유의.
        for l in lines:
            if "bridge.ino-on.net" in l:
                print("ubuntu host name is already brdige.ino-on.net :: skip setting")
                return False
            elif "ubuntu@" in l.replace(" ", ""): #호스트 네임이 적힌 부분을 찾는다
                new_service += F'-R {l[3:8]}:localhost:22 ubuntu@bridge.ino-on.net\n'
            else: # 바꿀 것이 없는 라인이라면 그대로 new_service에 추가
                new_service += l

    with open(service_route, 'w', encoding='UTF8') as f:
        f.write(new_service) #새롭게 구성한 string new_service를 이용해 새롭게 파일을 작성한다

    os.system(F"sudo chmod 744 {service_route}")
    os.system("sudo systemctl daemon-reload")
    return True

def ssh_init():
    child=pexpect.spawn("ssh ubuntu@bridge.ino-on.net")
    try:
        child.expect("fingerprint", timeout = 2)
        child.sendline("yes")
        print("connect to ubuntu@bridge.ino-on.net...")
        child.expect("pi@localhost")
        child.sendline("exit")
    except pexpect.TIMEOUT:
        print("known host : bridge.ino-on.net")
        child.expect("pi@localhost")
        child.sendline("exit")

    #child.interact()
    #os.system("sudo systemctl restart autossh")

# 하단부분은 ssh_patch를 import했을 때 자동으로 1회 실행된다.

try:
    import pexpect
except ImportError: # import할 수 없었다는 것은 pexpect 모듈이 설치되어있지 않다는 의미. 설치를 시행하고 import한다
    print("there is no pexpect module.")
    print("install pexpect...")
    os.system("pip install pexpect")
    import pexpect