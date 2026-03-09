"use client";

import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Sphere, Icosahedron, MeshDistortMaterial, Line } from "@react-three/drei";
import * as THREE from "three";
import { motion } from "framer-motion";

// Emil Kowalski easing curves
const easeOutQuint = [0.23, 1, 0.32, 1] as const;

function DataCore() {
  const coreRef = useRef<THREE.Group>(null);
  const outerRingRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    if (coreRef.current) {
        coreRef.current.rotation.y = t * 0.5;
        coreRef.current.rotation.x = t * 0.2;
    }
    if (outerRingRef.current) {
        outerRingRef.current.rotation.z = -t * 0.3;
        outerRingRef.current.rotation.x = t * 0.1;
    }
  });

  return (
    <group>
      <Float speed={2} rotationIntensity={0.5} floatIntensity={1}>
        {/* Central Hub */}
        <group ref={coreRef}>
            <Icosahedron args={[0.8, 0]} position={[0, 0, 0]}>
            <meshStandardMaterial 
                color="#0ea5e9"
                wireframe={false}
                roughness={0.2}
                metalness={0.8}
            />
            </Icosahedron>
            {/* Inner pulsing core */}
            <Sphere args={[0.5, 32, 32]}>
              <MeshDistortMaterial
                  color="#38bdf8"
                  speed={3}
                  distort={0.4}
                  transparent
                  opacity={0.8}
              />
            </Sphere>
        </group>
        
        {/* Orbiting Data Nodes */}
        <group ref={outerRingRef}>
           {[0, 1, 2].map((i) => {
               const angle = (i / 3) * Math.PI * 2;
               const radius = 1.6;
               const x = Math.cos(angle) * radius;
               const z = Math.sin(angle) * radius;
               
               return (
                   <group key={i}>
                       <Line 
                          points={[[0, 0, 0], [x, 0, z]]} 
                          color="#38bdf8" 
                          opacity={0.3} 
                          transparent 
                          lineWidth={1}
                       />
                       <Sphere args={[0.15, 16, 16]} position={[x, 0, z]}>
                           <meshStandardMaterial color="#f0f9ff" emissive="#0ea5e9" emissiveIntensity={0.5} />
                       </Sphere>
                   </group>
               );
           })}
        </group>
      </Float>
    </group>
  );
}

export default function LoadingOverlay({ 
    activeStep
}: { 
    activeStep: string
}) {
  const steps = [
    { label: "Fetching paper metadata from ArXiv...", id: "fetch" },
    { label: "Summarizing & parsing core concepts with AI...", id: "ai" },
    { label: "Generating Python Manim script and 3D schema...", id: "script" },
    { label: "Rendering 2D Manim MP4 (This process takes ~1 minute)...", id: "render" }
  ];

  const currentIndex = steps.findIndex(s => activeStep === s.label) || 0;
  const activeIndex = currentIndex === -1 ? 0 : currentIndex;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/80 backdrop-blur-sm"
    >
      <motion.div
        initial={{ scale: 0.95, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.95, y: 20 }}
        transition={{ duration: 0.4, ease: easeOutQuint }}
        className="w-full max-w-md bg-white rounded-3xl overflow-hidden shadow-2xl flex flex-col items-center relative"
      >
        {/* 3D Canvas Container */}
        <div className="w-full h-56 bg-gradient-to-b from-slate-900 to-slate-800 relative">
            <Canvas camera={{ position: [0, 2, 5], fov: 45 }}>
                <ambientLight intensity={0.5} />
                <directionalLight position={[10, 10, 5]} intensity={1} color="#38bdf8" />
                <directionalLight position={[-10, -10, -5]} intensity={0.5} color="#0284c7" />
                <DataCore />
            </Canvas>
        </div>

        {/* Content Area */}
        <div className="px-8 pb-10 pt-2 w-full flex flex-col items-center text-center">
            <h2 className="text-2xl font-bold text-neutral-900 mb-2">Analyzing your paper...</h2>
            <p className="text-neutral-500 text-sm mb-8">This may take up to a minute</p>

            <div className="w-full flex flex-col space-y-3">
                {steps.map((step, idx) => {
                    const isPast = idx < activeIndex;
                    const isCurrent = idx === activeIndex && activeStep === step.label;
                    
                    return (
                        <motion.div 
                            key={step.id}
                            className={`flex items-center space-x-4 p-3 rounded-xl transition-all duration-300 ${isCurrent ? 'bg-teal-50 border border-teal-200 shadow-sm' : isPast ? 'bg-neutral-50 border border-transparent' : 'bg-transparent border border-transparent opacity-40'}`}
                            layout
                        >
                            <div className="shrink-0 flex items-center justify-center w-6 h-6 rounded-full">
                                {isPast ? (
                                    <svg className="w-5 h-5 text-teal-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                    </svg>
                                ) : isCurrent ? (
                                    <div className="w-5 h-5 rounded-full border-2 border-teal-500 flex items-center justify-center">
                                        <div className="w-2 h-2 rounded-full bg-teal-500 animate-pulse" />
                                    </div>
                                ) : (
                                    <div className="w-5 h-5 rounded-full bg-neutral-200" />
                                )}
                            </div>
                            <span className={`text-sm font-medium text-left ${isCurrent ? 'text-teal-700' : isPast ? 'text-neutral-600' : 'text-neutral-400'}`}>
                                {step.label}
                            </span>
                        </motion.div>
                    );
                })}
            </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
