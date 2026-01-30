/**
 * Clementine DAQ Dashboard v2 - Frontend JavaScript
 * Highlander Space Program
 * 
 * Features:
 * - WebSocket for real-time bidirectional communication
 * - PIN-protected controls page
 * - TCP board connection monitoring
 * - Raw packet inspection for debugging
 * - Command history with full trace
 */

// =============================================================================
// CONFIGURATION
// =============================================================================

const CONFIG = {
    CHART_HISTORY: { 10: 200, 30: 600, 120: 2400 },
    CHART_UPDATE_INTERVAL: 100,
    LOG_REFRESH_INTERVAL: 3000,
    DEBUG_REFRESH_INTERVAL: 1000,
    COLORS: {
        primary: '#ff6b35',
        secondary: '#ff8c5a',
        safe: '#22c55e',
        warn: '#f59e0b',
        fault: '#ef4444',
        info: '#3b82f6',
        grid: '#2a3040',
        text: '#9aa0a9'
    }
};

// =============================================================================
// STATE
// =============================================================================

const state = {
    socket: null,
    connected: false,
    currentPage: 'overview',
    timeWindow: 10,
    systemState: 'SAFE',
    armed: false,
    controlsUnlocked: false,
    charts: {},
    dataBuffers: {},
    sparklineData: {},
    boardStatus: {},
    actuatorStates: {},
    activeAlarms: [],
    rawPackets: [],
    commandHistory: [],
    latencyHistory: [],
    pendingActuation: null
};

const CHANNELS = ['pt_1', 'pt_2', 'pt_3', 'tc_1', 'tc_2', 'lc_1', 'lc_2', 'flow_1', 'imu_acc', 'imu_gyro', 'altitude'];
CHANNELS.forEach(ch => {
    state.dataBuffers[ch] = [];
    state.sparklineData[ch] = [];
});

// =============================================================================
// WEBSOCKET CONNECTION
// =============================================================================

function initWebSocket() {
    state.socket = io({
        transports: ['websocket'],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000
    });

    state.socket.on('connect', () => {
        state.connected = true;
        updateConnectionStatus(true);
        console.log('WebSocket connected');
        state.socket.emit('request_state');
    });

    state.socket.on('disconnect', () => {
        state.connected = false;
        updateConnectionStatus(false);
        console.log('WebSocket disconnected');
    });

    state.socket.on('connect_error', (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus(false);
    });

    // Telemetry data from sensor boards
    state.socket.on('sensor_data', (data) => {
        // console.log(data)
        handleSensorData(data);
    });

    // System state updates
    state.socket.on('system_state', (data) => {
        updateSystemState(data);
    });

    // Board status updates
    state.socket.on('board_status', (data) => {
        state.boardStatus = data;
        updateBoardStatusDisplay();
    });

    // Actuator state updates
    state.socket.on('actuator_state', (data) => {
        state.actuatorStates[data.actuator_id] = data;
        updateActuatorDisplay(data.actuator_id);
    });

    state.socket.on('actuator_states', (data) => {
        state.actuatorStates = data;
        Object.keys(data).forEach(id => updateActuatorDisplay(id));
    });

    // Alarms
    state.socket.on('alarm', (alarm) => {
        state.activeAlarms.push(alarm);
        updateAlarmDisplay();
    });

    state.socket.on('alarm_cleared', (data) => {
        state.activeAlarms = state.activeAlarms.filter(a => a.id !== data.id);
        updateAlarmDisplay();
    });

    state.socket.on('alarms', (alarms) => {
        state.activeAlarms = alarms;
        updateAlarmDisplay();
    });

    // Log entries (for real-time log page)
    state.socket.on('log_entry', (entry) => {
        if (state.currentPage === 'logs') {
            prependLogEntry(entry);
        }
    });

    // E-STOP notification
    state.socket.on('estop', (data) => {
        showNotification('E-STOP ACTIVATED', 'fault');
    });
}

function updateConnectionStatus(connected) {
    const dot = document.getElementById('ws-status-dot');
    const text = document.getElementById('ws-status-text');
    
    if (connected) {
        dot.classList.add('connected');
        dot.classList.remove('disconnected');
        text.textContent = 'Connected';
    } else {
        dot.classList.remove('connected');
        dot.classList.add('disconnected');
        text.textContent = 'Disconnected';
    }
    
    // Update debug flow diagram
    const flowWs = document.getElementById('flow-ws-status');
    if (flowWs) {
        flowWs.textContent = connected ? 'WebSocket ✓' : 'WebSocket ✗';
        flowWs.style.color = connected ? CONFIG.COLORS.safe : CONFIG.COLORS.fault;
    }
}

// =============================================================================
// SENSOR DATA HANDLING
// =============================================================================

