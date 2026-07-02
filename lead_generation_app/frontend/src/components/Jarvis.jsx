import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const PARTICLE_COUNT = 2000;
const GLOBE_RADIUS = 2.2;
const RING_COUNT = 3;

function createParticles() {
  const geo = new THREE.BufferGeometry();
  const positions = new Float32Array(PARTICLE_COUNT * 3);
  const colors = new Float32Array(PARTICLE_COUNT * 3);
  const sizes = new Float32Array(PARTICLE_COUNT);
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = 5 + Math.random() * 20;
    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = r * Math.cos(phi);
    positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
    const c = new THREE.Color().setHSL(0.58 + Math.random() * 0.15, 0.8, 0.4 + Math.random() * 0.3);
    colors[i * 3] = c.r; colors[i * 3 + 1] = c.g; colors[i * 3 + 2] = c.b;
    sizes[i] = 0.02 + Math.random() * 0.08;
  }
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
  return geo;
}

function createGlobe(scene) {
  const group = new THREE.Group();

  const wireframe = new THREE.Mesh(
    new THREE.SphereGeometry(GLOBE_RADIUS, 32, 24),
    new THREE.MeshBasicMaterial({ wireframe: true, color: 0x00d4ff, transparent: true, opacity: 0.3 })
  );
  group.add(wireframe);

  const dots = new THREE.Points(
    new THREE.SphereGeometry(GLOBE_RADIUS * 1.002, 48, 32),
    new THREE.PointsMaterial({ color: 0x00d4ff, size: 0.015, transparent: true, opacity: 0.6 })
  );
  group.add(dots);

  const inner = new THREE.Mesh(
    new THREE.SphereGeometry(GLOBE_RADIUS * 0.98, 32, 24),
    new THREE.MeshBasicMaterial({ color: 0x0066ff, transparent: true, opacity: 0.05, side: THREE.BackSide })
  );
  group.add(inner);

  const latLines = new THREE.Group();
  for (let i = 0; i < 12; i++) {
    const phi = (i / 12) * Math.PI;
    const curve = [];
    for (let j = 0; j <= 36; j++) {
      const theta = (j / 36) * Math.PI * 2;
      const r = GLOBE_RADIUS * 1.01;
      curve.push(new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.cos(phi),
        r * Math.sin(phi) * Math.sin(theta)
      ));
    }
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(curve),
      new THREE.LineBasicMaterial({ color: 0x00d4ff, transparent: true, opacity: 0.08 })
    );
    latLines.add(line);
  }
  group.add(latLines);

  const lonLines = new THREE.Group();
  for (let i = 0; i < 12; i++) {
    const theta = (i / 12) * Math.PI * 2;
    const curve = [];
    for (let j = 0; j <= 36; j++) {
      const phi = (j / 36) * Math.PI;
      const r = GLOBE_RADIUS * 1.01;
      curve.push(new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.cos(phi),
        r * Math.sin(phi) * Math.sin(theta)
      ));
    }
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(curve),
      new THREE.LineBasicMaterial({ color: 0x00d4ff, transparent: true, opacity: 0.08 })
    );
    lonLines.add(line);
  }
  group.add(lonLines);

  scene.add(group);
  return group;
}

