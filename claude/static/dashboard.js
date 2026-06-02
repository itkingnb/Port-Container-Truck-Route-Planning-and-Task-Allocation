// Port Container Truck Dispatch System - Canvas Dashboard

const canvas = document.getElementById('port-canvas');
const ctx = canvas.getContext('2d');
const STATUS_CN = {
    IDLE: '空闲',
    PICKING: '前往取箱',
    LOADING: '装箱中',
    MOVING: '运输中',
    UNLOADING: '卸箱中',
    DELIVERING: '配送中',
    BUSY: '执行任务'
};
// Viewport
let viewX = -30, viewY = -10;
let scale = 1.8;
let dragging = false, dragStartX, dragStartY, dragViewX, dragViewY;

// State
let simState = null;
let autoRunning = false;
let mlEnabled = true;
let congestionEnabled = true;
let pollInterval = null;

// Colors
const COLORS = {
    sea: '#1a5276',
    quay: '#5d6d7e',
    yard: '#b9770e',
    road: '#566573',
    roadLine: '#839192',
    node: '#888',
    nodeMain: '#e74c3c',
    bg: '#0a0a1a',
    taskPending: '#3498db',
    heatHot: 'rgba(231,76,60,0.5)',
    heatWarm: 'rgba(243,156,18,0.3)',
};

// -----------------------------
// Canvas rendering
// -----------------------------
function resizeCanvas() {
    const container = document.getElementById('main-canvas');
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
}
window.addEventListener('resize', resizeCanvas);

function worldToScreen(wx, wy) {
    return [
        (wx - viewX) * scale + canvas.width / 2,
        (wy - viewY) * scale + canvas.height / 2
    ];
}

function drawPort() {
    if (!simState) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const { port_nodes, port_edges, heatmap } = simState;

    // Background - sea
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Sea area
    const [sx1, sy1] = worldToScreen(-30, -5);
    const [sx2, sy2] = worldToScreen(300, 9);
    ctx.fillStyle = COLORS.sea;
    ctx.fillRect(sx1, sy1, sx2 - sx1, sy2 - sy1);

    // Quay zones (approximate from nodes)
    for (const [name, pos] of Object.entries(port_nodes)) {
        if (name.startsWith('Q')) {
            const [qx, qy] = worldToScreen(pos[0], pos[1]);
            ctx.fillStyle = COLORS.quay;
            ctx.fillRect(qx - 14, qy - 6, 28, 12);
            ctx.fillStyle = '#fff';
            ctx.font = '9px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(name, qx, qy + 4);
        }
    }

    // Congestion heatmap
    if (heatmap && heatmap.length > 0) {
        for (const h of heatmap) {
            const [hx, hy] = worldToScreen(h.x, h.y);
            const size = 10 * scale;
            const alpha = Math.min(h.value * 0.35, 0.45);
            ctx.fillStyle = `rgba(255,60,30,${alpha})`;
            ctx.fillRect(hx, hy, size, size);
        }
    }

    // Road edges
    if (port_edges) {
        ctx.strokeStyle = COLORS.road;
        ctx.lineWidth = 4 * scale;
        ctx.lineCap = 'round';
        for (const [u, neighbors] of Object.entries(port_edges)) {
            const p1 = port_nodes[u];
            if (!p1) continue;
            for (const v of neighbors) {
                const p2 = port_nodes[v];
                if (!p2) continue;
                const [x1, y1] = worldToScreen(p1[0], p1[1]);
                const [x2, y2] = worldToScreen(p2[0], p2[1]);
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.stroke();
            }
        }
    }

    // Nodes
    for (const [name, pos] of Object.entries(port_nodes)) {
        const [nx, ny] = worldToScreen(pos[0], pos[1]);
        const isMain = name.includes('Gate') || name.endsWith('L0') || name.endsWith('R0');
        ctx.fillStyle = isMain ? COLORS.nodeMain : COLORS.node;
        const r = isMain ? 3 * scale : 1.5 * scale;
        ctx.beginPath();
        ctx.arc(nx, ny, r, 0, Math.PI * 2);
        ctx.fill();
    }

    // Yard blocks (from node positions, draw rectangles between L and R nodes)
    drawYards(port_nodes);

    // Tasks
    if (simState.tasks) {
        for (const task of simState.tasks) {
            const tp = port_nodes[task.start];
            if (!tp) continue;
            const [tx, ty] = worldToScreen(tp[0], tp[1]);
            const r = 5 + task.urgency * 5;
            ctx.strokeStyle = COLORS.taskPending;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(tx, ty, r, 0, Math.PI * 2);
            ctx.stroke();
            ctx.fillStyle = 'rgba(52,152,219,0.2)';
            ctx.fill();
        }
    }

    // Truck paths
    if (simState.trucks) {
        for (const truck of simState.trucks) {
            const [tx, ty] = worldToScreen(truck.pos[0], truck.pos[1]);
            // Truck body
            ctx.fillStyle = truck.color;
            ctx.fillRect(tx - 6, ty - 6, 12, 12);
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1;
            ctx.strokeRect(tx - 6, ty - 6, 12, 12);
            // Label
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`车${truck.id}`, tx, ty - 10);
            // Status indicator
            if (truck.status === 'IDLE') {
                ctx.fillStyle = '#2ecc71';
            } else if (truck.status === 'PICKING') {
                ctx.fillStyle = '#f39c12';
            } else {
                ctx.fillStyle = '#e74c3c';
            }
            ctx.beginPath();
            ctx.arc(tx + 6, ty - 6, 3, 0, Math.PI * 2);
            ctx.fill();
        }
    }
}