function handleSensorData(data) {
    const timestamp = new Date(data.timestamp * 1000);
    const maxHistory = CONFIG.CHART_HISTORY[state.timeWindow];

    // Store data for each channel
    Object.entries(data.channels).forEach(([channel, value]) => {
        if (state.dataBuffers[channel]) {
            state.dataBuffers[channel].push({ time: timestamp, value: value });
            while (state.dataBuffers[channel].length > maxHistory) {
                state.dataBuffers[channel].shift();
            }
            
            state.sparklineData[channel].push(value);
            while (state.sparklineData[channel].length > 30) {
                state.sparklineData[channel].shift();
            }
        }
    });
    
    // Track latency
    if (data.latency_ms) {
        state.latencyHistory.push({ time: timestamp, value: data.latency_ms, board: data.board_id });
        while (state.latencyHistory.length > 200) {
            state.latencyHistory.shift();
        }
    }
    
    // Update displays
    updateMetricDisplays(data.channels);
    updateChartValues(data.channels);
    
    // Add to raw packet buffer for debug
    if (state.rawPackets.length < 100) {
        state.rawPackets.push({
            timestamp: new Date().toISOString(),
            direction: 'rx',
            board_id: data.board_id,
            channels: Object.keys(data.channels).length,
            latency_ms: data.latency_ms
        });
    }
}

function updateMetricDisplays(channels) {
    if (channels.pt_1 !== undefined) {
        document.getElementById('val-pc').textContent = channels.pt_1.toFixed(1);
    }
    if (channels.lc_1 !== undefined) {
        document.getElementById('val-thrust').textContent = Math.round(channels.lc_1).toLocaleString();
    }
    if (channels.altitude !== undefined) {
        document.getElementById('val-altitude').textContent = Math.round(channels.altitude).toLocaleString();
        const pct = Math.min((channels.altitude / 50000) * 100, 100);
        document.getElementById('altitude-gauge-fill').style.width = `${pct}%`;
    }
    if (channels.tc_1 !== undefined) {
        document.getElementById('val-tc1').textContent = channels.tc_1.toFixed(1);
    }
    if (channels.tc_2 !== undefined) {
        document.getElementById('val-tc2').textContent = channels.tc_2.toFixed(1);
    }
    
    document.getElementById('time-display').textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
}

function updateChartValues(channels) {
    // Overview
    if (channels.pt_1 !== undefined) {
        document.getElementById('chart-val-pc').textContent = `${channels.pt_1.toFixed(1)} psi`;
    }
    if (channels.lc_1 !== undefined) {
        // console.log(channels.lc_1)
        document.getElementById('chart-val-thrust').textContent = `${Math.round(channels.lc_1).toLocaleString()} lbf`;
    }
    if (channels.flow_1 !== undefined) {
        document.getElementById('chart-val-flow').textContent = `${channels.flow_1.toFixed(2)} kg/s`;
    }
    if (channels.altitude !== undefined) {
        document.getElementById('chart-val-altitude').textContent = `${Math.round(channels.altitude).toLocaleString()} m`;
    }
    
    // Telemetry page
    const telemMappings = {
        'pt_1': 'telem-val-pc',
        'pt_2': 'telem-val-lox',
        'pt_3': 'telem-val-fuel',
        'lc_1': 'telem-val-thrust',
        'flow_1': 'telem-val-flow',
        'lc_2': 'telem-val-weight',
        'imu_gyro': 'telem-val-gyro',
        'altitude': 'telem-val-altitude'
    };
    
    Object.entries(telemMappings).forEach(([ch, elemId]) => {
        if (channels[ch] !== undefined) {
            const el = document.getElementById(elemId);
            if (el) {
                const val = ch.startsWith('lc_') ? Math.round(channels[ch]).toLocaleString() : channels[ch].toFixed(2);
                el.textContent = val;
            }
        }
    });
    
    // TVC page
    if (channels.imu_gyro !== undefined) {
        document.getElementById('tvc-gyro').textContent = channels.imu_gyro.toFixed(2);
        document.getElementById('viz-gyro').textContent = channels.imu_gyro.toFixed(1);
    }
    if (channels.imu_acc !== undefined) {
        document.getElementById('tvc-acc').textContent = channels.imu_acc.toFixed(2);
        document.getElementById('viz-acc').textContent = channels.imu_acc.toFixed(2);
    }
    if (channels.altitude !== undefined) {
        document.getElementById('tvc-altitude').textContent = Math.round(channels.altitude).toLocaleString();
    }
    
    // Update rocket visualization based on gyro
    if (channels.imu_gyro !== undefined) {
        const rocket = document.getElementById('rocket-model');
        if (rocket) {
            const rotation = channels.imu_gyro * 2; // Amplify for visibility
            rocket.style.transform = `translate(-50%, -50%) rotateZ(${rotation}deg)`;
        }
    }
}

