from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import os,json,time,threading,secrets,random,pathlib
ROOT=pathlib.Path(__file__).parent
LOCK=threading.RLock()
rooms={}
puzzles=[
("What has many keys but cannot open a single lock?","A piano."),
("What gets wetter the more it dries?","A towel."),
("What belongs to you but others use more than you do?","Your name."),
("What can travel around the world while staying in a corner?","A stamp."),
("What has a neck but no head?","A bottle."),
("What can you break without touching it?","A promise."),
("What has hands but cannot clap?","A clock."),
("What has one eye but cannot see?","A needle."),
("What has cities but no houses, forests but no trees, and water but no fish?","A map."),
("What goes up but never comes down?","Your age."),
("What has many teeth but cannot bite?","A comb."),
("What has a head and a tail but no body?","A coin."),
("What can fill a room but takes up no space?","Light."),
("What has words but never speaks?","A book."),
("What five-letter word becomes shorter when you add two letters?","Short."),
("The more you take, the more you leave behind. What are they?","Footsteps."),
("What has a bottom at the top?","Your legs."),
("What has branches but no fruit, trunk, or leaves?","A bank."),
("What can run but never walks, has a mouth but never talks?","A river."),
("What begins with T, ends with T, and has T inside?","A teapot.")]
def finish(r):
    for p in r['players'].values():
        if len(p['scores'])<r['round']: p['scores'].append(None)
    r['phase']='finished' if r['round']==3 else 'between'
def tick(r):
    if r['phase']=='running' and time.monotonic()-r['start']>=300: finish(r)
def view(r,t):
    tick(r)
    host=t==r['host']
    if not host and t not in r['players']: raise ValueError('Unknown player.')
    s=dict(host=host,code=r['code'],phase=r['phase'],round=r['round'],count=len(r['players']),name='' if host else r['players'][t]['name'])
    if host and ((r['round']==2 and r['phase']=='between') or (r['round']==3 and r['phase'] in ('running','finished'))): s['puzzle']=r['puzzle'][0]
    if host and r['phase']=='lobby': s['names']=[p['name'] for p in r['players'].values()]
    if host and r['phase']=='finished':
        s['answer']=r['puzzle'][1]
        s['results']=sorted([dict(name=p['name'],scores=p['scores'],error=round(sum(abs((x if x is not None else 300)-120) for x in p['scores']),3)) for p in r['players'].values()],key=lambda p:p['error'])
    return s
class Handler(BaseHTTPRequestHandler):
    def reply(self,status,data,typ='application/json'):
        b=json.dumps(data).encode() if typ=='application/json' else data
        self.send_response(status);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
    def do_GET(self):
        if self.path.split('?')[0] in ('/','/index.html'): self.reply(200,(ROOT/'index.html').read_bytes(),'text/html; charset=utf-8')
        else: self.reply(404,{'error':'Not found'})
    def do_POST(self):
        try:
            d=json.loads(self.rfile.read(min(int(self.headers.get('Content-Length',0)),16000)))
            a=self.path.removeprefix('/api/')
            with LOCK:
                if a=='create':
                    c=secrets.token_hex(3).upper()
                    while c in rooms: c=secrets.token_hex(3).upper()
                    t=secrets.token_urlsafe(24)
                    rooms[c]=dict(code=c,host=t,players={},phase='lobby',round=0,start=None,puzzle=random.choice(puzzles))
                    result=dict(code=c,token=t)
                else:
                    c=str(d.get('code','')).upper();r=rooms.get(c);t=d.get('token','')
                    if not r: raise ValueError('Room not found.')
                    tick(r)
                    if a=='join':
                        if r['phase']!='lobby': raise ValueError('Game already started.')
                        n=str(d.get('name','')).strip()[:24]
                        if not n: raise ValueError('Enter a name.')
                        if any(p['name'].casefold()==n.casefold() for p in r['players'].values()): raise ValueError('Choose another name.')
                        if len(r['players'])>=24: raise ValueError('Room full.')
                        t=secrets.token_urlsafe(24);r['players'][t]=dict(name=n,scores=[]);result=dict(code=c,token=t)
                    elif a=='state': result=view(r,t)
                    elif a=='change_question':
                        if t!=r['host'] or r['phase']!='between' or r['round']!=2: raise ValueError('Only the host can change the question before round 3.')
                        r['puzzle']=random.choice([p for p in puzzles if p!=r['puzzle']]);result=view(r,t)
                    elif a=='start':
                        if t!=r['host']: raise ValueError('Host only.')
                        if r['phase'] not in ('lobby','between') or len(r['players'])<2: raise ValueError('Two players required.')
                        r['round']+=1;r['start']=time.monotonic();r['phase']='running';result=view(r,t)
                    elif a=='submit':
                        if t not in r['players']: raise ValueError('Player only.')
                        p=r['players'][t]
                        if r['phase']=='running' and d.get('round')==r['round'] and len(p['scores'])<r['round']:
                            p['scores'].append(round(time.monotonic()-r['start'],3))
                            if all(len(p['scores'])==r['round'] for p in r['players'].values()): finish(r)
                        result={'ok':True}
                    else: raise ValueError('Unknown action.')
            self.reply(200,result)
        except (ValueError,TypeError,KeyError) as e: self.reply(400,{'error':str(e)})
        except Exception: self.reply(500,{'error':'Server error.'})
if __name__=='__main__':
    ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8000'))),Handler).serve_forever()
