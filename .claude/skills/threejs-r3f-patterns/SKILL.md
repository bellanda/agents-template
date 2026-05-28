---
name: threejs-r3f-patterns
description: Three.js + React Three Fiber (R3F) + drei patterns — Canvas declarativo (não imperative `new THREE.Scene()`), animation loop via `useFrame` (NUNCA `requestAnimationFrame` solto), cleanup automático pelo R3F + manual em listeners customizados, helpers drei (`OrbitControls`, `Stars`, `Float`, `useGLTF`, `Environment`, `Stats`), shaders via `shaderMaterial`/Lygia, particles via `BufferGeometry` + `Points`. Inclui anti-padrão "usar Three.js pra qualquer animação" — alternativas Motion (2D), CSS (hover/transition), Magic UI (cards com brilho/glow). INVOCAR ANTES de — criar Canvas/scene 3D, importar `three`/`@react-three/fiber`/`@react-three/drei`, shader/material customizado, animação de partículas, scene interativa, modelo GLTF, animação imperativa com `useFrame`, ou decisão "isso justifica Three.js ou cabe em Motion/CSS/Magic UI?". NUNCA `requestAnimationFrame` em scene 3D (use `useFrame`); NUNCA `new THREE.Scene()` imperative em React; NUNCA Three.js pra animação 2D normal (gasto de WebGL context não justifica).
---

# Three.js + React Three Fiber — Padrões React Idiomáticos

R3F traz Three.js para o mundo declarativo do React. Em vez de imperative `new THREE.Scene()` + `scene.add(mesh)`, você escreve JSX e R3F reconcilia. Animation loop, cleanup e instancing são automáticos.

## 1. Decisão — Three.js ou outra coisa?

Three.js abre WebGL context (caro). Use somente quando o visual justifica:

| Caso                                                         | Use                                |
| ------------------------------------------------------------ | ---------------------------------- |
| 3D real (mesh, lighting, depth, camera)                      | **Three.js + R3F**                 |
| Partículas/shader complexos                                  | **Three.js + R3F**                 |
| Modelo GLTF                                                  | **Three.js + R3F**                 |
| Card com brilho/glow/border animado                          | **Magic UI** (Shimmer, BorderBeam) |
| Number ticker, Globe, Marquee, Animated Beam                 | **Magic UI**                       |
| Animação 2D — fade, slide, transição de página               | **Motion** (`motion`, não framer)  |
| Hover state, micro-interaction                               | **CSS** + Tailwind                 |
| Confetti / particle 2D simples                               | **canvas-confetti** ou Magic UI    |

Regra: se uma alternativa cobre, não pague o custo do WebGL context.

## 2. Install

```bash
bun add three @react-three/fiber @react-three/drei
bun add -d @types/three
```

## 3. Canvas básico

```tsx
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";

export function HeroScene() {
  return (
    <Canvas
      camera={{ position: [3, 3, 3], fov: 50 }}
      gl={{ antialias: true, alpha: true }}
      className="h-[480px] w-full"
    >
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 5, 5]} intensity={1} />
      <mesh>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial color="hotpink" />
      </mesh>
      <OrbitControls />
    </Canvas>
  );
}
```

Critical:

- `<Canvas>` cria a scene, renderer, camera default. NUNCA `new THREE.Scene()`.
- Componentes em PascalCase JSX (`<mesh>`, `<boxGeometry>`) mapeiam direto para Three.js classes. R3F reconcilia.
- Cleanup: ao unmount do Canvas, R3F dispõe geometry/material/renderer. Sem leak.

## 4. Animation loop — `useFrame`

```tsx
import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";

function SpinningBox() {
  const ref = useRef<THREE.Mesh>(null!);

  useFrame((state, delta) => {
    ref.current.rotation.x += delta;
    ref.current.rotation.y += delta * 0.5;
  });

  return (
    <mesh ref={ref}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="orange" />
    </mesh>
  );
}
```

`useFrame` roda ANTES de cada frame, recebe `(state, delta)`. `delta` é segundos desde last frame — multiplique por velocidade para movimento frame-rate independente.

- **NUNCA** `requestAnimationFrame` solto dentro de R3F — quebra o cleanup.
- **NUNCA** `useEffect + setInterval` pra animar.

## 5. drei helpers — essenciais

```tsx
import {
  OrbitControls,
  Stars,
  Float,
  Environment,
  useGLTF,
  Stats,           // FPS overlay (dev only)
  PerspectiveCamera,
  ContactShadows,
  Sparkles,
  Text,
} from "@react-three/drei";
```

