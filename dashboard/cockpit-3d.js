import * as THREE from 'three';
import { EffectComposer } from './vendor/addons/postprocessing/EffectComposer.js';
import { RenderPass } from './vendor/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from './vendor/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from './vendor/addons/postprocessing/OutputPass.js';
import { RoomEnvironment } from './vendor/addons/environments/RoomEnvironment.js';
import { createCabin } from './cabin.js';

const LegacyRenderer = window.CockpitRenderer;
const presets = { pilot: [0, 1.45, -.65], cabin: [0, 1.65, 2.65], window: [0, 1.6, -1.75] };
const clamp = THREE.MathUtils.clamp;
const finite = (n, fallback = 0) => Number.isFinite(n) ? n : fallback;

function clearFraction(start,end,boxes) {
  let fraction=1;
  for (const box of boxes) {
    if (box.min.y>=1.65 || box.max.y<=0) continue;
    let enter=-Infinity, exit=Infinity;
    for (const axis of ['x','z']) {
      const delta=end[axis]-start[axis];
      if (Math.abs(delta)<1e-12) {
        if (start[axis]<box.min[axis] || start[axis]>box.max[axis]) { exit=-Infinity; break; }
      } else {
        const a=(box.min[axis]-start[axis])/delta, b=(box.max[axis]-start[axis])/delta;
        enter=Math.max(enter,Math.min(a,b)); exit=Math.min(exit,Math.max(a,b));
      }
    }
    if (enter<=exit && exit>=0 && enter>=0 && enter<=fraction) fraction=Math.max(0,enter-1e-4);
  }
  return fraction;
}

// Reuse every null-path/disk intersection equation. Only ray construction changes.
function exteriorShader() {
  if (!window.BlackHoleShader?.fragment) throw new Error('Black-hole shader unavailable');
  const source = window.BlackHoleShader.fragment;
  const start = source.indexOf('    vec2 screen = (2.*gl_FragCoord.xy-resolution)/resolution.x;');
  const end = source.indexOf('    float radialSpeed = dot(direction,radial);', start);
  if (start < 0 || end < 0) throw new Error('Black-hole camera interface changed');
  const ray = `
    vec2 screen = (2.*gl_FragCoord.xy-resolution)/resolution.y;
    float inclination = .13962634;
    vec3 radial = vec3(cos(orbitAngle)*cos(inclination),sin(inclination),
      sin(orbitAngle)*cos(inclination));
    vec3 right = normalize(cross(vec3(0.,1.,0.),radial));
    vec3 direction = normalize(rayBasis*vec3(screen*tanHalfFov,-1.));
`;
  return (source.slice(0, start)+ray+source.slice(end))
    .replace('#version 300 es', '')
    .replace('  uniform vec2 lookOffset;', '  uniform mat3 rayBasis;\n  uniform float tanHalfFov;');
}

function dustCloud() {
  const count = 90, positions = new Float32Array(count*3), colors = new Float32Array(count*3);
  const seeds = new Float32Array(count*3);
  let seed = 104729;
  const random = () => ((seed = (1664525*seed+1013904223) >>> 0)/4294967296);
  for (let i = 0; i < count; i++) {
    const x = (random()-.5)*3.4, y = .45+random()*2.15, z = -2.8+random()*5.8;
    seeds.set([x, y, z], i*3);
    colors.set([.55, .40, .24], i*3);
  }
  positions.set(seeds);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 32;
  const ctx = canvas.getContext('2d'), glow = ctx.createRadialGradient(16,16,0,16,16,16);
  glow.addColorStop(0,'rgba(255,255,255,1)'); glow.addColorStop(.2,'rgba(255,255,255,.4)');
  glow.addColorStop(1,'rgba(255,255,255,0)'); ctx.fillStyle=glow; ctx.fillRect(0,0,32,32);
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.PointsMaterial({ size: .012, map: texture,
    vertexColors: true, transparent: true, opacity: .30, depthWrite: false,
    blending: THREE.AdditiveBlending, sizeAttenuation: true });
  const points = new THREE.Points(geometry, material);
  return { points, update(time, reduced, light) {
    for (let i = 0; i < count; i++) {
      const j=i*3, t=reduced ? 0 : time;
      positions[j]=seeds[j]+.035*Math.sin(t*.17+i);
      positions[j+1]=seeds[j+1]+.06*Math.sin(t*.11+i*2.1);
      positions[j+2]=seeds[j+2]+.04*Math.cos(t*.13+i*1.7);
    }
    geometry.attributes.position.needsUpdate=true;
    material.opacity=.16+light*.12;
  }, dispose() { geometry.dispose(); material.dispose(); texture.dispose(); } };
}

