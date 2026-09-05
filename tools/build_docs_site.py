"""Generate modern, interactive GitHub Pages site in docs/index.html."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# Load documentation markdown
manual_md = (DOCS / "USER_MANUAL.md").read_text(encoding="utf-8")
philosophy_md = (DOCS / "PHILOSOPHY.md").read_text(encoding="utf-8")
citations_md = (DOCS / "CITATIONS.md").read_text(encoding="utf-8")

manual_json = json.dumps(manual_md)
philosophy_json = json.dumps(philosophy_md)
citations_json = json.dumps(citations_md)

html_template = """<!DOCTYPE html>
<html lang="en" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MoDe 3D Studio — Metric Monocular Depth & Splat Relighter for Blender</title>
    <meta name="description" content="Turn single photographs into metric 3D point-splats, accurate camera projection, and real-time relighting in Blender 4.2+ & 5.x. Zero polygon tearing. Powered by Microsoft MoGe-3.">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🧊</text></svg>">

    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        blender: {
                            DEFAULT: '#E87D0D',
                            hover: '#FA8D1E',
                            light: '#FFB067',
                            dark: '#A35300'
                        },
                        brand: {
                            cyan: '#00F0FF',
                            purple: '#8B5CF6',
                            green: '#10B981',
                            surface: '#0F172A',
                            card: '#1E293B',
                            border: '#334155'
                        }
                    },
                    fontFamily: {
                        sans: ['Inter', 'system-ui', 'sans-serif'],
                        mono: ['JetBrains Mono', 'monospace']
                    }
                }
            }
        }
    </script>

    <!-- Marked.js & Highlight.js for interactive docs -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>

    <style>
        body {
            background-color: #090D16;
            color: #E2E8F0;
        }
        .bg-grid {
            background-size: 40px 40px;
            background-image: 
                linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
        }
        .prose pre {
            background-color: #0b1120 !important;
            border: 1px solid #1e293b;
            border-radius: 0.75rem;
            padding: 1rem;
            overflow-x: auto;
        }
        .prose code {
            color: #38bdf8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9em;
        }
        .prose table {
            width: 100%;
            border-collapse: collapse;
            margin: 1.5rem 0;
            display: block;
            overflow-x: auto;
        }
        .prose th, .prose td {
            border: 1px solid #334155;
            padding: 0.75rem 1rem;
            text-align: left;
        }
        .prose th {
            background-color: #1e293b;
            color: #f1f5f9;
        }
        .prose h1, .prose h2, .prose h3 {
            color: #f8fafc;
            font-weight: 700;
            margin-top: 2rem;
            margin-bottom: 0.75rem;
        }
        .prose h1 { font-size: 1.85rem; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; }
        .prose h2 { font-size: 1.45rem; color: #E87D0D; }
        .prose h3 { font-size: 1.2rem; color: #38bdf8; }
        .prose p { margin: 0.85rem 0; line-height: 1.7; color: #cbd5e1; }
        .prose ul, .prose ol { padding-left: 1.5rem; margin: 0.85rem 0; color: #cbd5e1; }
        .prose li { margin: 0.35rem 0; }
        .prose blockquote {
            border-left: 4px solid #E87D0D;
            background: rgba(30, 41, 59, 0.4);
            padding: 0.75rem 1.25rem;
            border-radius: 0 0.5rem 0.5rem 0;
            font-style: italic;
            color: #94a3b8;
        }
    </style>
</head>
<body class="font-sans antialiased selection:bg-blender selection:text-white">

    <!-- Ambient glow background -->
    <div class="fixed top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-96 bg-gradient-to-b from-blender/10 via-brand-purple/5 to-transparent blur-3xl pointer-events-none -z-10"></div>

    <!-- Navigation Bar -->
    <nav class="sticky top-0 z-50 backdrop-blur-xl bg-slate-950/80 border-b border-slate-800/80">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <a href="#" class="flex items-center gap-3 group">
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-blender to-blender-dark flex items-center justify-center shadow-lg shadow-blender/20 group-hover:scale-105 transition">
                        <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                            <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                            <line x1="12" y1="22.08" x2="12" y2="12"></line>
                        </svg>
                    </div>
                    <div>
                        <span class="font-bold text-lg text-white tracking-tight">MoDe <span class="text-blender">3D</span> Studio</span>
                        <span class="hidden sm:inline-block ml-2 px-2 py-0.5 text-xs font-mono font-medium rounded-full bg-slate-800 text-blender border border-blender/30">v2.2.0</span>
                    </div>
                </a>
            </div>

            <!-- Desktop Nav Links -->
            <div class="hidden md:flex items-center gap-7 text-sm font-medium text-slate-300">
                <a href="#features" class="hover:text-white transition">Features</a>
                <a href="#interactive-sandbox" class="hover:text-brand-cyan transition flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full bg-brand-cyan animate-pulse"></span>
                    Live Sandbox
                </a>
                <a href="#presets" class="hover:text-white transition">Presets</a>
                <a href="#quickstart" class="hover:text-white transition">Quickstart</a>
                <a href="#docs" class="hover:text-white transition">User Manual</a>
                <a href="#philosophy" class="hover:text-white transition">Philosophy</a>
            </div>

            <!-- CTA Buttons -->
            <div class="flex items-center gap-3">
                <a href="https://github.com/RhaggyRhelp/mode-3d" target="_blank" rel="noreferrer" class="p-2 text-slate-400 hover:text-white hover:bg-slate-800/80 rounded-lg transition" title="GitHub Repository">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                        <path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
                    </svg>
                </a>
                <a href="#quickstart" class="hidden sm:inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg bg-gradient-to-r from-blender to-blender-hover text-white shadow-lg shadow-blender/25 hover:brightness-110 active:scale-95 transition">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                    Download Addon
                </a>
            </div>
        </div>
    </nav>

    <!-- Hero Section -->
    <header class="relative pt-12 pb-20 md:pt-20 md:pb-28 overflow-hidden bg-grid">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
            <!-- Badge -->
            <div class="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-800/80 border border-slate-700/80 text-xs font-medium text-slate-300 mb-8 backdrop-blur-sm">
                <span class="flex h-2 w-2 rounded-full bg-emerald-400"></span>
                <span>Blender 4.2 LTS & 5.2 Compatible</span>
                <span class="text-slate-600">|</span>
                <span class="text-blender">Warm MoGe-3 GPU Engine</span>
            </div>

            <!-- Headline -->
            <h1 class="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-extrabold text-white tracking-tight max-w-5xl mx-auto leading-[1.12]">
                Single Photo In. <br class="hidden sm:inline">
                <span class="bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">Metric 3D Splats Out.</span> <br>
                <span class="bg-gradient-to-r from-blender via-amber-400 to-brand-cyan bg-clip-text text-transparent">Real-Time Relighting</span> in Blender.
            </h1>

            <p class="mt-6 text-lg sm:text-xl text-slate-400 max-w-3xl mx-auto font-normal leading-relaxed">
                Connect Blender to a high-speed GPU daemon powered by <strong>Microsoft MoGe-3</strong>.
                Turn any 2D photograph into millimeter-accurate camera projections, adaptive Gaussian surfels, and a dynamic 2.5D normal-gizmo relighter in <strong class="text-white">~1.5 seconds</strong>.
            </p>

            <!-- Call to Actions -->
            <div class="mt-10 flex flex-wrap items-center justify-center gap-4">
                <a href="https://github.com/RhaggyRhelp/mode-3d/releases" target="_blank" rel="noreferrer" class="inline-flex items-center gap-2.5 px-6 py-3.5 rounded-xl bg-blender hover:bg-blender-hover text-white font-semibold text-base shadow-xl shadow-blender/30 hover:scale-[1.02] active:scale-95 transition">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                    Download Extension v2.2.0 (.zip)
                </a>
                <a href="#quickstart" class="inline-flex items-center gap-2.5 px-6 py-3.5 rounded-xl bg-slate-800/90 hover:bg-slate-750 border border-slate-700 hover:border-slate-600 text-slate-200 font-semibold text-base hover:scale-[1.02] active:scale-95 transition">
                    <svg class="w-5 h-5 text-brand-cyan" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                    One-Click Quickstart
                </a>
                <a href="https://github.com/RhaggyRhelp/mode-3d" target="_blank" rel="noreferrer" class="inline-flex items-center gap-2 px-5 py-3.5 rounded-xl bg-transparent hover:bg-slate-800/60 border border-transparent hover:border-slate-700 text-slate-400 hover:text-white text-base font-medium transition">
                    ⭐ View on GitHub
                </a>
            </div>

            <!-- Quick Stats Bar -->
            <div class="mt-14 max-w-4xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md">
                <div class="p-3">
                    <div class="text-2xl sm:text-3xl font-bold text-white">~1.2s</div>
                    <div class="text-xs text-slate-400 mt-1 uppercase tracking-wider font-mono">Inference Speed</div>
                </div>
                <div class="p-3 border-l border-slate-800">
                    <div class="text-2xl sm:text-3xl font-bold text-blender">Zero</div>
                    <div class="text-xs text-slate-400 mt-1 uppercase tracking-wider font-mono">Mesh Tearing</div>
                </div>
                <div class="p-3 border-l border-slate-800">
                    <div class="text-2xl sm:text-3xl font-bold text-brand-cyan">100%</div>
                    <div class="text-xs text-slate-400 mt-1 uppercase tracking-wider font-mono">Metric Scale</div>
                </div>
                <div class="p-3 border-l border-slate-800">
                    <div class="text-2xl sm:text-3xl font-bold text-emerald-400">5.2 & 4.2</div>
                    <div class="text-xs text-slate-400 mt-1 uppercase tracking-wider font-mono">Blender Native</div>
                </div>
            </div>
        </div>
    </header>

    <!-- Interactive 2.5D Relight & Splat Sandbox -->
    <section id="interactive-sandbox" class="py-16 bg-slate-950 border-y border-slate-800/80 relative">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="text-center max-w-3xl mx-auto mb-10">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-cyan/10 border border-brand-cyan/30 text-xs font-mono text-brand-cyan uppercase tracking-wider mb-3">
                    Interactive Demonstration
                </div>
                <h2 class="text-3xl sm:text-4xl font-bold text-white tracking-tight">Experience Live 2.5D Normal Relighting</h2>
                <p class="mt-3 text-slate-400 text-sm sm:text-base">
                    Move your mouse or finger across the canvas below. In Blender, MoDe 3D generates this exact Compositor node setup automatically, giving you an interactive 3D normal gizmo to relight any 2D photo in real time.
                </p>
            </div>

            <!-- Sandbox Widget -->
            <div class="rounded-2xl bg-slate-900 border border-slate-800 overflow-hidden shadow-2xl">
                <!-- Sandbox Toolbar -->
                <div class="bg-slate-900/90 border-b border-slate-800 px-4 py-3 flex flex-wrap items-center justify-between gap-3">
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-mono text-slate-400 uppercase">View Mode:</span>
                        <div class="inline-flex rounded-lg bg-slate-950 p-1 border border-slate-800 text-xs font-medium" id="sandbox-modes">
                            <button onclick="setSandboxMode('relight')" class="mode-btn px-3 py-1 rounded-md bg-blender text-white font-semibold transition" data-mode="relight">2.5D Relit</button>
                            <button onclick="setSandboxMode('normals')" class="mode-btn px-3 py-1 rounded-md text-slate-400 hover:text-white transition" data-mode="normals">Surface Normals</button>
                            <button onclick="setSandboxMode('splats')" class="mode-btn px-3 py-1 rounded-md text-slate-400 hover:text-white transition" data-mode="splats">Point Splats</button>
                            <button onclick="setSandboxMode('depth')" class="mode-btn px-3 py-1 rounded-md text-slate-400 hover:text-white transition" data-mode="depth">Metric Depth</button>
                        </div>
                    </div>

                    <div class="flex items-center gap-4 text-xs font-mono text-slate-400">
                        <span id="light-pos-indicator">Light: (X: 0.0, Y: 0.0, Z: 1.0)</span>
                        <span class="hidden sm:inline text-slate-600">|</span>
                        <span class="hidden sm:inline text-emerald-400">● 60 FPS Real-time</span>
                    </div>
                </div>

                <!-- Canvas Container -->
                <div class="relative w-full h-80 sm:h-[420px] bg-slate-950 cursor-crosshair flex items-center justify-center overflow-hidden" id="canvas-container">
                    <canvas id="relightCanvas" class="w-full h-full block"></canvas>
                    <div class="absolute bottom-4 left-4 bg-slate-900/80 backdrop-blur-md border border-slate-800 px-3 py-1.5 rounded-lg text-xs font-mono text-slate-300 pointer-events-none">
                        💡 Hover & drag anywhere to steer the normal relighter
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Key Features Section -->
    <section id="features" class="py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center max-w-3xl mx-auto mb-16">
            <h2 class="text-xs font-mono uppercase tracking-widest text-blender font-semibold">Engineered For Visual Fidelity</h2>
            <p class="mt-2 text-3xl sm:text-4xl font-bold text-white tracking-tight">Why MoDe 3D Studio is Different</p>
            <p class="mt-4 text-slate-400 text-base">
                Traditional AI depth tools produce wobbly relative depth and ragged polygon curtains. MoDe 3D combines Microsoft MoGe-3 metric prediction with modern Blender procedural geometry.
            </p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <!-- Feature 1 -->
            <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-blender/40 transition group">
                <div class="w-12 h-12 rounded-xl bg-blender/10 border border-blender/20 flex items-center justify-center text-blender mb-5 group-hover:scale-110 transition">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
                </div>
                <h3 class="text-xl font-bold text-white mb-2">Metric Point Splats (Zero Faceting)</h3>
                <p class="text-slate-400 text-sm leading-relaxed">
                    Uses Geometry Nodes to instance adaptive point splats or oriented Gaussian surfels. Completely eliminates the jagged polygon curtains and mesh tearing typical of naive triangulated depth meshes.
                </p>
            </div>

            <!-- Feature 2 -->
            <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-brand-cyan/40 transition group">
                <div class="w-12 h-12 rounded-xl bg-brand-cyan/10 border border-brand-cyan/20 flex items-center justify-center text-brand-cyan mb-5 group-hover:scale-110 transition">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                </div>
                <h3 class="text-xl font-bold text-white mb-2">Decoupled Full-Resolution Color</h3>
                <p class="text-slate-400 text-sm leading-relaxed">
                    Runs the AI vision backbone at an optimal token resolution while sampling vertex colors directly from the native 4K+ camera photograph, keeping surface textures razor-sharp.
                </p>
            </div>

            <!-- Feature 3 -->
            <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-emerald-500/40 transition group">
                <div class="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-5 group-hover:scale-110 transition">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                </div>
                <h3 class="text-xl font-bold text-white mb-2">Instant Ground Grid Levelling</h3>
                <p class="text-slate-400 text-sm leading-relaxed">
                    Detects physical floor planes via signed-normal RANSAC estimation and aligns the room to Blender's ground grid (<code class="text-emerald-300">Z=0</code>) via a non-destructive parent transformation Empty.
                </p>
            </div>

            <!-- Feature 4 -->
            <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-amber-500/40 transition group">
                <div class="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-5 group-hover:scale-110 transition">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
                </div>
                <h3 class="text-xl font-bold text-white mb-2">2.5D Compositor Relighter</h3>
                <p class="text-slate-400 text-sm leading-relaxed">
                    Builds a real-time normal-pass relighting graph in Blender's Compositor. Adjust lighting angle, color, and intensity directly with an interactive 3D normal gizmo in the 3D viewport.
                </p>
            </div>

            <!-- Feature 5 -->
            <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-brand-purple/40 transition group">
                <div class="w-12 h-12 rounded-xl bg-brand-purple/10 border border-brand-purple/20 flex items-center justify-center text-brand-purple mb-5 group-hover:scale-110 transition">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                </div>
                <h3 class="text-xl font-bold text-white mb-2">Warm GPU Daemon Architecture</h3>
                <p class="text-slate-400 text-sm leading-relaxed">
                    Keeps MoGe-3 warm in VRAM on a local FastAPI server (<code class="text-brand-purple">:8766</code>). Eliminates cold Python startup overhead, giving you lightning-fast iterations.
                </p>
            </div>

            <!-- Feature 6 -->
            <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-rose-500/40 transition group">
                <div class="w-12 h-12 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 mb-5 group-hover:scale-110 transition">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </div>
                <h3 class="text-xl font-bold text-white mb-2">Zero-Accumulation Cache Purger</h3>
                <p class="text-slate-400 text-sm leading-relaxed">
                    Auto-cleans previous scans on new runs. Includes a 1-click Purge button inside Blender to scrub both temporary disk arrays and unreferenced Blender mesh/material datablocks.
                </p>
            </div>
        </div>
    </section>

    <!-- Presets & Hardware Matrix -->
    <section id="presets" class="py-20 bg-slate-950 border-y border-slate-800">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="text-center max-w-3xl mx-auto mb-16">
                <h2 class="text-xs font-mono uppercase tracking-widest text-blender font-semibold">Tuned For Any GPU</h2>
                <p class="mt-2 text-3xl sm:text-4xl font-bold text-white tracking-tight">Presets & Hardware Requirements</p>
                <p class="mt-4 text-slate-400">
                    From sub-second camera previews to dense 4,000,000 point hero scans, pick the preset tuned for your hardware.
                </p>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                <!-- Draft -->
                <div class="rounded-2xl bg-slate-900 border border-slate-800 p-6 flex flex-col justify-between hover:border-slate-700 transition">
                    <div>
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs font-mono font-bold uppercase text-slate-400">Preset</span>
                            <span class="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">~0.6s</span>
                        </div>
                        <h3 class="text-2xl font-extrabold text-white mb-1">Draft</h3>
                        <p class="text-xs text-blender font-medium mb-4">6GB – 8GB VRAM</p>
                        <ul class="text-xs text-slate-300 space-y-2 border-t border-slate-800 pt-4">
                            <li class="flex items-center gap-2">✓ MoGe-3 ViT-L</li>
                            <li class="flex items-center gap-2">✓ 1024px Resolution</li>
                            <li class="flex items-center gap-2">✓ 0 Refine Passes</li>
                            <li class="flex items-center gap-2 text-slate-400">Instant camera matching & preview</li>
                        </ul>
                    </div>
                </div>

                <!-- Balanced -->
                <div class="rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border-2 border-blender p-6 flex flex-col justify-between relative shadow-xl shadow-blender/10">
                    <div class="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-blender text-white text-[11px] font-bold uppercase tracking-wider">
                        Recommended
                    </div>
                    <div>
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs font-mono font-bold uppercase text-blender">Preset</span>
                            <span class="text-xs font-mono px-2 py-0.5 rounded bg-blender/20 text-blender font-bold">~1.8s</span>
                        </div>
                        <h3 class="text-2xl font-extrabold text-white mb-1">Balanced</h3>
                        <p class="text-xs text-blender font-medium mb-4">8GB – 12GB VRAM</p>
                        <ul class="text-xs text-slate-300 space-y-2 border-t border-slate-800 pt-4">
                            <li class="flex items-center gap-2">✓ MoGe-3 ViT-L</li>
                            <li class="flex items-center gap-2">✓ 1536px Resolution</li>
                            <li class="flex items-center gap-2">✓ 2 Refine Passes</li>
                            <li class="flex items-center gap-2 text-emerald-400 font-medium">Sweet spot of speed & detail</li>
                        </ul>
                    </div>
                </div>

                <!-- Quality -->
                <div class="rounded-2xl bg-slate-900 border border-slate-800 p-6 flex flex-col justify-between hover:border-slate-700 transition">
                    <div>
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs font-mono font-bold uppercase text-slate-400">Preset</span>
                            <span class="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">~3.2s</span>
                        </div>
                        <h3 class="text-2xl font-extrabold text-white mb-1">Quality</h3>
                        <p class="text-xs text-blender font-medium mb-4">12GB – 16GB VRAM</p>
                        <ul class="text-xs text-slate-300 space-y-2 border-t border-slate-800 pt-4">
                            <li class="flex items-center gap-2">✓ MoGe-3 ViT-L</li>
                            <li class="flex items-center gap-2">✓ 2448px Resolution</li>
                            <li class="flex items-center gap-2">✓ 3 Refine Passes</li>
                            <li class="flex items-center gap-2 text-slate-400">Sharper structural boundaries</li>
                        </ul>
                    </div>
                </div>

                <!-- Max Quality -->
                <div class="rounded-2xl bg-slate-900 border border-slate-800 p-6 flex flex-col justify-between hover:border-brand-purple/40 transition">
                    <div>
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs font-mono font-bold uppercase text-brand-purple">Preset</span>
                            <span class="text-xs font-mono px-2 py-0.5 rounded bg-brand-purple/20 text-brand-purple font-bold">~5.5s</span>
                        </div>
                        <h3 class="text-2xl font-extrabold text-white mb-1">Max Quality</h3>
                        <p class="text-xs text-brand-purple font-medium mb-4">16GB+ VRAM</p>
                        <ul class="text-xs text-slate-300 space-y-2 border-t border-slate-800 pt-4">
                            <li class="flex items-center gap-2">✓ Giant MoGe-3 ViT-G (5GB)</li>
                            <li class="flex items-center gap-2">✓ 4096px (4K) Backbone</li>
                            <li class="flex items-center gap-2">✓ 7 Passes + Flip x2 Anti-Jitter</li>
                            <li class="flex items-center gap-2 text-brand-purple font-medium">4 Million Point Budget</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Quickstart Section -->
    <section id="quickstart" class="py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center max-w-3xl mx-auto mb-16">
            <h2 class="text-xs font-mono uppercase tracking-widest text-blender font-semibold">Zero-Terminal Onboarding</h2>
            <p class="mt-2 text-3xl sm:text-4xl font-bold text-white tracking-tight">Get Started In 60 Seconds</p>
            <p class="mt-4 text-slate-400">
                No complex terminal commands or manual Python dependencies needed.
            </p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
            <!-- Step 1 -->
            <div class="relative p-6 rounded-2xl bg-slate-900/70 border border-slate-800">
                <div class="w-10 h-10 rounded-xl bg-blender text-white font-bold flex items-center justify-center mb-5 text-lg shadow-lg shadow-blender/20">
                    1
                </div>
                <h3 class="text-xl font-bold text-white mb-2">Run One-Click Setup</h3>
                <p class="text-slate-400 text-sm leading-relaxed mb-4">
                    Double-click <strong class="text-white">Start_MoDe_3D.bat</strong> (Windows) or run <strong class="text-white">./Start_MoDe_3D.sh</strong> (Linux/macOS).
                </p>
                <div class="bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs font-mono text-slate-300">
                    <code>Start_MoDe_3D.bat</code>
                </div>
                <p class="text-[11px] text-slate-400 mt-2">Auto-installs PyTorch CUDA, fetches MoGe-3, and stages the extension into Blender.</p>
            </div>

            <!-- Step 2 -->
            <div class="relative p-6 rounded-2xl bg-slate-900/70 border border-slate-800">
                <div class="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 text-white font-bold flex items-center justify-center mb-5 text-lg">
                    2
                </div>
                <h3 class="text-xl font-bold text-white mb-2">Enable in Blender</h3>
                <p class="text-slate-400 text-sm leading-relaxed mb-4">
                    Open Blender (4.2+ or 5.x) &rarr; <strong class="text-white">Edit &gt; Preferences &gt; Extensions</strong>.
                </p>
                <div class="bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs font-mono text-slate-300">
                    Enable &quot;MoDe 3D Studio&quot;
                </div>
                <p class="text-[11px] text-slate-400 mt-2">The extension is already staged! Or drag <code>dist/moge_splat_studio.zip</code> onto Blender.</p>
            </div>

            <!-- Step 3 -->
            <div class="relative p-6 rounded-2xl bg-slate-900/70 border border-slate-800">
                <div class="w-10 h-10 rounded-xl bg-emerald-500 text-white font-bold flex items-center justify-center mb-5 text-lg shadow-lg shadow-emerald-500/20">
                    3
                </div>
                <h3 class="text-xl font-bold text-white mb-2">Generate 3D Splats</h3>
                <p class="text-slate-400 text-sm leading-relaxed mb-4">
                    Press <strong class="text-white">N</strong> in the 3D Viewport to open the sidebar tab &rarr; pick your photo &rarr; click <strong class="text-white">Generate 3D Splats</strong>!
                </p>
                <div class="bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs font-mono text-emerald-400">
                    &rarr; Metric Camera, Splats &amp; Relight ready in ~1.5s
                </div>
            </div>
        </div>
    </section>

    <!-- Interactive Documentation Hub (Manual + Philosophy + Citations) -->
    <section id="docs" class="py-20 bg-slate-950 border-t border-slate-800">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex flex-wrap items-center justify-between gap-4 mb-8 border-b border-slate-800 pb-6">
                <div>
                    <h2 class="text-2xl sm:text-3xl font-bold text-white">Documentation &amp; Philosophy</h2>
                    <p class="text-slate-400 text-sm mt-1">Full offline reference, Ian Hubert flow state design, and academic citations.</p>
                </div>

                <!-- Tab Switchers -->
                <div class="flex items-center rounded-xl bg-slate-900 p-1 border border-slate-800 text-xs font-semibold">
                    <button onclick="switchDocTab('manual')" id="tab-manual" class="px-4 py-2 rounded-lg bg-blender text-white transition">User Manual</button>
                    <button onclick="switchDocTab('philosophy')" id="tab-philosophy" class="px-4 py-2 rounded-lg text-slate-400 hover:text-white transition">Philosophy</button>
                    <button onclick="switchDocTab('citations')" id="tab-citations" class="px-4 py-2 rounded-lg text-slate-400 hover:text-white transition">Citations</button>
                </div>
            </div>

            <!-- Docs Viewer Container -->
            <div class="rounded-2xl bg-slate-900/80 border border-slate-800 p-6 sm:p-10 shadow-2xl">
                <!-- Search bar for docs -->
                <div class="mb-8 flex items-center gap-3 bg-slate-950 px-4 py-2.5 rounded-xl border border-slate-800">
                    <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                    <input type="text" id="docSearch" placeholder="Search documentation (e.g., FOV, RANSAC, daemon, relighting)..." oninput="filterDocContent()" class="bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none w-full">
                </div>

                <!-- Prose Container -->
                <article id="docContent" class="prose max-w-none text-slate-300">
                    <!-- Rendered by Marked.js on page load -->
                </article>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer class="py-12 bg-slate-950 border-t border-slate-800/80 text-sm text-slate-400">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-6">
            <div class="flex items-center gap-3">
                <div class="w-7 h-7 rounded-lg bg-blender flex items-center justify-center text-white font-bold text-xs">
                    M
                </div>
                <span class="text-slate-300 font-semibold">MoDe 3D Studio</span>
                <span class="text-slate-600">|</span>
                <span class="text-xs">Licensed under <a href="https://github.com/RhaggyRhelp/mode-3d/blob/main/LICENSE" class="text-slate-300 underline">MIT</a></span>
            </div>

            <div class="flex items-center gap-6 text-xs font-medium">
                <a href="https://github.com/RhaggyRhelp/mode-3d" target="_blank" rel="noreferrer" class="hover:text-white transition">GitHub Repo</a>
                <a href="https://www.blender.org/" target="_blank" rel="noreferrer" class="hover:text-white transition">Blender.org</a>
                <a href="https://github.com/microsoft/MoGe" target="_blank" rel="noreferrer" class="hover:text-white transition">Microsoft MoGe</a>
                <a href="#quickstart" class="text-blender hover:underline">Download Latest</a>
            </div>
        </div>
    </footer>

    <!-- Interactive Canvas & Docs Script -->
    <script>
        // Embedded Docs Data
        const rawDocs = {
            manual: __MANUAL_JSON__,
            philosophy: __PHILOSOPHY_JSON__,
            citations: __CITATIONS_JSON__
        };

        let activeTab = 'manual';

        function renderActiveDoc() {
            const markdown = rawDocs[activeTab] || '';
            const htmlContent = marked.parse(markdown);
            const container = document.getElementById('docContent');
            container.innerHTML = htmlContent;
            hljs.highlightAll();
        }

        function switchDocTab(tab) {
            activeTab = tab;
            ['manual', 'philosophy', 'citations'].forEach(t => {
                const btn = document.getElementById('tab-' + t);
                if (t === tab) {
                    btn.className = 'px-4 py-2 rounded-lg bg-blender text-white transition';
                } else {
                    btn.className = 'px-4 py-2 rounded-lg text-slate-400 hover:text-white transition';
                }
            });
            renderActiveDoc();
        }

        function filterDocContent() {
            const query = document.getElementById('docSearch').value.toLowerCase().trim();
            if (!query) {
                renderActiveDoc();
                return;
            }
            const markdown = rawDocs[activeTab] || '';
            const lines = markdown.split('\\n');
            let filtered = [];
            let inMatch = false;
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                if (line.toLowerCase().includes(query) || (line.startsWith('#') && inMatch)) {
                    filtered.push(line);
                    inMatch = true;
                } else if (line.startsWith('#')) {
                    inMatch = false;
                } else if (inMatch) {
                    filtered.push(line);
                }
            }
            if (filtered.length === 0) {
                document.getElementById('docContent').innerHTML = '<p class="text-slate-400 italic">No matching sections found for "' + query + '". Try searching for camera, floor, normal, or preset.</p>';
            } else {
                document.getElementById('docContent').innerHTML = marked.parse(filtered.join('\\n'));
                hljs.highlightAll();
            }
        }

        // --- Interactive 2.5D Relight & Splat Canvas ---
        const canvas = document.getElementById('relightCanvas');
        const ctx = canvas.getContext('2d');
        let currentMode = 'relight';
        let lightX = 0.5, lightY = 0.35, lightZ = 0.6;

        function resizeCanvas() {
            const rect = canvas.getBoundingClientRect();
            canvas.width = rect.width;
            canvas.height = rect.height;
            drawSandbox();
        }

        function setSandboxMode(mode) {
            currentMode = mode;
            document.querySelectorAll('.mode-btn').forEach(btn => {
                if (btn.getAttribute('data-mode') === mode) {
                    btn.className = 'mode-btn px-3 py-1 rounded-md bg-blender text-white font-semibold transition';
                } else {
                    btn.className = 'mode-btn px-3 py-1 rounded-md text-slate-400 hover:text-white transition';
                }
            });
            drawSandbox();
        }

        function drawSandbox() {
            const w = canvas.width;
            const h = canvas.height;
            if (!w || !h) return;

            const imgData = ctx.createImageData(w, h);
            const data = imgData.data;

            const cx = w * 0.5;
            const cy = h * 0.5;
            const radius = Math.min(w, h) * 0.38;

            const lx = (lightX * 2 - 1);
            const ly = (lightY * 2 - 1);
            const lz = Math.max(0.2, lightZ);
            const lLen = Math.sqrt(lx*lx + ly*ly + lz*lz);
            const normLx = lx / lLen;
            const normLy = ly / lLen;
            const normLz = lz / lLen;

            // Render loop
            const step = (currentMode === 'splats') ? 6 : 2;

            ctx.fillStyle = '#070a12';
            ctx.fillRect(0, 0, w, h);

            if (currentMode === 'splats') {
                // Draw procedural splats
                for (let py = 10; py < h - 10; py += step) {
                    for (let px = 10; px < w - 10; px += step) {
                        const dx = (px - cx) / radius;
                        const dy = (py - cy) / radius;
                        const distSq = dx*dx + dy*dy;
                        if (distSq <= 1.0) {
                            const nz = Math.sqrt(1.0 - distSq);
                            const nx = dx;
                            const ny = dy;

                            // Depth proportional radius r = Z/f
                            const depth = 1.0 - nz * 0.5;
                            const dot = Math.max(0, nx*normLx + ny*normLy + nz*normLz);
                            const intensity = 0.2 + 0.8 * dot;

                            ctx.beginPath();
                            const splatR = (step * 0.65) * (1.2 / depth);
                            ctx.arc(px, py, Math.max(1.5, splatR), 0, Math.PI * 2);
                            
                            // Splat color with Blender orange accent
                            const r = Math.min(255, Math.floor(232 * intensity));
                            const g = Math.min(255, Math.floor(125 * intensity + 30));
                            const b = Math.min(255, Math.floor(20 * intensity + 60));
                            ctx.fillStyle = 'rgb(' + r + ',' + g + ',' + b + ')';
                            ctx.fill();
                        } else {
                            // Background grid splats
                            if ((px % (step * 2) === 0) && (py % (step * 2) === 0)) {
                                ctx.beginPath();
                                ctx.arc(px, py, 1.2, 0, Math.PI * 2);
                                ctx.fillStyle = 'rgba(51, 65, 85, 0.4)';
                                ctx.fill();
                            }
                        }
                    }
                }
            } else {
                // Pixel shader emulation
                for (let y = 0; y < h; y += step) {
                    for (let x = 0; x < w; x += step) {
                        const dx = (x - cx) / radius;
                        const dy = (y - cy) / radius;
                        const distSq = dx*dx + dy*dy;

                        let r = 15, g = 23, b = 42;

                        if (distSq <= 1.0) {
                            const nz = Math.sqrt(1.0 - distSq);
                            const nx = dx;
                            const ny = dy;

                            if (currentMode === 'normals') {
                                // Standard normal map RGB
                                r = Math.floor(((nx + 1.0) * 0.5) * 255);
                                g = Math.floor(((ny + 1.0) * 0.5) * 255);
                                b = Math.floor(((nz + 1.0) * 0.5) * 255);
                            } else if (currentMode === 'depth') {
                                // Metric Depth colormap
                                const depthVal = nz;
                                r = Math.floor((1.0 - depthVal) * 60 + depthVal * 0);
                                g = Math.floor(depthVal * 200 + 40);
                                b = Math.floor(depthVal * 255);
                            } else {
                                // 2.5D Relighted Lambert + Specular
                                const dot = Math.max(0, nx*normLx + ny*normLy + nz*normLz);
                                const spec = Math.pow(dot, 16) * 0.6;
                                const diff = 0.15 + 0.85 * dot;
                                r = Math.min(255, Math.floor(240 * diff + spec * 255));
                                g = Math.min(255, Math.floor(160 * diff + spec * 255));
                                b = Math.min(255, Math.floor(80 * diff + spec * 255));
                            }
                        }

                        // Fill block
                        for (let by = 0; by < step && (y + by) < h; by++) {
                            for (let bx = 0; bx < step && (x + bx) < w; bx++) {
                                const idx = ((y + by) * w + (x + bx)) * 4;
                                data[idx] = r;
                                data[idx + 1] = g;
                                data[idx + 2] = b;
                                data[idx + 3] = 255;
                            }
                        }
                    }
                }
                ctx.putImageData(imgData, 0, 0);
            }

            // Draw Light Indicator Gizmo
            const lxPx = lightX * w;
            const lyPx = lightY * h;
            ctx.beginPath();
            ctx.arc(lxPx, lyPx, 8, 0, Math.PI * 2);
            ctx.fillStyle = '#00F0FF';
            ctx.fill();
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#FFFFFF';
            ctx.stroke();

            // Light ray line
            ctx.beginPath();
            ctx.moveTo(lxPx, lyPx);
            ctx.lineTo(cx, cy);
            ctx.strokeStyle = 'rgba(0, 240, 255, 0.25)';
            ctx.setLineDash([4, 4]);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // Canvas events
        canvas.addEventListener('mousemove', (e) => {
            const rect = canvas.getBoundingClientRect();
            lightX = (e.clientX - rect.left) / rect.width;
            lightY = (e.clientY - rect.top) / rect.height;
            document.getElementById('light-pos-indicator').innerText = 
                'Light: (X: ' + (lightX*2 - 1).toFixed(2) + ', Y: ' + (-(lightY*2 - 1)).toFixed(2) + ', Z: ' + lightZ.toFixed(2) + ')';
            drawSandbox();
        });

        canvas.addEventListener('touchmove', (e) => {
            if (e.touches.length > 0) {
                const rect = canvas.getBoundingClientRect();
                lightX = (e.touches[0].clientX - rect.left) / rect.width;
                lightY = (e.touches[0].clientY - rect.top) / rect.height;
                drawSandbox();
                e.preventDefault();
            }
        }, { passive: false });

        window.addEventListener('resize', resizeCanvas);

        // Initial setup
        window.addEventListener('DOMContentLoaded', () => {
            renderActiveDoc();
            resizeCanvas();
        });
    </script>
</body>
</html>"""

final_html = (
    html_template
    .replace("__MANUAL_JSON__", manual_json)
    .replace("__PHILOSOPHY_JSON__", philosophy_json)
    .replace("__CITATIONS_JSON__", citations_json)
)

out_file = DOCS / "index.html"
out_file.write_text(final_html, encoding="utf-8")
print(f"[OK] Generated docs site: {out_file} ({len(final_html)} bytes)")
