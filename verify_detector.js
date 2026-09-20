const assert=require('node:assert/strict');
const {detect,pick,hsv}=require('./detector.js');
const w=160,h=90;
function frame(){const p=new Uint8ClampedArray(w*h*4);for(let i=0;i<p.length;i+=4){p[i]=70;p[i+1]=70;p[i+2]=70;p[i+3]=255;}return p;}
function box(p,x,y,bw,bh,c){for(let yy=y;yy<y+bh;yy++)for(let xx=x;xx<x+bw;xx++)p.set([...c,255],(yy*w+xx)*4);}
let backdrop=frame();box(backdrop,0,0,121,90,[38,63,61]);box(backdrop,30,30,15,15,[44,198,194]);assert(detect(backdrop,w,h,178,121).visible);
let p=frame();box(p,30,30,15,15,[44,198,194]);assert(detect(p,w,h,178,121).visible);
p=frame();box(p,50,30,30,30,[30,95,65]);assert(!detect(p,w,h,178,121).visible);const c=pick(p,w,h,60,40,121);assert(!c.error);assert(detect(p,w,h,c.h,121).visible);
box(p,50,30,30,30,[18,57,39]);assert(detect(p,w,h,c.h,121).visible);
p=frame();box(p,125,20,20,30,[44,198,194]);assert(!detect(p,w,h,178,121).visible);assert(pick(p,w,h,130,30,121).error);
p=frame();for(let i=0;i<30;i++)box(p,(i*7)%120,Math.floor(i/17)*12,1,1,[44,198,194]);assert(!detect(p,w,h,178,121).visible);
p=frame();box(p,10,10,10,10,[44,198,194]);box(p,70,30,20,20,[44,198,194]);assert(detect(p,w,h,178,121).cx>.45);
p=frame();box(p,0,0,121,90,[44,198,194]);assert(!detect(p,w,h,178,121).visible);
assert(pick(frame(),w,h,50,50,121).error);assert(hsv(255,0,0).h===0);
console.log('PASS: cyan default, picked dark green, darker lighting, privacy exclusion, isolated noise, largest region, background rejection, gray selection rejection');