function createRings(scene) {
  const rings = [];
  for (let i = 0; i < RING_COUNT; i++) {
    const radius = GLOBE_RADIUS * (1.3 + i * 0.4);
    const geo = new THREE.RingGeometry(radius - 0.01, radius, 64);
    const mat = new THREE.MeshBasicMaterial({
      color: 0x00d4ff,
      transparent: true,
      opacity: 0.15 - i * 0.04,
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = Math.PI / 2 + (i * 0.3);
    mesh.rotation.z = i * 0.5;
    scene.add(mesh);
    rings.push(mesh);
  }
  return rings;
}

function createConnectionLines(scene) {
  const group = new THREE.Group();
  const points = [];
  const count = 60;
  for (let i = 0; i < count; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = GLOBE_RADIUS * 1.02;
    points.push(new THREE.Vector3(
      r * Math.sin(phi) * Math.cos(theta),
      r * Math.cos(phi),
      r * Math.sin(phi) * Math.sin(theta)
    ));
  }
  for (let i = 0; i < count; i += 2) {
    if (i + 1 < count) {
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([points[i], points[i + 1]]),
        new THREE.LineBasicMaterial({ color: 0x00d4ff, transparent: true, opacity: 0.06 })
      );
      group.add(line);
    }
  }
  scene.add(group);
  return group;
}

function createScanRing(scene) {
  const geo = new THREE.RingGeometry(GLOBE_RADIUS * 1.1, GLOBE_RADIUS * 1.2, 48);
  const mat = new THREE.MeshBasicMaterial({
    color: 0x00d4ff,
    transparent: true,
    opacity: 0.3,
    side: THREE.DoubleSide,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.rotation.x = Math.PI / 2;
  scene.add(mesh);
  return mesh;
}

function MetricCard({ label, value, icon, color }) {
  return (
    <div className="relative group">
      <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500/20 to-cyan-500/20 rounded-xl blur-sm group-hover:blur-md transition-all opacity-0 group-hover:opacity-100" />
      <div className="relative bg-black/60 backdrop-blur-xl border border-blue-500/20 rounded-xl p-5 overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-full -translate-y-1/2 translate-x-1/2" />
        <div className="flex items-center justify-between mb-3">
          <span className="text-blue-400/60 text-xs uppercase tracking-[0.2em] font-light">{label}</span>
          <span className="text-lg" style={{ color }}>{icon}</span>
        </div>
        <div className="text-3xl font-bold text-white font-mono tracking-tight">
          {value === null ? (
            <span className="text-blue-400/30 animate-pulse">--</span>
          ) : (
            <span className="bg-gradient-to-r from-white to-blue-300 bg-clip-text text-transparent">{value.toLocaleString()}</span>
          )}
        </div>
        <div className="mt-2 h-px bg-gradient-to-r from-blue-500/40 via-cyan-500/20 to-transparent" />
      </div>
    </div>
  );
}

function CommandBar({ onCommand }) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    { type: 'system', text: 'JARVIS online. Lead Engine systems nominal.' },
    { type: 'system', text: 'Awaiting command, sir.' },
  ]);
  const messagesEndRef = useRef(null);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    const cmd = input.trim();
    setMessages(prev => [...prev, { type: 'user', text: cmd }]);
    setInput('');
    if (onCommand) onCommand(cmd, (response) => {
      setMessages(prev => [...prev, { type: 'response', text: response }]);
    });
  };

  return (
    <div className="bg-black/40 backdrop-blur-xl border border-blue-500/10 rounded-xl overflow-hidden">
      <div className="h-48 overflow-y-auto p-4 space-y-2 font-mono text-sm scrollbar-thin">
        {messages.map((msg, i) => (
          <div key={i} className={`${msg.type === 'user' ? 'text-blue-300' : msg.type === 'response' ? 'text-cyan-300' : 'text-gray-500'}`}>
            <span className="text-gray-600 mr-2">
              {msg.type === 'user' ? '>' : msg.type === 'response' ? '←' : '♦'}
            </span>
            {msg.text}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <form onSubmit={handleSubmit} className="border-t border-blue-500/10 flex">
        <span className="text-blue-400/50 px-4 py-3 font-mono text-sm">chopstick@jarvis:~$</span>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 bg-transparent px-2 py-3 text-white font-mono text-sm outline-none placeholder:text-gray-600"
          placeholder="Enter command..."
        />
      </form>
    </div>
  );
}

export default function Jarvis() {
  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const animRef = useRef(null);
  const [metrics, setMetrics] = useState({ jobs: null, records: null, leads: null, emails: null, credits: null });
  const [time, setTime] = useState(new Date());
  const scanRef = useRef(null);
  const globeRef = useRef(null);
  const ringRefs = useRef([]);

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let mounted = true;
    const fetchMetrics = async () => {
      try {
        const [mRes, cRes] = await Promise.all([
          axios.get(`${API_BASE}/dashboard/metrics`),
          axios.get(`${API_BASE}/dashboard/credits`).catch(() => ({ data: {} })),
        ]);
        if (!mounted) return;
        setMetrics({
          jobs: mRes.data.total_jobs || 0,
          records: mRes.data.total_records || 0,
          leads: mRes.data.total_enriched || 0,
          emails: mRes.data.total_valid_emails || 0,
          credits: cRes.data.credits || 0,
        });
      } catch (e) { /* silent */ }
    };
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    const scene = new THREE.Scene();
    sceneRef.current = scene;
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(0, 1, 6);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const particles = new THREE.Points(
      createParticles(),
      new THREE.PointsMaterial({ size: 0.04, vertexColors: true, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending })
    );
    scene.add(particles);

    const globe = createGlobe(scene);
    globeRef.current = globe;
    const rings = createRings(scene);
    ringRefs.current = rings;
    createConnectionLines(scene);
    const scanRing = createScanRing(scene);
    scanRef.current = scanRing;

    const mouse = { x: 0, y: 0 };
    const handleMouse = (e) => {
      mouse.x = (e.clientX / width - 0.5) * 2;
      mouse.y = (e.clientY / height - 0.5) * 2;
    };
    window.addEventListener('mousemove', handleMouse);

    let time3js = 0;
    const animate = () => {
      animRef.current = requestAnimationFrame(animate);
      time3js += 0.005;

      particles.rotation.y += 0.0002;
      globe.rotation.y += 0.003;
      globe.rotation.x += Math.sin(time3js * 0.5) * 0.001;

      rings.forEach((ring, i) => {
        ring.rotation.z += 0.002 * (1 + i * 0.3);
        const pulse = 0.08 + Math.sin(time3js * 2 + i) * 0.06;
        ring.material.opacity = pulse;
      });

      if (scanRef.current) {
        scanRef.current.position.y = Math.sin(time3js * 1.5) * 2.5;
        scanRef.current.material.opacity = 0.15 + Math.sin(time3js * 2) * 0.1;
      }

      globe.rotation.x += (mouse.y * 0.3 - globe.rotation.x) * 0.01;
      globe.rotation.y += (mouse.x * 0.3 - globe.rotation.y) * 0.01;

      renderer.render(scene, camera);
    };
    animate();

    const resize = () => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', resize);

    return () => {
      mounted = false;
      window.removeEventListener('mousemove', handleMouse);
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animRef.current);
      renderer.dispose();
      if (container.contains(renderer.domElement)) container.removeChild(renderer.domElement);
    };
  }, []);

  const handleCommand = useCallback((cmd, reply) => {
    const lower = cmd.toLowerCase();
    if (lower.includes('status') || lower.includes('metrics') || lower.includes('report')) {
      const m = metrics;
      const r = `System Status:\n  Jobs: ${m.jobs ?? '--'}\n  Companies: ${m.records ?? '--'}\n  Leads: ${m.leads ?? '--'}\n  Verified Emails: ${m.emails ?? '--'}\n  MV Credits: ${m.credits ?? '--'}`;
      setTimeout(() => reply(r), 500);
    } else if (lower.includes('hello') || lower.includes('hi ')) {
      setTimeout(() => reply('Good to see you, sir. Systems are ready.'), 300);
    } else if (lower.includes('clear')) {
      setTimeout(() => reply('Command not available. Try "status" or "help".'), 300);
    } else {
      setTimeout(() => reply(`Command "${cmd}" not recognized. Try: status, help`), 400);
    }
  }, [metrics]);

  return (
    <div className="relative min-h-[calc(100vh-8rem)] flex flex-col">
      <div ref={containerRef} className="absolute inset-0 z-0" />

      <div className="relative z-10 flex-1 flex flex-col">
        <div className="flex items-center justify-between mb-6 px-2">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 via-cyan-300 to-blue-400 bg-clip-text text-transparent">
              J.A.R.V.I.S
            </h1>
            <p className="text-blue-400/40 text-xs tracking-[0.3em] uppercase mt-1">Lead Engine Command Interface</p>
          </div>
          <div className="text-right">
            <div className="text-blue-300 font-mono text-lg">{time.toLocaleTimeString()}</div>
            <div className="text-blue-400/30 text-xs font-mono">{time.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <MetricCard label="Jobs Processed" value={metrics.jobs} icon="⚡" color="#00d4ff" />
          <MetricCard label="Companies" value={metrics.records} icon="🏢" color="#00ff88" />
          <MetricCard label="Enriched Leads" value={metrics.leads} icon="👤" color="#ff6b35" />
          <MetricCard label="Verified Emails" value={metrics.emails} icon="✉️" color="#ffd700" />
          <MetricCard label="MV Credits" value={metrics.credits} icon="💎" color="#c084fc" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1">
          <div className="space-y-4">
            <div className="bg-black/40 backdrop-blur-xl border border-blue-500/10 rounded-xl p-5">
              <h3 className="text-blue-400/60 text-xs tracking-[0.2em] uppercase mb-4 font-light">System Overview</h3>
              <div className="space-y-3">
                {[
                  { label: 'Pipeline Status', value: 'ACTIVE', color: '#00ff88' },
                  { label: 'Active Workers', value: `${metrics.jobs > 0 ? '3/3' : '2/3'}`, color: '#00d4ff' },
                  { label: 'Data Collection', value: metrics.records > 0 ? 'OPERATIONAL' : 'STANDBY', color: metrics.records > 0 ? '#00ff88' : '#ffd700' },
                  { label: 'Email Verification', value: metrics.credits > 0 ? 'READY' : 'N/A', color: metrics.credits > 0 ? '#00ff88' : '#ff6b35' },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-blue-500/5 last:border-0">
                    <span className="text-gray-400 text-sm">{item.label}</span>
                    <div className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: item.color }} />
                      <span className="text-white font-mono text-sm tracking-wider">{item.value}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="flex flex-col">
            <CommandBar onCommand={handleCommand} />
          </div>
        </div>
      </div>
    </div>
  );
}
