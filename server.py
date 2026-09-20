"""Local research demo: actual flybrain, synthetic camera, no external messaging."""
import json
import math
import os
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

os.environ.setdefault('NUMBA_NUM_THREADS', '4')
import numpy as np
from flybrain import FlyBrain

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('FLY_DATA', str(HERE / 'data'))).expanduser()


class FlyAttention:
    def __init__(self):
        self.brain = FlyBrain(data=DATA_DIR, device='cpu', seed=64)
        self.inputs = {s: self.brain.cells(['LC10a'], side=s) for s in 'LR'}
        self.outputs = {s: self.brain.cells(['DNa02'], side=s) for s in 'LR'}
        valid = np.isfinite(self.brain.positions).all(axis=1)
        self.view_ids = np.flatnonzero(valid)
        self.view_map = np.full(self.brain.n, -1, dtype=np.int32)
        self.view_map[self.view_ids] = np.arange(len(self.view_ids))
        p = self.brain.positions[valid]
        xyz = np.column_stack(((p[:, 0]-49000)/35000, -(p[:, 2]-32000)/35000,
                               (p[:, 1]-33000)/35000))
        classes = self.brain.superclass[self.view_ids]
        labels = ['ol_intrinsic', 'visual_projection', 'cb_intrinsic', 'descending_neuron', 'vnc_intrinsic']
        groups = np.full(len(p), 5, dtype=np.int32)
        for i, label in enumerate(labels):
            groups[classes == label] = i
        # Sample actual matrix edges, not invented fibers. Endpoints are soma coordinates.
        slots = np.unique(np.random.default_rng(64).integers(0, len(self.brain.weights), 50000))
        pre = np.searchsorted(self.brain.indptr, slots, side='right')-1
        post = self.brain.indices[slots]
        edges = np.column_stack((self.view_map[pre], self.view_map[post]))
        edges = edges[(edges >= 0).all(axis=1)]
        self.geometry = json.dumps({'positions': np.round(xyz, 5).ravel().tolist(),
            'groups': groups.tolist(), 'edges': edges.ravel().tolist(),
            'indices': self.view_ids.tolist(), 'shown': len(p), 'missing': int((~valid).sum()),
            'network_size': self.brain.n, 'edge_count': len(edges),
            'coordinate_source': 'MaleCNS preprocessed soma positions; edges are sampled schematic links, not neurite reconstructions'}).encode()
        self.brain.step()  # Compile before accepting requests.
        self.lock = Lock()
        self.reset()

    def reset(self):
        self.brain.reset(seed=64)
        self.history = deque(maxlen=4)

    def step(self, x, visible, mode):
        with self.lock:
            t = time.perf_counter()
            inject = []
            if visible and abs(x) > .12 and mode == 'fly':
                inject = [(self.inputs['L' if x < 0 else 'R'], .8)]
            count = {'L': 0, 'R': 0}
            spike_frames = []
            raw_spikes = 0
            for _ in range(25):
                fired = self.brain.step(inject=inject)
                raw_spikes += len(fired)
                shown = self.view_map[fired]
                spike_frames.append(shown[shown >= 0].tolist())
                for side in 'LR':
                    count[side] += int(np.isin(self.outputs[side], fired).sum())
            self.history.append(count)
            seconds = len(self.history) * .5
            rates = {s: sum(row[s] for row in self.history) / seconds for s in 'LR'}
            # No direct coordinate bypass in fly mode; rates decide direction.
            delta = rates['R'] - rates['L']
            neural = 0 if abs(delta) < 1.0 else (1 if delta > 0 else -1)
            if mode == 'baseline':
                action = 0 if abs(x) < .12 else (1 if x > 0 else -1)
            elif mode == 'disconnected':
                action = 0
            else:
                action = neural
            if not visible or abs(x) < .12:
                action = 0
            return {'left': rates['L'], 'right': rates['R'], 'action': action,
                    'injection': 'none' if not inject else ('LC10a-L' if x < 0 else 'LC10a-R'),
                    'compute_ms': round((time.perf_counter()-t)*1000, 2),
                    'neurons': self.brain.n, 'mode': mode,
                    'spike_frames': spike_frames, 'step_ms': self.brain.dt*1000,
                    'raw_spikes': raw_spikes, 'shown_spikes': sum(map(len, spike_frames)),
                    'step_end': self.brain.steps}


attention = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/api/geometry':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(attention.geometry)
            return
        if self.path == '/api/health':
            return self.send(200, {'ready': True, 'neurons': attention.brain.n,
                                   'camera': 'simulated', 'sdk': 'not_connected'})
        routes = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css',
                  '/brain.js': 'brain.js', '/vendor/three.module.min.js': 'vendor/three.module.min.js',
                  '/vendor/OrbitControls.js': 'vendor/OrbitControls.js'}
        if self.path not in routes:
            return self.send(404, {'error': 'not_found'})
        name = routes[self.path]
        self.send_response(200)
        self.send_header('Content-Type', {'html': 'text/html', 'js': 'text/javascript',
                         'css': 'text/css'}[name.rsplit('.', 1)[1]] + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write((HERE / name).read_bytes())

    def do_POST(self):
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.send(403, {'error': 'origin_mismatch'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 0 or size > 2048:
                return self.send(413, {'error': 'too_large'})
            data = json.loads(self.rfile.read(size) or '{}')
            if self.path == '/api/reset':
                with attention.lock:
                    attention.reset()
                return self.send(200, {'reset': True})
            if self.path != '/api/step':
                return self.send(404, {'error': 'not_found'})
            x = float(data.get('x', 0))
            mode = data.get('mode', 'fly')
            if not math.isfinite(x) or abs(x) > 1 or mode not in ('fly', 'baseline', 'disconnected'):
                raise ValueError('invalid input')
            return self.send(200, attention.step(x, bool(data.get('visible', False)), mode))
        except (ValueError, TypeError):
            return self.send(400, {'error': 'invalid_input'})


if __name__ == '__main__':
    attention = FlyAttention()
    port = int(os.environ.get('FLY_CARE_PORT', '8765'))
    print(f'FlyBrain Camera ready: http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