function drawYards(port_nodes) {
    // Find yard columns by parsing node names
    const columns = {};
    for (const [name, pos] of Object.entries(port_nodes)) {
        const m = name.match(/^C(\d+)_([LR])(\d+)$/);
        if (!m || m[3] === '0') continue;
        const col = m[1], side = m[2], row = m[3];
        if (!columns[col]) columns[col] = {};
        if (!columns[col][row]) columns[col][row] = {};
        columns[col][row][side] = pos;
    }
    for (const [col, rows] of Object.entries(columns)) {
        for (const [row, sides] of Object.entries(rows)) {
            if (sides['L'] && sides['R']) {
                const [lx, ly] = worldToScreen(sides['L'][0] + 2, sides['L'][1] - 3);
                const [rx, ry] = worldToScreen(sides['R'][0] - 2, sides['R'][1] + 3);
                ctx.fillStyle = COLORS.yard;
                ctx.fillRect(lx, ly, rx - lx, ry - ly);
                ctx.strokeStyle = '#333';
                ctx.lineWidth = 1;
                ctx.strokeRect(lx, ly, rx - lx, ry - ly);
                // Label
                if (rx - lx > 25) {
                    ctx.fillStyle = '#000';
                    ctx.font = '8px sans-serif';
                    ctx.textAlign = 'center';
                    ctx.fillText(`B${col}-${row}`, (lx + rx) / 2, (ly + ry) / 2 + 3);
                }
            }
        }
    }
}

// -----------------------------
// API calls
// -----------------------------
async function fetchState() {
    try {
        const resp = await fetch('/api/state');
        if (resp.ok) {
            simState = await resp.json();
            renderAll();
        }
    } catch (e) {
        console.error('Failed to fetch state:', e);
    }
}

function renderAll() {
    drawPort();
    updateSidebar();
}

