"use client";

import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Text, Line, Sphere, Box, Cylinder } from "@react-three/drei";
import * as THREE from "three";

// Type definitions matching our strict Gemini prompt
type NodeType = {
  id: string;
  type: "box" | "sphere" | "cylinder";
  position: [number, number, number];
  color: string;
  label: string;
  scale: [number, number, number];
};

type EdgeType = {
  source: string;
  target: string;
  color: string;
};

type ThreeConfig = {
  nodes?: NodeType[];
  edges?: EdgeType[];
};

function Scene({ data }: { data: ThreeConfig }) {
  const groupRef = useRef<THREE.Group>(null);

  // Auto-rotate slowly
  useFrame(({ clock }) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = clock.getElapsedTime() * 0.1;
    }
  });

  // Create a fast lookup for node positions to draw edges
  const nodeDict = useMemo(() => {
    const dict: Record<string, [number, number, number]> = {};
    if (data.nodes) {
      data.nodes.forEach(n => {
        dict[n.id] = n.position;
      });
    }
    return dict;
  }, [data.nodes]);

  return (
    <group ref={groupRef}>
      {/* Lights */}
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} intensity={1} />
      <directionalLight position={[-10, 5, 5]} intensity={0.5} />

      {/* Render Edges */}
      {data.edges?.map((edge, i) => {
        const start = nodeDict[edge.source];
        const end = nodeDict[edge.target];
        if (!start || !end) return null;
        return (
          <Line
            key={`edge-${i}`}
            points={[start, end]}
            color={edge.color || "#ffffff"}
            lineWidth={2}
          />
        );
      })}

      {/* Render Nodes */}
      {data.nodes?.map((node) => {
        return (
          <group key={node.id} position={node.position}>
            {node.type === "sphere" && (
              <Sphere args={[0.5, 32, 32]} scale={node.scale || [1, 1, 1]}>
                <meshStandardMaterial color={node.color} />
              </Sphere>
            )}
            {node.type === "box" && (
              <Box args={[1, 1, 1]} scale={node.scale || [1, 1, 1]}>
                <meshStandardMaterial color={node.color} />
              </Box>
            )}
            {node.type === "cylinder" && (
              <Cylinder args={[0.5, 0.5, 1, 32]} scale={node.scale || [1, 1, 1]}>
                 <meshStandardMaterial color={node.color} />
              </Cylinder>
            )}
            
            {/* Fallback to Box if unknown type */}
            {!["sphere", "box", "cylinder"].includes(node.type) && (
              <Box args={[1, 1, 1]} scale={node.scale || [1, 1, 1]}>
                <meshStandardMaterial color={node.color} />
              </Box>
            )}

            {node.label && (
              <Text
                position={[0, -0.8, 0]}
                fontSize={0.3}
                color="#ffffff"
                anchorX="center"
                anchorY="middle"
              >
                {node.label}
              </Text>
            )}
          </group>
        );
      })}
    </group>
  );
}

export default function ThreeScene({ configStr }: { configStr: string }) {
  const parsedData = useMemo(() => {
    try {
      return JSON.parse(configStr) as ThreeConfig;
    } catch (e) {
      console.error("Failed to parse Three.js config", e);
      return { nodes: [], edges: [] };
    }
  }, [configStr]);

  if (!parsedData.nodes || parsedData.nodes.length === 0) {
     return (
       <div className="w-full h-full flex flex-col items-center justify-center text-neutral-500">
          <p>No 3D Architecture generated for this concept.</p>
       </div>
     );
  }

  return (
    <Canvas camera={{ position: [0, 2, 8], fov: 50 }}>
      <color attach="background" args={['#000000']} />
      <Scene data={parsedData} />
      <OrbitControls makeDefault enableDamping dampingFactor={0.05} />
    </Canvas>
  );
}
