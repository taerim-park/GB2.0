import json

def mygraph(d):
    with open("graph.html") as f: format=f.read()
    label=''
    data=''
    raw=''
    k=0
    for x in d:
        if label!="": label+=","
        label+=f"'{x[0]}'"
        if data!="": data+=","
        data+=f"{x[1]}"
        raw+=f" {x[1]}"
        k+=1
    #print(s)
    s = format.replace('<%LABEL%>', label)
    s = s.replace('<%DATA%>', data)
    s = s.replace('<%RAWDATA%>', raw)
    s = s.replace('<%LENGTH%>', str(k))
    return s