// =============================================================================
// SYSTEM STATE
// =============================================================================

function updateSystemState(sysState) {
    state.systemState = sysState.state;
    state.armed = sysState.armed;
    
    // Update pill
    const pill = document.getElementById('system-state-pill');
    pill.querySelector('.state-text').textContent = sysState.state;
    pill.className = 'system-state-pill';
    if (sysState.state === 'ARMED') pill.classList.add('armed');
    if (sysState.state === 'FAULT') pill.classList.add('fault');
    
    // Update arm status
    const armStatus = document.getElementById('arm-status');
    if (armStatus) {
        const indicator = armStatus.querySelector('.arm-indicator');
        armStatus.querySelector('span:last-child').textContent = sysState.armed ? 'ARMED' : 'DISARMED';
        indicator.className = 'arm-indicator ' + (sysState.armed ? 'armed' : 'disarmed');
    }
    
    // Update arm toggle
    const armToggle = document.getElementById('arm-toggle');
    if (armToggle) {
        armToggle.classList.toggle('armed', sysState.armed);
    }
    
    updateControlsEnabled();
}

function updateControlsEnabled() {
    const canControl = state.armed;
    
    document.querySelectorAll('.actuator-control .act-btn.open-btn').forEach(btn => {
        btn.disabled = !canControl;
    });
}

// =============================================================================
// BOARD STATUS
// =============================================================================

function updateBoardStatusDisplay() {
    // Count connected boards
    let sensorConnected = 0;
    let controlConnected = 0;
    
    Object.values(state.boardStatus).forEach(board => {
        if (board.state === 'CONNECTED' || board.state === 'DEGRADED') {
            if (board.board_type === 'sensor') sensorConnected++;
            else if (board.board_type === 'control') controlConnected++;
        }
    });
    
    document.getElementById('sensor-board-count').textContent = sensorConnected;
    document.getElementById('control-board-count').textContent = controlConnected;
    
    // Update board status strip
    const strip = document.getElementById('board-status-strip');
    if (strip) {
        strip.innerHTML = Object.values(state.boardStatus).map(board => {
            const stateClass = board.state.toLowerCase();
            return `
                <div class="board-chip ${stateClass}" title="${board.board_id}: ${board.ip}:${board.port}">
                    <span class="chip-name">${board.board_id.replace('_board_', '')}</span>
                    <span class="chip-latency">${board.latency_ms.toFixed(1)}ms</span>
                </div>
            `;
        }).join('');
    }
    
    // Update debug page
    updateDebugBoardList();
    
    // Update flow diagram
    const flowSensor = document.getElementById('flow-sensor-status');
    const flowControl = document.getElementById('flow-control-status');
    if (flowSensor) {
        flowSensor.textContent = `TCP ${sensorConnected}/3`;
        flowSensor.style.color = sensorConnected === 3 ? CONFIG.COLORS.safe : CONFIG.COLORS.warn;
    }
    if (flowControl) {
        flowControl.textContent = `TCP ${controlConnected}/3`;
        flowControl.style.color = controlConnected === 3 ? CONFIG.COLORS.safe : CONFIG.COLORS.warn;
    }
}

function updateDebugBoardList() {
    const list = document.getElementById('debug-board-list');
    if (!list) return;
    
    list.innerHTML = Object.values(state.boardStatus).map(board => {
        const stateClass = board.state.toLowerCase();
        return `
            <div class="board-row ${stateClass}">
                <div class="board-info">
                    <span class="board-name">${board.board_id}</span>
                    <span class="board-type">${board.board_type}</span>
                </div>
                <div class="board-address">${board.ip}:${board.port}</div>
                <div class="board-stats">
                    <span>RX: ${board.packets_received}</span>
                    <span>TX: ${board.packets_sent}</span>
                    <span>Err: ${board.errors}</span>
                </div>
                <div class="board-latency">
                    <span class="latency-current">${board.latency_ms.toFixed(1)}ms</span>
                    <span class="latency-avg">avg: ${board.avg_latency_ms.toFixed(1)}ms</span>
                </div>
                <div class="board-state-badge ${stateClass}">${board.state}</div>
            </div>
        `;
    }).join('');
}

// =============================================================================
// ALARMS
// =============================================================================