function updateSidebar() {
    if (!simState || !simState.stats) return;
    const s = simState.stats;
    document.getElementById('m-completed').textContent = s.completed || 0;
    document.getElementById('m-pending').textContent = s.pending || 0;
    document.getElementById('m-wait').textContent = (s.avg_wait_time || 0) + 's';
    document.getElementById('m-util').textContent =
        Math.round((simState.utilization || 0) * 100) + '%';

    // Task list
    const taskList = document.getElementById('task-list');
    if (simState.tasks && simState.tasks.length > 0) {
        taskList.innerHTML = simState.tasks.slice(0, 10).map(t => {
            const cls = t.urgency > 0.7 ? 'task-item task-urgent' : 'task-item';
            return `<div class="${cls}">
                <span>任务${t.id} ${t.type}</span>
                <span style="color:#f0c040;">紧急度:${t.urgency.toFixed(1)}</span>
                <span>${t.start}→${t.end}</span>
            </div>`;
        }).join('');
    } else {
        taskList.innerHTML = '<span style="color:#888;">暂无待调度任务</span>';
    }

    // Truck list
    const truckList = document.getElementById('truck-list');
    if (simState.trucks) {
        truckList.innerHTML = simState.trucks.map(t => `
            <div class="truck-item">
                <span class="truck-dot" style="background:${t.color}"></span>
                车辆${t.id}
                | ${STATUS_CN[t.status] || t.status}
                | 利用率:${Math.round(t.utilization * 100)}%
                | 完成运输:${t.trip_count || 0}次
            </div>
        `).join('');
    }
}

async function stepOnce() {
    await fetch('/api/step', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ steps: 1 })
    });
    await fetchState();
}

async function toggleAuto() {
    const resp = await fetch('/api/auto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'toggle' })
    });
    const data = await resp.json();
    autoRunning = data.auto_run;
    updateAutoButton();
}

async function stopAuto() {
    await fetch('/api/auto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'stop' })
    });
    autoRunning = false;
    updateAutoButton();
}

function updateAutoButton() {
    const btn = document.getElementById('btn-auto');
    btn.textContent = autoRunning ? '暂停' : '开始';
    btn.className = autoRunning ? 'btn-stop' : 'btn-start';
}

async function resetSim() {
    stopAuto();
    await fetch('/api/reset', { method: 'POST' });
    await fetchState();
}

async function addTask() {
    await fetch('/api/tasks/add', { method: 'POST' });
    await fetchState();
}

async function toggleML() {
    const btn = document.getElementById('btn-ml');
    mlEnabled = !mlEnabled;
    btn.textContent = '机器学习: ' + (mlEnabled ? '开' : '关');
    btn.style.background = mlEnabled ? '#2ecc71' : '#7f8c8d';
    await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ml_enabled: mlEnabled })
    });
}

async function toggleCongestion() {
    const btn = document.getElementById('btn-congestion');
    congestionEnabled = !congestionEnabled;
    btn.textContent = '拥堵趋势预测: ' + (congestionEnabled ? '开' : '关');
    btn.style.background = congestionEnabled ? '#2ecc71' : '#7f8c8d';
    await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ congestion_enabled: congestionEnabled })
    });
}

async function setSpeed(val) {
    document.getElementById('speed-label').textContent = val + 's';
    await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speed: parseFloat(val) })
    });
}

// -----------------------------
// Mouse / touch interactions
// -----------------------------
canvas.addEventListener('mousedown', (e) => {
    dragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragViewX = viewX;
    dragViewY = viewY;
});

canvas.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    viewX = dragViewX - (e.clientX - dragStartX) / scale;
    viewY = dragViewY - (e.clientY - dragStartY) / scale;
});

canvas.addEventListener('mouseup', () => { dragging = false; });
canvas.addEventListener('mouseleave', () => { dragging = false; });

canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    scale *= factor;
    scale = Math.max(0.5, Math.min(5, scale));
});

// -----------------------------
// Init
// -----------------------------
function startPolling() {
    fetchState();
    // Poll for state updates every 300ms when auto is off (manual)
    pollInterval = setInterval(() => {
        if (!autoRunning) return; // only poll during auto for rendering
        fetchState();
    }, 200);

    // Always poll at low frequency for UI updates
    setInterval(fetchState, 1000);
}

resizeCanvas();
startPolling();
