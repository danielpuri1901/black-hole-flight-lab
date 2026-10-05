'use strict';

// The replay chooses when to draw. No second animation loop runs in this class.
(() => {
  const vertex = `#version 300 es
  layout(location=0) in vec2 position;
  void main() { gl_Position = vec4(position, 0.0, 1.0); }`;
  const fragment = `#version 300 es
  precision highp float;
  uniform vec2 resolution;
  uniform float cameraRadius;
  uniform float orbitAngle;
  uniform float properTime;
  uniform vec2 lookOffset;
  uniform bool floatTexture;
  out vec4 color;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
  float hash3(vec3 p) { return fract(sin(dot(p,vec3(127.1,311.7,74.7)))*43758.5453); }
  float noise(vec3 p) {
    vec3 cell=floor(p), f=fract(p); f=f*f*(3.-2.*f);
    return mix(mix(mix(hash3(cell),hash3(cell+vec3(1,0,0)),f.x),
      mix(hash3(cell+vec3(0,1,0)),hash3(cell+vec3(1,1,0)),f.x),f.y),
      mix(mix(hash3(cell+vec3(0,0,1)),hash3(cell+vec3(1,0,1)),f.x),
      mix(hash3(cell+vec3(0,1,1)),hash3(cell+vec3(1,1,1)),f.x),f.y),f.z);
  }
  float turbulence(vec3 p) {
    return .57*noise(p)+.28*noise(p*2.03+17.)+.15*noise(p*4.13+43.);
  }
  vec3 stars(vec2 sphere,float density,float cutoff) {
    vec2 cells=sphere*vec2(density,density*.5), cell=floor(cells);
    float seed=hash(cell), weight=step(cutoff,seed);
    vec2 local=fract(cells)-vec2(.15+.7*hash(cell+9.),.15+.7*hash(cell+37.));
    float core=exp(-dot(local,local)*mix(80.,220.,hash(cell+11.)));
    float glare=exp(-abs(local.x)*85.-abs(local.y)*7.)
      +exp(-abs(local.y)*85.-abs(local.x)*7.);
    float brightness=.5+8.*pow(hash(cell+21.),6.);
    vec3 tint=mix(vec3(.63,.76,1.),vec3(1.,.83,.59),hash(cell+47.));
    return weight*brightness*(core+.04*glare*step(.9992,seed))*tint;
  }
  vec3 sky(vec3 direction) {
    vec2 sphere = vec2(atan(direction.z,direction.x)/6.2831853+.5,
      asin(clamp(direction.y,-1.,1.))/3.1415927+.5);
    float haze=pow(max(0.,1.-abs(direction.y+.17*direction.x)),24.);
    float dust=turbulence(direction*18.+vec3(3,7,11));
    return vec3(.00018,.00023,.0007)+vec3(.0008,.00045,.0013)*haze*dust
      +stars(sphere,960.,.9985)+stars(sphere+vec2(.17,.31),410.,.998);
  }
  vec3 rates(vec3 state, float b) {
    float r = max(state.x,1.8);
    return vec3(state.y,b*b*(r-3.)/(r*r*r*r),b/(r*r));
  }
  vec3 disk(float r, float angle, vec3 radial, vec3 tangent, float b) {
    vec3 location = radial*cos(angle)+tangent*sin(angle);
    float azimuth = atan(location.x,location.z);
    float spin = b*cross(radial,tangent).y;
    float shift = sqrt(1.-3./r)/(sqrt(1.-2./cameraRadius)*(1.+spin/pow(r,1.5)));
    float edge = pow(clamp((r-6.)/1.4,0.,1.),.65)*pow(clamp((18.-r)/2.,0.,1.),1.4);
    // Emitting texture shears with radius. This is art, not a fluid simulation.
    float phase=azimuth-properTime/pow(r,1.5);
    // Anisotropic emission: short radial structure and long azimuthal threads.
    // Smaller filaments avoid the broad bright cells of Cartesian turbulence.
    vec2 orbit=vec2(cos(phase),sin(phase));
    float warp=noise(vec3(r*.7,orbit*1.3));
    float band=noise(vec3(r*5.5+warp*1.8,orbit*1.5));
    float fine=noise(vec3(r*19.+warp*3.,orbit*5.));
    float filament=pow(.5+.5*sin(r*72.+warp*7.+sin(phase*3.)*.7),7.);
    float structure=.31+.56*band+.20*fine+.23*filament;
    float emission=2.4*pow(8.5/r,2.8)*edge*structure*pow(shift,3.);
    float heat=clamp(.12+(14.-r)/12.+.11*(shift-1.)+.06*filament,0.,.84);
    return emission*mix(vec3(1.,.35,.075),vec3(1.,.87,.64),heat);
  }
  void main() {
    vec2 screen = (2.*gl_FragCoord.xy-resolution)/resolution.x;
    float inclination = .13962634; // Cinematic camera lift: eight degrees.
    vec3 radial = vec3(cos(orbitAngle)*cos(inclination),sin(inclination),
      sin(orbitAngle)*cos(inclination));
    vec3 right = normalize(cross(vec3(0.,1.,0.),radial));
    vec3 up = cross(radial,right);
    float shadowAngle = asin(clamp(5.1961524*sqrt(1.-2./cameraRadius)/cameraRadius,0.,1.));
    if (cameraRadius < 3.) shadowAngle = 3.14159265-shadowAngle;
    float yaw = .90*shadowAngle*smoothstep(0.,1.,(30.-cameraRadius)/20.)+lookOffset.x;
    vec3 forward = -radial*cos(yaw)+right*sin(yaw);
    vec3 viewRight = radial*sin(yaw)+right*cos(yaw);
    vec3 viewUp = up*cos(lookOffset.y)-forward*sin(lookOffset.y);
    forward = forward*cos(lookOffset.y)+up*sin(lookOffset.y);
    float bank = .07*sin(orbitAngle);
    vec2 banked = mat2(cos(bank),sin(bank),-sin(bank),cos(bank))*screen;
    vec3 direction = normalize(forward+.75355*(banked.x*viewRight+banked.y*viewUp));
    float radialSpeed = dot(direction,radial);
    float sine = sqrt(max(0.,1.-radialSpeed*radialSpeed));
    vec3 tangent = sine > .00001 ? (direction-radialSpeed*radial)/sine : right;
    float b = cameraRadius*sine/sqrt(1.-2./cameraRadius);
    vec3 state = vec3(cameraRadius,radialSpeed,0.);
    vec3 light = vec3(0.);
    bool resolved = false;
    // Midpoint integration trades precision for bounded replay cost.
    for (int i=0;i<192;i++) {
      float h = min(1.35,.055*state.x);
      vec3 next = state+h*rates(state+.5*h*rates(state,b),b);
      float oldY = radial.y*cos(state.z)+tangent.y*sin(state.z);
      float newY = radial.y*cos(next.z)+tangent.y*sin(next.z);
      if (oldY*newY < 0.) {
        float fraction = abs(oldY)/(abs(oldY)+abs(newY));
        float crossing = mix(state.x,next.x,fraction);
        if (crossing >= 6. && crossing <= 18.) {
          light = disk(crossing,mix(state.z,next.z,fraction),radial,tangent,b);
          resolved = true; break;
        }
      }
      state = next;
      if (state.x <= 2.001) { resolved = true; break; }
      if (state.x >= 60. && state.y > 0.) {
        vec3 outRadial = radial*cos(state.z)+tangent*sin(state.z);
        vec3 outTangent = -radial*sin(state.z)+tangent*cos(state.z);
        light = sky(normalize(state.y*outRadial+b/state.x*outTangent));
        resolved = true; break;
      }
    }
    // Unresolved near-critical rays remain dark; there is no invented disk hit.
    if (!resolved) light = vec3(.00005,.00004,.00009);
    float vignette = 1.-.14*dot(screen,screen);
    light*=max(.65,vignette);
    color=vec4(floatTexture ? light : log2(light+1.)/12.,1.);
  }`;
  const display = `#version 300 es
  precision highp float;
  uniform sampler2D scene;
  uniform vec2 resolution;
  uniform bool floatTexture;
  uniform float properTime;
  out vec4 color;
  vec3 radiance(vec2 uv) {
    vec3 c=texture(scene,uv).rgb;
    return floatTexture ? c : exp2(c*12.)-1.;
  }
  vec3 bright(vec2 uv) {
    vec3 c=radiance(uv);
    return c*smoothstep(1.,3.,max(c.r,max(c.g,c.b)));
  }
  vec3 film(vec3 c) {
    c*=.74;
    return clamp((c*(2.51*c+.03))/(c*(2.43*c+.59)+.14),0.,1.);
  }
  void main() {
    vec2 uv = gl_FragCoord.xy/resolution, pixel = (1./resolution)*(resolution.x/960.);
    vec3 base = radiance(uv)*.84;
    base += .04*(radiance(uv+pixel*vec2(1,0))+radiance(uv-pixel*vec2(1,0))
      +radiance(uv+pixel*vec2(0,1))+radiance(uv-pixel*vec2(0,1)));
    vec3 glow = bright(uv+pixel*vec2(5,0))+bright(uv-pixel*vec2(5,0))
      +bright(uv+pixel*vec2(0,5))+bright(uv-pixel*vec2(0,5));
    glow += .5*(bright(uv+pixel*vec2(12,0))+bright(uv-pixel*vec2(12,0))
      +bright(uv+pixel*vec2(0,12))+bright(uv-pixel*vec2(0,12)));
    vec3 streak=bright(uv+pixel*vec2(32,0))+bright(uv-pixel*vec2(32,0));
    vec3 glare=vec3(streak.r*.008,streak.g*.006,streak.b*.009);
    float grain=fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233))+properTime*7.)*43758.5453)-.5;
    vec3 result=pow(film(base+.04*glow+glare),vec3(1./2.2));
    color=vec4(result+grain*.0022,1.);
  }`;

  window.BlackHoleShader = { fragment };
  window.CockpitRenderer = class CockpitRenderer {
    constructor(canvas) {
      this.canvas = canvas;
      this.mode = 'Schwarzschild ray tracing';
      this.error = null;
      this.lastFrame = null;
      this.gl = canvas.getContext('webgl2', { antialias: false, alpha: false, depth: false, preserveDrawingBuffer: true });
      if (!this.gl) { this.startFallback(); return; }
      try {
        const gl = this.gl;
        const compile = (type, source) => {
          const shader = gl.createShader(type);
          gl.shaderSource(shader, source); gl.compileShader(shader);
          if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            const message = gl.getShaderInfoLog(shader); gl.deleteShader(shader); throw new Error(message);
          }
          return shader;
        };
        const link = source => {
          const a = compile(gl.VERTEX_SHADER, vertex), b = compile(gl.FRAGMENT_SHADER, source);
          const program = gl.createProgram();
          gl.attachShader(program,a); gl.attachShader(program,b); gl.linkProgram(program);
          gl.deleteShader(a); gl.deleteShader(b);
          if (!gl.getProgramParameter(program,gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
          return program;
        };
        this.program = link(fragment); this.displayProgram = link(display);
        gl.useProgram(this.program);
        this.buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
        const position = gl.getAttribLocation(this.program, 'position');
        gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
        this.uniforms = Object.fromEntries(['resolution','cameraRadius','orbitAngle','properTime','floatTexture','lookOffset'].map(name => [name, gl.getUniformLocation(this.program,name)]));
        this.displayResolution = gl.getUniformLocation(this.displayProgram,'resolution');
        this.displayTime = gl.getUniformLocation(this.displayProgram,'properTime');
        this.displayFloat = gl.getUniformLocation(this.displayProgram,'floatTexture');
        this.hdr = Boolean(gl.getExtension('EXT_color_buffer_float'));
        this.texture = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,this.texture);
        gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
        this.framebuffer = gl.createFramebuffer();
      } catch (error) {
        this.error = String(error.message || error);
        this.startFallback();
      }
      canvas.addEventListener('webglcontextlost', event => {
        event.preventDefault(); this.error = 'WebGL context lost'; this.startFallback();
        if (this.lastFrame) this.render(this.lastFrame);
      });
    }

    startFallback() {
      if (this.fallback) return;
      this.mode = 'Illustrative image fallback';
      // A canvas cannot switch context types. Copy a small 2D image into a new sibling.
      this.fallback = document.createElement('canvas');
      this.fallback.className = `${this.canvas.className} cockpit-fallback`.trim();
      this.fallback.style.cssText = this.canvas.style.cssText;
      this.fallback.style.position = 'absolute'; this.fallback.style.inset = '0';
      this.fallback.style.width = '100%'; this.fallback.style.height = '100%';
      this.fallback.setAttribute('aria-hidden', 'true');
      this.canvas.insertAdjacentElement('afterend', this.fallback);
      this.canvas.style.visibility = 'hidden';
      this.context = this.fallback.getContext('2d');
      this.image = new Image();
      this.image.onload = () => { if (this.lastFrame) this.render(this.lastFrame); };
      this.image.src = '/black-hole.png';
    }

    render(frame) {
      this.lastFrame = frame;
      const box = this.canvas.getBoundingClientRect();
      const w = Math.max(1, Number(frame.width) || box.width || 640);
      const h = Math.max(1, Number(frame.height) || box.height || 400);
      const ratio = Math.min((frame.playing ? 800 : 1440)/w,(frame.playing ? 500 : 900)/h,
        frame.playing ? 1 : Math.min(window.devicePixelRatio || 1,2));
      const width = Math.max(1, Math.round(w*ratio)), height = Math.max(1, Math.round(h*ratio));
      const radius = Math.max(2.05, Number.isFinite(frame.radius) ? frame.radius : 30);
      const phi = Number.isFinite(frame.phi) ? frame.phi : 0;
      const time = Number.isFinite(frame.time) ? frame.time : (Number(frame.progress)||0)*220;
      const lookYaw = Number.isFinite(frame.lookYaw) ? Math.max(-.8,Math.min(.8,frame.lookYaw)) : 0;
      const lookPitch = Number.isFinite(frame.lookPitch) ? Math.max(-.45,Math.min(.45,frame.lookPitch)) : 0;
      if (this.mode === 'Schwarzschild ray tracing') {
        if (this.canvas.width !== width || this.canvas.height !== height || !this.textureReady) {
          this.canvas.width = width; this.canvas.height = height;
          const gl = this.gl; gl.bindTexture(gl.TEXTURE_2D,this.texture);
          gl.texImage2D(gl.TEXTURE_2D,0,this.hdr ? gl.RGBA16F : gl.RGBA,width,height,0,gl.RGBA,
            this.hdr ? gl.HALF_FLOAT : gl.UNSIGNED_BYTE,null);
          gl.bindFramebuffer(gl.FRAMEBUFFER,this.framebuffer);
          gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,this.texture,0);
          if (gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE) {
            this.hdr=false;
            gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,width,height,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
          }
          this.textureReady = true;
        }
        const gl = this.gl; gl.viewport(0,0,width,height); gl.useProgram(this.program);
        gl.bindFramebuffer(gl.FRAMEBUFFER,this.framebuffer);
        gl.uniform2f(this.uniforms.resolution,width,height);
        gl.uniform1f(this.uniforms.cameraRadius,radius); gl.uniform1f(this.uniforms.orbitAngle,phi);
        gl.uniform1f(this.uniforms.properTime,time); gl.uniform1i(this.uniforms.floatTexture,this.hdr ? 1 : 0);
        gl.uniform2f(this.uniforms.lookOffset,lookYaw,lookPitch);
        gl.drawArrays(gl.TRIANGLES,0,3);
        gl.bindFramebuffer(gl.FRAMEBUFFER,null); gl.useProgram(this.displayProgram);
        gl.bindTexture(gl.TEXTURE_2D,this.texture); gl.uniform2f(this.displayResolution,width,height);
        gl.uniform1f(this.displayTime,time); gl.uniform1i(this.displayFloat,this.hdr ? 1 : 0);
        gl.drawArrays(gl.TRIANGLES,0,3);
      } else {
        const canvas = this.fallback, c = this.context;
        canvas.width = width; canvas.height = height;
        c.fillStyle = '#03040a'; c.fillRect(0,0,width,height);
        if (!this.image.complete || !this.image.naturalWidth) return;
        const zoom = Math.min(8, Math.max(.85, 30/radius));
        const scale = Math.max(width/this.image.width,height/this.image.height)*zoom;
        c.save(); c.translate(width*(.5-lookYaw/.9),height*.47+lookPitch*width/.9);
        c.rotate(.07*Math.sin(phi));
        c.drawImage(this.image,-this.image.width*.55*scale,-this.image.height*.53*scale,
          this.image.width*scale,this.image.height*scale); c.restore();
        if (radius < 3) {
          c.fillStyle = `rgba(0,0,0,${Math.min(1,(3-radius)/.95)})`; c.fillRect(0,0,width,height);
        }
      }
    }

    dispose() {
      if (this.gl) {
        this.gl.deleteBuffer(this.buffer); this.gl.deleteProgram(this.program);
        this.gl.deleteProgram(this.displayProgram); this.gl.deleteTexture(this.texture);
        this.gl.deleteFramebuffer(this.framebuffer);
      }
      this.fallback?.remove();
    }
  };
})();