function updateAlarmDisplay() {
    const count = document.getElementById('alarm-count');
    const list = document.getElementById('alarm-list');
    const banner = document.getElementById('alarm-banner');
    
    count.textContent = state.activeAlarms.length;
    count.classList.toggle('has-alarms', state.activeAlarms.length > 0);
    
    if (state.activeAlarms.length === 0) {
        list.innerHTML = '<div class="no-alarms">No active alarms</div>';
        banner.style.display = 'none';
    } else {
        list.innerHTML = state.activeAlarms.map(alarm => `
            <div class="alarm-item ${alarm.severity.toLowerCase()}">
                <span class="alarm-severity ${alarm.severity.toLowerCase()}">${alarm.severity}</span>
                <span class="alarm-text">${alarm.message}</span>
                <span class="alarm-time">${formatTime(alarm.timestamp)}</span>
            </div>
        `).join('');
        
        const faults = state.activeAlarms.filter(a => a.severity === 'FAULT');
        if (faults.length > 0 && state.systemState === 'FAULT') {
            banner.style.display = 'block';
            document.getElementById('alarm-banner-message').textContent = 
                `${faults.length} FAULT${faults.length > 1 ? 'S' : ''}: ${faults[0].message}`;
        } else {
            banner.style.display = 'none';
        }
    }
}

function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// =============================================================================
// ACTUATOR DISPLAY
// =============================================================================

function updateActuatorDisplay(actuatorId) {
    const actState = state.actuatorStates[actuatorId];
    if (!actState) return;
    
    const stateEl = document.getElementById(`state-${actuatorId}`);
    if (stateEl) {
        stateEl.textContent = actState.state;
        stateEl.className = 'actuator-state ' + (actState.state === 'open' || actState.state === 'on' ? 'open' : 'closed');
    }
    
    // TVC display
    if (actuatorId === 'tvc_pitch') {
        document.getElementById('tvc-servo-pitch').textContent = actState.state.toFixed(1);
        document.getElementById('servo-pitch').value = actState.state;
        document.getElementById('servo-pitch-val').textContent = `${actState.state.toFixed(1)}°`;
    }
    if (actuatorId === 'tvc_yaw') {
        document.getElementById('tvc-servo-yaw').textContent = actState.state.toFixed(1);
        document.getElementById('servo-yaw').value = actState.state;
        document.getElementById('servo-yaw-val').textContent = `${actState.state.toFixed(1)}°`;
    }
}

// =============================================================================
// NAVIGATION
// =============================================================================

function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            navigateTo(page);
        });
    });
}

function navigateTo(page) {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });
    
    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('active', p.id === `page-${page}`);
    });
    
    state.currentPage = page;
    
    if (page === 'logs') fetchLogs();
    if (page === 'debug') refreshDebugData();
    if (page === 'controls') checkControlsAuth();
}

// =============================================================================
// CONTROLS PAGE AUTHENTICATION
// =============================================================================

async function checkControlsAuth() {
    try {
        const resp = await fetch('/api/controls/status');
        const data = await resp.json();
        state.controlsUnlocked = data.unlocked;
        updateControlsLockState();
    } catch (e) {
        console.error('Failed to check controls auth:', e);
    }
}

function updateControlsLockState() {
    const overlay = document.getElementById('controls-lock-overlay');
    const content = document.getElementById('controls-content');
    const badge = document.getElementById('controls-lock-badge');
    
    if (state.controlsUnlocked) {
        overlay.style.display = 'none';
        content.style.display = 'block';
        badge.textContent = '🔓';
        badge.classList.remove('locked');
    } else {
        overlay.style.display = 'flex';
        content.style.display = 'none';
        badge.textContent = '🔒';
        badge.classList.add('locked');
    }
}

async function unlockControls(pin) {
    try {
        const resp = await fetch('/api/controls/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin })
        });
        
        const data = await resp.json();
        
        if (data.success) {
            state.controlsUnlocked = true;
            updateControlsLockState();
            document.getElementById('pin-input').value = '';
            document.getElementById('pin-error').textContent = '';
        } else {
            document.getElementById('pin-error').textContent = data.message || 'Invalid PIN';
        }
    } catch (e) {
        document.getElementById('pin-error').textContent = 'Connection error';
    }
}

async function lockControls() {
    try {
        await fetch('/api/controls/lock', { method: 'POST' });
        state.controlsUnlocked = false;
        updateControlsLockState();
    } catch (e) {
        console.error('Failed to lock controls:', e);
    }
}

// =============================================================================
// CONTROL COMMANDS
// =============================================================================

async function sendActuatorCommand(actuatorId, newState) {
    if (!state.controlsUnlocked) {
        showNotification('Controls locked', 'warn');
        return;
    }
    
    try {
        const resp = await fetch('/api/control/actuate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                actuator_id: actuatorId,
                command: 'set_state',
                state: newState
            })
        });
        
        const data = await resp.json();
        
        // Add to command log UI
        addCommandToUI(data);
        
        if (data.success) {
            showNotification(`${actuatorId} → ${newState}`, 'safe');
        } else {
            showNotification(`Failed: ${data.errors?.join(', ') || 'Unknown error'}`, 'fault');
        }
        
        return data;
    } catch (e) {
        showNotification('Command failed: ' + e.message, 'fault');
        return { success: false };
    }
}

