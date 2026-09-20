"""Verify rendering payloads are exactly the model's visible spike indices."""
import json
from pathlib import Path
import numpy as np
from server import FlyAttention

a=FlyAttention()
g=json.loads(a.geometry)
assert len(g['positions']) == 3*g['shown']
assert g['shown']+g['missing']==g['network_size']
assert min(g['edges'])>=0 and max(g['edges'])<g['shown']
a.reset()
expected=[]
for i in range(25):
    fired=a.brain.step(inject=[(a.inputs['R'],.8)])
    ids=a.view_map[fired]
    expected.append(ids[ids>=0].tolist())
a.reset()
out=a.step(.7,True,'fly')
assert out['spike_frames']==expected
assert out['shown_spikes']==sum(map(len,expected))
assert out['raw_spikes']>=out['shown_spikes']
report={'passed':True,'test':'25 step payloads exactly match direct model execution with the same seed and stimulus',
        'network_neurons':g['network_size'],'positioned_neurons':g['shown'],
        'missing_coordinates':g['missing'],'sampled_real_edges':g['edge_count'],
        'shown_spike_events':out['shown_spikes'],'raw_spike_events':out['raw_spikes'],
        'not_proven':'Biological realism, anatomical neurite reconstruction, or reference video replication'}
Path(__file__).with_name('spike-test-results.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
