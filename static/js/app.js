// this is start of code
document.addEventListener('DOMContentLoaded', function () {
  $('#playSound').on('click', function () {
    const audioCtx = new (
      window.AudioContext || window.webkitAudioContext
    )();

    authentication()

    const oscillator = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();

    const waveforms = ['sine', 'square', 'sawtooth', 'triangle'];
    const randomWaveform =
      waveforms[Math.floor(Math.random() * waveforms.length)];
    const randomFrequency =
      Math.floor(Math.random() * (1200 - 200 + 1)) + 200;

    oscillator.type = randomWaveform;
    oscillator.frequency.setValueAtTime(
      randomFrequency,
      audioCtx.currentTime,
    );

    gainNode.gain.setValueAtTime(0.5, audioCtx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(
      0.0001,
      audioCtx.currentTime + 0.5,
    );

    oscillator.connect(gainNode);
    gainNode.connect(audioCtx.destination);

    oscillator.start();
    oscillator.stop(audioCtx.currentTime + 0.5);
  });


});

function clearClickablePlant() {
  const speciesName = document.getElementById('speciesName');
  if (speciesName) {
    speciesName.classList.remove('clickable-plant');
    speciesName.onclick = null;
  }
}

window.addEventListener('DOMContentLoaded', () => {
  const statusFidgetSpinner = document.getElementById(
    'statusFidgetSpinner',
  );
  let audioContext = null;

  function playBellChime() {
    if (!statusFidgetSpinner) return;

    if (!audioContext) {
      const AudioCtor = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtor) return;
      audioContext = new AudioCtor();
    }

    if (audioContext.state === 'suspended') {
      audioContext.resume().catch(() => { });
    }

    const now = audioContext.currentTime;
    const baseFreq = 420 + Math.random() * 180;
    const notes = [
      baseFreq,
      baseFreq * (1.25 + Math.random() * 0.1),
      baseFreq * (1.6 + Math.random() * 0.12),
    ];

    notes.forEach((freq, index) => {
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      oscillator.type = index === 0 ? 'triangle' : 'sine';
      oscillator.frequency.setValueAtTime(freq, now + index * 0.04);
      gainNode.gain.setValueAtTime(0.0001, now + index * 0.04);
      gainNode.gain.exponentialRampToValueAtTime(
        0.05 + Math.random() * 0.02,
        now + index * 0.04 + 0.015,
      );
      gainNode.gain.exponentialRampToValueAtTime(
        0.0001,
        now + index * 0.04 + 0.18,
      );

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      oscillator.start(now + index * 0.04);
      oscillator.stop(now + index * 0.04 + 0.2);
    });

    statusFidgetSpinner.classList.remove('is-ringing');
    void statusFidgetSpinner.offsetWidth;
    statusFidgetSpinner.classList.add('is-ringing');
    statusFidgetSpinner.setAttribute('aria-pressed', 'true');
  }

  if (statusFidgetSpinner) {
    statusFidgetSpinner.addEventListener('click', playBellChime);

    statusFidgetSpinner.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        statusFidgetSpinner.click();
      }
    });
  }

  let vantaEffect = null;
  try {
    if (typeof VANTA !== 'undefined') {
      vantaEffect = VANTA.NET({
        el: '#vanta-canvas',
        mouseControls: false,
        touchControls: false,
        gyroControls: false,
        minHeight: 200.0,
        minWidth: 200.0,
        scale: 1.0,
        scaleMobile: 0.85,
        color: 0x10b981,
        backgroundColor: 0x06110d,
        points: 8.0,
        maxDistance: 18.0,
        spacing: 18.0,
      });
    }
  } catch (e) {
    console.warn('Vanta initialization fallback:', e);
  }

  window.addEventListener('resize', () => {
    if (vantaEffect) vantaEffect.resize();
  });

  // App Loader Animation
  const pageLoader = document.getElementById('pageLoader');
  const appContent = document.getElementById('appContent');
  const loaderSubtext = document.getElementById('loaderSubtext');

  const statusPhrases = [
    { time: 0, text: 'Initializing Sprout...' },
    { time: 800, text: 'Loading Neural Networks...' },
    { time: 1600, text: 'Preparing Interface...' },
    { time: 2200, text: 'Ready!' },
  ];

  statusPhrases.forEach((phase) => {
    setTimeout(() => {
      if (loaderSubtext) loaderSubtext.textContent = phase.text;
    }, phase.time);
  });

  setTimeout(() => {
    if (pageLoader) {
      pageLoader.style.opacity = '0';
      setTimeout(() => pageLoader.remove(), 500);
    }
    if (appContent) appContent.style.opacity = '1';
  }, 2500);

  // Web Worker Mode Integration
  let worker = null;
  let isOfflineMode = false;
  let isWorkerReady = false;

  const offlineToggle = document.getElementById('offlineToggle');
  const modeIcon = document.getElementById('modeIcon');
  const modeLabel = document.getElementById('modeLabel');

  const candidates = [
    './worker.js',
    './static/worker.js',
    './templates/worker.js',
  ];

  const initWorker = async () => {
    if (state.worker) return;

    let workerPath = './worker.js';

    for (const candidate of candidates) {
      try {
        const response = await fetch(candidate, { method: 'HEAD', cache: 'no-store' });
        if (response.ok) {
          workerPath = candidate;
          break;
        }
      } catch (e) { }
    }

    state.worker = new Worker(workerPath);

    state.worker.onmessage = (e) => {
      if (e.data.type === 'RESULT') handleResult(e.data.data, true);
    };

    state.worker.postMessage({ type: 'INIT_OFFLINE' });
  };


  const words = [
    'Thanks for your patience! ⏳',
    'Just a second now...⏱️',
    'Sprout waves! 🍃',
    'Engines running... 🛠️',
  ];
  let index = 0;
  let textRotationInterval = null;

  const $loaderContainer = $('<div>')
    .attr('id', 'dynamic-loader-text')
    .addClass(
      'hidden text-xl font-medium text-gray-700 flex flex-col items-center justify-center gap-2 mt-4',
    );

  const $rotatingText = $('<span>')
    .addClass(
      'text-indigo-600 transition-opacity duration-300 opacity-100',
    )
    .text(words[index]);

  $loaderContainer.append($rotatingText);
  $('#loading').append($loaderContainer);
  $('#loadingOverlay').hide();

  async function initOfflineWorker() {
    if (worker) {
      worker.postMessage({ type: 'INIT_OFFLINE' });
      return;
    }

    const workerScript = await resolveWorkerScript();
    worker = new Worker(workerScript);

    worker.onmessage = (e) => {
      const { type, message, data, value } = e.data;

      if (type === 'STATUS') {
        if (pestStatus) $(pestStatus).text(message);
      } else if (type === 'READY') {
        isWorkerReady = true;
        if (pestStatus)
          $(pestStatus).text(
            'Offline model ready. You can identify plants without a network connection.',
          );
      } else if (type === 'RESULT') {
        handleOfflineResult(data);
      } else if (type === 'ERROR') {
        showMessageModal({
          title: 'Offline issue',
          message:
            message || 'The offline model could not finish the request.',
          iconClass: 'fa-solid fa-triangle-exclamation',
        });
      } else if (type === 'PROGRESS') {
        const downloadProgress = value;

        if (downloadProgress === 0.5) {
          if ($('#page-overlay').length === 0) {
            $('body').append('<div id="page-overlay"></div>');
            $('#page-overlay').css({
              position: 'fixed',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              background: 'rgba(0, 0, 0, 0.4)',
              'z-index': 99999,
              cursor: 'not-allowed',
            });
          }
          $('#loading').fadeIn();
          $loaderContainer.removeClass('hidden');
          $rotatingText
            .text(words[0])
            .removeClass('opacity-0')
            .addClass('opacity-100');
          index = 0;

          if (!textRotationInterval) {
            textRotationInterval = setInterval(function () {
              $rotatingText
                .removeClass('opacity-100')
                .addClass('opacity-0');
              setTimeout(function () {
                index = (index + 1) % words.length;
                $rotatingText
                  .text(words[index])
                  .removeClass('opacity-0')
                  .addClass('opacity-100');
              }, 300);
            }, 2500);
          }
        } else if (downloadProgress === 1.0) {
          if (textRotationInterval) {
            clearInterval(textRotationInterval);
            textRotationInterval = null;
          }
          $('#page-overlay').remove();
          $loaderContainer.addClass('hidden');
          $('#loading').fadeOut();
        }
      }
    };

    worker.postMessage({ type: 'INIT_OFFLINE' });
  }

  // UI Event Listener
  $(offlineToggle).on('change', (e) => {
    new Audio(
      'https://raw.githubusercontent.com/RanukaDinsitha/Quickly/main/sounds/button.mp3',
    ).play();
    isOfflineMode = e.target.checked;
    const $modeIcon = $(modeIcon);
    const $modeLabel = $(modeLabel);

    /*         $(".audioBtn").play();
     */
    if (isOfflineMode) {
      $modeIcon
        .html(
          `<div style="display: flex; align-items: center; gap: 4px;">
      <img src="https://raw.githubusercontent.com/RanukaDinsitha/Quickly/main/images/wifi_slash.svg"
           alt="offline"
           style="width: 1.2em; height: auto; vertical-align: middle; margin-right: -2px; display: inline-block;"></div>`,
        )
        .removeAttr('class', 'fa-solid fa-wifi text-emerald-400');
      $modeLabel
        .text('Offline')
        .removeClass('text-slate-300')
        .addClass('text-amber-400');

      initOfflineWorker();
    } else {
      $modeIcon
        .text('')
        .attr('class', 'fa-solid fa-wifi text-emerald-400');

      $modeLabel
        .text('Online')
        .removeClass('text-amber-400')
        .addClass('text-slate-300');

      if (pestStatus) {
        $(pestStatus).html(
          'Offline mode is now inactive. Switch back on when you want local inference.',
        );
      }
    }
  }); // Matches your original wrapper closure
  // Modal Helpers
  const openHelpBtn = document.getElementById('openHelpBtn');
  const closeHelpBtn = document.getElementById('closeHelpBtn');
  const dismissHelpBtn = document.getElementById('dismissHelpBtn');
  const helpModal = document.getElementById('helpModal');
  const helpModalCard = document.getElementById('helpModalCard');

  function openHelpModal() {
    if (!helpModal || !helpModalCard) return;
    helpModal.classList.add('active');
    setTimeout(() => {
      helpModalCard.classList.remove('scale-95');
      helpModalCard.classList.add('scale-100');
    }, 10);
  }

  function closeHelpModal() {
    if (!helpModal || !helpModalCard) return;
    helpModalCard.classList.remove('scale-100');
    helpModalCard.classList.add('scale-95');
    setTimeout(() => {
      helpModal.classList.remove('active');
    }, 200);
  }

  if (openHelpBtn) openHelpBtn.addEventListener('click', openHelpModal);
  if (closeHelpBtn)
    closeHelpBtn.addEventListener('click', closeHelpModal);
  if (dismissHelpBtn)
    dismissHelpBtn.addEventListener('click', closeHelpModal);
  if (helpModal) {
    helpModal.addEventListener('click', (e) => {
      if (e.target === helpModal) closeHelpModal();
    });
  }

  // History Modal Handlers
  const openHistoryBtn = document.getElementById('openHistoryBtn');
  const closeHistoryBtn = document.getElementById('closeHistoryBtn');
  const dismissHistoryBtn = document.getElementById('dismissHistoryBtn');
  const historyModal = document.getElementById('historyModal');
  const historyModalCard = document.getElementById('historyModalCard');
  const historyList = document.getElementById('historyList');
  const clearHistoryBtn = document.getElementById('clearHistoryBtn');

  function openHistoryModal() {
    if (!historyModal || !historyModalCard) return;
    renderHistoryList();
    historyModal.classList.add('active');
    setTimeout(() => {
      historyModalCard.classList.remove('scale-95');
      historyModalCard.classList.add('scale-100');
    }, 10);
  }

  function closeHistoryModal() {
    if (!historyModal || !historyModalCard) return;
    historyModalCard.classList.remove('scale-100');
    historyModalCard.classList.add('scale-95');
    setTimeout(() => {
      historyModal.classList.remove('active');
    }, 200);
  }

  function getHistory() {
    try {
      const rawHistory =
        JSON.parse(localStorage.getItem('sprout_history')) || [];
      return rawHistory.map((item) => {
        if (typeof item === 'string') {
          return { name: item, date: 'Recent Scan', image: null };
        }
        return item;
      });
    } catch (e) {
      return [];
    }
  }

  function saveToHistory(item) {
    let history = getHistory();
    const itemForStorage = { ...item, lat: null, lng: null };
    history.unshift(itemForStorage);
    if (history.length > 20) history = history.slice(0, 20);
    localStorage.setItem('sprout_history', JSON.stringify(history));
  }

  function clearHistory() {
    localStorage.removeItem('sprout_history');
    renderHistoryList();
  }

  function renderHistoryList() {
    if (!historyList) return;
    const history = getHistory();
    if (history.length === 0) {
      historyList.innerHTML = `
                                <div class="text-center py-8 text-slate-400">
                                  <i class="fa-solid fa-seedling text-3xl mb-2 text-slate-600 block"></i>
                                  <p class="text-xs">No plant scans in your history yet.</p>
                                </div>
                              `;
      return;
    }

    historyList.innerHTML = history
      .map(
        (item, idx) => `
                              <div class="flex items-center gap-3 bg-white/5 hover:bg-white/10 p-3 rounded-xl border border-white/5 transition">
                                <div class="flex-shrink-0 cursor-pointer" onclick="window.open('https://www.google.com/search?q=${encodeURIComponent(item.name)}', '_blank')">
                                  ${item.image
            ? `<img src="${item.image}" alt="${item.name}" class="w-12 h-12 object-cover rounded-lg border border-emerald-500/20" />`
            : `<div class="w-12 h-12 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400"><i class="fa-solid fa-leaf"></i></div>`
          }
                                </div>
                                <div class="min-w-0 flex-1 cursor-pointer" onclick="window.open('https://www.google.com/search?q=${encodeURIComponent(item.name)}', '_blank')">
                                  <h4 class="text-sm font-bold text-white truncate">${item.name}</h4>
                                  <p class="text-[10px] text-slate-400 mt-0.5">${item.date || 'Recent Scan'}</p>
                                  ${item.lat && item.lng
            ? `<p class="text-[10px] text-emerald-400/80 mt-0.5"><i class="fa-solid fa-location-dot text-[9px]"></i> ${Number(item.lat).toFixed(4)}, ${Number(item.lng).toFixed(4)}</p>`
            : `<p class="text-[10px] text-slate-600 mt-0.5"><i class="fa-solid fa-location-dot text-[9px]"></i> No location</p>`
          }
                                </div>
                                <div class="flex items-center gap-2 flex-shrink-0">
                                  ${item.lat && item.lng
            ? `<button
                                        class="w-8 h-8 rounded-full bg-emerald-500/10 border border-emerald-500/25 hover:bg-emerald-500/25 text-emerald-400 hover:text-emerald-300 flex items-center justify-center transition"
                                        title="View on map"
                                        onclick="openSinglePlantMap(${idx})"
                                      >
                                        <i class="fa-solid fa-map-location-dot text-xs"></i>
                                      </button>`
            : `<div class="w-8 h-8 flex items-center justify-center text-slate-700" title="No location data"><i class="fa-solid fa-location-slash text-xs"></i></div>`
          }
                                  <button class="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 text-slate-400 hover:text-emerald-400 flex items-center justify-center transition" onclick="window.open('https://www.google.com/search?q=${encodeURIComponent(item.name)}', '_blank')" title="Search plant">
                                    <i class="fa-solid fa-arrow-up-right-from-square text-xs"></i>
                                  </button>
                                </div>
                              </div>
                            `,
      )
      .join('');
  }

  if (openHistoryBtn)
    openHistoryBtn.addEventListener('click', openHistoryModal);
  if (closeHistoryBtn)
    closeHistoryBtn.addEventListener('click', closeHistoryModal);
  if (dismissHistoryBtn)
    dismissHistoryBtn.addEventListener('click', closeHistoryModal);
  if (clearHistoryBtn)
    clearHistoryBtn.addEventListener('click', clearHistory);
  if (historyModal) {
    historyModal.addEventListener('click', (e) => {
      if (e.target === historyModal) closeHistoryModal();
    });
  }

  let sproutMap = null;
  let sproutMapInitialized = false;

  const mapModal = document.getElementById('mapModal');
  const mapModalCard = document.getElementById('mapModalCard');
  const mapModalTitle = document.getElementById('mapModalTitle');
  const mapModalSub = document.getElementById('mapModalSubtitle');
  const closeMapBtn = document.getElementById('closeMapBtn');
  const openAllMapBtn = document.getElementById('openAllMapBtn');

  function openMapModal(focusItem) {
    if (!mapModal) return;
    mapModal.classList.add('active');

    setTimeout(() => {
      mapModalCard.classList.remove('scale-95');
      mapModalCard.classList.add('scale-100');
    }, 10);

    setTimeout(() => {
      initSproutMap();
      if (sproutMap) {
        sproutMap.resize();
      }

      const history = getHistory();
      const geoItems = history.filter(
        (h) =>
          h.lat !== undefined &&
          h.lng !== undefined &&
          h.lat !== null &&
          h.lng !== null,
      );

      if (
        focusItem &&
        focusItem.lat !== undefined &&
        focusItem.lng !== undefined
      ) {
        mapModalTitle.textContent = focusItem.name;
        mapModalSub.textContent = `${Number(focusItem.lat).toFixed(5)}, ${Number(focusItem.lng).toFixed(5)}`;
      } else {
        mapModalTitle.textContent = 'Map';
        mapModalSub.textContent = `${geoItems.length} location${geoItems.length !== 1 ? 's' : ''} recorded`;
      }

      populateMapMarkers(history, focusItem);
    }, 150);
  }

  function closeMapModal() {
    if (!mapModal) return;
    mapModalCard.classList.remove('scale-100');
    mapModalCard.classList.add('scale-95');
    setTimeout(() => {
      mapModal.classList.remove('active');
    }, 220);
  }

  function initSproutMap() {
    if (sproutMapInitialized) return;

    // TODO old
    // sproutMap = new maplibregl.Map({
    //   container: 'plantMap',
    //   style: 'https://demotiles.maplibre.org/style.json',
    //   center: [174.7645, -36.8509], // [Lng, Lat]
    //   zoom: 5,
    // });

    sproutMap = new maplibregl.Map({
      container: 'plantMap',
      style: 'https://tiles.openfreemap.org/styles/bright',
      center: [174.7762, -41.2866],
      zoom: 5
    });

    sproutMap.on('load', () => {
      sproutMap.resize();
      if (!sproutMap.getSource('plants')) {
        sproutMap.addSource('plants', {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: [] },
        });

        sproutMap.addLayer({
          id: 'plants-circle',
          type: 'circle',
          source: 'plants',
          paint: {
            'circle-radius': 14,
            'circle-color': '#10b981',
            'circle-stroke-width': 2.5,
            'circle-stroke-color': '#fff',
            'circle-opacity': 0.92,
          },
        });

        sproutMap.addLayer({
          id: 'plants-label',
          type: 'symbol',
          source: 'plants',
          layout: {
            'text-field': '🌿',
            'text-size': 14,
            'text-allow-overlap': true,
          },
        });

        sproutMap.on('click', 'plants-circle', (e) => {
          const props = e.features[0].properties;
          const coords = e.features[0].geometry.coordinates.slice();
          const imgHtml = props.image
            ? `<img src="${props.image}" style="width:100%;height:90px;object-fit:cover;border-radius:10px 10px 0 0;display:block;" />`
            : '';
          const confHtml = props.confidence
            ? `<span style="background:rgba(16,185,129,0.18);color:#34d399;border:1px solid rgba(16,185,129,0.3);border-radius:999px;padding:1px 8px;font-size:9px;font-weight:700;letter-spacing:.04em;">${props.confidence}</span>`
            : '';
          const popupHtml = `
                                    <div style="font-family:'Inter',sans-serif;min-width:170px;max-width:210px;border-radius:14px;overflow:hidden;">
                                      ${imgHtml}
                                      <div style="padding:10px 13px 12px;">
                                        <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:4px;">
                                          <h5 style="margin:0;font-size:13px;font-weight:800;color:#10b981;line-height:1.2;">${props.name}</h5>
                                          ${confHtml}
                                        </div>
                                        <p style="margin:0 0 3px;font-size:10px;color:#94a3b8;">
                                          <i class="fa-solid fa-calendar-days" style="margin-right:3px;"></i>${props.date || 'Recent Scan'}
                                        </p>
                                        <p style="margin:0;font-size:10px;color:#64748b;">
                                          <i class="fa-solid fa-location-dot" style="margin-right:3px;color:#10b981;"></i>${Number(coords[1]).toFixed(5)}, ${Number(coords[0]).toFixed(5)}
                                        </p>
                                      </div>
                                    </div>`;
          new maplibregl.Popup({ maxWidth: '520px', maxHeight: '400px' }) //height: 520px; width:400px
            .setLngLat(coords)
            .setHTML(popupHtml)
            .addTo(sproutMap);
        });

        sproutMap.on('mouseenter', 'plants-circle', () => {
          sproutMap.getCanvas().style.cursor = 'pointer';
        });
        sproutMap.on('mouseleave', 'plants-circle', () => {
          sproutMap.getCanvas().style.cursor = '';
        });
      }

      sproutMapInitialized = true;
      if (window._pendingMapData) {
        const { history, focusItem } = window._pendingMapData;
        window._pendingMapData = null;
        _applyMapMarkers(history, focusItem);
      }
    });
  }

  function _applyMapMarkers(history, focusItem) {
    if (!sproutMap || !sproutMap.getSource('plants')) return;

    const geoItems = history.filter(
      (h) =>
        h.lat !== undefined &&
        h.lng !== undefined &&
        h.lat !== null &&
        h.lng !== null,
    );

    const features = geoItems.map((item) => ({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [Number(item.lng), Number(item.lat)],
      },
      properties: {
        name: item.name,
        confidence: item.confidence || null,
        date: item.date || 'Recent Scan',
        image: item.image || null,
      },
    }));

    sproutMap.getSource('plants').setData({
      type: 'FeatureCollection',
      features,
    });

    if (features.length === 0) return;

    if (
      focusItem &&
      focusItem.lat !== undefined &&
      focusItem.lng !== undefined
    ) {
      sproutMap.flyTo({
        center: [Number(focusItem.lng), Number(focusItem.lat)],
        zoom: 14,
      });
    } else if (features.length === 1) {
      sproutMap.flyTo({
        center: features[0].geometry.coordinates,
        zoom: 14,
      });
    } else {
      const lngs = features.map((f) => f.geometry.coordinates[0]);
      const lats = features.map((f) => f.geometry.coordinates[1]);
      const bounds = [
        [Math.min(...lngs), Math.min(...lats)],
        [Math.max(...lngs), Math.max(...lats)],
      ];
      sproutMap.fitBounds(bounds, { padding: 60, maxZoom: 14 });
    }
  }

  function populateMapMarkers(history, focusItem) {
    if (!sproutMapInitialized || !sproutMap.getSource('plants')) {
      window._pendingMapData = { history, focusItem };
      return;
    }
    _applyMapMarkers(history, focusItem);
  }

  window.openSinglePlantMap = function (idx) {
    const history = getHistory();
    const item = history[idx];
    if (!item) return;
    closeHistoryModal();
    setTimeout(() => openMapModal(item), 250);
  };

  if (openAllMapBtn) {
    openAllMapBtn.addEventListener('click', () => {
      closeHistoryModal();
      setTimeout(() => openMapModal(null), 250);
    });
  }
  if (closeMapBtn) closeMapBtn.addEventListener('click', closeMapModal);
  if (mapModal) {
    mapModal.addEventListener('click', (e) => {
      if (e.target === mapModal) closeMapModal();
    });
  }

  let userLocation = null;

  // Tab Controller
  const tabUpload = document.getElementById('tabUpload');
  const tabCamera = document.getElementById('tabCamera');
  const uploadSection = document.getElementById('uploadSection');
  const cameraSection = document.getElementById('cameraSection');

  if (tabUpload && tabCamera) {
    tabUpload.addEventListener('click', () => {
      tabUpload.classList.add('active');
      tabCamera.classList.remove('active');
      if (uploadSection) uploadSection.classList.remove('hidden');
      if (cameraSection) cameraSection.classList.add('hidden');
    });

    tabCamera.addEventListener('click', () => {
      tabCamera.classList.add('active');
      tabUpload.classList.remove('active');
      if (cameraSection) cameraSection.classList.remove('hidden');
      if (uploadSection) uploadSection.classList.add('hidden');
    });
  }

  const startCameraBtn = document.getElementById('startCameraBtn');
  const capturePhotoBtn = document.getElementById('capturePhotoBtn');
  const cameraVideo = document.getElementById('cameraVideo');
  const cameraOverlay = document.getElementById('cameraOverlay');
  const uploadDropzone = document.getElementById('uploadDropzone');
  const plantImage = document.getElementById('plantImage');
  const previewContainer = document.getElementById('previewContainer');
  const previewImage = document.getElementById('previewImage');
  const changePhotoBtn = document.getElementById('changePhotoBtn');
  const speciesName = document.getElementById('speciesName');
  const pestStatus = document.getElementById('pestStatus');
  const statusIcon = document.getElementById('statusIcon');
  const extendedDetailsCard = document.getElementById(
    'extendedDetailsCard',
  );
  const extendedDetailsText = document.getElementById(
    'extendedDetailsText',
  );
  const treatmentSection = document.getElementById('treatmentSection');
  const treatmentText = document.getElementById('treatmentText');
  const controlSection = document.getElementById('controlSection');
  const controlText = document.getElementById('controlText');
  const analyzeButton = document.getElementById('analyzeButton');
  const analyzeIcon = document.getElementById('analyzeIcon');
  const analyzeBtnText = document.getElementById('analyzeBtnText');

  const hazardBadge = document.getElementById('hazardBadge');
  const hazardIcon = document.getElementById('hazardIcon');
  const hazardLabel = document.getElementById('hazardLabel');

  const plantTypeBadge = document.getElementById('plantTypeBadge');
  const plantTypeIcon = document.getElementById('plantTypeIcon');
  const plantTypeLabel = document.getElementById('plantTypeLabel');

  const consentOverlay = document.getElementById('consentOverlay');
  const consentTitle = document.getElementById('consentTitle');
  const consentBody = document.getElementById('consentBody');
  const consentStatusText = document.getElementById('consentStatusText');
  const consentAllowBtn = document.getElementById('consentAllowBtn');
  const consentDeclineBtn = document.getElementById('consentDeclineBtn');
  const consentStateKey = 'sprout-identification-consent';
  const locationPromptOverlay = document.getElementById(
    'locationPromptOverlay',
  );
  const locationAllowBtn = document.getElementById('locationAllowBtn');
  const locationDeclineBtn =
    document.getElementById('locationDeclineBtn');
  const locationPromptStatus = document.getElementById(
    'locationPromptStatus',
  );
  const messageModal = document.getElementById('messageModal');
  const messageModalTitle = document.getElementById('messageModalTitle');
  const messageModalBody = document.getElementById('messageModalBody');
  const messageModalIcon = document.getElementById('messageModalIcon');
  const messageModalIconInner = document.getElementById(
    'messageModalIconInner',
  );
  const messageModalOkBtn = document.getElementById('messageModalOkBtn');

  let cameraStream = null;
  let selectedFile = null;
  let identificationConsentGranted = false;
  let pendingIdentificationAfterConsent = false;

  function releaseConsentOverlay() {
    if (consentOverlay) {
      consentOverlay.classList.remove('active');
    }
    if (appContent) {
      appContent.style.opacity = '1';
      appContent.style.pointerEvents = 'auto';
    }
  }

  function showMessageModal({
    title,
    message,
    iconClass = 'fa-solid fa-circle-info',
    confirmText = 'Continue',
  }) {
    if (
      !messageModal ||
      !messageModalTitle ||
      !messageModalBody ||
      !messageModalIcon ||
      !messageModalIconInner ||
      !messageModalOkBtn
    ) {
      return;
    }

    messageModalTitle.textContent = title || 'Just a quick note';
    messageModalBody.textContent = message || 'Everything is ready.';
    messageModalIconInner.className = `${iconClass} text-xl`;
    messageModalOkBtn.textContent = confirmText;
    messageModal.classList.add('active');
  }

  function closeMessageModal() {
    if (messageModal) {
      messageModal.classList.remove('active');
    }
  }

  if (messageModalOkBtn) {
    messageModalOkBtn.addEventListener('click', closeMessageModal);
  }
  if (messageModal) {
    messageModal.addEventListener('click', (event) => {
      if (event.target === messageModal) {
        closeMessageModal();
      }
    });
  }

  function showLocationPrompt() {
    if (!locationPromptOverlay) return;
    locationPromptOverlay.classList.add('active');
    if (appContent) {
      appContent.style.opacity = '0.35';
      appContent.style.pointerEvents = 'none';
    }
  }

  function hideLocationPrompt() {
    if (locationPromptOverlay) {
      locationPromptOverlay.classList.remove('active');
    }
    if (appContent) {
      appContent.style.opacity = '1';
      appContent.style.pointerEvents = 'auto';
    }
  }
  if (locationAllowBtn) {
    locationAllowBtn.addEventListener('click', () => {
      if ('geolocation' in navigator) {
        getLocation();
      }
      hideLocationPrompt();
    });
  }

  if (locationDeclineBtn) {
    locationDeclineBtn.addEventListener('click', () => {
      hideLocationPrompt();
    });
  }

  if (locationPromptOverlay) {
    locationPromptOverlay.addEventListener('click', (event) => {
      if (event.target === locationPromptOverlay) {
        hideLocationPrompt();
      }
    });
  }

  function showConsentOverlay(state, message) {
    if (
      !consentOverlay ||
      !consentTitle ||
      !consentBody ||
      !consentStatusText
    ) {
      return;
    }

    consentOverlay.classList.add('active');
    if (appContent) {
      appContent.style.opacity = '0.35';
      appContent.style.pointerEvents = 'none';
    }

    if (state === 'declined') {
      consentTitle.textContent = 'Identification paused';
      consentBody.textContent =
        message ||
        'You can keep using the app without identifying a plant. Start again whenever you want.';
      consentStatusText.textContent = 'Location stays optional.';
    } else {
      consentTitle.textContent = 'Agree to identify your plant';
      consentBody.textContent =
        message ||
        "This app uses experimental technology. Your image will be sent to a server for processing, and results may not always be accurate. By pressing 'Yes', you consent to this process.";
      consentStatusText.textContent = 'Location stays optional.';
    }
  }

  function handleConsentAllow() {
    identificationConsentGranted = true;
    try {
      window.sessionStorage.setItem(consentStateKey, 'accepted');
    } catch (err) {
      console.warn('Could not persist consent state:', err);
    }
    releaseConsentOverlay();
    if (pendingIdentificationAfterConsent && analyzeButton) {
      pendingIdentificationAfterConsent = false;
      analyzeButton.click();
    }
  }

  function handleConsentDecline() {
    identificationConsentGranted = false;
    try {
      window.sessionStorage.setItem(consentStateKey, 'declined');
    } catch (err) {
      console.warn('Could not persist consent state:', err);
    }
    releaseConsentOverlay();
    showMessageModal({
      title: 'Identification paused',
      message:
        'You can keep using the app without identifying a plant. Start again whenever you want.',
      iconClass: 'fa-solid fa-circle-info',
    });
  }

  if (consentAllowBtn) {
    consentAllowBtn.addEventListener('click', handleConsentAllow);
  }
  if (consentDeclineBtn) {
    consentDeclineBtn.addEventListener('click', handleConsentDecline);
  }

  setTimeout(() => {
    if (pageLoader) {
      pageLoader.style.opacity = '0';
      pageLoader.style.display = 'none';
    }
    if (appContent) {
      appContent.style.opacity = '1';
      appContent.style.pointerEvents = 'auto';
    }
    showLocationPrompt();
  }, 2500);

  function updateHazardBadge(type) {
    if (!hazardBadge || !hazardIcon || !hazardLabel) return;

    hazardBadge.className = 'hazard-badge';

    switch (type) {
      case 'poisonous':
        hazardBadge.classList.add('hazard-poisonous');
        hazardIcon.className = 'fa-solid fa-skull-crossbones';
        hazardLabel.textContent = 'Poisonous';
        break;
      case 'prickly':
        hazardBadge.classList.add('hazard-prickly');
        hazardIcon.className = 'fa-solid fa-triangle-exclamation';
        hazardLabel.textContent = 'Sharp / Prickly';
        break;
      case 'deadly':
        hazardBadge.classList.add('hazard-deadly');
        hazardIcon.className = 'fa-solid fa-biohazard';
        hazardLabel.textContent = 'Deadly / Toxic';
        break;
      case 'safe':
      default:
        hazardBadge.classList.add('hazard-safe');
        hazardIcon.className = 'fa-solid fa-shield-heart';
        hazardLabel.textContent = 'Harmless / Low Risk';
        break;
    }

    hazardBadge.classList.remove('hidden');
  }

  function updatePlantTypeBadge(category) {
    if (!plantTypeBadge || !plantTypeIcon || !plantTypeLabel) return;

    const catLower = (category || '').toLowerCase();
    const isWeed =
      catLower.includes('weed') ||
      catLower.includes('pest') ||
      catLower.includes('invasive');

    if (isWeed) {
      plantTypeBadge.className = 'hazard-badge badge-weed';
      plantTypeIcon.className = 'fa-solid fa-ban text-xs';
      plantTypeLabel.textContent = 'WEED';
    } else {
      plantTypeBadge.className = 'hazard-badge badge-plant';
      plantTypeIcon.className = 'fa-solid fa-seedling text-xs';
      plantTypeLabel.textContent = 'PLANT';
    }

    plantTypeBadge.classList.remove('hidden');
  }

  if (uploadDropzone && plantImage) {
    uploadDropzone.addEventListener('click', () => {
      plantImage.click();
    });

    ['dragenter', 'dragover'].forEach((eventName) => {
      uploadDropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadDropzone.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
      uploadDropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadDropzone.classList.remove('drag-over');
      });
    });

    uploadDropzone.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files && files.length > 0) {
        handleFileSelect(files[0]);
      }
    });
  }

  if (plantImage) {
    plantImage.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        handleFileSelect(e.target.files[0]);
      }
    });
  }

  function handleFileSelect(file) {
    if (!file.type.startsWith('image/')) {
      showMessageModal({
        title: 'Image needed',
        message: 'Please choose a valid image file to continue.',
        iconClass: 'fa-solid fa-image',
      });
      return;
    }
    selectedFile = file;
    const reader = new FileReader();
    reader.onload = (e) => {
      displayPreview(e.target.result);
    };
    reader.readAsDataURL(file);
  }

  function displayPreview(imageSrc) {
    if (previewImage) previewImage.src = imageSrc;
    if (uploadSection) uploadSection.classList.add('hidden');
    if (cameraSection) cameraSection.classList.add('hidden');
    if (previewContainer) previewContainer.classList.remove('hidden');
    stopCamera();
  }

  function getLocation() {
    const locationOptions = {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0,
    };

    function handleSingleLocation(position) {
      const lat = position.coords.latitude;
      const lon = position.coords.longitude;
      userLocation = { lat: lat, lng: lon };
    }

    function handleLocationError(error) {
      console.error(`Error (${error.code}): ${error.message}`);
    }

    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        handleSingleLocation,
        handleLocationError,
        locationOptions,
      );
    } else {
      showMessageModal({
        title: 'Location optional',
        message:
          'Geolocation is not available here, but identification can still continue without it.',
        iconClass: 'fa-solid fa-location-crosshairs',
      });
    }
  }

  function resetPhotoSelection() {
    selectedFile = null;

    if (previewImage) previewImage.src = '';
    if (previewContainer) previewContainer.classList.add('hidden');
    if (extendedDetailsCard) extendedDetailsCard.classList.add('hidden');
    if (hazardBadge) hazardBadge.classList.add('hidden');
    if (plantTypeBadge) plantTypeBadge.classList.add('hidden');
    if (treatmentSection) treatmentSection.classList.add('hidden');
    if (controlSection) controlSection.classList.add('hidden');

    clearClickablePlant();
    if (speciesName) speciesName.textContent = 'Waiting for your photo!';
    if (pestStatus)
      pestStatus.innerHTML =
        'Upload or capture a picture of a plant and <b>Sprout</b> will tell you what it is.';

    if (tabUpload && tabUpload.classList.contains('active')) {
      if (uploadSection) uploadSection.classList.remove('hidden');
    } else {
      if (cameraSection) cameraSection.classList.remove('hidden');
    }
  }

  if (changePhotoBtn) {
    changePhotoBtn.addEventListener('click', resetPhotoSelection);
  }

  async function startCamera() {
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false,
      });
      if (cameraVideo) {
        cameraVideo.srcObject = cameraStream;
      }
      if (cameraOverlay) cameraOverlay.classList.add('hidden');
    } catch (err) {
      showMessageModal({
        title: 'Camera access needed',
        message:
          'Please allow camera access so you can take a photo for identification.',
        iconClass: 'fa-solid fa-camera',
      });
      console.error(err);
    }
  }

  function stopCamera() {
    if (cameraStream) {
      cameraStream.getTracks().forEach((track) => track.stop());
      cameraStream = null;
    }
    if (cameraOverlay) cameraOverlay.classList.remove('hidden');
  }

  if (startCameraBtn)
    startCameraBtn.addEventListener('click', startCamera);

  if (capturePhotoBtn) {
    capturePhotoBtn.addEventListener('click', () => {
      if (!cameraStream || !cameraVideo) {
        showMessageModal({
          title: 'Camera not ready',
          message: 'Turn on the camera first, then capture a photo.',
          iconClass: 'fa-solid fa-video',
        });
        return;
      }
      const canvas = document.createElement('canvas');
      canvas.width = cameraVideo.videoWidth || 640;
      canvas.height = cameraVideo.videoHeight || 480;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(cameraVideo, 0, 0, canvas.width, canvas.height);

      const dataUrl = canvas.toDataURL('image/jpeg');
      displayPreview(dataUrl);

      fetch(dataUrl)
        .then((res) => res.blob())
        .then((blob) => {
          selectedFile = new File([blob], 'camera_snapshot.jpg', {
            type: 'image/jpeg',
          });
        });
    });
  }

  async function sendLocationData(lat, lng, itemName) {
    const url = 'https://sproutboy.pythonanywhere.com/location';
    const payload = {
      item_name: itemName || 'Unknown Plant',
      lat: lat,
      lng: lng,
    };
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Basic ' + btoa('sprout:1667'),
        },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      console.log('Location saved:', result);
    } catch (error) {
      console.error('Error sending location:', error);
    }
  }

  async function extractImageData() {
    const size = 224;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });

    if (!previewImage) {
      throw new Error('No preview image is available yet.');
    }

    if (!previewImage.complete) {
      await new Promise((resolve) => {
        previewImage.onload = resolve;
        previewImage.onerror = resolve;
      });
    }

    ctx.drawImage(previewImage, 0, 0, size, size);
    const imgData = ctx.getImageData(0, 0, size, size).data;
    const totalPixels = size * size;
    const float32Array = new Float32Array(3 * totalPixels);

    const MEAN = [0.485, 0.456, 0.406];
    const STD = [0.229, 0.224, 0.225];

    for (let i = 0; i < imgData.length; i += 4) {
      const pixelIndex = i / 4;
      float32Array[pixelIndex] = (imgData[i] / 255.0 - MEAN[0]) / STD[0];
      float32Array[totalPixels + pixelIndex] =
        (imgData[i + 1] / 255.0 - MEAN[1]) / STD[1];
      float32Array[2 * totalPixels + pixelIndex] =
        (imgData[i + 2] / 255.0 - MEAN[2]) / STD[2];
    }

    return Array.from(float32Array);
  }

  function handleOfflineResult(data) {
    const confidencePercent = data.confidence
      ? `${(Number(data.confidence) * 100).toFixed(1)}%`
      : 'High';
    const identifiedPlant = {
      name: data.name || 'Offline Plant Scan',
      confidence: confidencePercent,
      summary: `Identified plant in ${data.duration.toFixed(1)}ms using your device’s browser runtime; unable to fetch description and other details in offline mode`,
      hazardType: 'safe',
      date: new Date().toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }),
      image: previewImage ? previewImage.src : null,
      lat: userLocation ? userLocation.lat : null,
      lng: userLocation ? userLocation.lng : null,
    };

    if (speciesName) {
      speciesName.textContent = identifiedPlant.name;
      speciesName.classList.add('clickable-plant');
      speciesName.onclick = () =>
        window.open(
          `https://www.google.com/search?q=${encodeURIComponent(identifiedPlant.name)}`,
          '_blank',
        );
    }
    if (pestStatus) {
      pestStatus.textContent = `The engine identified the photo as a ${identifiedPlant.name} with a ${identifiedPlant.confidence} confidence rate.`;
    }
    if (extendedDetailsText) {
      extendedDetailsText.textContent = identifiedPlant.summary;
      if (extendedDetailsCard)
        extendedDetailsCard.classList.remove('hidden');
    }

    updatePlantTypeBadge(data.category || 'Plant');
    updateHazardBadge(identifiedPlant.hazardType);
    saveToHistory(identifiedPlant);

    if (analyzeButton) analyzeButton.disabled = false;
    if (analyzeIcon)
      analyzeIcon.className = 'fa-solid fa-sparkles text-xs';
    if (analyzeBtnText) analyzeBtnText.textContent = 'Identify Plant';
  }

  if (analyzeButton) {
    analyzeButton.addEventListener('click', async () => {
      const savedConsent = window.sessionStorage.setItem
        ? window.sessionStorage.getItem(consentStateKey)
        : null;
      if (savedConsent !== 'accepted') {
        pendingIdentificationAfterConsent = true;
        if (consentOverlay) {
          showConsentOverlay(
            'prompt',
            'This app uses experimental technology and is not to be used alone. You are responsible for the choices you make.',
          );
        }
        return;
      }

      identificationConsentGranted = true;
      analyzeButton.disabled = true;
      if (analyzeIcon)
        analyzeIcon.className = 'fa-solid fa-spinner fa-spin text-xs';
      if (analyzeBtnText)
        analyzeBtnText.textContent = 'Analyzing Plant...';
      if (speciesName)
        speciesName.textContent = 'Scanning plant details...';
      if (pestStatus)
        pestStatus.textContent = 'Extracting botanical features...';
      if (hazardBadge) hazardBadge.classList.add('hidden');
      if (plantTypeBadge) plantTypeBadge.classList.add('hidden');
      if (treatmentSection) treatmentSection.classList.add('hidden');
      if (controlSection) controlSection.classList.add('hidden');
      let modalOpened = false;
      const warmupCheckInterval = setInterval(function () {
        const needsWarmup =
          !isWorkerReady &&
          (analyzeButton.disabled === false || isOfflineMode);

        if (needsWarmup) {
          if (!modalOpened) {
            modalOpened = true;

            showMessageModal({
              title: 'Still warming up',
              message:
                'The offline model is still warming up. Please wait a moment and try again.',
              iconClass: '',
            });

            setTimeout(function () {
              const $loader = $('<div class="loader"></div>');
              $('#messageModalIcon, .swal2-icon').replaceWith($loader);
              $loader.css({
                margin: '0 auto 20px auto',
              });
            }, 50);
          }
        } else {
          clearInterval(warmupCheckInterval);

          if (modalOpened) {
            if (
              typeof Swal !== 'undefined' &&
              Swal.isVisible &&
              Swal.isVisible()
            ) {
              Swal.close();
            }
            $(
              '.swal2-container, .modal, .modal-backdrop, .swal2-popup, #messageModal',
            ).hide();
            $('body').removeClass('modal-open swal2-shown');
          }
        }
      }, 300);

      try {
        const formData = new FormData();

        if (selectedFile) {
          formData.append('file', selectedFile);
          formData.append('image', selectedFile);
        } else if (previewImage && previewImage.src) {
          const res = await fetch(previewImage.src);
          const blob = await res.blob();
          const file = new File([blob], 'plant.jpg', {
            type: 'image/jpeg',
          });
          formData.append('file', file);
          formData.append('image', file);
        }

        const response = await fetch(
          'https://sproutboy.pythonanywhere.com/predict',
          {
            method: 'POST',
            body: formData,
          },
        );

        if (!response.ok) {
          let bodyText = '';
          try {
            bodyText = await response.text();
          } catch (e) {
            // ignore
          }
          console.error(
            `Predict request failed: HTTP ${response.status}`,
            bodyText,
          );
          throw new Error(
            `Server returned HTTP ${response.status}${bodyText ? ` — ${bodyText.slice(0, 200)}` : ''}`,
          );
        }

        const apiData = await response.json();

        console.log(apiData);

        const plantName =
          apiData.class ||
          apiData.plant_name ||
          apiData.name ||
          apiData.label ||
          'Unknown Plant';

        let confidence = 'High confidence';
        if (apiData.confidence !== undefined) {
          const confVal = parseFloat(apiData.confidence);
          confidence =
            confVal <= 1
              ? `${(confVal * 100).toFixed(1)}%`
              : `${confVal.toFixed(1)}%`;
        } else if (apiData.probability !== undefined) {
          const probVal = parseFloat(apiData.probability);
          confidence =
            probVal <= 1
              ? `${(probVal * 100).toFixed(1)}%`
              : `${probVal.toFixed(1)}%`;
        }

        const category = apiData.category || '';
        const toxicity = apiData.toxicity || '';
        const poisonType = apiData.poison_type || '';
        const symptoms = apiData.symptoms || '';
        const treatment = apiData.poison_treatment || '';
        const control = apiData.control || '';

        let summaryParts = [];
        if (category) summaryParts.push(`Category: ${category}.`);
        if (toxicity && toxicity !== 'N/A')
          summaryParts.push(`Toxicity: ${toxicity}.`);
        if (poisonType && poisonType !== 'N/A')
          summaryParts.push(`Poison type: ${poisonType}.`);
        if (symptoms && symptoms !== 'N/A')
          summaryParts.push(`Symptoms: ${symptoms}.`);

        const summary =
          apiData.summary ||
          apiData.description ||
          (summaryParts.length > 0
            ? summaryParts.join(' ')
            : 'No detailed summary available for this species.');

        let hazardType = 'safe';
        const toxLower = toxicity.toLowerCase();
        if (
          toxLower.includes('highly toxic') ||
          toxLower.includes('deadly')
        ) {
          hazardType = 'deadly';
        } else if (
          toxLower.includes('toxic') ||
          toxLower.includes('poisonous')
        ) {
          hazardType = 'poisonous';
        } else if (
          toxLower.includes('irritant') ||
          toxLower.includes('mildly')
        ) {
          hazardType = 'prickly';
        }

        const identifiedPlant = {
          name: plantName,
          confidence: confidence,
          summary: summary,
          hazardType: hazardType,
          date: new Date().toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          }),
          image: previewImage ? previewImage.src : null,
          lat: userLocation ? userLocation.lat : null,
          lng: userLocation ? userLocation.lng : null,
        };

        if (speciesName) {
          speciesName.textContent = identifiedPlant.name;
          speciesName.classList.add('clickable-plant');
          speciesName.onclick = () =>
            window.open(
              `https://www.google.com/search?q=${encodeURIComponent(identifiedPlant.name)}`,
              '_blank',
            );
        }
        if (pestStatus) {
          const categoryLabel = category ? ` — ${category}` : '';
          pestStatus.textContent = `Sprout's engine identified the plant as ${identifiedPlant.name} it is a ${categoryLabel} and confidence is ${identifiedPlant.confidence}.`;
        }

        // Set summary and HTML treatment/control fields explicitly on the UI
        if (extendedDetailsText) {
          extendedDetailsText.textContent = identifiedPlant.summary;
          if (extendedDetailsCard)
            extendedDetailsCard.classList.remove('hidden');
        }

        if (treatment && treatment !== 'N/A' && treatmentText) {
          treatmentText.textContent = treatment;
          treatmentSection.classList.remove('hidden');
        }

        if (control && control !== 'N/A' && controlText) {
          controlText.textContent = control;
          controlSection.classList.remove('hidden');
        }

        updatePlantTypeBadge(category);
        updateHazardBadge(identifiedPlant.hazardType);
        saveToHistory(identifiedPlant);

        if (userLocation) {
          sendLocationData(userLocation.lat, userLocation.lng, plantName);
        }
      } catch (err) {
        console.error('Identification Error:', err);
        if (speciesName)
          speciesName.textContent = 'Identification Failed';
        if (pestStatus)
          pestStatus.textContent = `Unable to process the image right now (${err.message || 'unknown error'}). Please try again or switch back to offline mode.`;
      } finally {
        analyzeButton.disabled = false;
        if (analyzeIcon)
          analyzeIcon.className = 'fa-solid fa-sparkles text-xs';
        if (analyzeBtnText) analyzeBtnText.textContent = 'Identify Plant';
      }
    });
  }
});