- `OrbitControls` — orbita camera com mouse/touch. Default para preview.
- `Stars` / `Sparkles` — partículas decorativas, zero código.
- `Float` — flutuação suave no Y. `<Float speed={2} rotationIntensity={1}><Mesh/></Float>`.
- `Environment` — HDRI lighting (`preset="sunset" | "city" | "night"`).
- `useGLTF` — carrega .glb/.gltf com Suspense. `const { scene } = useGLTF("/model.glb")`.
- `Stats` — FPS overlay (só em dev).
- `Text` — texto 3D sem precisar de TextGeometry.

## 6. Loading GLTF model

```tsx
import { useGLTF } from "@react-three/drei";
import { Suspense } from "react";

function Robot() {
  const { scene } = useGLTF("/models/robot.glb");
  return <primitive object={scene} scale={2} />;
}

export function ModelScene() {
  return (
    <Canvas>
      <Suspense fallback={null}>
        <Robot />
        <Environment preset="city" />
      </Suspense>
    </Canvas>
  );
}

// Preload para não bloquear render
useGLTF.preload("/models/robot.glb");
```

## 7. Particles via BufferGeometry

```tsx
import * as THREE from "three";
import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";

function ParticleField({ count = 5000 }) {
  const ref = useRef<THREE.Points>(null!);

  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 10;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 10;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 10;
    }
    return arr;
  }, [count]);

  useFrame((_, delta) => {
    ref.current.rotation.y += delta * 0.05;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial size={0.02} color="white" sizeAttenuation />
    </points>
  );
}
```

Crítico: `positions` em `useMemo` (evita rebuild). `ref.current` direto no `useFrame` — não passe por state (re-render storm).

## 8. Shader material customizado

Para shader simples (color/UV manipulation), use `shaderMaterial` do drei:

```tsx
import { shaderMaterial } from "@react-three/drei";
import { extend, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useRef } from "react";

const GradientMaterial = shaderMaterial(
  { uTime: 0, uColorA: new THREE.Color("#ff0080"), uColorB: new THREE.Color("#7928ca") },
  // vertex
  /* glsl */ `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  // fragment
  /* glsl */ `
    uniform float uTime;
    uniform vec3 uColorA;
    uniform vec3 uColorB;
    varying vec2 vUv;
    void main() {
      vec3 color = mix(uColorA, uColorB, vUv.y + sin(uTime) * 0.5);
      gl_FragColor = vec4(color, 1.0);
    }
  `
);

extend({ GradientMaterial });

function GradientPlane() {
  const ref = useRef<THREE.ShaderMaterial>(null!);
  useFrame((_, delta) => {
    ref.current.uniforms.uTime.value += delta;
  });
  return (
    <mesh>
      <planeGeometry args={[3, 3]} />
      {/* @ts-expect-error - extend types */}
      <gradientMaterial ref={ref} />
    </mesh>
  );
}
```

Para shaders complexos: importe biblioteca Lygia (`bun add lygia`) para snippets reutilizáveis (noise, fbm, hash, etc.).

## 9. Cleanup manual (raro)

R3F já dispõe geometry/material no unmount. Se você adicionou listener manual ou subscribed em store externo, precisa cleanup:

```tsx
function ScrollyMesh() {
  const ref = useRef<THREE.Mesh>(null!);

  useEffect(() => {
    const onScroll = () => {
      if (ref.current) ref.current.position.y = window.scrollY * 0.01;
    };
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return <mesh ref={ref}>...</mesh>;
}
```

## 10. Performance budget

- **≤ 100k triangles** em scene web — acima disso reduza geometry ou use LOD.
- **≤ 50 lights** — cada light multiplica draw calls.
- **`<Suspense>` + GLTF preload** — não bloqueie initial paint.
- **`<Stats />` em dev** — FPS deve ficar 60 estável (≥ 30 mínimo em mobile mid-range).
- **DPR clamp**: `<Canvas dpr={[1, 2]}>` para limitar pixel ratio em mobile retina.

## Don'ts

- **NUNCA** `new THREE.Scene()` em código React — use `<Canvas>` declarativo.
- **NUNCA** `requestAnimationFrame` em scene R3F — use `useFrame`.
- **NUNCA** mutar state em `useFrame` (`setState` em loop = re-render storm). Mutate ref direto.
- **NUNCA** ignore `dispose()` em listeners customizados — leaks de memória acumulam.
- **NUNCA** carregar GLTF sem `<Suspense>` + sem preload.
- **NUNCA** use Three.js pra animação 2D normal — Motion ou CSS resolvem mais barato.
- **NUNCA** card com brilho/glow precisa de WebGL — use Magic UI.
- **NUNCA** misturar imperative `mesh.add(child)` com declarativo `<mesh><Mesh/></mesh>` — escolha uma direção.
