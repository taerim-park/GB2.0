import json

def mygraph(d):
    with open("graph.html") as f: format=f.read()
    s=''
    s2=''
    k=0
    for x in d:
        s+= f",['{x[0]}',{x[1]}]"
        s2+=f" {x[1]}"
        k+=1
    #print(s)
    s = format.replace('<%DATA%>', s)
    s = s.replace('<%RAWDATA%>', s2)
    s = s.replace('<%LENGTH%>', str(k))
    return s