async function sendArmCommand(arm) {
    if (!state.controlsUnlocked) return;
    
    try {
        const resp = await fetch('/api/control/arm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ arm })
        });
        
        const data = await resp.json();
        
        if (data.success) {
            showNotification(data.message, arm ? 'warn' : 'safe');
        } else {
            showNotification(data.message, 'fault');
        }
        
        const feedback = document.getElementById('arm-feedback');
        if (feedback) {
            feedback.textContent = data.message;
            feedback.style.color = data.success ? CONFIG.COLORS.safe : CONFIG.COLORS.fault;
        }
    } catch (e) {
        console.error('Arm command failed:', e);
    }
}

async function sendEstop() {
    try {
        const resp = await fetch('/api/control/estop', { method: 'POST' });
        const data = await resp.json();
        showNotification('E-STOP ACTIVATED', 'fault');
    } catch (e) {
        console.error('E-STOP failed:', e);
    }
}

async function sendAcknowledge() {
    try {
        await fetch('/api/control/acknowledge', { method: 'POST' });
    } catch (e) {
        console.error('Acknowledge failed:', e);
    }
}

function addCommandToUI(cmdData) {
    const log = document.getElementById('command-log');
    if (!log) return;
    
    const noCmd = log.querySelector('.no-commands');
    if (noCmd) noCmd.remove();
    
    const entry = document.createElement('div');
    entry.className = `cmd-entry ${cmdData.success ? 'success' : 'failed'}`;
    entry.innerHTML = `
        <span class="cmd-time">${formatTime(new Date().toISOString())}</span>
        <span class="cmd-id">${cmdData.cmd_id || '--'}</span>
        <span class="cmd-result">${cmdData.success ? 'OK' : 'FAIL'}</span>
        <span class="cmd-latency">${cmdData.latency_ms?.toFixed(1) || '--'}ms</span>
    `;
    
    log.insertBefore(entry, log.firstChild);
    
    // Keep only last 20
    while (log.children.length > 20) {
        log.removeChild(log.lastChild);
    }
}

// =============================================================================
// CHARTS
// =============================================================================

function initCharts() {
    Chart.defaults.color = CONFIG.COLORS.text;
    Chart.defaults.borderColor = CONFIG.COLORS.grid;
    Chart.defaults.font.family = "'JetBrains Mono', monospace";
    
    const baseOptions = {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
            legend: { display: false },
            tooltip: { mode: 'index', intersect: false }
        },
        scales: {
            x: { type: 'linear', display: true, grid: { color: CONFIG.COLORS.grid }, ticks: { display: false } },
            y: { display: true, grid: { color: CONFIG.COLORS.grid }, ticks: { font: { size: 10 }, maxTicksLimit: 5 } }
        }
    };
    
    // Overview charts
    state.charts['overview-pc'] = createChart('chart-pc', baseOptions, 0, 300);
    state.charts['overview-thrust'] = createChart('chart-thrust', baseOptions, 0, 300);
    state.charts['overview-flow'] = createChart('chart-flow', baseOptions, 0, 50);
    state.charts['overview-altitude'] = createChart('chart-altitude', baseOptions, 0, 50000);
    
    // Telemetry charts
    state.charts['telem-pc'] = createChart('telem-chart-pc', baseOptions, 0, 300);
    state.charts['telem-lox'] = createChart('telem-chart-lox', baseOptions, 0, 600);
    state.charts['telem-fuel'] = createChart('telem-chart-fuel', baseOptions, 0, 600);
    state.charts['telem-thrust'] = createChart('telem-chart-thrust', baseOptions, 0, 300);
    state.charts['telem-flow'] = createChart('telem-chart-flow', baseOptions, 0, 50);
    state.charts['telem-weight'] = createChart('telem-chart-weight', baseOptions, 0, 5000);
    state.charts['telem-gyro'] = createChart('telem-chart-gyro', baseOptions, -10, 10);
    state.charts['telem-altitude'] = createChart('telem-chart-altitude', baseOptions, 0, 50000);
    
    // TVC chart
    state.charts['tvc-rates'] = createMultiChart('tvc-chart-rates', baseOptions, -10, 10, [
        { label: 'Gyro', color: CONFIG.COLORS.primary },
        { label: 'Acc', color: CONFIG.COLORS.info }
    ]);
    
    // Debug latency chart
    state.charts['latency'] = createChart('latency-chart', baseOptions, 0, 20);
    
    setInterval(updateCharts, CONFIG.CHART_UPDATE_INTERVAL);
}