window.CockpitRenderer = class CockpitRenderer {
  constructor(canvas) {
    this.canvas=canvas; this.error=null; this.is3D=false; this.lastFrame=null;
    this.mode='3D cabin + Schwarzschild ray tracing';
    this.location=new THREE.Vector3(...presets.pilot);
    this.look=new THREE.Quaternion(); this.localRotation=new THREE.Matrix4();
    this.exteriorBasis=new THREE.Matrix4(); this.combined=new THREE.Matrix4();
    try {
      this.renderer=new THREE.WebGLRenderer({ canvas, antialias:true, alpha:false,
        powerPreference:'high-performance', preserveDrawingBuffer:true });
      this.renderer.info.autoReset=false;
      this.stats={frames:0,rayFrames:0,gpuMs:null}; this.costs=[]; this.statsTime=0;
      this.context=this.renderer.getContext();
      this.timer=this.context.getExtension('EXT_disjoint_timer_query_webgl2');
      this.renderer.setPixelRatio(1);
      this.renderer.outputColorSpace=THREE.SRGBColorSpace;
      this.renderer.toneMapping=THREE.ACESFilmicToneMapping;
      this.renderer.toneMappingExposure=.75;
      this.renderer.shadowMap.enabled=true;
      this.renderer.shadowMap.type=THREE.PCFSoftShadowMap;
      // Cabin and key-light transforms are static; intensity changes do not
      // change shadow visibility. Generate this map once, then retain it.
      this.renderer.shadowMap.autoUpdate=false;
      this.renderer.shadowMap.needsUpdate=true;
      this.scene=new THREE.Scene();
      this.camera=new THREE.PerspectiveCamera(56, 1, .04, 50);
      this.cabin=createCabin(THREE); this.scene.add(this.cabin.group);
      this.colliders=(this.cabin.colliders || []).map(box=>new THREE.Box3(
        new THREE.Vector3(...box.min),new THREE.Vector3(...box.max))
        .expandByVector(new THREE.Vector3(.24,0,.24)));
      this.cabin.group.traverse(node=>{ if (node.isMesh) {
        node.castShadow=true; node.receiveShadow=true;
      } });
      const pmrem=new THREE.PMREMGenerator(this.renderer);
      const room=new RoomEnvironment();
      this.environment=pmrem.fromScene(room, .06);
      this.scene.environment=this.environment.texture;
      this.scene.environmentIntensity=.42;
      room.dispose(); pmrem.dispose();
      this.scene.add(new THREE.HemisphereLight(0xadbccc,0x181116,.48));
      this.windowLight=new THREE.DirectionalLight(0xffd4a1,2.1);
      this.windowLight.position.set(2.2,2.8,-6);
      this.windowLight.target.position.set(-.4,.8,1.2);
      this.windowLight.castShadow=true;
      const shadow=this.windowLight.shadow;
      shadow.mapSize.set(1024,1024); shadow.camera.near=.1; shadow.camera.far=16;
      shadow.camera.left=-4; shadow.camera.right=4; shadow.camera.top=4; shadow.camera.bottom=-4;
      shadow.bias=-.0002; shadow.normalBias=.03;
      this.scene.add(this.windowLight,this.windowLight.target);
      const fill=new THREE.DirectionalLight(0x9caec9,.38); fill.position.set(-3,2.5,3);
      this.scene.add(fill);
      const consoleLight=new THREE.PointLight(0x9fcac2,2.1,5,2);
      consoleLight.position.set(0,1.05,-1.55); this.scene.add(consoleLight);
      this.dust=dustCloud(); this.scene.add(this.dust.points);
      this.exteriorScene=new THREE.Scene();
      this.exteriorCamera=new THREE.Camera();
      this.exteriorTarget=new THREE.WebGLRenderTarget(1,1,{ type:THREE.HalfFloatType,
        depthBuffer:false, stencilBuffer:false, minFilter:THREE.LinearFilter });
      this.rayUniforms={ resolution:{value:new THREE.Vector2(1,1)}, cameraRadius:{value:30},
        orbitAngle:{value:0}, properTime:{value:0}, floatTexture:{value:true},
        rayBasis:{value:new THREE.Matrix3()}, tanHalfFov:{value:Math.tan(56*Math.PI/360)} };
      this.exteriorMaterial=new THREE.ShaderMaterial({ glslVersion:THREE.GLSL3,
        uniforms:this.rayUniforms, depthTest:false, depthWrite:false, toneMapped:false,
        vertexShader:'void main(){gl_Position=vec4(position.xy,0.,1.);}',
        fragmentShader:exteriorShader() });
      this.exteriorQuad=new THREE.Mesh(new THREE.PlaneGeometry(2,2),this.exteriorMaterial);
      this.exteriorQuad.frustumCulled=false; this.exteriorScene.add(this.exteriorQuad);
      this.scene.background=this.exteriorTarget.texture;
      const target=new THREE.WebGLRenderTarget(1,1,{type:THREE.HalfFloatType,samples:4});
      this.composer=new EffectComposer(this.renderer,target);
      this.composer.addPass(new RenderPass(this.scene,this.camera));
      this.bloom=new UnrealBloomPass(new THREE.Vector2(1,1),.11,.30,1.35);
      this.outputPass=new OutputPass();
      this.composer.addPass(this.bloom); this.composer.addPass(this.outputPass);
      this.is3D=true;
      this.handleContextLoss=()=>{
        this.error='3D graphics context lost'; this.contextLost=true;
        this.mode='3D graphics unavailable';
      };
      canvas.addEventListener('webglcontextlost',this.handleContextLoss);
    } catch (error) {
      this.error=String(error.message || error);
      this.renderer?.dispose();
      if (!LegacyRenderer) throw error;
      this.fallback=new LegacyRenderer(canvas);
      this.mode=this.fallback.mode;
    }
  }

  setView(name) {
    if (!(name in presets)) throw new Error('Unknown camera view');
    this.location.set(...presets[name]); this.view=name;
    if (this.camera) {
      this.camera.fov=name==='cabin' ? 68 : 56; this.camera.updateProjectionMatrix();
      this.rayUniforms.tanHalfFov.value=Math.tan(this.camera.fov*Math.PI/360);
      this.rayKey=null;
    }
  }

  moveLocal(dx,dz) {
    const facing=new THREE.Vector3(0,0,-1).applyQuaternion(this.look);
    facing.y=0; facing.normalize();
    const shift=new THREE.Vector3(-facing.z*finite(dx)+facing.x*finite(dz),0,
      facing.x*finite(dx)+facing.z*finite(dz));
    this.location.y=1.65;
    const bounds={x:[-1.45,1.45],z:[-1.85,2.7]};
    for (const axis of ['x','z']) {
      const end=this.location.clone();
      end[axis]=clamp(end[axis]+shift[axis],...bounds[axis]);
      this.location.lerp(end,clearFraction(this.location,end,this.colliders || []));
    }
  }

  resize(width,height,playing) {
    const cap=playing ? 1120 : 1440, pixelBudget=playing ? 700000 : 1300000;
    const ratio=Math.min(cap/width,Math.sqrt(pixelBudget/(width*height)),
      playing ? 1 : Math.min(devicePixelRatio || 1,1.5));
    const w=Math.max(1,Math.round(width*ratio)), h=Math.max(1,Math.round(height*ratio));
    if (w===this.width && h===this.height) return;
    this.width=w; this.height=h;
    this.renderer.setSize(w,h,false); this.composer.setSize(w,h);
    this.camera.aspect=width/height; this.camera.updateProjectionMatrix();
    const rayScale=Math.min(1,(playing ? 800 : 1200)/w,
      Math.sqrt((playing ? 400000 : 900000)/(w*h)));
    const rw=Math.max(1,Math.round(w*rayScale)), rh=Math.max(1,Math.round(h*rayScale));
    this.exteriorTarget.setSize(rw,rh); this.rayUniforms.resolution.value.set(rw,rh);
  }

  render(frame) {
    this.lastFrame=frame;
    if (this.fallback) { this.fallback.render(frame); return; }
    if (this.contextLost) throw new Error(this.error);
    if (!this.is3D) return;
    const started=performance.now();
    this.renderer.info.reset();
    this.pollGpu();
    const box=this.canvas.getBoundingClientRect();
    this.resize(Math.max(1,finite(frame.width,box.width || 800)),
      Math.max(1,finite(frame.height,box.height || 500)),Boolean(frame.playing));
    const radius=Math.max(2.05,finite(frame.radius,30)), phi=finite(frame.phi);
    const time=finite(frame.time,finite(frame.progress)*220);
    const effects=finite(frame.effectsTime,time), reduced=Boolean(frame.reducedMotion);
    const burn=Math.min(1,Math.hypot(...(frame.burn || [0,0])));
    const shake=(frame.flightPlaying ?? frame.playing) && !reduced ? burn*.0017 : 0;
    const yaw=finite(frame.lookYaw), pitch=clamp(finite(frame.lookPitch),-1.35,1.35);
    this.look.setFromEuler(new THREE.Euler(pitch,-yaw,0,'YXZ'));
    this.camera.position.copy(this.location);
    this.camera.position.x+=shake*Math.sin(effects*33.1);
    this.camera.position.y+=shake*.6*Math.sin(effects*47.3);
    this.camera.quaternion.copy(this.look);
    if (shake) this.camera.rotateZ(shake*.5*Math.sin(effects*39.7));
    this.camera.updateMatrixWorld();
    const inclination=8*Math.PI/180;
    const radial=new THREE.Vector3(Math.cos(phi)*Math.cos(inclination),
      Math.sin(inclination),Math.sin(phi)*Math.cos(inclination));
    const right=new THREE.Vector3().crossVectors(new THREE.Vector3(0,1,0),radial).normalize();
    const up=new THREE.Vector3().crossVectors(radial,right);
    let shadow=Math.asin(clamp(3*Math.sqrt(3)*Math.sqrt(1-2/radius)/radius,0,1));
    if (radius<3) shadow=Math.PI-shadow;
    // Aim centrally at large radius; gently graze the shadow on close approach.
    const aimFraction=THREE.MathUtils.lerp(.91,.25,
      THREE.MathUtils.smoothstep(radius,2.05,10));
    const aim=aimFraction*shadow*THREE.MathUtils.smoothstep((30-radius)/20,0,1);
    const forward=radial.clone().multiplyScalar(-Math.cos(aim)).addScaledVector(right,Math.sin(aim));
    const viewRight=radial.clone().multiplyScalar(Math.sin(aim)).addScaledVector(right,Math.cos(aim));
    // Lift the launch framing toward the lensed upper arc, rather than the
    // middle of the shadow. This orientation is cinematic, not a new orbit.
    const tilt=.24*THREE.MathUtils.smoothstep(radius,4.5,8)
      *(1-THREE.MathUtils.smoothstep(radius,18,32));
    const viewUp=up.clone().multiplyScalar(Math.cos(tilt)).addScaledVector(forward,-Math.sin(tilt));
    forward.multiplyScalar(Math.cos(tilt)).addScaledVector(up,Math.sin(tilt));
    this.exteriorBasis.makeBasis(viewRight,viewUp,forward.clone().negate());
    this.localRotation.makeRotationFromQuaternion(this.camera.quaternion);
    this.combined.multiplyMatrices(this.exteriorBasis,this.localRotation);
    this.rayUniforms.rayBasis.value.setFromMatrix4(this.combined);
    this.rayUniforms.cameraRadius.value=radius;
    this.rayUniforms.orbitAngle.value=phi;
    this.rayUniforms.properTime.value=time;
    const illumination=clamp(8/radius,.22,1);
    this.windowLight.intensity=1.3+illumination*1.5;
    this.bloom.strength=frame.effects === false ? .05 : .11;
    this.dust.points.visible=frame.effects !== false;
    const updateStart=performance.now();
    this.dust.update(effects,reduced,illumination);
    this.cabin.update?.(frame);
    this.stats.updateMs=performance.now()-updateStart;
    const gpu=this.timer && !this.gpuQuery && this.stats.frames%15===0;
    if (gpu) {
      this.gpuQuery=this.context.createQuery();
      this.context.beginQuery(this.timer.TIME_ELAPSED_EXT,this.gpuQuery);
    }
    const rayStart=performance.now();
    const rayKey=[radius,phi,time,yaw,pitch,shake ? effects : 0,this.width,this.height].join(',');
    if (rayKey!==this.rayKey) {
      this.renderer.setRenderTarget(this.exteriorTarget);
      this.renderer.render(this.exteriorScene,this.exteriorCamera);
      this.rayKey=rayKey;
      this.stats.rayFrames++;
    }
    this.stats.rayCpuMs=performance.now()-rayStart;
    this.renderer.setRenderTarget(null);
    const cabinStart=performance.now();
    this.composer.render();
    this.stats.sceneCpuMs=performance.now()-cabinStart;
    if (gpu) this.context.endQuery(this.timer.TIME_ELAPSED_EXT);
    this.stats.frames++;
    this.stats.cpuMs=performance.now()-started;
    this.costs.push(this.stats.cpuMs); if (this.costs.length>120) this.costs.shift();
    if (performance.now()-this.statsTime>1000) {
      const sorted=[...this.costs].sort((a,b)=>a-b);
      Object.assign(this.stats,{cpuMedianMs:sorted[Math.floor(sorted.length*.5)],
        cpuP95Ms:sorted[Math.min(sorted.length-1,Math.floor(sorted.length*.95))],
        drawCalls:this.renderer.info.render.calls,triangles:this.renderer.info.render.triangles,
        resolution:[this.width,this.height],
        rayResolution:[this.exteriorTarget.width,this.exteriorTarget.height],
        cameraPosition:this.location.toArray(),preset:this.view || 'pilot',
        timingNote:'CPU submission costs; gpuMs is asynchronous GPU elapsed time when supported.'});
      this.canvas.dataset.renderStats=JSON.stringify(this.stats);
      this.statsTime=performance.now();
    }
  }

  pollGpu() {
    if (!this.gpuQuery) return;
    const gl=this.context;
    if (gl.getQueryParameter(this.gpuQuery,gl.QUERY_RESULT_AVAILABLE)) {
      if (!gl.getParameter(this.timer.GPU_DISJOINT_EXT)) {
        this.stats.gpuMs=gl.getQueryParameter(this.gpuQuery,gl.QUERY_RESULT)/1e6;
      }
      gl.deleteQuery(this.gpuQuery); this.gpuQuery=null;
    }
  }

  dispose() {
    if (this.gpuQuery) this.context.deleteQuery(this.gpuQuery);
    this.canvas.removeEventListener('webglcontextlost',this.handleContextLoss);
    this.fallback?.dispose();
    this.cabin?.dispose(); this.dust?.dispose(); this.environment?.dispose();
    this.exteriorMaterial?.dispose(); this.exteriorQuad?.geometry.dispose();
    this.exteriorTarget?.dispose(); this.composer?.dispose(); this.bloom?.dispose();
    this.outputPass?.dispose();
    this.windowLight?.shadow.dispose(); this.renderer?.dispose();
  }
};
