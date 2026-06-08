document.addEventListener('DOMContentLoaded', () => {
    const chatHistory = document.getElementById('chatHistory');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');

    // Tabs elements
    const tabs = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    // Result elements
    const terminalOutput = document.getElementById('terminalOutput');
    const codeOutput = document.getElementById('codeOutput');
    const visualsGrid = document.getElementById('visualsGrid');
    const logSelect = document.getElementById('logSelect');
    const logOutput = document.getElementById('logOutput');
    const resultsOutput = document.getElementById('resultsOutput');

    // Backend & Gauge components
    const backendSelector = document.getElementById('backendSelector');
    const activeBackend = document.getElementById('activeBackend');
    const workflowSelector = document.getElementById('workflowSelector');
    const gaugePath = document.getElementById('gaugePath');
    const gaugeText = document.getElementById('gaugeText');
    const modeSelector = document.getElementById('modeSelector');

    // IBM Backend components
    const ibmModeSelector = document.getElementById('ibmModeSelector');
    const runIbmBtn = document.getElementById('runIbmBtn');
    const ibmStatus = document.getElementById('ibmStatus');
    let lastCompiledCode = null;
    let lastFidelity = 0;

    // Dynamic inputs
    const bvInput = document.getElementById('bvInput');
    const zzInput = document.getElementById('zzInput');
    const ecgInputs = document.getElementById('ecgInputs');
    const ecgRecord = document.getElementById('ecgRecord');
    const ecgBeat = document.getElementById('ecgBeat');
    const ecgFeatures = document.getElementById('ecgFeatures');
    const voiceToggle = document.getElementById('voiceToggle');

    let currentLogs = { architect: '', verifier: '', optimizer: '' };
    let voiceEnabled = true;

    // Speech Synthesis for Audio Enhancement
    const synth = window.speechSynthesis;
    const announce = (text) => {
        if (!voiceEnabled || !synth) return;
        
        // Cancel any ongoing speech
        synth.cancel();
        
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        
        // Try to find a polite/professional English voice
        const voices = synth.getVoices();
        const preferredVoice = voices.find(v => v.lang.includes('en') && (v.name.includes('Female') || v.name.includes('Google')));
        if (preferredVoice) utterance.voice = preferredVoice;
        
        synth.speak(utterance);
    };

    voiceToggle.addEventListener('click', () => {
        voiceEnabled = !voiceEnabled;
        voiceToggle.textContent = voiceEnabled ? '🔊 Voice: ON' : '🔇 Voice: OFF';
        if (!voiceEnabled) synth.cancel();
    });

    // --- QUANTUM MESH BACKGROUND ---
    const canvas = document.getElementById('quantumMesh');
    const ctx = canvas.getContext('2d');
    let particles = [];

    const resizeCanvas = () => {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    class Particle {
        constructor() {
            this.reset();
        }
        reset() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.size = Math.random() * 2 + 1;
            this.speedX = (Math.random() - 0.5) * 0.5;
            this.speedY = (Math.random() - 0.5) * 0.5;
            this.opacity = Math.random() * 0.5 + 0.1;
        }
        update() {
            this.x += this.speedX;
            this.y += this.speedY;
            if (this.x < 0 || this.x > canvas.width) this.speedX *= -1;
            if (this.y < 0 || this.y > canvas.height) this.speedY *= -1;
        }
        draw() {
            ctx.fillStyle = `rgba(99, 102, 241, ${this.opacity})`;
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    for (let i = 0; i < 50; i++) particles.push(new Particle());

    const animateMesh = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach(p => {
            p.update();
            p.draw();
        });

        // Draw connections
        ctx.strokeStyle = 'rgba(99, 102, 241, 0.05)';
        ctx.lineWidth = 1;
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 150) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.stroke();
                }
            }
        }
        requestAnimationFrame(animateMesh);
    };
    animateMesh();

    // --- FIDELITY GAUGE LOGIC ---
    const updateGauge = (value) => {
        const percentage = Math.round(value * 100);
        const dashOffset = 126 - (126 * percentage) / 100; // 126 is approx half circum of 40r circle

        // Arc setup: C=2*pi*r. Here r=35, whole circle=220. Semi-circle path length is approx 126
        gaugePath.style.strokeDasharray = `126, 220`;
        gaugePath.style.strokeDashoffset = 126; // start at 126 (0%)

        // Force reflow
        gaugePath.getBoundingClientRect();

        const offset = 126 - (126 * (percentage / 100));
        gaugePath.style.strokeDashoffset = offset;
        gaugeText.textContent = `${percentage}%`;

        // Color based on value
        let color = '#ef4444'; // error
        if (percentage > 50) color = '#f59e0b'; // warning
        if (percentage >= 70) color = '#10b981'; // success
        gaugePath.style.stroke = color;
    };
    updateGauge(0); // Initialize at 0

    backendSelector.addEventListener('change', (e) => {
        const val = e.target.value;
        activeBackend.textContent = `QPU: ${val}`;
        
        if (val.includes('IBM')) {
            ibmStatus.textContent = val === 'IBMRealQPU' ? '⚠️ QPU may have long queues' : '☁️ Service: IBM Cloud';
            ibmStatus.style.color = val === 'IBMRealQPU' ? '#f59e0b' : '#60a5fa';
        } else {
            ibmStatus.textContent = 'Local Digital Twin Active';
            ibmStatus.style.color = '#9ca3af';
        }
    });

    // --- TABS LOGIC ---
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            // Add to clicked
            tab.classList.add('active');
            document.getElementById(tab.dataset.tab).classList.add('active');
        });
    });

    logSelect.addEventListener('change', (e) => {
        const val = e.target.value;
        logOutput.textContent = currentLogs[val] || 'No logs generated for this agent yet.';
    });

    modeSelector.addEventListener('change', (e) => {
        const mode = e.target.value;
        userInput.style.display = 'none';
        bvInput.style.display = 'none';
        zzInput.style.display = 'none';
        ecgInputs.style.display = 'none';

        if (mode === '1') userInput.style.display = 'block';
        if (mode === '2') bvInput.style.display = 'block';
        if (mode === '3') zzInput.style.display = 'block';
        if (mode === '4') ecgInputs.style.display = 'flex';
    });

    // --- MAIN API LOGIC ---
    const addMessage = (role, text) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;

        const avatarStr = role === 'user' ? 'U' : 'Q';

        msgDiv.innerHTML = `
            <div class="avatar">${avatarStr}</div>
            <div class="message-content">${text}</div>
        `;
        chatHistory.appendChild(msgDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    };

    const processRequest = async () => {
        const mode = modeSelector.value;
        const workflow = workflowSelector.value;
        let text = "";
        let payload = { backend: backendSelector.value, mode: mode, workflow: workflow };

        if (mode === '1') {
            text = userInput.value.trim();
            if (!text) return;
            userInput.value = '';
            payload.message = text;
        } else if (mode === '2') {
            text = "Bernstein-Vazirani mode with hidden string: " + (bvInput.value.trim() || '1011');
            payload.hidden_string = bvInput.value.trim() || '1011';
            payload.message = text;
            bvInput.value = '';
        } else if (mode === '3') {
            text = "ZZ Feature Map mode for Iris index: " + (zzInput.value.trim() || '0');
            payload.iris_index = zzInput.value.trim() || '0';
            payload.message = text;
            zzInput.value = '';
        } else if (mode === '4') {
            text = "ECG Arrhythmia mode for Record: " + (ecgRecord.value || '100') + " Beat: " + (ecgBeat.value || '10');
            payload.ecg_record = ecgRecord.value || '100';
            payload.ecg_beat = ecgBeat.value || '10';
            payload.ecg_features = ecgFeatures.value || '2';
            payload.message = text;
        }

        addMessage('user', text);

        // Disable input
        userInput.disabled = true;
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<span class="spinner"></span>';

        // Reset results UI for a new run
        terminalOutput.textContent = 'Initializing Q-Optima CrewAI Workflow...\n\n';
        codeOutput.textContent = '# Waiting for compilation...';
        resultsOutput.textContent = '// Waiting for compilation...';
        visualsGrid.innerHTML = '<div class="empty-state">Compiling circuit to generate visualizations...</div>';
        updateGauge(0);
        
        runIbmBtn.disabled = true;
        ibmStatus.textContent = 'Compile a circuit first';
        ibmStatus.style.color = '#9ca3af';

        // Switch to terminal tab so user sees it live
        tabs[0].click();

        try {
            const reqTimer = setInterval(() => {
                terminalOutput.textContent += '.\n';
                terminalOutput.scrollTop = terminalOutput.scrollHeight;
            }, 2000); // fake "live" feel while waiting for long polling

            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            clearInterval(reqTimer);
            const data = await response.json();

            // Populate terminal (real logs) with typewriter effect
            if (data.logs) {
                const lines = data.logs.split('\n');
                terminalOutput.textContent = '';
                let lineIdx = 0;

                const typeLine = () => {
                    if (lineIdx < lines.length) {
                        terminalOutput.textContent += lines[lineIdx] + '\n';
                        terminalOutput.scrollTop = terminalOutput.scrollHeight;
                        lineIdx++;
                        setTimeout(typeLine, lines[lineIdx - 1].includes('PHASE') ? 100 : 20); // slower for headers
                    }
                };
                typeLine();
            }

            // Populate code
            if (data.code) {
                codeOutput.textContent = data.code;
            }

            // Populate Results JSON
            if (data.results_json) {
                resultsOutput.textContent = JSON.stringify(data.results_json, null, 2);
            }

            // Update Gauge
            if (data.fidelity !== undefined) {
                updateGauge(data.fidelity);
            }

            // Populate visuals
            if (data.images && data.images.length > 0) {
                visualsGrid.innerHTML = ''; // clear empty state
                data.images.forEach(imgData => {
                    const card = document.createElement('div');
                    card.className = 'visual-card';
                    
                    const imgUrl = imgData.url || imgData; // handle both object and string for safety
                    const title = imgData.title || "Circuit Visual";

                    // Append timestamp to prevent caching
                    const cacheBustedUrl = imgUrl + '?t=' + new Date().getTime();

                    card.innerHTML = `
                        <h3>${title}</h3>
                        <img src="${cacheBustedUrl}" alt="${title}" />
                    `;
                    visualsGrid.appendChild(card);
                });
            } else if (data.status === 'success') {
                visualsGrid.innerHTML = '<div class="empty-state">No visualizations were generated correctly.</div>';
            } else {
                visualsGrid.innerHTML = '<div class="empty-state" style="color:var(--error);">Compilation failed. See raw logs.</div>';
            }

            // Populate Raw Logs
            currentLogs.architect = data.architect_log || '';
            currentLogs.verifier = data.verifier_log || '';
            currentLogs.optimizer = data.optimizer_log || '';
            // Trigger UI update
            logSelect.dispatchEvent(new Event('change'));

            // Respond in chat
            if (data.status === 'success') {
                lastCompiledCode = data.code;
                lastFidelity = data.fidelity || 0;
                runIbmBtn.disabled = false;
                ibmStatus.textContent = 'Ready for cloud execution';
                ibmStatus.style.color = '#10b981';
                
                const message = `✅ Success! I have successfully compiled the circuit preserving the hardware topology. The code and graphs are available in the tabs on the right.`;
                addMessage('assistant', `${message} <br><br>Let me know if you want to modify this circuit.`);
                const backendName = backendSelector.value.replace('Fake', '').replace('IBM', 'IBM ');
                announce(`Compilation successful on backend ${backendName}. The fidelity is ${Math.round((data.fidelity || 0) * 100)} percent.`);
            } else {
                const message = `❌ Compilation failed.<br><br>Details:<br>${data.message || 'Check the Terminal/Logs for details.'}`;
                addMessage('assistant', message);
                announce(`The compilation failed during the verification phase. Please check the logs.`);
            }

        } catch (err) {
            console.error(err);
            terminalOutput.textContent += `\n\nERROR: Fetch failed - ${err.message}`;
            addMessage('assistant', '⚠️ Connecting to backend failed. Make sure the FastAPI server is running.');
            announce('Connection to the backend failed.');
        } finally {
            userInput.disabled = false;
            sendBtn.disabled = false;
            sendBtn.innerHTML = 'Compile';
            userInput.focus();
        }
    };

    // Events
    sendBtn.addEventListener('click', processRequest);
    
    runIbmBtn.addEventListener('click', async () => {
        if (!lastCompiledCode) return;
        
        tabs[0].click(); // target terminal
        terminalOutput.textContent += `\n\n=== ☁️ IBM QUANTUM EXECUTION ===\n`;
        terminalOutput.textContent += `Routing to IBM Cloud... (Mode: ${ibmModeSelector.value})\n`;
        terminalOutput.scrollTop = terminalOutput.scrollHeight;
        
        runIbmBtn.disabled = true;
        runIbmBtn.innerHTML = '<span class="spinner" style="border-top-color: #fff;"></span>';
        ibmStatus.textContent = 'Requesting cloud resources...';
        ibmStatus.style.color = '#f59e0b';
        
        try {
            const resp = await fetch('/api/run_ibm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: lastCompiledCode,
                    mode: ibmModeSelector.value,
                    local_fidelity: lastFidelity
                })
            });
            const ibmData = await resp.json();
            
            if (ibmData.error) {
                terminalOutput.textContent += `\n❌ IBM Request Failed:\n${ibmData.error}\n`;
                ibmStatus.textContent = 'Execution Failed';
                ibmStatus.style.color = '#ef4444';
                runIbmBtn.disabled = false;
                runIbmBtn.innerHTML = 'Execute on IBM';
                return;
            } 
            
            const jobId = ibmData.job_id;
            terminalOutput.textContent += `\n🚀 Job Submitted! ID: ${jobId}\n`;
            ibmStatus.textContent = 'Job in IBM Queue...';
            
            // Poll for status
            let pollCount = 0;
            const pollInterval = setInterval(async () => {
                pollCount++;
                try {
                    const statusResp = await fetch(`/api/ibm_status/${jobId}`);
                    const statusData = await statusResp.json();
                    
                    if (statusData.error) {
                        clearInterval(pollInterval);
                        terminalOutput.textContent += `\n❌ Status Check Failed: ${statusData.error}\n`;
                        ibmStatus.textContent = 'Status Error';
                        ibmStatus.style.color = '#ef4444';
                        runIbmBtn.disabled = false;
                        runIbmBtn.innerHTML = 'Execute on IBM';
                        return;
                    }

                    const jobData = statusData.data;
                    ibmStatus.textContent = `Status: ${jobData.status || 'Checking...'}`;
                    terminalOutput.textContent += `[Polling ${pollCount}] Status: ${jobData.status}\n`;
                    terminalOutput.scrollTop = terminalOutput.scrollHeight;

                    if (jobData.success === true) {
                        clearInterval(pollInterval);
                        terminalOutput.textContent += `\n✅ IBM Hardware Returned Results!\n`;
                        terminalOutput.textContent += `Backend Used: ${jobData.backend}\n`;
                        terminalOutput.textContent += `Job ID: ${jobId}\n\n`;
                        
                        // Print visual histogram
                        terminalOutput.textContent += `Measurement Counts:\n`;
                        terminalOutput.textContent += `-------------------\n`;
                        const maxVal = Math.max(...Object.values(jobData.counts));
                        for (const [state, count] of Object.entries(jobData.counts)) {
                            let pct = Math.round((count / (jobData.shots || 100)) * 100);
                            let barLen = Math.round((count / maxVal) * 30);
                            let bar = "█".repeat(barLen);
                            terminalOutput.textContent += ` |${state}⟩ ${bar} ${count} (${pct}%)\n`;
                        }
                        
                        if (jobData.real_fidelity !== undefined) {
                            terminalOutput.textContent += `\n============================================================\n`;
                            terminalOutput.textContent += ` 🚀 CLOUD DEPLOYMENT VERIFICATION (CONSTRAINT CHECK)\n`;
                            terminalOutput.textContent += `============================================================\n`;
                            terminalOutput.textContent += ` Local Simulated Fidelity : ${jobData.local_fidelity.toFixed(4)}\n`;
                            terminalOutput.textContent += ` Real Hardware Fidelity   : ${jobData.real_fidelity.toFixed(4)}\n`;
                            const diff = jobData.real_fidelity - jobData.local_fidelity;
                            if (diff > 0) {
                                terminalOutput.textContent += ` Outcome: ✅ Improved by ${Math.abs(diff).toFixed(4)}\n`;
                            } else {
                                terminalOutput.textContent += ` Outcome: ⚠️ Degraded by ${Math.abs(diff).toFixed(4)}\n`;
                            }
                            terminalOutput.textContent += `============================================================\n\n`;

                            // Also append a visual card to the Visualizations tab below the graphs
                            const diffText = diff > 0 ? `<span style="color:#10b981;">Improved by ${Math.abs(diff).toFixed(4)}</span>` : `<span style="color:#ef4444;">Degraded by ${Math.abs(diff).toFixed(4)}</span>`;
                            const visGrid = document.getElementById('visualsGrid');
                            const fidelityCard = document.createElement('div');
                            fidelityCard.className = 'visual-card';
                            fidelityCard.style.padding = '20px';
                            fidelityCard.style.display = 'flex';
                            fidelityCard.style.flexDirection = 'column';
                            fidelityCard.style.justifyContent = 'center';
                            fidelityCard.style.background = 'linear-gradient(135deg, rgba(37,99,235,0.1), rgba(0,0,0,0.5))';
                            fidelityCard.innerHTML = `
                                <h3 style="margin-bottom: 15px; color:#60a5fa; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px;">☁️ Cloud Deployment Fidelity</h3>
                                <div style="display:flex; justify-content: space-between; margin-bottom: 10px; font-size: 1.1em;">
                                    <span>🖥️ Local Sim:</span>
                                    <strong style="color: #cbd5e1;">${jobData.local_fidelity.toFixed(4)}</strong>
                                </div>
                                <div style="display:flex; justify-content: space-between; margin-bottom: 10px; font-size: 1.1em;">
                                    <span>⚛️ IBM Hardware:</span>
                                    <strong style="color: #cbd5e1;">${jobData.real_fidelity.toFixed(4)}</strong>
                                </div>
                                <div style="display:flex; justify-content: space-between; margin-top: 15px; font-weight: bold; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 15px;">
                                    <span>Outcome:</span>
                                    ${diffText}
                                </div>
                            `;
                            if (visGrid) {
                                visGrid.appendChild(fidelityCard);
                            }
                        }
                        
                        resultsOutput.textContent += '\n\n// --- IBM EXECUTION SUCCESS ---\n' + JSON.stringify(jobData, null, 2);
                        ibmStatus.textContent = 'Execution Completed';
                        ibmStatus.style.color = '#10b981';
                        
                        runIbmBtn.disabled = false;
                        runIbmBtn.innerHTML = 'Execute on IBM';
                    } else if (jobData.status === 'ERROR') {
                        clearInterval(pollInterval);
                        terminalOutput.textContent += `\n❌ IBM Job Failed:\n${jobData.error}\n`;
                        ibmStatus.textContent = 'Execution Failed';
                        ibmStatus.style.color = '#ef4444';
                        runIbmBtn.disabled = false;
                        runIbmBtn.innerHTML = 'Execute on IBM';
                    }
                    
                } catch (err) {
                    terminalOutput.textContent += `\n⚠️ Polling Error: ${err.message}\n`;
                }
            }, 8000); // Poll every 8 seconds

        } catch (err) {
            terminalOutput.textContent += `\n❌ Network Error reaching backend:\n${err.message}\n`;
            ibmStatus.textContent = 'Network Error';
            ibmStatus.style.color = '#ef4444';
            runIbmBtn.disabled = false;
            runIbmBtn.innerHTML = 'Execute on IBM';
        }
    });

    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            processRequest();
        }
    });
});