function createChart(canvasId, baseOptions, yMin, yMax) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    
    return new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [{
                data: [],
                borderColor: CONFIG.COLORS.primary,
                backgroundColor: CONFIG.COLORS.primary + '15',
                borderWidth: 2,
                fill: true,
                pointRadius: 0,
                tension: 0.1
            }]
        },
        options: {
            ...baseOptions,
            scales: { ...baseOptions.scales, y: { ...baseOptions.scales.y, min: yMin, max: yMax } }
        }
    });
}

function createMultiChart(canvasId, baseOptions, yMin, yMax, datasets) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    
    return new Chart(ctx, {
        type: 'line',
        data: {
            datasets: datasets.map(ds => ({
                label: ds.label,
                data: [],
                borderColor: ds.color,
                backgroundColor: 'transparent',
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.1
            }))
        },
        options: {
            ...baseOptions,
            plugins: { ...baseOptions.plugins, legend: { display: true, position: 'top' } },
            scales: { ...baseOptions.scales, y: { ...baseOptions.scales.y, min: yMin, max: yMax } }
        }
    });
}

function updateCharts() {
    const formatData = (buffer) => {
        if (!buffer.length) return [];
        const startTime = buffer[0].time.getTime();
        return buffer.map(p => ({ x: (p.time.getTime() - startTime) / 1000, y: p.value }));
    };
    
    // Overview
    updateChartData(state.charts['overview-pc'], state.dataBuffers.pt_1);
    updateChartData(state.charts['overview-thrust'], state.dataBuffers.lc_1);
    updateChartData(state.charts['overview-flow'], state.dataBuffers.flow_1);
    updateChartData(state.charts['overview-altitude'], state.dataBuffers.altitude);
    
    // Telemetry
    updateChartData(state.charts['telem-pc'], state.dataBuffers.pt_1);
    updateChartData(state.charts['telem-lox'], state.dataBuffers.pt_2);
    updateChartData(state.charts['telem-fuel'], state.dataBuffers.pt_3);
    updateChartData(state.charts['telem-thrust'], state.dataBuffers.lc_1);
    updateChartData(state.charts['telem-flow'], state.dataBuffers.flow_1);
    updateChartData(state.charts['telem-weight'], state.dataBuffers.lc_2);
    updateChartData(state.charts['telem-gyro'], state.dataBuffers.imu_gyro);
    updateChartData(state.charts['telem-altitude'], state.dataBuffers.altitude);
    
    // TVC
    if (state.charts['tvc-rates']) {
        state.charts['tvc-rates'].data.datasets[0].data = formatData(state.dataBuffers.imu_gyro);
        state.charts['tvc-rates'].data.datasets[1].data = formatData(state.dataBuffers.imu_acc);
        state.charts['tvc-rates'].update('none');
    }
    
    // Latency
    updateChartData(state.charts['latency'], state.latencyHistory);
    
    function updateChartData(chart, buffer) {
        if (!chart || !buffer) return;
        chart.data.datasets[0].data = formatData(buffer);
        chart.update('none');
    }
}

// =============================================================================
// TIME WINDOW
// =============================================================================

function initTimeControls() {
    document.querySelectorAll('.time-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const window = parseInt(btn.dataset.window);
            state.timeWindow = window;
            
            document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const maxHistory = CONFIG.CHART_HISTORY[window];
            CHANNELS.forEach(ch => {
                while (state.dataBuffers[ch].length > maxHistory) {
                    state.dataBuffers[ch].shift();
                }
            });
        });
    });
}

// =============================================================================
// DEBUG PAGE
// =============================================================================

async function refreshDebugData() {
    try {
        // Fetch debug metrics
        const metricsResp = await fetch('/api/debug/metrics');
        const metrics = await metricsResp.json();
        
        document.getElementById('debug-ws-clients').textContent = metrics.websocket_clients;
        document.getElementById('debug-pps').textContent = metrics.packets_per_second?.toFixed(1) || '0';
        document.getElementById('debug-influx-queue').textContent = metrics.influx_queue_size;
        document.getElementById('debug-uptime').textContent = formatUptime(metrics.uptime_seconds);
        
        // Update sidebar
        document.getElementById('uptime-display').textContent = `Uptime: ${formatUptime(metrics.uptime_seconds)}`;
        document.getElementById('pps-display').textContent = `${metrics.packets_per_second?.toFixed(0) || 0} pkt/s`;
        
        // Fetch command history
        const cmdResp = await fetch('/api/commands?limit=20');
        const cmdData = await cmdResp.json();
        state.commandHistory = cmdData.commands;
        renderCommandHistory();
        
        // Fetch raw packets
        const pktResp = await fetch('/api/debug/packets');
        const pktData = await pktResp.json();
        renderRawPackets(pktData.packets);
        
    } catch (e) {
        console.error('Failed to refresh debug data:', e);
    }
}

