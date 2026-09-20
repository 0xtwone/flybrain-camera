"""Controlled synthetic closed-loop checks; not camera or biological validation."""
import json
from pathlib import Path
from server import FlyAttention

a = FlyAttention()
rows=[]
for mode in ('fly', 'baseline', 'disconnected'):
    for target in (-.4875, .375):
        a.reset();pan=0;first_centered=None;wrong=0;centered=0
        for i in range(30):
            error=target-pan/45*.625
            r=a.step(error, True, mode)
            if abs(error)<.12:
                centered+=1
                if first_centered is None:first_centered=i
            if r['action']*error<0:wrong+=1
            pan=max(-45,min(45,pan+r['action']*3))
        final_error=target-pan/45*.625
        if mode in ('fly','baseline'):assert abs(final_error)<.12,(mode,target,final_error)
        else:assert pan==0
        assert a.step(.8,False,mode)['action']==0
        rows.append({'mode':mode,'target':target,'steps':30,'first_centered_step':first_centered,
                     'centered_samples':centered,'wrong_direction_steps':wrong,'final_pan':pan,
                     'final_error':final_error,'hidden_target_stops':True})
out={'scope':'fixed synthetic left/right targets, seed 64, same 30 control iterations per mode; no webcam or SDK',
     'passed':True,'results':rows}
Path(__file__).with_name('test-results.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
