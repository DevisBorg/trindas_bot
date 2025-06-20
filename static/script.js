// static/script.js
let selectedGuildId = null; let socket = null; let state = {}; let sortableInstance = null; let volumeDebounceTimer = null; let progressUpdateInterval = null;

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('/api/me');
        if (!response.ok) throw new Error('Não autenticado');
        const data = await response.json();
        showUserInfo(data.user, data.guilds);
    } catch (error) { showLoginButton(); }
    setupControls();
});

function showLoginButton() { document.getElementById('user-info').innerHTML = '<a href="/login"><button>Login com Discord</button></a>';}
function showUserInfo(user, guilds) {
    document.getElementById('user-info').innerHTML = `<span>Logado como: <strong>${user.username}</strong></span>`;
    const guildSelect = document.getElementById('guild-select');
    guildSelect.innerHTML = '<option>-- Selecione um Servidor --</option>';
    guilds.forEach(g => guildSelect.innerHTML += `<option value="${g.id}">${g.name}</option>`);
    document.getElementById('dashboard-content').style.display = 'block';
}

document.getElementById('guild-select').addEventListener('change', () => {
    selectedGuildId = document.getElementById('guild-select').value;
    if (socket) socket.close();
    if (!selectedGuildId.includes('--')) connectWebSocket();
});

function connectWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(`${wsProtocol}//${window.location.host}/ws/${selectedGuildId}`);
    socket.onopen = () => fetchQueue();
    socket.onmessage = (event) => { state = JSON.parse(event.data); updateUI(); };
    socket.onerror = (error) => console.error('WebSocket Error:', error);
}

async function fetchQueue() {
    const response = await fetch(`/api/guilds/${selectedGuildId}/queue`);
    state = await response.json(); updateUI();
}

function formatDuration(seconds) {
    if (seconds === null || isNaN(seconds) || seconds < 0) return "00:00";
    return new Date(seconds * 1000).toISOString().substr(14, 5);
}

function updateUI() {
    if (progressUpdateInterval) clearInterval(progressUpdateInterval);

    const art = document.getElementById('current-song-art');
    const title = document.getElementById('current-song-title');
    const requester = document.getElementById('current-song-requester');
    const progressTime = document.getElementById('progress-time');
    const totalTime = document.getElementById('total-time');
    const progressBar = document.getElementById('progress-bar-foreground');
    const playPauseBtnIcon = document.querySelector('#play-pause-btn i');
    const loopBtn = document.getElementById('loop-btn');
    const volumeSlider = document.getElementById('volume-slider');

    if (state.current_song) {
        art.src = state.current_song.thumbnail || 'https://i.imgur.com/gse3cPC.png';
        title.textContent = state.current_song.title;
        requester.textContent = `Pedida por: ${state.current_song.requester}`;
        totalTime.textContent = formatDuration(state.current_song.duration);
        let elapsed = state.elapsed;
        progressTime.textContent = formatDuration(elapsed);
        progressBar.style.width = state.current_song.duration > 0 ? `${(elapsed / state.current_song.duration) * 100}%` : '0%';
        if (!state.is_paused) {
            progressUpdateInterval = setInterval(() => {
                elapsed += 1;
                const current_duration = state.current_song ? state.current_song.duration : 0;
                if (elapsed > current_duration) elapsed = current_duration;
                progressTime.textContent = formatDuration(elapsed);
                progressBar.style.width = current_duration > 0 ? `${(elapsed / current_duration) * 100}%` : '0%';
            }, 1000);
        }
    } else {
        art.src = 'https://i.imgur.com/gse3cPC.png';
        title.textContent = 'Nenhuma música tocando';
        requester.textContent = 'Adicione uma música pelo Discord ou por aqui!';
        progressTime.textContent = "00:00"; totalTime.textContent = "00:00"; progressBar.style.width = '0%';
    }
    
    playPauseBtnIcon.className = `fas ${state.is_paused ? 'fa-play' : 'fa-pause'}`;
    loopBtn.classList.toggle('active', state.loop_mode !== 'off');
    loopBtn.innerHTML = `<i class="fas ${state.loop_mode === 'song' ? 'fa-redo-alt' : 'fa-repeat'}"></i>`;
    if (document.activeElement !== volumeSlider) { volumeSlider.value = state.volume; }

    const queueList = document.getElementById('queue-list');
    const scrollPosition = queueList.scrollTop;
    queueList.innerHTML = '';
    state.queue.forEach((song, index) => {
        const li = document.createElement('li');
        li.className = 'queue-item'; li.dataset.index = index;
        li.innerHTML = `
            <span class="queue-item-drag-handle"><i class="fas fa-bars"></i></span>
            <div class="queue-item-title"><strong>${song.title}</strong><br><small>Pedida por: ${song.requester}</small></div>
            <button class="remove-btn" title="Remover">&times;</button>
        `;
        queueList.appendChild(li);
    });
    queueList.scrollTop = scrollPosition;

    if (sortableInstance) sortableInstance.destroy();
    sortableInstance = new Sortable(queueList, {
        animation: 150, handle: '.queue-item-drag-handle',
        onEnd: (evt) => {
            fetch(`/api/guilds/${selectedGuildId}/queue/move`, {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ old_index: evt.oldIndex, new_index: evt.newIndex }),
            });
        }
    });
}

function setupControls() {
    const controlsMap = {'shuffle-btn': 'shuffle', 'prev-btn': 'previous', 'play-pause-btn': 'pause-resume', 'skip-btn': 'skip', 'loop-btn': 'toggle-loop', 'leave-btn': 'leave'};
    for (const [btnId, action] of Object.entries(controlsMap)) {
        document.getElementById(btnId).addEventListener('click', () => {
            if (!selectedGuildId) return alert('Selecione um servidor.');
            fetch(`/api/guilds/${selectedGuildId}/control/${action}`, { method: 'POST' });
        });
    }
    const volumeSlider = document.getElementById('volume-slider');
    volumeSlider.addEventListener('input', () => {
        clearTimeout(volumeDebounceTimer);
        volumeDebounceTimer = setTimeout(() => {
            if (!selectedGuildId) return;
            fetch(`/api/guilds/${selectedGuildId}/volume`, {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ volume: parseInt(volumeSlider.value) }),
            });
        }, 250);
    });
    const queueList = document.getElementById('queue-list');
    queueList.addEventListener('click', (event) => {
        const target = event.target;
        const queueItem = target.closest('.queue-item');
        if (!queueItem) return;
        const index = queueItem.dataset.index;
        if (target.closest('.remove-btn')) {
            fetch(`/api/guilds/${selectedGuildId}/remove`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ index: parseInt(index) })});
        } else if (target.closest('.queue-item-title')) {
            fetch(`/api/guilds/${selectedGuildId}/skipto`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ index: parseInt(index) })});
        }
    });
    const addSongBtn = document.getElementById('add-song-btn');
    const songQueryInput = document.getElementById('song-query-input');
    addSongBtn.addEventListener('click', () => {
        const query = songQueryInput.value;
        if (!query) return alert('Digite o nome ou link de uma música.');
        if (!selectedGuildId) return alert('Selecione um servidor primeiro.');
        fetch(`/api/guilds/${selectedGuildId}/play`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ query: query })});
        songQueryInput.value = '';
    });
    songQueryInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') { event.preventDefault(); addSongBtn.click(); }
    });
}