function formatUptime(seconds) {
    if (!seconds) return '0s';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

function renderCommandHistory() {
    const list = document.getElementById('debug-command-history');
    if (!list) return;
    
    if (state.commandHistory.length === 0) {
        list.innerHTML = '<div class="no-commands">No commands</div>';
        return;
    }
    
    list.innerHTML = state.commandHistory.slice(0, 20).map(cmd => `
        <div class="cmd-history-row ${cmd.ack_received ? 'success' : 'failed'}">
            <div class="cmd-header">
                <span class="cmd-time">${formatTime(cmd.timestamp)}</span>
                <span class="cmd-actuator">${cmd.actuator_id}</span>
                <span class="cmd-state-req">${cmd.state_requested}</span>
                <span class="cmd-result-badge ${cmd.ack_received ? 'success' : 'failed'}">${cmd.ack_received ? 'ACK' : 'NACK'}</span>
            </div>
            <div class="cmd-details">
                <span>Validation: ${cmd.validation_result}</span>
                <span>Latency: ${cmd.latency_ms?.toFixed(1) || '--'}ms</span>
                <span>InfluxDB: ${cmd.influx_logged ? '✓' : '✗'}</span>
            </div>
        </div>
    `).join('');
}

function renderRawPackets(packets) {
    const list = document.getElementById('packet-list');
    if (!list) return;
    
    const showRx = document.getElementById('packet-show-rx')?.checked ?? true;
    const showTx = document.getElementById('packet-show-tx')?.checked ?? true;
    
    const filtered = packets.filter(p => 
        (p.direction === 'rx' && showRx) || (p.direction === 'tx' && showTx)
    );
    
    list.innerHTML = filtered.slice(0, 50).map(pkt => `
        <div class="packet-row ${pkt.direction}">
            <span class="pkt-time">${formatTime(pkt.timestamp)}</span>
            <span class="pkt-dir ${pkt.direction}">${pkt.direction.toUpperCase()}</span>
            <span class="pkt-board">${pkt.board_id}</span>
            <span class="pkt-size">${pkt.size_bytes}B</span>
            <span class="pkt-latency">${pkt.latency_ms?.toFixed(1) || '--'}ms</span>
            <pre class="pkt-data">${JSON.stringify(pkt.packet, null, 1).substring(0, 100)}...</pre>
        </div>
    `).join('');
}

// =============================================================================
// LOGS
// =============================================================================

async function fetchLogs() {
    const filter = document.getElementById('log-filter')?.value || '';
    const url = filter ? `/api/logs?type=${filter}&limit=100` : '/api/logs?limit=100';
    
    try {
        const resp = await fetch(url);
        const data = await resp.json();
        renderLogs(data.logs);
    } catch (e) {
        console.error('Failed to fetch logs:', e);
    }
}

function renderLogs(logs) {
    const tbody = document.getElementById('logs-tbody');
    if (!logs.length) {
        tbody.innerHTML = '<tr><td colspan="3" class="no-logs">No logs</td></tr>';
        return;
    }
    
    tbody.innerHTML = logs.map(log => `
        <tr>
            <td class="timestamp">${formatTimestamp(log.timestamp)}</td>
            <td><span class="log-type ${log.type}">${log.type}</span></td>
            <td>${escapeHtml(log.message)}</td>
        </tr>
    `).join('');
}

function prependLogEntry(entry) {
    const tbody = document.getElementById('logs-tbody');
    const noLogs = tbody.querySelector('.no-logs');
    if (noLogs) noLogs.parentElement.remove();
    
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td class="timestamp">${formatTimestamp(entry.timestamp)}</td>
        <td><span class="log-type ${entry.type}">${entry.type}</span></td>
        <td>${escapeHtml(entry.message)}</td>
    `;
    tbody.insertBefore(tr, tbody.firstChild);
    
    while (tbody.children.length > 100) {
        tbody.removeChild(tbody.lastChild);
    }
}

function formatTimestamp(iso) {
    const d = new Date(iso);
    return d.toLocaleString('en-US', { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// =============================================================================
// NOTIFICATIONS
// =============================================================================

function showNotification(message, type = 'info') {
    // Simple notification - could be enhanced with a toast library
    console.log(`[${type.toUpperCase()}] ${message}`);
}

// =============================================================================
// INITIALIZATION
// =============================================================================

function initControls() {
    // PIN unlock
    document.getElementById('unlock-btn')?.addEventListener('click', () => {
        const pin = document.getElementById('pin-input').value;
        unlockControls(pin);
    });
    
    document.getElementById('pin-input')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const pin = document.getElementById('pin-input').value;
            unlockControls(pin);
        }
    });
    
    // Lock controls
    document.getElementById('lock-controls-btn')?.addEventListener('click', lockControls);
    
    // Arm toggle
    const armToggle = document.getElementById('arm-toggle');
    const armModal = document.getElementById('arm-modal');
    
    armToggle?.addEventListener('click', () => {
        if (state.armed) {
            sendArmCommand(false);
        } else {
            armModal.style.display = 'flex';
        }
    });
    
    document.getElementById('arm-cancel')?.addEventListener('click', () => {
        armModal.style.display = 'none';
    });
    
    document.getElementById('arm-confirm')?.addEventListener('click', () => {
        armModal.style.display = 'none';
        sendArmCommand(true);
    });
    
    // Actuator buttons
    document.querySelectorAll('.actuator-control').forEach(ctrl => {
        const actuatorId = ctrl.dataset.actuator;
        ctrl.querySelectorAll('.act-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const newState = btn.dataset.state;
                const isCritical = ctrl.classList.contains('critical');
                
                if (isCritical && (newState === 'open' || newState === 'on')) {
                    // Show confirmation for critical actuators
                    state.pendingActuation = { actuatorId, newState };
                    document.getElementById('actuate-confirm-message').textContent = 
                        `Confirm: Set ${actuatorId} to ${newState}?`;
                    document.getElementById('actuate-confirm-modal').style.display = 'flex';
                } else {
                    sendActuatorCommand(actuatorId, newState);
                }
            });
        });
    });
    
    // Actuate confirmation modal
    document.getElementById('actuate-cancel')?.addEventListener('click', () => {
        document.getElementById('actuate-confirm-modal').style.display = 'none';
        state.pendingActuation = null;
    });
    
    document.getElementById('actuate-confirm')?.addEventListener('click', () => {
        document.getElementById('actuate-confirm-modal').style.display = 'none';
        if (state.pendingActuation) {
            sendActuatorCommand(state.pendingActuation.actuatorId, state.pendingActuation.newState);
            state.pendingActuation = null;
        }
    });
    
    // TVC sliders
    const pitchSlider = document.getElementById('servo-pitch');
    const yawSlider = document.getElementById('servo-yaw');
    
    pitchSlider?.addEventListener('input', (e) => {
        document.getElementById('servo-pitch-val').textContent = `${parseFloat(e.target.value).toFixed(1)}°`;
    });
    pitchSlider?.addEventListener('change', (e) => {
        sendActuatorCommand('tvc_pitch', parseFloat(e.target.value));
    });
    
    yawSlider?.addEventListener('input', (e) => {
        document.getElementById('servo-yaw-val').textContent = `${parseFloat(e.target.value).toFixed(1)}°`;
    });
    yawSlider?.addEventListener('change', (e) => {
        sendActuatorCommand('tvc_yaw', parseFloat(e.target.value));
    });
    
    // Center button
    document.getElementById('btn-center')?.addEventListener('click', () => {
        sendActuatorCommand('tvc_pitch', 0);
        sendActuatorCommand('tvc_yaw', 0);
    });
    
    // E-STOP
    const estopBtn = document.getElementById('btn-estop');
    const estopModal = document.getElementById('estop-modal');
    
    estopBtn?.addEventListener('click', () => {
        estopModal.style.display = 'flex';
    });
    
    document.getElementById('estop-cancel')?.addEventListener('click', () => {
        estopModal.style.display = 'none';
    });
    
    document.getElementById('estop-confirm')?.addEventListener('click', () => {
        estopModal.style.display = 'none';
        sendEstop();
    });
    
    // Alarm acknowledge
    document.getElementById('alarm-ack-btn')?.addEventListener('click', sendAcknowledge);
    
    // Log filter
    document.getElementById('log-filter')?.addEventListener('change', fetchLogs);
    
    // Download logs
    document.getElementById('btn-download-logs')?.addEventListener('click', () => {
        window.location.href = '/api/logs/download';
    });
    
    // Debug refresh
    document.getElementById('btn-refresh-debug')?.addEventListener('click', refreshDebugData);
    
    // Packet filter checkboxes
    document.getElementById('packet-show-rx')?.addEventListener('change', () => refreshDebugData());
    document.getElementById('packet-show-tx')?.addEventListener('change', () => refreshDebugData());
    document.getElementById('btn-clear-packets')?.addEventListener('click', () => {
        document.getElementById('packet-list').innerHTML = '';
    });
}

// Modal close handlers
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay').forEach(m => m.style.display = 'none');
    }
});

document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.style.display = 'none';
    });
});

// Main init
document.addEventListener('DOMContentLoaded', () => {
    console.log('Clementine Dashboard v2 initializing...');
    
    initNavigation();
    initWebSocket();
    initCharts();
    initTimeControls();
    initControls();
    
    // Periodic debug refresh
    setInterval(() => {
        if (state.currentPage === 'debug') refreshDebugData();
    }, CONFIG.DEBUG_REFRESH_INTERVAL);
    
    console.log('Dashboard ready');
});
