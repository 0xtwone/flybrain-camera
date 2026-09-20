import * as THREE from 'three';
import {OrbitControls} from '/vendor/OrbitControls.js';
const el=id=>document.getElementById(id),canvas=el('brainCanvas');
let scene,camera,renderer,controls,points,lines,last,geometry,meta,queue=[],frames=0,auto=true,frozen=false,clock=0,lastNow=performance.now();
const palette=['#50a7dd','#b391f2','#cf9156','#89e4a0','#ec8d8b','#8daaa8'].map(c=>new THREE.Color(c));
const uniforms={time:{value:0},pixelRatio:{value:Math.min(devicePixelRatio,2)},cut:{value:-.94}};
let activeView='brain';
function view(which){
 activeView=which;uniforms.cut.value=which==='brain'?-.94:-10;
 if(which==='brain'){camera.position.set(0,.1,3.8);controls.target.set(0,.03,0);}
 else{camera.position.set(.1,-.8,6);controls.target.set(0,-1.05,0);}
 controls.update();el('brainView').classList.toggle('selected',which==='brain');el('cnsView').classList.toggle('selected',which!=='brain');
 if(meta)el('nodeCount').textContent=(which==='brain'?meta.positions.filter((_,i)=>i%3===1&&meta.positions[i]>=-.94).length:meta.shown).toLocaleString();
}
async function boot(){
 renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'high-performance'});
 renderer.setPixelRatio(Math.min(devicePixelRatio,2));
 scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(42,1,.01,100);
 controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.07;controls.autoRotate=true;controls.autoRotateSpeed=.3;controls.minDistance=1.3;controls.maxDistance=12;
 const r=await fetch('/api/geometry');if(!r.ok)throw new Error('geometry request failed');meta=await r.json();
 last=new Float32Array(meta.shown).fill(-1000);
 const colors=new Float32Array(meta.shown*3);
 for(let i=0;i<meta.shown;i++){const c=palette[meta.groups[i]];colors.set([c.r,c.g,c.b],i*3);}
 geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(meta.positions,3));geometry.setAttribute('color',new THREE.BufferAttribute(colors,3));geometry.setAttribute('lastSpike',new THREE.BufferAttribute(last,1).setUsage(THREE.DynamicDrawUsage));
 const material=new THREE.ShaderMaterial({uniforms,vertexColors:true,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
 vertexShader:`attribute float lastSpike;uniform float time;uniform float pixelRatio;uniform float cut;varying vec3 vColor;varying float vFire;varying float vShow;
 void main(){float age=max(0.,time-lastSpike);vFire=exp(-age*19.);vColor=color;vShow=step(cut,position.y);vec4 mv=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*mv;gl_PointSize=(1.+vFire*3.8)*pixelRatio*clamp(3.6/(-mv.z),.5,3.);}`,
 fragmentShader:`varying vec3 vColor;varying float vFire;varying float vShow;
 void main(){if(vShow<.5)discard;float r=length(gl_PointCoord-.5)*2.;if(r>1.)discard;float glow=exp(-r*r*4.);float alpha=(.12+vFire*.6)*glow;vec3 c=mix(vColor*.7,vec3(1.,.91,.71),vFire*.4);gl_FragColor=vec4(c,alpha);}`});
 points=new THREE.Points(geometry,material);scene.add(points);
 const ep=new Float32Array(meta.edges.length*3);
 for(let i=0;i<meta.edges.length;i++){let j=meta.edges[i]*3;ep.set(meta.positions.slice(j,j+3),i*3);}
 const eg=new THREE.BufferGeometry();eg.setAttribute('position',new THREE.BufferAttribute(ep,3));
 const edgeMaterial=new THREE.ShaderMaterial({uniforms,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
 vertexShader:'uniform float cut;varying float show;void main(){show=step(cut,position.y);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
 fragmentShader:'varying float show;void main(){if(show<.99)discard;gl_FragColor=vec4(.42,.38,.59,.021);}'});
 lines=new THREE.LineSegments(eg,edgeMaterial);scene.add(lines);
 el('brainLoading').hidden=true;
 el('geometryNote').textContent='有效坐标 '+meta.shown.toLocaleString()+' / '+meta.network_size.toLocaleString()+' · 缺坐标 '+meta.missing.toLocaleString()+' · 拖动旋转 / 滚轮缩放';
 view('brain');
 new ResizeObserver(()=>{const box=canvas.parentElement.getBoundingClientRect();renderer.setSize(box.width,box.height,false);camera.aspect=box.width/box.height;camera.updateProjectionMatrix();}).observe(canvas.parentElement);
 el('brainView').onclick=()=>view('brain');el('cnsView').onclick=()=>view('cns');
 el('rotateBrain').onclick=()=>{auto=!auto;controls.autoRotate=auto;el('rotateBrain').textContent=auto?'停止旋转':'自动旋转';};
 el('showEdges').onchange=()=>lines.visible=el('showEdges').checked;
 canvas.ondblclick=()=>view(activeView);
 function render(now){const dt=Math.min(.1,(now-lastNow)/1000);lastNow=now;if(!frozen)clock+=dt;uniforms.time.value=clock;
 if(!frozen){let changed=false;while(queue.length&&queue[0].at<=clock){const f=queue.shift();let visibleCount=0;for(const idx of f.ids){last[idx]=clock;if(meta.positions[idx*3+1]>=uniforms.cut.value)visibleCount++;}el('activeCount').textContent=visibleCount.toLocaleString();el('stepCount').textContent=f.step.toLocaleString();changed=true;}if(changed)geometry.attributes.lastSpike.needsUpdate=true;}
 controls.autoRotate=auto&&!frozen;controls.update();renderer.render(scene,camera);requestAnimationFrame(render);}
 requestAnimationFrame(render);
}
window.addEventListener('fly-spikes',ev=>{if(!meta||frozen)return;const d=ev.detail;const base=Math.max(clock,queue.length?queue[queue.length-1].at+.02:clock);
 d.spike_frames.forEach((ids,i)=>queue.push({at:base+i*d.step_ms/1000,ids,step:d.step_end-d.spike_frames.length+i+1}));
 // The transport normally keeps less than one batch queued; discard stale backlog after a hidden tab.
 if(queue.length>100)queue=queue.slice(-25);
});
window.addEventListener('fly-reset',()=>{queue=[];if(last){last.fill(-1000);geometry.attributes.lastSpike.needsUpdate=true;}el('activeCount').textContent='0';el('stepCount').textContent='0';});
window.addEventListener('fly-pause',ev=>{frozen=ev.detail;});
boot().catch(e=>{el('brainLoading').textContent='脑图未能加载：'+e.message;console.error(e);});
