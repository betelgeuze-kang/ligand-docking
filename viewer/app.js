const DEFAULT_BUNDLE_PATH = '/runs/selected_allatom_visual_bundle_current.json';
const DEFAULT_BUNDLE_CATALOG_PATH = '/runs/selected_allatom_visual_bundle_catalog_current.json';
const DEFAULT_GALLERY_PATH = '/runs/selected_allatom_visual_gallery_current.html';
const DEFAULT_ENGINE_BLOCKER_QUEUE_PATH = '/runs/local_engine_commercialization_queue_current.json';
const DEFAULT_VIEWER_SMOKE_REFRESH_PATH = '/runs/viewer_smoke_refresh_current.json';
const DEFAULT_VIEWER_SMOKE_REFRESH_MD_PATH = '/runs/viewer_smoke_refresh_current.md';
const DEFAULT_VIEWER_SMOKE_INDEX_MD_PATH = '/runs/viewer_smoke_index_current.md';
const DEFAULT_WETLAB_MASTER_HANDOFF_PATH = '/runs/wetlab_master_handoff_dashboard_current.json';
const DEFAULT_WETLAB_READINESS_QUEUE_PATH = '/runs/wetlab_execution_readiness_queue_current.json';
const DEFAULT_METRICS = [
    'mean_min_distance_A',
    'binding_energy_proxy',
    'contact_fraction',
    'commercial_overall_score_v2',
];
const COMPARE_CONSOLE_METRICS = [
    { key: 'mean_min_distance_A', label: 'Mean Min Distance', unit: 'A', precision: 3, direction: 'lower' },
    { key: 'binding_energy_proxy', label: 'Binding Energy', unit: 'proxy', precision: 3, direction: 'lower' },
    { key: 'contact_fraction', label: 'Contact Fraction', unit: '', precision: 3, direction: 'higher' },
    { key: 'stability_score', label: 'Stability', unit: '', precision: 3, direction: 'higher' },
    { key: 'commercial_overall_score_v2', label: 'Commercial v2', unit: '', precision: 1, direction: 'higher' },
    { key: 'trajectory_frames', label: 'Trajectory Frames', unit: 'frames', precision: 0, direction: 'higher' },
];
const COMPARE_RESULTS_EXPLORER_FIELDS = [
    { label: 'Translation', value: (candidate) => firstTruthy(candidate?.translationGateStatus, 'not_reported') },
    { label: 'Shortlist', value: (candidate) => firstTruthy(candidate?.shortlistTier, 'not_reported') },
    { label: 'Next Lane', value: (candidate) => firstTruthy(candidate?.recommendedLane, 'not_reported') },
    { label: 'Render', value: (candidate) => describeTrajectoryRenderMode(candidate) },
    { label: 'Ligand Update', value: (candidate) => describeTrajectoryUpdateMode(candidate) },
    { label: 'Protein Color', value: (candidate) => describeProteinFrameColorMode(candidate) },
    { label: 'BVH Path', value: (candidate) => describePocketBvhPath(candidate) },
    { label: 'BVH Query', value: (candidate) => describePocketBvhQuery(candidate) },
];
const CUSTOMER_REPORT_REQUIRED_BLOCKS = [
    'binding_site_explanation',
    'pose_comparison',
    'interaction_rationale',
    'uncertainty_narrative',
    'scope_claim_limit',
    'counterfactual_rescue_suggestion',
];
const INTERACTION_KIND_META = {
    hbond: { label: 'H-bond', shortLabel: 'HB', color: '#38bdf8' },
    pipi: { label: 'Pi-Pi', shortLabel: 'Pi', color: '#c084fc' },
    hydrophobic: { label: 'Hydrophobic', shortLabel: 'Hyd', color: '#f59e0b' },
    contact: { label: 'Contact', shortLabel: 'Ct', color: '#94a3b8' },
};
const FALLBACK_BUNDLE_PRESETS = [
    {
        surfaceLabel: 'protein_atom_frames_smoke',
        targetId: 'Protein Motion Smoke',
        bundlePath: '/runs/viewer_protein_atom_smoke/protein_atom_frames_smoke_bundle_current.json',
    },
    {
        surfaceLabel: 'tcruzi_pde_allatom_review_packet',
        targetId: 'T. cruzi PDE',
        bundlePath: '/runs/selected_allatom_visual_bundle_tcruzi_pde_current.json',
    },
    {
        surfaceLabel: 'cathepsin_k_allatom_review_packet',
        targetId: 'Cathepsin K',
        bundlePath: '/runs/selected_allatom_visual_bundle_cathepsin_k_current.json',
    },
    {
        surfaceLabel: 'sarscov2_mpro_allatom_review_packet',
        targetId: 'SARS-CoV-2 Mpro',
        bundlePath: '/runs/selected_allatom_visual_bundle_sarscov2_mpro_current.json',
    },
];
const VIEWER_SESSION_STORAGE_KEY = 'md_dynamics_viewer_session_v2';

const state = {
    viewer: null,
    compareViewers: { A: null, B: null },
    viewerMode: 'single',
    viewerRenderTicket: 0,
    bundlePayload: null,
    bundleSummary: null,
    candidates: [],
    selectedIndex: -1,
    compareSlots: { A: null, B: null },
    trajectoryTimer: null,
    trajectoryFrameIndex: 0,
    selectedTrajectoryCandidateIndex: -1,
    localFilesByBasename: new Map(),
    localFilesByPath: new Map(),
    localObjectUrls: [],
    activePreviewUrl: '',
    lastSnapshotDataUri: '',
    surfacePresets: [],
    activeSurfaceLabel: '',
    activeBundleSourceLabel: '',
    annotationExpanded: false,
    lastPlaybackPanelRefreshAt: 0,
    measurementMode: '',
    measurementPicks: [],
    measurementRecords: [],
    measurementClickSub: null,
    measurementBusy: false,
    interactionOverlayFrame: 0,
    autoInteractionSegments: [],
    overlayInteractionSegments: new Map(),
    residueHighlightRef: '',
    residueHighlightTimer: 0,
    localFocusOverlay: null,
    localFocusOverlayTimer: 0,
    trajectorySceneMode: 'reference',
    bindingFocusTicket: 0,
    cameraUserLocked: false,
    suppressSessionPersist: false,
    pendingViewerState: null,
    smokePreset: '',
    smokeState: { enabled: false, status: 'idle', checks: {}, message: '' },
    blockerSurface: {
        queue: null,
        viewerSmoke: null,
        wetlabDashboard: null,
        wetlabReadiness: null,
        loadError: '',
    },
    writebackCompare: {
        beforePayload: null,
        beforeSummary: null,
        beforeCandidates: [],
        beforeSourceLabel: '',
        pairs: [],
        selectedPairKey: '',
    },
};

const dom = {};

document.addEventListener('DOMContentLoaded', async () => {
    cacheDom();
    state.smokePreset = getRequestedSmokePreset();
    setSessionStateBadge('session: idle', 'muted');
    setSmokeStateBadge('smoke: idle', 'muted');
    setSmokeState('idle', {}, 'viewer initialized');
    await initBundlePresets();
    bindStaticUi();
    const blockerSurfacePromise = loadCurrentBlockerSurface();

    try {
        await initViewer();
        await tryAutoLoadInitialBundle();
    } catch (error) {
        console.error(error);
        toast(`초기화 실패: ${error.message}`, 'error');
    }

    if (window.location.protocol === 'file:') {
        toast('권장 실행 방식: repo 루트에서 `python3 -m http.server` 후 브라우저로 viewer/index.html 열기', 'warn');
    }

    await blockerSurfacePromise;
});

function cacheDom() {
    const ids = [
        'btnLoadCurrentBundle',
        'bundleSurfaceSelect',
        'btnLoadSurfaceBundle',
        'btnLoadBundle',
        'btnLoadWritebackBefore',
        'btnUseCurrentAsWritebackAfter',
        'btnClearWritebackCompare',
        'btnLoadPDB',
        'btnLoadDir',
        'btnOpenGallery',
        'btnCopyPermalink',
        'btnSaveSession',
        'btnRestoreSession',
        'sessionStateBadge',
        'smokeStateBadge',
        'opsSurfaceStrip',
        'engineQueueBadge',
        'viewerUsabilityBadge',
        'wetlabExecutionBadge',
        'btnSnapshot',
        'btnThemeToggle',
        'bundleInput',
        'writebackBeforeInput',
        'fileInput',
        'dirInput',
        'fileList',
        'searchBox',
        'bundleStatus',
        'infoPanel',
        'structInfo',
        'reprSelect',
        'colorSelect',
        'bgSelect',
        'aoPresetSelect',
        'toggleSpin',
        'togglePocketSurface',
        'toggleElectroSurface',
        'toggleFog',
        'btnFocusBinding',
        'btnMeasureDist',
        'btnMeasureAngle',
        'btnMeasureDihedral',
        'btnClearMeasure',
        'measurementStatus',
        'measurementList',
        'interactionLegend',
        'viewerContainer',
        'viewerOverlay',
        'compareSplitLayout',
        'compareViewerA',
        'compareViewerB',
        'compareViewerATitle',
        'compareViewerBTitle',
        'interactionOverlay',
        'viewerAnnotationLayer',
        'sceneGuidePanel',
        'annotationPanel',
        'annotationDetailGrid',
        'annotationStrip',
        'btnToggleAnnotations',
        'annotationHero',
        'annotationContact',
        'annotationTranslation',
        'annotationBlockers',
        'trajSlider',
        'trajFrameLabel',
        'btnTrajPlay',
        'btnTrajPause',
        'trajSpeed',
        'trajectoryBar',
        'trajectoryStatusNote',
        'chartsSection',
        'metricSelect',
        'chartsGrid',
        'slotA',
        'slotB',
        'btnSuperpose',
        'btnSideBySide',
        'compareConsoleStatus',
        'compareWritebackSource',
        'compareBeforeAfter',
        'compareDiffMatrix',
        'compareDecisionBoard',
        'rmsdResult',
        'bindingSection',
        'bindingInfo',
        'ligand2D',
        'contactMap',
        'pocketVolumeDisplay',
        'residueContactHeatmap',
        'residueContactMeta',
        'sequenceSummary',
        'sequenceViewer',
        'bindingRecipeList',
        'mediaSection',
        'mediaPreview',
        'figurePreview',
        'videoPreview',
        'mediaEmpty',
        'mediaStatus',
        'mediaMeta',
        'btnOpenFigure',
        'btnFigureModal',
        'btnOpenMovie',
        'btnOpenDashboard',
        'snapshotRes',
        'snapshotFormat',
        'snapshotTransparent',
        'blockerSurfacePanel',
        'blockerSurfaceStatus',
        'blockerSurfaceSummary',
        'blockerSurfaceGrid',
        'quickStats',
        'kpiMiniGrid',
        'snapshotModal',
        'btnCloseModal',
        'snapshotImage',
        'btnDownloadSnapshot',
        'btnCopySnapshot',
        'figureModal',
        'btnCloseFigureModal',
        'figureModalImage',
        'figureModalCaption',
        'btnOpenFigureFromModal',
        'toastContainer',
        'molstarViewer',
    ];

    for (const id of ids) dom[id] = document.getElementById(id);
}

async function initBundlePresets() {
    let presets = FALLBACK_BUNDLE_PRESETS.map((entry) => ({ ...entry }));
    try {
        const catalog = await fetchJson(DEFAULT_BUNDLE_CATALOG_PATH);
        const catalogRows = Array.isArray(catalog?.rows) ? catalog.rows : [];
        if (catalogRows.length) {
            const catalogPresets = catalogRows.map((row) => ({
                surfaceLabel: firstTruthy(row.surface_label),
                targetId: firstTruthy(row.target_id),
                bundlePath: firstTruthy(row.bundle_json),
                bundleReady: toBool(row.bundle_ready, true),
            })).filter((entry) => entry.surfaceLabel && entry.bundlePath);
            const merged = new Map();
            for (const entry of presets.concat(catalogPresets)) {
                const key = normalizeSurfaceLabelKey(entry.surfaceLabel);
                if (!key || merged.has(key)) continue;
                merged.set(key, entry);
            }
            presets = Array.from(merged.values());
        }
    } catch (_error) {
        // fallback presets are sufficient when the catalog is not present yet.
    }

    state.surfacePresets = presets;
    renderSurfacePresetOptions();
}

function renderSurfacePresetOptions() {
    const options = ['<option value="">Surface 선택</option>'].concat(
        state.surfacePresets.map((entry) => `
            <option value="${escapeHtml(entry.surfaceLabel)}">
              ${escapeHtml(entry.targetId)} · ${escapeHtml(entry.surfaceLabel)}
            </option>
        `),
    );
    dom.bundleSurfaceSelect.innerHTML = options.join('');
}

function normalizeSurfaceLabelKey(value) {
    return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
}

function getRequestedSurfaceLabel() {
    try {
        const params = new URLSearchParams(window.location.search);
        return String(params.get('surface-label') || params.get('surface') || '').trim();
    } catch (_error) {
        return '';
    }
}

function getRequestedSmokePreset() {
    try {
        const params = new URLSearchParams(window.location.search);
        return String(params.get('smoke') || '').trim().toLowerCase();
    } catch (_error) {
        return '';
    }
}

function getRequestedViewerState() {
    try {
        const params = new URLSearchParams(window.location.search);
        const surfaceLabel = String(params.get('surface-label') || params.get('surface') || '').trim();
        const ligandId = String(params.get('ligand') || params.get('candidate') || '').trim();
        const packetRank = toInt(params.get('rank'), NaN);
        const frameIndex = toInt(params.get('frame'), NaN);
        const sceneMode = String(params.get('scene') || '').trim();
        const compareA = String(params.get('compareA') || '').trim();
        const compareB = String(params.get('compareB') || '').trim();
        const repr = String(params.get('repr') || '').trim();
        const color = String(params.get('color') || '').trim();
        const bg = String(params.get('bg') || '').trim();
        const ao = String(params.get('ao') || '').trim();
        if (!surfaceLabel && !ligandId && !Number.isFinite(packetRank) && !Number.isFinite(frameIndex) && !sceneMode && !compareA && !compareB && !repr && !color && !bg && !ao) {
            return null;
        }
        return {
            surfaceLabel,
            ligandId,
            packetRank,
            frameIndex,
            sceneMode,
            compareA,
            compareB,
            repr,
            color,
            bg,
            ao,
            pocketSurface: toNullableBool(params.get('pocket')),
            electroSurface: toNullableBool(params.get('electro')),
            fog: toNullableBool(params.get('fog')),
        };
    } catch (_error) {
        return null;
    }
}

function getSavedViewerState() {
    try {
        const raw = window.localStorage?.getItem(VIEWER_SESSION_STORAGE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : null;
    } catch (_error) {
        return null;
    }
}

function setSessionStateBadge(text, tone = 'muted') {
    if (!dom.sessionStateBadge) return;
    dom.sessionStateBadge.className = `session-state-badge ${tone}`;
    dom.sessionStateBadge.textContent = text;
}

function setSmokeStateBadge(text, tone = 'muted') {
    if (!dom.smokeStateBadge) return;
    const enabled = Boolean(state.smokePreset);
    dom.smokeStateBadge.style.display = enabled ? 'inline-flex' : 'none';
    if (!enabled) return;
    dom.smokeStateBadge.className = `session-state-badge ${tone}`;
    dom.smokeStateBadge.textContent = text;
}

function buildViewerDebugState() {
    const compareDebugA = collectViewerGeometryDebugState(state.compareViewers?.A || null);
    const compareDebugB = collectViewerGeometryDebugState(state.compareViewers?.B || null);
    const compareIndexA = Number.isInteger(state.compareSlots?.A) ? state.compareSlots.A : null;
    const compareIndexB = Number.isInteger(state.compareSlots?.B) ? state.compareSlots.B : null;
    const compareCandidateA = compareIndexA != null && compareIndexA >= 0 ? state.candidates[compareIndexA] || null : null;
    const compareCandidateB = compareIndexB != null && compareIndexB >= 0 ? state.candidates[compareIndexB] || null : null;
    const selectedCandidate = Number.isInteger(state.selectedIndex) && state.selectedIndex >= 0
        ? state.candidates[state.selectedIndex] || null
        : null;
    return {
        viewerMode: state.viewerMode,
        activeSurfaceLabel: state.activeSurfaceLabel || '',
        activeBundleSourceLabel: state.activeBundleSourceLabel || '',
        selectedIndex: state.selectedIndex,
        selectedLigandId: selectedCandidate?.ligandId || '',
        candidateCount: Array.isArray(state.candidates) ? state.candidates.length : 0,
        bundleLoaded: Boolean(state.bundlePayload && state.candidates.length),
        compareSlots: { A: compareIndexA, B: compareIndexB },
        compareLigands: {
            A: compareCandidateA?.ligandId || '',
            B: compareCandidateB?.ligandId || '',
        },
        compareViewerAReady: Boolean(state.compareViewers?.A?.plugin?.canvas3d),
        compareViewerBReady: Boolean(state.compareViewers?.B?.plugin?.canvas3d),
        singleViewerReady: Boolean(state.viewer?.plugin?.canvas3d),
        compareViewerAGeometryStatus: compareDebugA.statusKind,
        compareViewerBGeometryStatus: compareDebugB.statusKind,
        compareViewerAGeometryLabel: compareDebugA.statusLabel,
        compareViewerBGeometryLabel: compareDebugB.statusLabel,
    };
}

function publishViewerDebugState(extra = {}) {
    const payload = {
        ...buildViewerDebugState(),
        ...extra,
    };
    const inspectViewer = (slot = 'single') => {
        const normalized = String(slot || 'single').toUpperCase();
        const viewer = normalized === 'A'
            ? state.compareViewers?.A || null
            : normalized === 'B'
                ? state.compareViewers?.B || null
                : state.viewer || null;
        const plugin = viewer?.plugin || null;
        const canvas3d = plugin?.canvas3d || null;
        const webgl = canvas3d?.webgl || null;
        const scene = canvas3d?.scene || null;
        const keys = (value) => (value && typeof value === 'object' ? Object.keys(value).slice(0, 80) : []);
        const countCollection = (value) => {
            if (!value) return 0;
            if (Array.isArray(value)) return value.length;
            if (typeof value.size === 'number') return value.size;
            if (typeof value.length === 'number') return value.length;
            if (typeof value === 'object') return Object.keys(value).length;
            return 0;
        };
        return {
            slot: normalized === 'SINGLE' ? 'single' : normalized,
            viewer_exists: Boolean(viewer),
            plugin_exists: Boolean(plugin),
            canvas3d_exists: Boolean(canvas3d),
            webgl_exists: Boolean(webgl),
            scene_exists: Boolean(scene),
            repr_count: Number(canvas3d?.reprCount || 0),
            keys: {
                viewer: keys(viewer),
                plugin: keys(plugin),
                canvas3d: keys(canvas3d),
                webgl: keys(webgl),
                scene: keys(scene),
                context: keys(canvas3d?.context),
                passes: keys(canvas3d?.passes),
                renderer: keys(canvas3d?.renderer),
                stats: keys(canvas3d?.stats),
            },
            counts: {
                scene_renderables: countCollection(scene?.renderables),
                scene_primitives: countCollection(scene?.primitives),
                scene_objects: countCollection(scene?.objects),
            },
            geometry_probe: collectCanvas3dGeometryProbeForViewer(viewer),
            geometry_debug: collectViewerGeometryDebugState(viewer),
        };
    };
    window.__viewerDebugState = payload;
    window.__viewerDebugApi = {
        getState: () => buildViewerDebugState(),
        getSelectedCandidate: () => getSelectedCandidate() || null,
        getCompareCandidate: (slot) => {
            const key = String(slot || '').toUpperCase();
            const index = Number.isInteger(state.compareSlots?.[key]) ? state.compareSlots[key] : -1;
            const candidate = index >= 0 ? state.candidates[index] || null : null;
            return candidate ? { ...candidate, index } : null;
        },
        inspectViewer,
    };
    return payload;
}

function setSmokeState(status, checks = {}, message = '') {
    const enabled = Boolean(state.smokePreset);
    state.smokeState = { enabled, status, checks, message };
    const debugState = publishViewerDebugState();
    if (!enabled) return;
    const tone = status === 'pass' ? 'good' : (status === 'fail' ? 'bad' : 'warn');
    setSmokeStateBadge(`smoke: ${status}`, tone);
    window.__viewerSmokeState = {
        preset: state.smokePreset,
        status,
        checks,
        message,
        surfaceLabel: state.activeSurfaceLabel || '',
        selectedIndex: state.selectedIndex,
        compareViewerGeometry: {
            A: {
                statusKind: debugState.compareViewerAGeometryStatus,
                statusLabel: debugState.compareViewerAGeometryLabel,
            },
            B: {
                statusKind: debugState.compareViewerBGeometryStatus,
                statusLabel: debugState.compareViewerBGeometryLabel,
            },
        },
    };
}

function applyViewerControlState(viewState = {}) {
    if (viewState.repr && dom.reprSelect) dom.reprSelect.value = viewState.repr;
    if (viewState.color && dom.colorSelect) dom.colorSelect.value = viewState.color;
    if (viewState.bg && dom.bgSelect) dom.bgSelect.value = viewState.bg;
    if (viewState.ao && dom.aoPresetSelect) dom.aoPresetSelect.value = viewState.ao;
    if (typeof viewState.pocketSurface === 'boolean' && dom.togglePocketSurface) dom.togglePocketSurface.checked = viewState.pocketSurface;
    if (typeof viewState.electroSurface === 'boolean' && dom.toggleElectroSurface) dom.toggleElectroSurface.checked = viewState.electroSurface;
    if (typeof viewState.fog === 'boolean' && dom.toggleFog) dom.toggleFog.checked = viewState.fog;
}

function buildSerializableViewState() {
    const candidate = getSelectedCandidate();
    return {
        savedAt: new Date().toISOString(),
        surfaceLabel: state.activeSurfaceLabel || candidate?.surfaceLabel || '',
        ligandId: candidate?.ligandId || '',
        packetRank: candidate?.packetRank ?? null,
        frameIndex: state.trajectoryFrameIndex,
        sceneMode: state.trajectorySceneMode,
        compareA: state.candidates[state.compareSlots.A]?.ligandId || '',
        compareB: state.candidates[state.compareSlots.B]?.ligandId || '',
        repr: dom.reprSelect?.value || '',
        color: dom.colorSelect?.value || '',
        bg: dom.bgSelect?.value || '',
        ao: dom.aoPresetSelect?.value || '',
        pocketSurface: Boolean(dom.togglePocketSurface?.checked),
        electroSurface: Boolean(dom.toggleElectroSurface?.checked),
        fog: Boolean(dom.toggleFog?.checked),
    };
}

function buildViewerPermalink(viewState = buildSerializableViewState()) {
    const url = new URL(window.location.href);
    const params = url.searchParams;
    const pairs = [
        ['surface-label', viewState.surfaceLabel],
        ['ligand', viewState.ligandId],
        ['rank', Number.isFinite(viewState.packetRank) ? String(viewState.packetRank) : ''],
        ['frame', Number.isFinite(viewState.frameIndex) ? String(viewState.frameIndex) : ''],
        ['scene', viewState.sceneMode],
        ['compareA', viewState.compareA],
        ['compareB', viewState.compareB],
        ['repr', viewState.repr],
        ['color', viewState.color],
        ['bg', viewState.bg],
        ['ao', viewState.ao],
        ['pocket', typeof viewState.pocketSurface === 'boolean' ? String(viewState.pocketSurface) : ''],
        ['electro', typeof viewState.electroSurface === 'boolean' ? String(viewState.electroSurface) : ''],
        ['fog', typeof viewState.fog === 'boolean' ? String(viewState.fog) : ''],
    ];
    for (const [key, value] of pairs) {
        if (String(value || '').trim()) params.set(key, value);
        else params.delete(key);
    }
    return url.toString();
}

function persistViewerSession({ saveLocal = true, replaceUrl = true, badgeText = 'session: synced' } = {}) {
    if (state.suppressSessionPersist || !state.candidates.length) return;
    const payload = buildSerializableViewState();
    if (saveLocal) {
        try {
            window.localStorage?.setItem(VIEWER_SESSION_STORAGE_KEY, JSON.stringify(payload));
        } catch (_error) {
        }
    }
    if (replaceUrl) {
        try {
            window.history.replaceState({}, '', buildViewerPermalink(payload));
        } catch (_error) {
        }
    }
    setSessionStateBadge(badgeText, 'good');
}

function findCandidateIndexFromViewState(viewState) {
    if (!viewState || !state.candidates.length) return 0;
    if (viewState.ligandId) {
        const ligandMatch = state.candidates.findIndex((candidate) => candidate.ligandId === viewState.ligandId);
        if (ligandMatch >= 0) return ligandMatch;
    }
    if (Number.isFinite(viewState.packetRank)) {
        const rankMatch = state.candidates.findIndex((candidate) => candidate.packetRank === viewState.packetRank);
        if (rankMatch >= 0) return rankMatch;
    }
    return 0;
}

function applyCompareStateFromView(viewState) {
    if (!viewState) return;
    const slotA = viewState.compareA
        ? state.candidates.findIndex((candidate) => candidate.ligandId === viewState.compareA)
        : -1;
    const slotB = viewState.compareB
        ? state.candidates.findIndex((candidate) => candidate.ligandId === viewState.compareB)
        : -1;
    state.compareSlots.A = slotA >= 0 ? slotA : null;
    state.compareSlots.B = slotB >= 0 ? slotB : null;
    updateCompareUi();
}

async function applyRequestedViewerState(viewState, sourceLabel = 'saved session') {
    if (!viewState || !state.candidates.length) return false;
    state.suppressSessionPersist = true;
    try {
        applyViewerControlState(viewState);
        await selectCandidate(findCandidateIndexFromViewState(viewState));
        applyCompareStateFromView(viewState);
        const candidate = getSelectedCandidate();
        if (candidate?.trajectoryData?.frameCount && Number.isFinite(viewState.frameIndex)) {
            state.trajectoryFrameIndex = clamp(viewState.frameIndex, 0, candidate.trajectoryData.frameCount - 1);
            state.trajectorySceneMode = viewState.sceneMode === 'trajectory' ? 'trajectory' : 'reference';
            if (state.trajectorySceneMode === 'trajectory') {
                candidate.lastRenderedTrajectoryFrame = -1;
                await renderTrajectoryFrameInViewer(candidate, state.trajectoryFrameIndex);
            } else {
                await loadFocusedCandidateScene(candidate, null);
            }
            refreshInteractionOverlayData(candidate, state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null);
        }
        syncTrajectoryUi();
        renderSelectedCandidateSurfaces(getSelectedCandidate());
        setSessionStateBadge(`session: restored (${sourceLabel})`, 'good');
    } finally {
        state.suppressSessionPersist = false;
    }
    persistViewerSession({ badgeText: `session: restored (${sourceLabel})` });
    return true;
}

async function restoreViewerSession() {
    const saved = getSavedViewerState();
    if (!saved) {
        setSessionStateBadge('session: none', 'muted');
        toast('저장된 세션이 없습니다.', 'warn');
        return;
    }
    state.pendingViewerState = saved;
    const targetSurface = String(saved.surfaceLabel || '').trim();
    if (targetSurface && normalizeSurfaceLabelKey(targetSurface) !== normalizeSurfaceLabelKey(state.activeSurfaceLabel)) {
        const restored = await loadSurfaceBundlePreset(targetSurface, { showSuccessToast: false });
        if (restored) return;
    }
    await applyRequestedViewerState(saved, 'saved session');
}

async function copyViewerPermalink() {
    const url = buildViewerPermalink();
    try {
        await navigator.clipboard.writeText(url);
        setSessionStateBadge('session: link copied', 'good');
        toast('현재 viewer 링크를 복사했습니다.', 'success');
    } catch (error) {
        setSessionStateBadge('session: copy failed', 'warn');
        toast(`링크 복사 실패: ${error.message}`, 'error');
    }
}

async function tryAutoLoadInitialBundle() {
    const requestedSurfaceLabel = getRequestedSurfaceLabel();
    if (requestedSurfaceLabel) {
        const loaded = await loadSurfaceBundlePreset(requestedSurfaceLabel, { showSuccessToast: false });
        if (loaded) return;
    }
    if (state.smokePreset === 'protein-motion') {
        const loaded = await loadSurfaceBundlePreset('protein_atom_frames_smoke', { showSuccessToast: false });
        if (loaded) return;
    }
    const savedViewState = getSavedViewerState();
    if (savedViewState?.surfaceLabel) {
        state.pendingViewerState = savedViewState;
        const restored = await loadSurfaceBundlePreset(savedViewState.surfaceLabel, { showSuccessToast: false });
        if (restored) return;
        state.pendingViewerState = null;
    }
    await tryAutoLoadCurrentBundle();
}

async function loadSurfaceBundlePreset(surfaceLabel, { showSuccessToast = true } = {}) {
    const requestedKey = normalizeSurfaceLabelKey(surfaceLabel);
    const preset = state.surfacePresets.find((entry) => normalizeSurfaceLabelKey(entry.surfaceLabel) === requestedKey);
    if (!preset?.bundlePath) return false;
    try {
        const payload = await fetchJson(preset.bundlePath);
        ingestBundle(payload, `surface bundle: ${preset.surfaceLabel}`);
        if (showSuccessToast) toast(`${preset.targetId} surface bundle을 로드했습니다.`, 'success');
        return true;
    } catch (error) {
        console.warn('surface bundle load failed', preset, error);
        if (showSuccessToast) toast(`Surface bundle 로드 실패: ${error.message}`, 'error');
        return false;
    }
}

async function initViewer() {
    state.viewer = await molstar.Viewer.create(dom.molstarViewer, buildViewerCreateOptions());
    installMeasurementClickHandler();
    applyViewerRenderSettings();
}

function buildViewerCreateOptions() {
    return {
        layoutIsExpanded: false,
        layoutShowControls: false,
        layoutShowRemoteState: false,
        layoutShowSequence: true,
        layoutShowLog: false,
        layoutShowLeftPanel: false,
        viewportShowExpand: false,
        viewportShowSelectionMode: false,
        viewportShowAnimation: false,
        backgroundColor: parseHexColor(dom.bgSelect.value),
    };
}

async function ensureCompareViewers() {
    if (!state.compareViewers.A && dom.compareViewerA) {
        state.compareViewers.A = await molstar.Viewer.create(dom.compareViewerA, buildViewerCreateOptions());
    }
    if (!state.compareViewers.B && dom.compareViewerB) {
        state.compareViewers.B = await molstar.Viewer.create(dom.compareViewerB, buildViewerCreateOptions());
    }
    applyViewerRenderSettings();
}

function bindStaticUi() {
    dom.btnLoadSurfaceBundle.addEventListener('click', async () => {
        const surfaceLabel = dom.bundleSurfaceSelect.value;
        if (!surfaceLabel) {
            toast('먼저 surface bundle을 선택하세요.', 'warn');
            return;
        }
        await loadSurfaceBundlePreset(surfaceLabel);
    });
    dom.bundleSurfaceSelect.addEventListener('change', async () => {
        const surfaceLabel = dom.bundleSurfaceSelect.value;
        if (!surfaceLabel) return;
        await loadSurfaceBundlePreset(surfaceLabel, { showSuccessToast: false });
    });

    dom.btnLoadCurrentBundle.addEventListener('click', () => {
        tryAutoLoadCurrentBundle(true);
    });

    dom.btnLoadBundle.addEventListener('click', () => dom.bundleInput.click());
    dom.bundleInput.addEventListener('change', handleBundleInput);
    dom.btnLoadWritebackBefore.addEventListener('click', () => dom.writebackBeforeInput.click());
    dom.writebackBeforeInput.addEventListener('change', handleWritebackBeforeBundleInput);
    dom.btnUseCurrentAsWritebackAfter.addEventListener('click', async () => {
        syncWritebackCompareWithCurrentBundle();
        await renderCompareConsole();
        toast('현재 explorer bundle을 writeback after 기준으로 동기화했습니다.', 'success');
    });
    dom.btnClearWritebackCompare.addEventListener('click', () => {
        clearWritebackCompare();
        void renderCompareConsole();
        toast('Writeback compare 입력을 초기화했습니다.', 'success');
    });

    dom.btnLoadPDB.addEventListener('click', () => dom.fileInput.click());
    dom.fileInput.addEventListener('change', handleStructureInput);

    dom.btnLoadDir.addEventListener('click', () => dom.dirInput.click());
    dom.dirInput.addEventListener('change', handleDirectoryInput);
    dom.btnOpenGallery.addEventListener('click', () => openAsset(DEFAULT_GALLERY_PATH));
    dom.btnCopyPermalink.addEventListener('click', () => {
        copyViewerPermalink().catch((error) => {
            console.error(error);
            toast(`링크 복사 실패: ${error.message}`, 'error');
        });
    });
    dom.btnSaveSession.addEventListener('click', () => {
        persistViewerSession({ badgeText: 'session: saved' });
        toast('현재 viewer 세션을 저장했습니다.', 'success');
    });
    dom.btnRestoreSession.addEventListener('click', () => {
        restoreViewerSession().catch((error) => {
            console.error(error);
            toast(`세션 복원 실패: ${error.message}`, 'error');
        });
    });

    dom.searchBox.addEventListener('input', renderFileList);

    dom.bgSelect.addEventListener('change', () => {
        applyViewerRenderSettings();
        persistViewerSession();
    });
    dom.aoPresetSelect.addEventListener('change', () => {
        applyViewerRenderSettings();
        persistViewerSession();
    });
    dom.toggleSpin.addEventListener('change', () => {
        applyViewerRenderSettings();
        persistViewerSession();
    });
    dom.toggleFog.addEventListener('change', () => {
        applyViewerRenderSettings();
        persistViewerSession();
    });
    dom.togglePocketSurface.addEventListener('change', async () => {
        if (state.selectedIndex >= 0) {
            await selectCandidate(state.selectedIndex, { forceReload: true });
        }
        persistViewerSession();
    });
    dom.toggleElectroSurface.addEventListener('change', async () => {
        if (state.selectedIndex >= 0) {
            await selectCandidate(state.selectedIndex, { forceReload: true });
        }
        persistViewerSession();
    });
    dom.btnFocusBinding.addEventListener('click', () => {
        focusSelectedBindingPocket().catch((error) => {
            console.error(error);
            toast(`결합부 확대 실패: ${error.message}`, 'error');
        });
    });
    dom.viewerContainer.addEventListener('wheel', noteUserCameraInteraction, { passive: true });
    dom.viewerContainer.addEventListener('pointerdown', noteUserCameraInteraction, { passive: true });

    dom.reprSelect.addEventListener('change', async () => {
        if (state.selectedIndex >= 0) {
            await selectCandidate(state.selectedIndex, { forceReload: true });
        }
        persistViewerSession();
    });

    dom.colorSelect.addEventListener('change', async () => {
        if (state.selectedIndex >= 0) {
            await selectCandidate(state.selectedIndex, { forceReload: true });
        }
        persistViewerSession();
    });

    dom.btnThemeToggle.addEventListener('click', () => {
        const root = document.documentElement;
        const light = root.getAttribute('data-theme') === 'light';
        if (light) {
            root.removeAttribute('data-theme');
            dom.btnThemeToggle.textContent = '🌙';
        } else {
            root.setAttribute('data-theme', 'light');
            dom.btnThemeToggle.textContent = '☀';
        }
    });

    dom.fileList.addEventListener('click', async (event) => {
        const button = event.target.closest('button[data-action]');
        const item = event.target.closest('[data-index]');
        if (!item) return;

        const index = Number(item.dataset.index);
        if (!Number.isFinite(index)) return;

        if (button) {
            const action = button.dataset.action;
            if (action === 'slot-a') assignCompareSlot('A', index);
            if (action === 'slot-b') assignCompareSlot('B', index);
            return;
        }

        await selectCandidate(index);
    });

    dom.btnSuperpose.addEventListener('click', () => loadCompareMode('superpose'));
    dom.btnSideBySide.addEventListener('click', () => loadCompareMode('side-by-side'));
    dom.compareDecisionBoard?.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-action]');
        if (!button) return;
        const pairKey = button.dataset.pairKey || '';
        const pair = state.writebackCompare.pairs.find((entry) => entry.key === pairKey) || null;
        if (!pair) return;
        if (button.dataset.action === 'writeback-select') {
            state.writebackCompare.selectedPairKey = pair.key;
            void renderCompareConsole();
            return;
        }
        if (!pair.beforeCandidate || !pair.afterCandidate) return;
        const mode = button.dataset.action === 'writeback-superpose' ? 'superpose' : 'side-by-side';
        loadCandidatePairCompareMode(mode, pair.beforeCandidate, pair.afterCandidate, {
            beforeRoleLabel: 'Before',
            afterRoleLabel: 'After',
            compareSummaryLabel: mode === 'superpose' ? 'Writeback Real Superposition' : 'Writeback Side-by-Side',
            compareToastPrefix: mode === 'superpose' ? 'writeback 중첩' : 'writeback 나란히',
        }).then(() => {
            updateCompareWritebackSmokeState();
        }).catch((error) => {
            console.error(error);
            toast(`writeback compare 실패: ${error.message}`, 'error');
        });
    });

    dom.btnSnapshot.addEventListener('click', openSnapshotModal);
    dom.btnCloseModal.addEventListener('click', closeSnapshotModal);
    dom.btnDownloadSnapshot.addEventListener('click', downloadSnapshot);
    dom.btnCopySnapshot.addEventListener('click', copySnapshot);
    dom.btnFigureModal.addEventListener('click', openFigureModal);
    dom.btnCloseFigureModal.addEventListener('click', closeFigureModal);
    dom.btnOpenFigureFromModal.addEventListener('click', () => openAsset(dom.btnOpenFigureFromModal.dataset.path));

    dom.btnOpenFigure.addEventListener('click', () => openAsset(dom.btnOpenFigure.dataset.path));
    dom.btnOpenMovie.addEventListener('click', () => openAsset(dom.btnOpenMovie.dataset.path));
    dom.btnOpenDashboard.addEventListener('click', () => openAsset(dom.btnOpenDashboard.dataset.path));
    dom.btnToggleAnnotations.addEventListener('click', () => {
        setViewerAnnotationExpanded(!state.annotationExpanded);
    });

    dom.btnTrajPlay.addEventListener('click', () => startTrajectoryPlayback());
    dom.btnTrajPause.addEventListener('click', () => stopTrajectoryPlayback());
    dom.trajSpeed.addEventListener('change', () => {
        if (dom.videoPreview.style.display !== 'none') {
            dom.videoPreview.playbackRate = Number(dom.trajSpeed.value || 1);
        }
    });
    dom.trajSlider.addEventListener('input', onTrajectorySliderInput);
    dom.videoPreview.addEventListener('loadedmetadata', syncTrajectoryUi);
    dom.videoPreview.addEventListener('timeupdate', handleVideoTimeUpdate);
    dom.videoPreview.addEventListener('error', () => {
        const candidate = getSelectedCandidate();
        if (candidate) {
            candidate.movieLoadError = true;
            renderMediaSection(candidate);
            syncTrajectoryUi();
            return;
        }
        dom.videoPreview.style.display = 'none';
        dom.mediaEmpty.style.display = 'block';
        syncTrajectoryUi();
    });
    dom.figurePreview.addEventListener('error', () => {
        dom.figurePreview.style.display = 'none';
        dom.mediaEmpty.style.display = dom.videoPreview.style.display === 'none' ? 'block' : 'none';
    });
    dom.figurePreview.addEventListener('click', () => {
        if (!dom.btnFigureModal.disabled) openFigureModal();
    });
    dom.interactionOverlay?.addEventListener('click', (event) => {
        handleInteractionOverlayClick(event).catch((error) => {
            console.error(error);
            toast(`contact highlight 실패: ${error.message}`, 'error');
        });
    });
    dom.sequenceViewer?.addEventListener('click', (event) => {
        handleSequenceViewerClick(event).catch((error) => {
            console.error(error);
            toast(`sequence highlight 실패: ${error.message}`, 'error');
        });
    });
    dom.residueContactHeatmap?.addEventListener('click', (event) => {
        handleResidueHeatmapClick(event).catch((error) => {
            console.error(error);
            toast(`heatmap highlight 실패: ${error.message}`, 'error');
        });
    });
    [dom.snapshotModal, dom.figureModal].forEach((modal) => {
        modal?.addEventListener('click', (event) => {
            if (event.target !== modal) return;
            if (modal === dom.snapshotModal) closeSnapshotModal();
            if (modal === dom.figureModal) closeFigureModal();
        });
    });
    window.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') return;
        closeSnapshotModal();
        closeFigureModal();
    });

    dom.metricSelect.addEventListener('change', renderCharts);

    dom.btnMeasureDist.addEventListener('click', () => startMeasurementMode('distance'));
    dom.btnMeasureAngle.addEventListener('click', () => startMeasurementMode('angle'));
    dom.btnMeasureDihedral.addEventListener('click', () => startMeasurementMode('dihedral'));
    dom.btnClearMeasure.addEventListener('click', () => {
        clearAllMeasurements().catch((error) => {
            console.error(error);
            toast(`측정 지우기 실패: ${error.message}`, 'error');
        });
    });
    updateMeasurementUi();
}

async function tryAutoLoadCurrentBundle(showSuccessToast = false) {
    try {
        const payload = await fetchJson(DEFAULT_BUNDLE_PATH);
        ingestBundle(payload, 'current bundle');
        if (showSuccessToast) toast('현재 selected-allatom bundle을 로드했습니다.', 'success');
    } catch (error) {
        console.warn('auto bundle load failed', error);
        if (showSuccessToast) toast(`Bundle 로드 실패: ${error.message}`, 'error');
    }
}

async function handleBundleInput(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
        const payload = JSON.parse(await file.text());
        ingestBundle(payload, file.name);
        toast(`Bundle 로드 완료: ${file.name}`, 'success');
    } catch (error) {
        toast(`Bundle JSON 파싱 실패: ${error.message}`, 'error');
    } finally {
        event.target.value = '';
    }
}

async function handleStructureInput(event) {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    registerLocalFiles(files);

    if (!state.bundlePayload) {
        const pseudoPayload = buildPseudoBundleFromFiles(files);
        ingestBundle(pseudoPayload, 'manual structures');
        toast(`수동 구조 ${files.length}개를 로드했습니다.`, 'success');
    } else {
        if (state.selectedIndex >= 0) {
            await selectCandidate(state.selectedIndex, { forceReload: true });
        }
        toast(`로컬 구조 파일 ${files.length}개를 인덱싱했습니다.`, 'success');
    }

    event.target.value = '';
}

async function handleDirectoryInput(event) {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    registerLocalFiles(files);

    const structureFiles = files.filter((file) => isStructureFile(file.name));
    if (!state.bundlePayload && structureFiles.length) {
        const pseudoPayload = buildPseudoBundleFromFiles(files);
        ingestBundle(pseudoPayload, 'manual directory');
    } else if (state.selectedIndex >= 0) {
        await selectCandidate(state.selectedIndex, { forceReload: true });
    }

    toast(`폴더 인덱싱 완료: ${files.length}개 파일`, 'success');
    event.target.value = '';
}

function buildPseudoBundleFromFiles(files) {
    const volumeFiles = files.filter((file) => isVolumeMapFile(file.name));
    const primaryVolume = volumeFiles[0] || null;
    const rows = files
        .filter((file) => isStructureFile(file.name))
        .map((file, index) => ({
            packet_rank: index + 1,
            target_id: 'Manual Import',
            ligand_id: file.name,
            compound_name: file.name,
            backmapped_pdb: file.webkitRelativePath || file.name,
            surface_map_path: primaryVolume ? (primaryVolume.webkitRelativePath || primaryVolume.name) : '',
            surface_map_format: primaryVolume ? inferVolumeFormat(primaryVolume.name) : '',
            surface_map_kind: primaryVolume ? 'manual_local_volume_map' : '',
            surface_map_isovalue: primaryVolume ? 1.0 : '',
        }));

    return {
        summary: {
            status: 'selected_allatom_visual_bundle_ready',
            visual_bundle_manifest_version: 'selected_allatom_visual_bundle_manual_v1',
            target_id: 'Manual Import',
            topk_count: rows.length,
            figure_count: 0,
            movie_plan_count: 0,
            binding_event_candidate_count: 0,
            human_summary: `수동으로 로드한 구조 ${rows.length}개`,
            primary_surface_map_path: primaryVolume ? (primaryVolume.webkitRelativePath || primaryVolume.name) : '',
            primary_surface_map_format: primaryVolume ? inferVolumeFormat(primaryVolume.name) : '',
            primary_surface_map_kind: primaryVolume ? 'manual_local_volume_map' : '',
            primary_surface_map_ready: Boolean(primaryVolume),
        },
        rows,
    };
}

function registerLocalFiles(files) {
    clearLocalObjectUrls();
    state.localFilesByBasename.clear();
    state.localFilesByPath.clear();

    for (const file of files) {
        const objectUrl = URL.createObjectURL(file);
        state.localObjectUrls.push(objectUrl);

        const basename = basenameOf(file.name);
        state.localFilesByBasename.set(basename, {
            file,
            objectUrl,
            text: () => file.text(),
            arrayBuffer: () => file.arrayBuffer(),
        });

        const relative = (file.webkitRelativePath || file.name || '').replace(/\\/g, '/');
        if (relative) {
            state.localFilesByPath.set(relative, {
                file,
                objectUrl,
                text: () => file.text(),
                arrayBuffer: () => file.arrayBuffer(),
            });
            state.localFilesByPath.set(`/${relative}`, {
                file,
                objectUrl,
                text: () => file.text(),
                arrayBuffer: () => file.arrayBuffer(),
            });
        }
    }
}

function clearLocalObjectUrls() {
    for (const url of state.localObjectUrls) URL.revokeObjectURL(url);
    state.localObjectUrls = [];
}

function buildNormalizedCandidatesFromPayload(payload, sourceLabel = 'bundle') {
    const summary = payload?.summary || {};
    const rows = Array.isArray(payload?.rows) ? payload.rows : [];
    return rows.map((row, index) => normalizeCandidate(row, summary, index, sourceLabel));
}

function ingestBundle(payload, sourceLabel) {
    const summary = payload?.summary || {};
    const surfaceLabel = firstTruthy(summary.selected_surface_label, summary.surface_label);

    state.bundlePayload = payload;
    state.bundleSummary = summary;
    state.candidates = buildNormalizedCandidatesFromPayload(payload, sourceLabel);
    state.activeSurfaceLabel = surfaceLabel;
    state.activeBundleSourceLabel = sourceLabel;
    syncSurfacePresetSelection(surfaceLabel);
    syncWritebackCompareWithCurrentBundle();

    dom.bundleStatus.textContent = [
        `source: ${sourceLabel}`,
        `status: ${summary.status || 'unknown'}`,
        `target: ${summary.target_id || '-'}`,
        `surface: ${surfaceLabel || '-'}`,
        `top-k: ${summary.topk_count ?? state.candidates.length ?? 0}`,
    ].join(' | ');

    renderFileList();
    renderQuickStats();
    populateMetricSelect();
    renderCharts();
    updateCompareUi();
    publishViewerDebugState();

    if (state.candidates.length) {
        const urlViewState = getRequestedViewerState();
        const requestedViewState = state.pendingViewerState || urlViewState || getSavedViewerState();
        state.pendingViewerState = null;
        const selectPromise = requestedViewState
            ? applyRequestedViewerState(requestedViewState, requestedViewState === urlViewState ? 'url' : 'saved session')
            : selectCandidate(0);
        selectPromise.catch((error) => {
            console.error(error);
            toast(`첫 후보 로드 실패: ${error.message}`, 'error');
        });
    } else {
        clearViewerOverlay(true);
    }
}

function syncSurfacePresetSelection(surfaceLabel) {
    const normalizedKey = normalizeSurfaceLabelKey(surfaceLabel);
    if (!normalizedKey) {
        dom.bundleSurfaceSelect.value = '';
        return;
    }
    const preset = state.surfacePresets.find((entry) => normalizeSurfaceLabelKey(entry.surfaceLabel) === normalizedKey);
    dom.bundleSurfaceSelect.value = preset ? preset.surfaceLabel : '';
}

function normalizeCandidate(row, summary, index, sourceLabel = 'bundle') {
    const processedPath = firstTruthy(
        row.visual_polish_processed_pdb_ready ? row.visual_polish_processed_pdb : '',
        row.visual_polish_processed_pdb,
        row.backmapped_pdb,
    );
    const figurePath = firstTruthy(
        row.primary_figure_path,
        summary.primary_figure_path,
        summary.metric_panel_png,
        summary.scatter_png,
    );
    const movieScriptPath = firstTruthy(
        row.visual_polish_turntable_movie_script_path,
        row.turntable_movie_script_path,
        summary.primary_visual_polish_movie_script_path,
        summary.primary_movie_script_path,
    );
    const movieMp4Path = firstTruthy(
        row.visual_polish_turntable_movie_mp4_path,
        row.turntable_movie_mp4_path,
        summary.primary_visual_polish_movie_mp4_path,
        summary.primary_movie_mp4_path,
    );

    return {
        index,
        bundleSourceLabel: sourceLabel,
        packetRank: toInt(row.packet_rank, index + 1),
        title: firstTruthy(row.compound_name, row.ligand_id, `Candidate ${index + 1}`),
        ligandId: firstTruthy(row.ligand_id, `candidate_${index + 1}`),
        targetId: firstTruthy(row.target_id, summary.target_id, 'Unknown Target'),
        surfaceLabel: firstTruthy(row.surface_label, summary.selected_surface_label, summary.surface_label),
        proteinReferencePath: firstTruthy(
            row.protein_reference_structure_path,
            summary.primary_protein_reference_structure_path,
        ),
        proteinReferenceReady: toBool(
            row.protein_reference_structure_ready,
            summary.primary_protein_reference_structure_ready,
        ),
        proteinReferenceAlignedPath: firstTruthy(
            row.protein_reference_aligned_viewer_path,
            summary.primary_protein_reference_aligned_viewer_path,
        ),
        proteinReferenceAligned: toBool(
            row.protein_reference_structure_aligned_for_viewer,
            summary.primary_protein_reference_structure_aligned_for_viewer,
        ),
        proteinReferenceViewerMode: firstTruthy(
            row.protein_reference_viewer_mode,
            summary.primary_protein_reference_viewer_mode,
            'none',
        ),
        proteinReferenceAlignmentMode: firstTruthy(
            row.protein_reference_alignment_mode,
            summary.primary_protein_reference_alignment_mode,
        ),
        proteinReferenceFormat: firstTruthy(
            row.protein_reference_structure_format,
            summary.primary_protein_reference_structure_format,
        ),
        proteinReferenceNote: firstTruthy(
            row.protein_reference_structure_note,
            summary.primary_protein_reference_structure_note,
        ),
        viewerPosePdb: firstTruthy(row.viewer_pose_pdb, summary.primary_viewer_pose_pdb),
        viewerPosePdbReady: toBool(row.viewer_pose_pdb_ready, summary.primary_viewer_pose_pdb_ready),
        viewerReferencePdb: firstTruthy(row.viewer_reference_pdb, summary.primary_viewer_reference_pdb),
        viewerReferencePdbReady: toBool(
            row.viewer_reference_pdb_ready,
            summary.primary_viewer_reference_pdb_ready,
        ),
        viewerStructureContextMode: firstTruthy(
            row.viewer_structure_context_mode,
            summary.primary_viewer_structure_context_mode,
            'ligand_only_backmapped',
        ),
        viewerProteinContextValid: toBool(
            row.viewer_protein_context_valid,
            summary.primary_viewer_protein_context_valid,
        ),
        viewerProteinContextQualityGatePass: toBool(
            row.viewer_protein_context_quality_gate_pass,
            summary.primary_viewer_protein_context_quality_gate_pass,
        ),
        viewerProteinContextReason: firstTruthy(
            row.viewer_protein_context_reason,
            summary.primary_viewer_protein_context_reason,
        ),
        viewerProteinCaCount: toInt(row.viewer_protein_ca_count, summary.primary_viewer_protein_ca_count ?? 0),
        viewerProteinCaSpreadA: toFloat(row.viewer_protein_ca_spread_A, summary.primary_viewer_protein_ca_spread_A),
        viewerProteinContextNote: firstTruthy(
            row.viewer_protein_context_note,
            summary.viewer_structure_context_note,
        ),
        pocketCenter: [
            toFloat(row.protein_reference_pocket_x),
            toFloat(row.protein_reference_pocket_y),
            toFloat(row.protein_reference_pocket_z),
        ],
        pocketVolumeA3: toFloat(
            firstTruthy(
                row.pocket_volume_A3,
                row.pocket_volume_a3,
                row.pocket_volume_angstrom3,
                summary.primary_pocket_volume_A3,
                summary.primary_pocket_volume_a3,
                summary.primary_pocket_volume_angstrom3,
            ),
        ),
        pocketVolumeSource: firstTruthy(
            row.pocket_volume_source,
            summary.primary_pocket_volume_source,
        ),
        backmappedProteinResidues: toInt(row.backmapped_protein_residues),
        backmappedProteinAtoms: toInt(row.backmapped_protein_atoms, summary.primary_backmapped_protein_atoms ?? 0),
        viewerReferenceFrameIndex: toInt(row.viewer_reference_frame_index, summary.primary_viewer_reference_frame_index ?? 0),
        renderStructureKind: firstTruthy(row.render_structure_kind, summary.primary_render_structure_kind),
        renderStructureNote: firstTruthy(row.render_structure_note),
        structurePath: processedPath,
        structurePathCandidates: uniqueTruthy([
            row.render_structure_path,
            row.protein_reference_aligned_viewer_path,
            row.viewer_reference_pdb,
            row.visual_polish_processed_pdb,
            processedPath,
            row.binding_event_clip_input_backmapped_pdb,
            row.backmapped_pdb,
        ]),
        compareStructurePath: firstTruthy(
            row.render_structure_path,
            row.protein_reference_aligned_viewer_path,
            row.viewer_reference_pdb,
            row.visual_polish_processed_pdb,
            processedPath,
            row.binding_event_clip_input_backmapped_pdb,
            row.backmapped_pdb,
            processedPath,
        ),
        fallbackStructurePath: firstTruthy(row.backmapped_pdb),
        figurePath,
        movieScriptPath,
        movieMp4Path,
        movieScriptReady: toBool(
            row.visual_polish_turntable_script_ready,
            row.turntable_script_ready,
            summary.primary_visual_polish_turntable_script_ready,
            summary.primary_turntable_script_ready,
            Boolean(movieScriptPath),
        ),
        movieMp4Ready: toBool(
            row.visual_polish_turntable_mp4_ready,
            row.turntable_mp4_ready,
            summary.primary_visual_polish_turntable_mp4_ready,
            summary.primary_turntable_mp4_ready,
            Boolean(movieMp4Path),
        ),
        movieAssetStatus: firstTruthy(
            row.visual_polish_turntable_asset_status,
            row.turntable_asset_status,
            summary.primary_visual_polish_turntable_asset_status,
            summary.primary_turntable_asset_status,
        ),
        movieAssetRecommendation: firstTruthy(
            row.visual_polish_turntable_asset_recommendation,
            row.turntable_asset_recommendation,
            summary.primary_visual_polish_turntable_asset_recommendation,
            summary.primary_turntable_asset_recommendation,
        ),
        dashboardPath: firstTruthy(summary.dashboard_html, summary.visual_pipeline_dashboard_html),
        surfaceMapPath: firstTruthy(
            row.surface_map_path,
            row.apbs_dx_path,
            row.apbs_cube_path,
            summary.primary_surface_map_path,
        ),
        surfaceMapFormat: firstTruthy(row.surface_map_format, summary.primary_surface_map_format),
        surfaceMapKind: firstTruthy(
            row.surface_map_kind,
            summary.primary_surface_map_kind,
        ),
        surfaceMapIsoValue: toFloat(
            firstTruthy(row.surface_map_isovalue, summary.primary_surface_map_isovalue),
            1.0,
        ),
        surfaceMapReady: toBool(
            row.surface_map_ready,
            summary.primary_surface_map_ready,
        ),
        trajectoryPath: firstTruthy(
            row.binding_event_clip_input_trajectory_npz,
            row.trajectory_npz,
            summary.primary_trajectory_npz,
        ),
        bindingRecipe: firstTruthy(
            row.binding_event_clip_recipe_summary,
            row.binding_event_clip_recipe,
            summary.primary_binding_event_clip_recipe,
        ),
        bindingStatus: firstTruthy(
            row.binding_event_movie_candidate_status,
            row.binding_event_clip_status,
            summary.primary_binding_event_clip_status,
        ),
        meanMinDistanceA: toFloat(row.mean_min_distance_A),
        bindingEnergyProxy: toFloat(row.binding_energy_proxy),
        contactFraction: toFloat(row.contact_fraction),
        stabilityScore: toFloat(row.stability_score),
        trajectoryFrames: toInt(row.trajectory_frames),
        commercialOverallScoreV2: toFloat(row.commercial_overall_score_v2),
        commercialConfidenceScoreV2: toFloat(row.commercial_confidence_score_v2),
        translationGateStatus: firstTruthy(row.translation_gate_status, 'not_reported'),
        translationGateReason: firstTruthy(row.translation_gate_reason),
        shortlistTier: firstTruthy(row.shortlist_tier, 'not_reported'),
        recommendedLane: firstTruthy(row.recommended_next_expensive_lane, 'not_reported'),
        recommendedLaneReason: firstTruthy(row.recommended_next_expensive_lane_reason),
        recommendedLaneAction: firstTruthy(row.recommended_next_expensive_lane_action),
        actionCodesText: firstTruthy(row.recommended_next_expensive_lane_action_codes_text),
        blockerCodesText: firstTruthy(row.recommended_next_expensive_lane_blocker_codes_text),
        trajectoryState: firstTruthy(
            row.binding_event_clip_status,
            row.binding_event_movie_candidate_status,
            row.trajectory_npz ? 'trajectory_npz_available' : 'trajectory_not_reported',
        ),
        trajectoryData: null,
        trajectoryError: '',
        movieLoadError: false,
        proteinTemplateAtoms: null,
        ligandTemplateAtoms: null,
        lastRenderedTrajectoryFrame: -1,
        pocketAnalyticsCache: null,
        fastTrajectorySceneCache: null,
        fastTrajectorySceneSignatureCache: new Map(),
        ligandFramePdbCache: new Map(),
        proteinFrameAtomCache: new Map(),
        proteinFrameCoordCache: new Map(),
        ligandInPlaceFailureCount: 0,
        ligandForceReloadOnly: false,
        row,
    };
}

function resolveMovieUiState(candidate) {
    const hasMovieMp4 = Boolean(candidate?.movieMp4Path) && !candidate?.movieLoadError;
    const hasMovieScript = Boolean(candidate?.movieScriptPath) || Boolean(candidate?.movieScriptReady);
    const assetStatus = firstTruthy(
        candidate?.movieAssetStatus,
        hasMovieMp4 ? 'turntable_mp4_ready' : '',
        hasMovieScript ? 'turntable_script_ready' : '',
        'turntable_not_ready',
    );
    const recommendation = firstTruthy(
        candidate?.movieAssetRecommendation,
        hasMovieMp4 ? '' : '',
        hasMovieScript ? 'render_turntable_mp4' : '',
    );

    if (hasMovieMp4) {
        return {
            hasMovieMp4,
            hasMovieScript,
            assetStatus,
            recommendation,
            label: 'mp4 ready',
            tone: 'good',
            message: 'Movie MP4가 준비되어 있어 바로 재생과 열기가 가능합니다.',
        };
    }

    if (hasMovieScript) {
        return {
            hasMovieMp4,
            hasMovieScript,
            assetStatus,
            recommendation,
            label: 'script only',
            tone: 'warn',
            message: `Movie MP4는 아직 렌더되지 않았습니다. Turntable script만 준비되어 있습니다.${recommendation ? ` 다음 단계: ${recommendation}` : ''}`,
        };
    }

    return {
        hasMovieMp4,
        hasMovieScript,
        assetStatus,
        recommendation,
        label: 'missing',
        tone: 'muted',
        message: 'Movie asset이 없습니다. Figure 또는 trajectory만 확인 가능합니다.',
    };
}

function resolveTrajectoryDeckState(candidate, hasVideoPreview = false) {
    const trajectory = candidate?.trajectoryData || null;
    const movie = resolveMovieUiState(candidate);
    const hasTrajectory = Boolean(trajectory?.frameCount);
    const ready = hasTrajectory || movie.hasMovieMp4;
    const sliderReady = hasTrajectory || hasVideoPreview;

    if (hasTrajectory && movie.hasMovieMp4) {
        return {
            ready,
            sliderReady,
            hasTrajectory,
            tone: 'good',
            message: `NPZ 3D trajectory와 Movie MP4 preview가 같이 준비되어 있습니다. 스크럽과 동기화 재생이 가능합니다. Ligand update: ${describeTrajectoryUpdateMode(candidate)}. Render: ${describeTrajectoryRenderMode(candidate)}. Protein color: ${describeProteinFrameColorMode(candidate)}. Miss: ${describeFastPathMissReason(candidate)}. Coalesced: ${candidate?.trajectoryRenderStats?.coalescedFrameCount || 0}.`,
        };
    }

    if (hasTrajectory) {
        const referenceCopy = !candidate?.viewerProteinContextQualityGatePass && candidate?.proteinReferenceAligned
            ? '기본은 aligned native pocket close-up을 보여주고, slider/play를 누르면 ligand만 trajectory frame으로 따라갑니다.'
            : '기본은 정렬된 reference pose를 보여주고, slider/play를 누르면 trajectory frame view로 전환됩니다.';
        return {
            ready,
            sliderReady,
            hasTrajectory,
            tone: movie.hasMovieScript ? 'warn' : 'muted',
            message: movie.hasMovieScript
                ? `${referenceCopy} Movie MP4는 아직 없습니다. Ligand update: ${describeTrajectoryUpdateMode(candidate)}. Render: ${describeTrajectoryRenderMode(candidate)}. Protein color: ${describeProteinFrameColorMode(candidate)}. Miss: ${describeFastPathMissReason(candidate)}. Coalesced: ${candidate?.trajectoryRenderStats?.coalescedFrameCount || 0}.`
                : `${referenceCopy} Ligand update: ${describeTrajectoryUpdateMode(candidate)}. Render: ${describeTrajectoryRenderMode(candidate)}. Protein color: ${describeProteinFrameColorMode(candidate)}. Miss: ${describeFastPathMissReason(candidate)}. Coalesced: ${candidate?.trajectoryRenderStats?.coalescedFrameCount || 0}.`,
        };
    }

    if (movie.hasMovieMp4) {
        return {
            ready,
            sliderReady,
            hasTrajectory,
            tone: 'good',
            message: 'Movie MP4 playback만 준비되어 있습니다. 3D trajectory frame 데이터는 없습니다.',
        };
    }

    if (movie.hasMovieScript) {
        return {
            ready,
            sliderReady,
            hasTrajectory,
            tone: 'warn',
            message: 'Playback용 MP4는 아직 없습니다. Turntable script만 준비되어 있어 deck controls는 비활성화됩니다.',
        };
    }

    return {
        ready,
        sliderReady,
        hasTrajectory,
        tone: 'muted',
        message: 'Trajectory NPZ와 Movie MP4가 모두 없어 playback deck을 사용할 수 없습니다.',
    };
}

function renderFileList() {
    const query = (dom.searchBox.value || '').trim().toLowerCase();
    const filtered = state.candidates.filter((candidate) => {
        const hay = [
            candidate.title,
            candidate.ligandId,
            candidate.targetId,
            candidate.translationGateStatus,
            candidate.shortlistTier,
        ].join(' ').toLowerCase();
        return !query || hay.includes(query);
    });

    if (!filtered.length) {
        dom.fileList.innerHTML = '<li class="empty-file-list">표시할 후보가 없습니다.</li>';
        return;
    }

    dom.fileList.innerHTML = filtered.map((candidate) => {
        const selected = candidate.index === state.selectedIndex;
        return `
            <li class="file-item-card ${selected ? 'active' : ''}" data-index="${candidate.index}">
              <div class="file-item-header">
                <div>
                  <div class="file-item-title">#${candidate.packetRank} ${escapeHtml(candidate.title)}</div>
                  <div class="file-item-subtitle">${escapeHtml(candidate.ligandId)}</div>
                </div>
                <div class="file-item-actions">
                  <button class="slot-chip ${state.compareSlots.A === candidate.index ? 'active' : ''}" data-action="slot-a">A</button>
                  <button class="slot-chip ${state.compareSlots.B === candidate.index ? 'active' : ''}" data-action="slot-b">B</button>
                </div>
              </div>
              <div class="chip-row">
                <span class="info-chip">${escapeHtml(candidate.translationGateStatus)}</span>
                <span class="info-chip">${escapeHtml(candidate.shortlistTier)}</span>
                <span class="info-chip">${formatNumber(candidate.commercialOverallScoreV2, 1)}</span>
              </div>
              <div class="metric-row">
                <span>d=${formatNumber(candidate.meanMinDistanceA, 3)}A</span>
                <span>E=${formatNumber(candidate.bindingEnergyProxy, 3)}</span>
                <span>CF=${formatNumber(candidate.contactFraction, 3)}</span>
              </div>
            </li>
        `;
    }).join('');
}

async function selectCandidate(index, { forceReload = false } = {}) {
    if (!Number.isFinite(index) || index < 0 || index >= state.candidates.length) return;
    if (!forceReload && state.selectedIndex === index) {
        renderSelectedCandidateSurfaces(state.candidates[index]);
        persistViewerSession();
        return;
    }

    stopTrajectoryPlayback();
    state.viewerMode = 'single';
    showSingleViewerLayout();
    state.selectedIndex = index;
    state.selectedTrajectoryCandidateIndex = index;
    state.trajectoryFrameIndex = 0;
    state.trajectorySceneMode = 'reference';
    state.cameraUserLocked = false;
    const candidate = state.candidates[index];
    renderFileList();
    renderSelectedCandidateSurfaces(candidate);
    await loadCandidateIntoViewer(candidate);
    renderSelectedCandidateSurfaces(candidate);
    syncTrajectoryUi();
    persistViewerSession();
}

function renderSelectedCandidateSurfaces(candidate) {
    renderStructureInfo(candidate);
    renderBindingInfo(candidate);
    renderSceneGuide(candidate);
    renderInteractionLegend(candidate);
    renderMediaSection(candidate);
    renderQuickStats(candidate);
    renderViewerAnnotations(candidate);
    renderCharts();
    updateProteinMotionSmokeState(candidate);
}

function updateProteinMotionSmokeState(candidate) {
    if (state.smokePreset !== 'protein-motion') return;
    if (!candidate) {
        setSmokeState('pending', { candidateLoaded: false }, 'candidate not selected');
        return;
    }
    const trajectory = candidate.trajectoryData;
    const schemaLabel = describeProteinTrajectorySchemaLabel(candidate);
    const checks = {
        bundleLoaded: Boolean(state.bundlePayload && state.candidates.length),
        smokeSurfaceSelected: normalizeSurfaceLabelKey(candidate.surfaceLabel) === 'proteinatomframessmoke',
        structureResolved: Boolean(candidate.activeStructurePath),
        trajectoryLoaded: Boolean(trajectory?.frameCount),
        proteinAtomSchemaReady: Boolean(trajectory?.proteinAtomSchemaReady),
        proteinAtomVersion: firstTruthy(trajectory?.proteinAtomSchemaVersion, ''),
        proteinSchemaLabel: schemaLabel,
        focusedSceneCacheReady: Boolean(candidate.fastTrajectorySceneCache),
        templateAtomCount: Array.isArray(candidate.proteinTemplateAtoms) ? candidate.proteinTemplateAtoms.length : 0,
        storedAtomCount: Number(trajectory?.proteinAtomFrames?.shape?.[1] || 0),
    };
    const passed = (
        checks.bundleLoaded
        && checks.smokeSurfaceSelected
        && checks.structureResolved
        && checks.trajectoryLoaded
        && checks.proteinAtomSchemaReady
        && /^full motion/.test(String(schemaLabel || ''))
        && checks.templateAtomCount > 0
        && checks.storedAtomCount > 0
    );
    setSmokeState(
        passed ? 'pass' : 'pending',
        checks,
        passed
            ? 'synthetic bundle/pdb/npz loaded and protein_atom_frames schema is visible in the UI'
            : 'waiting for synthetic bundle load, trajectory parse, or schema surface update',
    );
}

function updateCompareWritebackSmokeState() {
    if (state.smokePreset !== 'compare-writeback') return;
    const beforeLoaded = Array.isArray(state.writebackCompare.beforeCandidates) && state.writebackCompare.beforeCandidates.length > 0;
    const matchedCount = state.writebackCompare.pairs.filter((pair) => pair.status === 'matched').length;
    const pair = getSelectedWritebackPair();
    const diffReady = Boolean(pair?.beforeCandidate && pair?.afterCandidate);
    const resultsExplorerReady = Boolean(dom.compareBeforeAfter?.textContent?.trim());
    const diffMatrixReady = Boolean(dom.compareDiffMatrix?.textContent?.includes('Diff Row Matrix'));
    const decisionActionsReady = Boolean(dom.compareDecisionBoard?.querySelector('[data-action="writeback-side"], [data-action="writeback-superpose"]'));
    const splitVisible = Boolean(dom.compareSplitLayout) && window.getComputedStyle(dom.compareSplitLayout).display !== 'none';
    const compareGeometryA = collectViewerGeometryDebugState(state.compareViewers?.A || null);
    const compareGeometryB = collectViewerGeometryDebugState(state.compareViewers?.B || null);
    const geometryFailureCount = [compareGeometryA, compareGeometryB].filter((entry) => entry.failureKind === 'genuine_failure').length;
    const meshProbeUnavailableCount = [compareGeometryA, compareGeometryB].filter((entry) => entry.failureKind === 'mesh_probe_unavailable').length;
    const checks = {
        bundleLoaded: Boolean(state.bundlePayload && state.candidates.length),
        beforeBundleLoaded: beforeLoaded,
        matchedRows: matchedCount,
        selectedPairReady: diffReady,
        resultsExplorerReady,
        diffMatrixReady,
        decisionActionsReady,
        splitVisible,
        compareViewerAGeometryStatus: compareGeometryA.statusKind,
        compareViewerBGeometryStatus: compareGeometryB.statusKind,
        compareViewerAGeometryLabel: compareGeometryA.statusLabel,
        compareViewerBGeometryLabel: compareGeometryB.statusLabel,
        geometryFailureCount,
        meshProbeUnavailableCount,
        activeBundleSource: state.activeBundleSourceLabel || '',
        beforeBundleSource: state.writebackCompare.beforeSourceLabel || '',
    };
    const passed = (
        checks.bundleLoaded
        && checks.beforeBundleLoaded
        && checks.matchedRows > 0
        && checks.selectedPairReady
        && checks.resultsExplorerReady
        && checks.diffMatrixReady
        && checks.decisionActionsReady
    );
    const status = geometryFailureCount > 0 && (checks.selectedPairReady || checks.splitVisible)
        ? 'fail'
        : passed
            ? 'pass'
            : 'pending';
    const message = status === 'fail'
        ? 'compare viewers should be ready, but plugin/canvas3d geometry probing is unavailable in at least one pane'
        : passed
            ? (meshProbeUnavailableCount > 0
                ? 'writeback before/after bundle pairing, diff row matrix, and results explorer are visible; compare viewer is ready but mesh probe is unavailable, so state-cell geometry presence is used'
                : 'writeback before/after bundle pairing, diff row matrix, and results explorer are visible')
            : 'waiting for before bundle upload, matched row selection, or compare console render';
    setSmokeState(
        status,
        checks,
        message,
    );
}

function renderStructureInfo(candidate) {
    const loadedPath = firstTruthy(candidate.activeStructurePath, candidate.structurePath, candidate.fallbackStructurePath);
    const surfaceMapFormat = firstTruthy(candidate.surfaceMapFormat, inferVolumeFormat(candidate.surfaceMapPath));
    const movieState = resolveMovieUiState(candidate);
    const inspectionMode = describeInspectionSceneMode(
        candidate,
        state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null,
    );
    const proteinSchemaLabel = describeProteinTrajectorySchemaLabel(candidate);
    const fastMissBreakdown = describeFastPathMissBreakdown(candidate);
    const bvhDiagnostics = buildPocketContext(
        candidate,
        state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null,
    )?.bvhDiagnostics;
    const geometryPresence = describePocketGeometryPresence(candidate);
    dom.infoPanel.style.display = 'block';
    dom.structInfo.innerHTML = `
        <div class="info-grid">
          <div class="info-cell"><span>Target</span><strong>${escapeHtml(candidate.targetId)}</strong></div>
          <div class="info-cell"><span>Surface</span><strong>${escapeHtml(candidate.surfaceLabel || '-')}</strong></div>
          <div class="info-cell"><span>Ligand</span><strong>${escapeHtml(candidate.ligandId)}</strong></div>
          <div class="info-cell"><span>구조</span><strong>${escapeHtml(basenameOf(loadedPath || '-'))}</strong></div>
          <div class="info-cell"><span>Movie</span><strong>${escapeHtml(movieState.label)}</strong></div>
          <div class="info-cell"><span>Movie Asset</span><strong>${escapeHtml(movieState.assetStatus)}</strong></div>
          <div class="info-cell"><span>Source</span><strong>${escapeHtml(candidate.activeStructurePath ? 'resolved' : 'declared')}</strong></div>
          <div class="info-cell"><span>Path</span><strong>${escapeHtml(basenameOf(loadedPath || '-'))}</strong></div>
          <div class="info-cell"><span>Context</span><strong>${escapeHtml(candidate.viewerStructureContextMode)}</strong></div>
          <div class="info-cell"><span>Protein Context</span><strong>${candidate.viewerProteinContextValid ? 'available' : 'missing/coarse'}</strong></div>
          <div class="info-cell"><span>Protein Ref</span><strong>${candidate.proteinReferenceReady ? escapeHtml(basenameOf(candidate.proteinReferencePath)) : 'not ready'}</strong></div>
          <div class="info-cell"><span>Protein Ref Format</span><strong>${escapeHtml(candidate.proteinReferenceFormat || '-')}</strong></div>
          <div class="info-cell"><span>Viewer Mode</span><strong>${escapeHtml(candidate.proteinReferenceViewerMode)}</strong></div>
          <div class="info-cell"><span>Align Mode</span><strong>${escapeHtml(candidate.proteinReferenceAlignmentMode || '-')}</strong></div>
          <div class="info-cell"><span>Inspection Scene</span><strong>${escapeHtml(inspectionMode)}</strong></div>
          <div class="info-cell"><span>Binding View</span><strong>protein pocket + ligand spacefill</strong></div>
          <div class="info-cell"><span>APBS Map</span><strong>${candidate.surfaceMapPath ? escapeHtml(basenameOf(candidate.surfaceMapPath)) : 'not ready'}</strong></div>
          <div class="info-cell"><span>APBS Format</span><strong>${escapeHtml(surfaceMapFormat || '-')}</strong></div>
          <div class="info-cell"><span>Color Theme</span><strong>${escapeHtml(dom.colorSelect?.value || 'binding-focus')}</strong></div>
          <div class="info-cell"><span>Viewer Pose</span><strong>${candidate.viewerPosePdbReady ? escapeHtml(basenameOf(candidate.viewerPosePdb)) : 'not ready'}</strong></div>
          <div class="info-cell"><span>Protein CA</span><strong>${escapeHtml(String(candidate.viewerProteinCaCount || 0))}</strong></div>
          <div class="info-cell"><span>Protein Spread</span><strong>${Number.isFinite(candidate.viewerProteinCaSpreadA) ? `${formatNumber(candidate.viewerProteinCaSpreadA, 2)} A` : '-'}</strong></div>
          <div class="info-cell"><span>Quality Gate</span><strong>${candidate.viewerProteinContextQualityGatePass ? 'pass' : 'fail'}</strong></div>
          <div class="info-cell"><span>Backmap Protein Atoms</span><strong>${escapeHtml(String(candidate.backmappedProteinAtoms || 0))}</strong></div>
          <div class="info-cell"><span>RMSF Schema</span><strong>${candidate.trajectoryData?.proteinResidueSchemaReady ? escapeHtml(candidate.trajectoryData.proteinResidueSchemaVersion || 'ready') : 'not reported'}</strong></div>
          <div class="info-cell"><span>Protein Trajectory</span><strong>${escapeHtml(proteinSchemaLabel)}</strong></div>
          <div class="info-cell"><span>BVH Path</span><strong>${escapeHtml(describePocketBvhPath(candidate))}</strong></div>
          <div class="info-cell"><span>BVH Query</span><strong>${escapeHtml(describePocketBvhQuery(candidate))}</strong></div>
          <div class="info-cell"><span>Geometry State</span><strong>${escapeHtml(geometryPresence)}</strong></div>
          <div class="info-cell"><span>Geometry Probe</span><strong>${escapeHtml(describePocketGeometryProbe(candidate))}</strong></div>
          <div class="info-cell"><span>Renderable Count</span><strong>${escapeHtml(String(bvhDiagnostics?.geometryProbe?.canvas3d?.renderableCount || 0))}</strong></div>
          <div class="info-cell"><span>Triangle Est.</span><strong>${escapeHtml(String(bvhDiagnostics?.geometryProbe?.canvas3d?.primitiveEstimate || 0))}</strong></div>
          <div class="info-cell"><span>State Cells</span><strong>${escapeHtml(`${bvhDiagnostics?.geometryProbe?.activeStateCellCount || 0}/${bvhDiagnostics?.geometryProbe?.stateCellCount || 0}`)}</strong></div>
          <div class="info-cell"><span>BVH Nodes</span><strong>${escapeHtml(String(bvhDiagnostics?.nodeCount || 0))}</strong></div>
          <div class="info-cell"><span>BVH Leaves</span><strong>${escapeHtml(String(bvhDiagnostics?.leafCount || 0))}</strong></div>
          <div class="info-cell"><span>Fast Miss Breakdown</span><strong>${escapeHtml(fastMissBreakdown)}</strong></div>
        </div>
    `;
}

function renderBindingInfo(candidate) {
    const frame = getActiveTrajectoryFrame(candidate);
    const wetlab = getWetlabFocusSummary();
    const frameIndex = state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null;
    const interactionSummary = summarizeInteractionTypes(candidate, frameIndex);
    const pocketAnalytics = buildPocketAnalytics(
        candidate,
        frameIndex,
    );
    const extraMetricCards = buildTrajectoryExtraMetricCards(candidate, frame);
    const heatmapMode = describeProteinHeatmapMode(candidate);
    const proteinSchemaLabel = describeProteinTrajectorySchemaLabel(candidate);
    const fastMissBreakdown = describeFastPathMissBreakdown(candidate);
    const bvhDiagnostics = buildPocketContext(candidate, frameIndex)?.bvhDiagnostics;
    const geometryPresence = describePocketGeometryPresence(candidate, frameIndex);
    dom.bindingSection.style.display = 'block';
    dom.bindingInfo.innerHTML = `
        <div class="kpi-grid">
          ${kpiCard('Mean Min Distance', `${formatNumber(candidate.meanMinDistanceA, 3)} A`, candidate.meanMinDistanceA <= 2.5 ? 'good' : '')}
          ${kpiCard('Binding Energy', formatNumber(candidate.bindingEnergyProxy, 3))}
          ${kpiCard('Contact Fraction', formatNumber(candidate.contactFraction, 3))}
          ${kpiCard('Commercial v2', formatNumber(candidate.commercialOverallScoreV2, 1))}
          ${kpiCard('Translation Gate', escapeHtml(candidate.translationGateStatus))}
          ${kpiCard('Expensive Lane', escapeHtml(candidate.recommendedLane))}
          ${kpiCard('Trajectory', trajectoryStatusLabel(candidate))}
          ${kpiCard('Current Frame', frame ? `${frame.frameIndex + 1} / ${frame.frameCount}` : '-')}
          ${kpiCard('Frame Min Dist', frame ? `${formatNumber(frame.minDistanceA, 3)} A` : '-')}
          ${kpiCard('Centroid Shift', frame ? `${formatNumber(frame.centroidShiftA, 3)} A` : '-')}
          ${kpiCard('Wetlab Gate', wetlab.wetlabGatePassLabel)}
          ${kpiCard('Final Gate', wetlab.finalGatePassLabel)}
          ${kpiCard('Actionability', wetlab.actionabilityStatus)}
          ${kpiCard('Blocking Order', wetlab.blockingOrder)}
          ${kpiCard('Claim Mode', wetlab.rawClaimRequirementMode)}
          ${kpiCard('Interaction Types', interactionSummary.total ? interactionSummary.summaryShort : 'not reported')}
          ${kpiCard('RMSF Heatmap', heatmapMode)}
          ${kpiCard('Protein Trajectory', proteinSchemaLabel)}
          ${kpiCard('Pocket Volume', formatPocketVolumeLabel(pocketAnalytics.pocketVolumeA3))}
          ${kpiCard('BVH Path', describePocketBvhPath(candidate, frameIndex))}
          ${kpiCard('BVH Query', describePocketBvhQuery(candidate, frameIndex))}
          ${kpiCard('Geometry', geometryPresence)}
          ${kpiCard('Fast Miss Breakdown', fastMissBreakdown)}
          ${extraMetricCards.join('')}
        </div>
    `;

    const recipeRows = [
        candidate.translationGateReason ? `<li><strong>Gate Reason:</strong> ${escapeHtml(candidate.translationGateReason)}</li>` : '',
        candidate.recommendedLaneReason ? `<li><strong>Lane Reason:</strong> ${escapeHtml(candidate.recommendedLaneReason)}</li>` : '',
        candidate.recommendedLaneAction ? `<li><strong>Recommended Action:</strong> ${escapeHtml(candidate.recommendedLaneAction)}</li>` : '',
        candidate.actionCodesText ? `<li><strong>Action Codes:</strong> ${escapeHtml(candidate.actionCodesText)}</li>` : '',
        candidate.blockerCodesText ? `<li><strong>Blockers:</strong> ${escapeHtml(candidate.blockerCodesText)}</li>` : '',
        candidate.bindingRecipe ? `<li><strong>Binding Clip:</strong> ${escapeHtml(candidate.bindingRecipe)}</li>` : '',
        candidate.viewerProteinContextNote ? `<li><strong>Protein Context:</strong> ${escapeHtml(candidate.viewerProteinContextNote)}</li>` : '',
        candidate.viewerProteinContextReason ? `<li><strong>Protein Context Reason:</strong> ${escapeHtml(candidate.viewerProteinContextReason)}</li>` : '',
        candidate.proteinReferenceNote ? `<li><strong>Protein Reference:</strong> ${escapeHtml(candidate.proteinReferenceNote)}</li>` : '',
        candidate.proteinReferenceAlignmentMode ? `<li><strong>Protein Alignment:</strong> ${escapeHtml(candidate.proteinReferenceAlignmentMode)}</li>` : '',
        candidate.proteinReferenceViewerMode === 'unaligned_overlay' ? '<li><strong>Native Overlay:</strong> raw native protein is shown as an unaligned side overlay.</li>' : '',
        `<li><strong>Protein Trajectory Schema:</strong> ${escapeHtml(describeProteinTrajectorySchemaPrerequisites(candidate))}</li>`,
        `<li><strong>BVH Path:</strong> ${escapeHtml(describePocketBvhPath(candidate, frameIndex))} · nodes ${escapeHtml(String(bvhDiagnostics?.nodeCount || 0))} · leaves ${escapeHtml(String(bvhDiagnostics?.leafCount || 0))} · query ${escapeHtml(describePocketBvhQuery(candidate, frameIndex))}</li>`,
        `<li><strong>Geometry State:</strong> ${escapeHtml(geometryPresence)} · state cells ${escapeHtml(`${bvhDiagnostics?.geometryProbe?.activeStateCellCount || 0}/${bvhDiagnostics?.geometryProbe?.stateCellCount || 0}`)}</li>`,
        `<li><strong>Geometry Probe:</strong> ${escapeHtml(describePocketGeometryProbe(candidate, frameIndex))}</li>`,
        `<li><strong>Fast Miss Breakdown:</strong> ${escapeHtml(describeFastPathMissBreakdown(candidate, { long: true }))}</li>`,
        wetlab.translationSummary ? `<li><strong>Wetlab Translation:</strong> ${escapeHtml(wetlab.translationSummary)}</li>` : '',
        wetlab.commercialSummary ? `<li><strong>Wetlab Commercial:</strong> ${escapeHtml(wetlab.commercialSummary)}</li>` : '',
        wetlab.actionabilitySummary ? `<li><strong>Wetlab Actionability:</strong> ${escapeHtml(wetlab.actionabilitySummary)}</li>` : '',
        wetlab.actionRecipeRollup ? `<li><strong>Wetlab Recipe:</strong> ${escapeHtml(wetlab.actionRecipeRollup)}</li>` : '',
        interactionSummary.total ? `<li><strong>Interaction Mix:</strong> ${escapeHtml(interactionSummary.summaryLong)}</li>` : '',
    ].filter(Boolean);

    const customerReportCard = renderCustomerReportCard(candidate);
    const recipeMarkup = recipeRows.length
        ? `<ul class="action-list">${recipeRows.join('')}</ul>`
        : '<div class="contact-map-empty">현재 row에 추가 action recipe가 없습니다.</div>';
    dom.bindingRecipeList.innerHTML = `${customerReportCard}${recipeMarkup}`;
    renderLigand2DDepiction(candidate, frame);
    renderContactMap(candidate, frame, interactionSummary);
    renderResidueContactHeatmap(candidate, frame, pocketAnalytics);
    renderSequenceViewer(candidate, frame, pocketAnalytics);
}

function normalizeCustomerReportBlock(blockId, source = {}) {
    const rawBlock = source?.[blockId] || source?.blocks?.[blockId] || {};
    const status = firstTruthy(rawBlock.status, source.status, 'not_reported');
    return {
        sectionId: blockId,
        title: firstTruthy(rawBlock.title, humanizeCompactToken(blockId)),
        status,
        narrative: firstTruthy(rawBlock.narrative, rawBlock.customer_takeaway, rawBlock.customerTakeaway, ''),
        claimLimit: firstTruthy(rawBlock.claim_limit, rawBlock.claimLimit, source.claim_limit, ''),
        abstentionReason: firstTruthy(
            rawBlock.abstention_reason,
            rawBlock.abstentionReason,
            source.primary_abstention_reason,
            source.primaryAbstentionReason,
            '',
        ),
        whatWouldChangeDecision: firstTruthy(
            rawBlock.what_would_change_decision,
            rawBlock.whatWouldChangeDecision,
            source.what_would_change_decision,
            source.whatWouldChangeDecision,
            '',
        ),
    };
}

function renderCustomerReportCard(candidate) {
    const customerReportCard = candidate?.customerReportCard
        || candidate?.aiReportCustomerReportCard
        || candidate?.productAiReportUx?.customer_report_card
        || candidate?.productAiReportUx?.customerReportCard
        || null;
    if (!customerReportCard || typeof customerReportCard !== 'object') return '';
    const blocks = CUSTOMER_REPORT_REQUIRED_BLOCKS.map((blockId) => normalizeCustomerReportBlock(blockId, customerReportCard));
    const blockMarkup = blocks.map((block) => `
        <li>
          <strong>${escapeHtml(block.title)}</strong>
          <span>${escapeHtml(humanizeCompactToken(block.status))}</span>
          ${block.narrative ? `<p>${escapeHtml(block.narrative)}</p>` : ''}
          ${block.claimLimit ? `<em>${escapeHtml(block.claimLimit)}</em>` : ''}
        </li>
    `).join('');
    const primaryAbstention = firstTruthy(
        customerReportCard.primary_abstention_reason,
        customerReportCard.primaryAbstentionReason,
        'not_reported',
    );
    const whatWouldChange = firstTruthy(
        customerReportCard.what_would_change_decision,
        customerReportCard.whatWouldChangeDecision,
        '',
    );
    return `
        <div class="customer-report-card">
          <div class="section-title">AI Report</div>
          <div class="info-grid">
            <div class="info-cell"><span>Abstention</span><strong>${escapeHtml(humanizeCompactToken(primaryAbstention))}</strong></div>
            <div class="info-cell"><span>Allowed Scope</span><strong>${escapeHtml((customerReportCard.allowed_scope_families || customerReportCard.allowedScopeFamilies || []).join(', ') || 'not_reported')}</strong></div>
          </div>
          <ul class="action-list">${blockMarkup}</ul>
          ${whatWouldChange ? `<div class="analysis-empty">${escapeHtml(whatWouldChange)}</div>` : ''}
        </div>
    `;
}

function summarizeInteractionTypes(candidate, frameIndex = null) {
    if (!candidate) {
        return {
            counts: {},
            items: [],
            total: 0,
            dominantKind: '',
            summaryShort: 'not reported',
            summaryLong: 'interaction not reported',
        };
    }
    const effectiveFrameIndex = Number.isFinite(frameIndex)
        ? frameIndex
        : (state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null);
    const pocketContext = buildPocketContext(candidate, effectiveFrameIndex);
    const segments = Array.isArray(pocketContext.autoInteractions) ? pocketContext.autoInteractions : [];
    const counts = { hbond: 0, pipi: 0, hydrophobic: 0, contact: 0 };
    for (const segment of segments) {
        const kind = INTERACTION_KIND_META[segment?.kind] ? segment.kind : 'contact';
        counts[kind] += 1;
    }
    const items = Object.entries(counts)
        .filter(([, count]) => count > 0)
        .map(([kind, count]) => ({
            kind,
            count,
            label: INTERACTION_KIND_META[kind].label,
            shortLabel: INTERACTION_KIND_META[kind].shortLabel,
            color: INTERACTION_KIND_META[kind].color,
        }));
    const total = items.reduce((sum, item) => sum + item.count, 0);
    const dominant = items.slice().sort((a, b) => b.count - a.count)[0] || null;
    return {
        counts,
        items,
        total,
        dominantKind: dominant?.kind || '',
        summaryShort: items.length ? items.map((item) => `${item.shortLabel} ${item.count}`).join(' | ') : 'not reported',
        summaryLong: items.length ? items.map((item) => `${item.label} ${item.count}`).join(', ') : 'interaction not reported',
    };
}

function renderLigand2DDepiction(candidate, frame = null) {
    if (!dom.ligand2D) return;
    const model = buildLigandDepictionModel(candidate, frame);
    if (!model.atoms.length) {
        dom.ligand2D.innerHTML = '<div class="analysis-empty">리간드 좌표를 아직 해석하지 못했습니다.</div>';
        return;
    }

    const width = 300;
    const height = 220;
    const projected = projectLigandAtoms2D(model.atoms, width, height);
    const bonds = model.bonds.length ? model.bonds : inferLigandBonds(model.atoms);
    const bondMarkup = bonds
        .map((bond) => renderLigandBond2D(bond, projected.lookup))
        .filter(Boolean)
        .join('');
    const atomMarkup = projected.points.map((point) => `
        <g>
          <circle class="ligand-atom" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="${point.radius.toFixed(1)}" fill="${escapeHtml(point.color)}"></circle>
          <text class="ligand-atom-label" x="${point.x.toFixed(1)}" y="${point.y.toFixed(1)}" fill="${escapeHtml(point.textColor)}">${escapeHtml(point.label)}</text>
        </g>
    `).join('');
    const sourceLabel = model.sourceLabel || 'trajectory/projected';
    dom.ligand2D.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Ligand 2D depiction">
          ${bondMarkup}
          ${atomMarkup}
          <text class="ligand-caption" x="14" y="${height - 12}">source: ${escapeHtml(sourceLabel)} · atoms ${model.atoms.length} · bonds ${bonds.length}</text>
        </svg>
    `;
}

function buildLigandDepictionModel(candidate, frame = null) {
    const frameIndex = frame?.frameIndex ?? (state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null);
    const templateAtoms = Array.isArray(candidate?.ligandTemplateAtoms) ? candidate.ligandTemplateAtoms : [];
    const ligandPoints = getCandidateLigandCoords(candidate, frameIndex);
    const atoms = [];
    for (let index = 0; index < templateAtoms.length; index += 1) {
        const template = templateAtoms[index];
        const coords = ligandPoints[index] || atomToPoint(template);
        atoms.push({
            ...template,
            x: coords[0],
            y: coords[1],
            z: coords[2],
            sourceIndex: Number.isFinite(template?.sourceIndex) ? template.sourceIndex : index + 1,
        });
    }
    const bonds = Array.isArray(candidate?.activeStructureModel?.bonds) ? candidate.activeStructureModel.bonds : [];
    return {
        atoms,
        bonds,
        sourceLabel: bonds.length ? firstTruthy(candidate?.activeStructureModel?.sourceFormat, candidate?.activeStructureFormat, 'structure_model') : 'inferred_bond_layout',
    };
}

function projectLigandAtoms2D(atoms, width, height) {
    const ranges = ['x', 'y', 'z'].map((axis) => {
        const values = atoms.map((atom) => Number(atom?.[axis] || 0));
        return {
            axis,
            min: Math.min(...values),
            max: Math.max(...values),
            spread: Math.max(...values) - Math.min(...values),
        };
    }).sort((a, b) => b.spread - a.spread);
    const axisX = ranges[0]?.axis || 'x';
    const axisY = ranges[1]?.axis || 'y';
    const coords = atoms.map((atom) => ({
        atom,
        x: Number(atom?.[axisX] || 0),
        y: Number(atom?.[axisY] || 0),
    }));
    const minX = Math.min(...coords.map((entry) => entry.x));
    const maxX = Math.max(...coords.map((entry) => entry.x));
    const minY = Math.min(...coords.map((entry) => entry.y));
    const maxY = Math.max(...coords.map((entry) => entry.y));
    const spanX = Math.max(1e-3, maxX - minX);
    const spanY = Math.max(1e-3, maxY - minY);
    const scale = Math.min((width - 42) / spanX, (height - 42) / spanY);
    const lookup = new Map();
    const points = coords.map((entry) => {
        const x = 21 + (entry.x - minX) * scale;
        const y = height - 21 - (entry.y - minY) * scale;
        const color = ligandElementColor(atomElement(entry.atom));
        const textColor = ['#f8fafc', '#0f172a'].includes(color) ? '#0f172a' : '#ffffff';
        const point = {
            atom: entry.atom,
            x,
            y,
            radius: atomElement(entry.atom) === 'C' ? 8.2 : 9.2,
            color,
            textColor,
            label: ligandElementLabel(entry.atom),
        };
        lookup.set(point.atom.sourceIndex, point);
        return point;
    });
    return { points, lookup };
}

function renderLigandBond2D(bond, pointLookup) {
    const start = pointLookup.get(Number(bond?.from));
    const end = pointLookup.get(Number(bond?.to));
    if (!start || !end) return '';
    const type = String(bond?.type || '1').toLowerCase();
    const multiplicity = type === '2' ? 2 : (type === '3' ? 3 : 1);
    const normal = normalize2D([end.y - start.y, start.x - end.x]);
    const offset = multiplicity > 1 ? 2.1 : 0;
    const primary = `
        <line class="ligand-bond" x1="${(start.x + normal[0] * offset).toFixed(1)}" y1="${(start.y + normal[1] * offset).toFixed(1)}" x2="${(end.x + normal[0] * offset).toFixed(1)}" y2="${(end.y + normal[1] * offset).toFixed(1)}"></line>
    `;
    if (multiplicity === 1) return primary;
    const secondary = `
        <line class="ligand-bond double" x1="${(start.x - normal[0] * offset).toFixed(1)}" y1="${(start.y - normal[1] * offset).toFixed(1)}" x2="${(end.x - normal[0] * offset).toFixed(1)}" y2="${(end.y - normal[1] * offset).toFixed(1)}"></line>
    `;
    if (multiplicity === 2) return `${primary}${secondary}`;
    const tertiary = `
        <line class="ligand-bond" x1="${(start.x).toFixed(1)}" y1="${(start.y).toFixed(1)}" x2="${(end.x).toFixed(1)}" y2="${(end.y).toFixed(1)}"></line>
    `;
    return `${primary}${secondary}${tertiary}`;
}

function renderContactMap(candidate, frame = null, interactionSummary = null) {
    if (!dom.contactMap) return;
    const frameIndex = frame?.frameIndex ?? (state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null);
    const pocketContext = buildPocketContext(candidate, frameIndex);
    const interactions = Array.isArray(pocketContext.autoInteractions) ? pocketContext.autoInteractions.slice(0, 8) : [];
    if (!interactions.length) {
        dom.contactMap.innerHTML = '<div class="analysis-empty">자동 분류된 결합선이 아직 없습니다.</div>';
        return;
    }

    const width = 320;
    const rowHeight = 24;
    const height = Math.max(220, 70 + interactions.length * rowHeight);
    const ligandNode = { x: 72, y: height / 2 };
    const residueX = 248;
    const lines = interactions.map((segment, index) => {
        const y = 44 + index * rowHeight;
        const residueLabel = escapeHtml(firstTruthy(segment.residueLabel, segment.entryLabel, segment.label || 'Pocket residue'));
        const kind = INTERACTION_KIND_META[segment.kind] ? segment.kind : 'contact';
        return `
            <line class="contact-map-link ${kind}" x1="${ligandNode.x}" y1="${ligandNode.y}" x2="${residueX}" y2="${y}"></line>
            <rect class="contact-map-node" x="${(residueX - 8).toFixed(1)}" y="${(y - 11).toFixed(1)}" width="58" height="22" rx="11"></rect>
            <text class="contact-map-node-text" x="${(residueX + 21).toFixed(1)}" y="${(y + 3).toFixed(1)}">${residueLabel}</text>
            <text class="contact-map-distance" x="${(ligandNode.x + 78).toFixed(1)}" y="${(y - 5).toFixed(1)}">${escapeHtml(formatNumber(segment.distanceA, 2))}A · ${escapeHtml(INTERACTION_KIND_META[kind].label)}</text>
        `;
    }).join('');
    const summary = interactionSummary || summarizeInteractionTypes(candidate, frameIndex);
    dom.contactMap.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="2D contact map">
          <rect class="contact-map-node ligand" x="${(ligandNode.x - 40).toFixed(1)}" y="${(ligandNode.y - 18).toFixed(1)}" width="92" height="36" rx="18"></rect>
          <text class="contact-map-node-text" x="${ligandNode.x.toFixed(1)}" y="${(ligandNode.y + 4).toFixed(1)}">Ligand</text>
          ${lines}
          <text class="ligand-caption" x="14" y="${height - 10}">${escapeHtml(summary.summaryLong || 'interaction not reported')}</text>
        </svg>
    `;
}

function buildPocketAnalytics(candidate, frameIndex = null) {
    if (!candidate) {
        return {
            pocketVolumeA3: Number.NaN,
            volumeSource: 'not_reported',
            residues: [],
            matrix: [],
            closePairCount: 0,
        };
    }
    const key = `${candidate.index}:${Number.isFinite(frameIndex) ? frameIndex : 'ref'}`;
    if (candidate.pocketAnalyticsCache?.key === key) {
        return candidate.pocketAnalyticsCache.value;
    }
    const pocketContext = buildPocketContext(candidate, frameIndex);
    const residues = (pocketContext.focusResidues.length ? pocketContext.focusResidues : pocketContext.residues).slice(0, 12);
    const matrix = [];
    let closePairCount = 0;
    for (let rowIndex = 0; rowIndex < residues.length; rowIndex += 1) {
        const row = [];
        for (let colIndex = 0; colIndex < residues.length; colIndex += 1) {
            const distanceA = rowIndex === colIndex
                ? 0
                : pairResidueMinDistance(residues[rowIndex], residues[colIndex]);
            if (rowIndex < colIndex && Number.isFinite(distanceA) && distanceA <= 4.5) {
                closePairCount += 1;
            }
            row.push(distanceA);
        }
        matrix.push(row);
    }
    const ligandPoints = getCandidateLigandCoords(candidate, frameIndex);
    const explicitVolume = Number.isFinite(candidate.pocketVolumeA3) ? candidate.pocketVolumeA3 : Number.NaN;
    const pocketVolumeA3 = Number.isFinite(explicitVolume)
        ? explicitVolume
        : estimatePocketVolumeA3(pocketContext, ligandPoints);
    const analytics = {
        pocketVolumeA3,
        volumeSource: Number.isFinite(explicitVolume) ? (candidate.pocketVolumeSource || 'bundle_explicit') : 'viewer_grid_estimate',
        residues,
        matrix,
        closePairCount,
    };
    candidate.pocketAnalyticsCache = { key, value: analytics };
    return analytics;
}

function pairResidueMinDistance(a, b) {
    let minDistanceSq = Number.POSITIVE_INFINITY;
    const atomsA = (a?.atoms || []).filter((atom) => !isHydrogenAtom(atom));
    const atomsB = (b?.atoms || []).filter((atom) => !isHydrogenAtom(atom));
    for (const atomA of atomsA) {
        for (const atomB of atomsB) {
            const distSq = squaredDistance(atomToPoint(atomA), atomToPoint(atomB));
            if (distSq < minDistanceSq) minDistanceSq = distSq;
        }
    }
    return Number.isFinite(minDistanceSq) ? Math.sqrt(minDistanceSq) : Number.NaN;
}

function estimatePocketVolumeA3(pocketContext, ligandPoints) {
    const proteinAtoms = (pocketContext?.surfaceAtoms?.length ? pocketContext.surfaceAtoms : pocketContext?.selectedAtoms || [])
        .filter((atom) => !isHydrogenAtom(atom))
        .slice(0, 220);
    if (!proteinAtoms.length || !ligandPoints.length) return Number.NaN;
    const centroid = computeCentroid(ligandPoints);
    const allPoints = proteinAtoms.map((atom) => atomToPoint(atom)).concat(ligandPoints);
    const min = [
        Math.min(...allPoints.map((point) => point[0])) - 1.5,
        Math.min(...allPoints.map((point) => point[1])) - 1.5,
        Math.min(...allPoints.map((point) => point[2])) - 1.5,
    ];
    const max = [
        Math.max(...allPoints.map((point) => point[0])) + 1.5,
        Math.max(...allPoints.map((point) => point[1])) + 1.5,
        Math.max(...allPoints.map((point) => point[2])) + 1.5,
    ];
    const step = 1.0;
    let count = 0;
    for (let x = min[0]; x <= max[0]; x += step) {
        for (let y = min[1]; y <= max[1]; y += step) {
            for (let z = min[2]; z <= max[2]; z += step) {
                const voxel = [x, y, z];
                const nearLigand = ligandPoints.some((point) => distanceBetween(point, voxel) <= 6.4);
                if (!nearLigand) continue;
                const nearCentroid = distanceBetween(centroid, voxel) <= 7.4;
                if (!nearCentroid) continue;
                const clashesProtein = proteinAtoms.some((atom) => {
                    const radius = vdwRadius(atomElement(atom)) + 0.2;
                    return distanceBetween(atomToPoint(atom), voxel) <= radius;
                });
                if (clashesProtein) continue;
                count += 1;
            }
        }
    }
    return count * step * step * step;
}

function vdwRadius(element) {
    const table = {
        H: 1.2, C: 1.7, N: 1.55, O: 1.52, F: 1.47, P: 1.8, S: 1.8, Cl: 1.75, Br: 1.85, I: 1.98,
    };
    return table[element] || 1.7;
}

function formatPocketVolumeLabel(value) {
    return Number.isFinite(value) ? `${formatNumber(value, 1)} A^3` : 'not reported';
}

function renderResidueContactHeatmap(candidate, frame = null, pocketAnalytics = null) {
    if (!dom.residueContactHeatmap || !dom.pocketVolumeDisplay || !dom.residueContactMeta) return;
    const analytics = pocketAnalytics || buildPocketAnalytics(
        candidate,
        frame?.frameIndex ?? (state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null),
    );
    dom.pocketVolumeDisplay.innerHTML = `
        <div class="pocket-volume-stat">
          <span>Pocket Volume</span>
          <strong>${escapeHtml(formatPocketVolumeLabel(analytics.pocketVolumeA3))}</strong>
        </div>
        <div class="pocket-volume-stat">
          <span>Source</span>
          <strong>${escapeHtml(analytics.volumeSource)}</strong>
        </div>
        <div class="pocket-volume-stat">
          <span>Residues</span>
          <strong>${escapeHtml(String(analytics.residues.length))}</strong>
        </div>
        <div class="pocket-volume-stat">
          <span>Close Pairs</span>
          <strong>${escapeHtml(String(analytics.closePairCount))}</strong>
        </div>
    `;
    if (!analytics.residues.length || !analytics.matrix.length) {
        dom.residueContactHeatmap.innerHTML = '<div class="analysis-empty">residue-residue heatmap을 만들 pocket residue가 부족합니다.</div>';
        dom.residueContactMeta.innerHTML = '';
        return;
    }
    const cell = 24;
    const padding = 86;
    const size = analytics.residues.length * cell;
    const width = padding + size + 12;
    const height = padding + size + 18;
    const labels = analytics.residues.map((residue) => `${residue.residueName || 'UNK'} ${residue.residueSeq || '?'}`);
    const cells = [];
    for (let rowIndex = 0; rowIndex < analytics.residues.length; rowIndex += 1) {
        for (let colIndex = 0; colIndex < analytics.residues.length; colIndex += 1) {
            const distanceA = analytics.matrix[rowIndex][colIndex];
            const tone = heatmapToneForDistance(distanceA, rowIndex === colIndex);
            const x = padding + colIndex * cell;
            const y = 28 + rowIndex * cell;
            cells.push(`
                <rect class="residue-heatmap-cell ${tone}" data-row-index="${rowIndex}" data-col-index="${colIndex}" x="${x}" y="${y}" width="${cell - 2}" height="${cell - 2}" rx="4"></rect>
                <title>${escapeHtml(`${labels[rowIndex]} ↔ ${labels[colIndex]}: ${Number.isFinite(distanceA) ? `${formatNumber(distanceA, 2)} A` : 'n/a'}`)}</title>
            `);
        }
    }
    const axisLabels = analytics.residues.map((residue, index) => {
        const x = padding + index * cell + (cell / 2) - 1;
        const y = 28 + index * cell + 14;
        const shortLabel = `${residueOneLetterCode(residue.residueName)}${residue.residueSeq || index + 1}`;
        return `
            <text class="residue-heatmap-axis x" x="${x}" y="18" text-anchor="middle" transform="rotate(-45 ${x} 18)">${escapeHtml(shortLabel)}</text>
            <text class="residue-heatmap-axis y" x="${padding - 10}" y="${y}" text-anchor="end">${escapeHtml(shortLabel)}</text>
        `;
    }).join('');
    dom.residueContactHeatmap.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Residue contact heatmap">
          ${cells.join('')}
          ${axisLabels}
        </svg>
    `;
    dom.residueContactMeta.innerHTML = `
        <div class="heatmap-legend">
          <span class="heatmap-chip tight">tight <= 4.0A</span>
          <span class="heatmap-chip near">near <= 5.0A</span>
          <span class="heatmap-chip weak">weak <= 6.0A</span>
          <span class="heatmap-chip far">far</span>
        </div>
        <div class="heatmap-copy">
          ${escapeHtml(frame ? `trajectory frame ${frame.frameIndex + 1}` : 'reference pocket')} · ${escapeHtml(String(analytics.residues.length))} residues · ${escapeHtml(String(analytics.closePairCount))} close residue pairs
        </div>
    `;
}

function heatmapToneForDistance(distanceA, diagonal = false) {
    if (diagonal) return 'self';
    if (!Number.isFinite(distanceA)) return 'unknown';
    if (distanceA <= 4.0) return 'tight';
    if (distanceA <= 5.0) return 'near';
    if (distanceA <= 6.0) return 'weak';
    return 'far';
}

function renderSequenceViewer(candidate, frame = null, pocketAnalytics = null) {
    if (!dom.sequenceViewer || !dom.sequenceSummary) return;
    const proteinAtoms = Array.isArray(candidate?.proteinTemplateAtoms) ? candidate.proteinTemplateAtoms : [];
    if (!proteinAtoms.length) {
        dom.sequenceSummary.textContent = 'protein template residue가 아직 없습니다.';
        dom.sequenceViewer.innerHTML = '<div class="analysis-empty">sequence viewer를 만들 protein residue가 없습니다.</div>';
        return;
    }
    const groups = getProteinResidueGroups(candidate, proteinAtoms);
    if (!groups.length) {
        dom.sequenceSummary.textContent = 'residue group이 없습니다.';
        dom.sequenceViewer.innerHTML = '<div class="analysis-empty">sequence viewer data가 없습니다.</div>';
        return;
    }
    const analytics = pocketAnalytics || buildPocketAnalytics(
        candidate,
        frame?.frameIndex ?? (state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null),
    );
    const focusKeys = new Set((analytics.residues || []).map((entry) => entry.key));
    const fullContext = buildPocketContext(candidate, frame?.frameIndex ?? null);
    const shellKeys = new Set((fullContext.shellResidues || []).map((entry) => entry.key));
    const lookup = buildProteinResidueBFactorLookup(candidate, frame?.frameIndex ?? null) || new Map();
    const items = groups.map((group, index) => {
        const key = group.key;
        const isFocus = focusKeys.has(key);
        const isShell = shellKeys.has(key);
        const value = lookup.get(key);
        return {
            key,
            residueName: group.residueName,
            residueSeq: group.atoms?.[0]?.residueSeq || String(index + 1),
            chainId: group.atoms?.[0]?.chainId || '_',
            oneLetter: residueOneLetterCode(group.residueName),
            tone: isFocus ? 'focus' : (isShell ? 'shell' : 'muted'),
            heat: sequenceHeatTone(value),
            value,
            atoms: group.atoms,
        };
    });
    const focusIndices = items.map((item, index) => ({ item, index })).filter(({ item }) => item.tone !== 'muted');
    let sliceStart = 0;
    let sliceEnd = items.length;
    if (items.length > 140 && focusIndices.length) {
        sliceStart = Math.max(0, focusIndices[0].index - 18);
        sliceEnd = Math.min(items.length, focusIndices[focusIndices.length - 1].index + 19);
    }
    const visibleItems = items.slice(sliceStart, sliceEnd);
    dom.sequenceSummary.textContent = [
        `residues ${visibleItems.length}/${items.length}`,
        `focus ${focusIndices.length}`,
        `heatmap ${describeProteinHeatmapMode(candidate)}`,
    ].join(' | ');
    dom.sequenceViewer.innerHTML = visibleItems.map((item) => `
        <button class="sequence-residue ${escapeHtml(item.tone)} ${escapeHtml(item.heat)}" data-residue-key="${escapeHtml(item.key)}" type="button" title="${escapeHtml(`${item.residueName} ${item.chainId}${item.residueSeq}${Number.isFinite(item.value) ? ` | heat ${formatNumber(item.value, 1)}` : ''}`)}">
          <span class="sequence-code">${escapeHtml(item.oneLetter)}</span>
          <span class="sequence-index">${escapeHtml(item.residueSeq)}</span>
        </button>
    `).join('');
}

function residueOneLetterCode(name) {
    const table = {
        ALA: 'A', ARG: 'R', ASN: 'N', ASP: 'D', CYS: 'C', GLN: 'Q', GLU: 'E', GLY: 'G',
        HIS: 'H', ILE: 'I', LEU: 'L', LYS: 'K', MET: 'M', PHE: 'F', PRO: 'P', SER: 'S',
        THR: 'T', TRP: 'W', TYR: 'Y', VAL: 'V',
    };
    return table[String(name || '').toUpperCase()] || 'X';
}

function sequenceHeatTone(value) {
    if (!Number.isFinite(value)) return 'heat-unknown';
    if (value >= 45) return 'heat-high';
    if (value >= 30) return 'heat-mid';
    return 'heat-low';
}

function describeProteinHeatmapMode(candidate) {
    const trajectory = candidate?.trajectoryData;
    if (!trajectory?.proteinResidueSchemaReady) return 'not reported';
    if (trajectory.proteinResidueCentroids?.data && Array.isArray(trajectory.proteinResidueBFactors) && trajectory.proteinResidueBFactors.length) {
        return 'dynamic frame-aware';
    }
    if (Array.isArray(trajectory.proteinResidueBFactors) && trajectory.proteinResidueBFactors.length) {
        return 'static bfactor';
    }
    if (Array.isArray(trajectory.proteinResidueRmsf) && trajectory.proteinResidueRmsf.length) {
        return 'static rmsf';
    }
    return 'schema ready';
}

function inferLigandBonds(atoms) {
    const bonds = [];
    for (let i = 0; i < atoms.length; i += 1) {
        for (let j = i + 1; j < atoms.length; j += 1) {
            const atomA = atoms[i];
            const atomB = atoms[j];
            const maxDistance = covalentRadius(atomElement(atomA)) + covalentRadius(atomElement(atomB)) + 0.45;
            const distanceA = distanceBetween(atomToPoint(atomA), atomToPoint(atomB));
            if (Number.isFinite(distanceA) && distanceA > 0.4 && distanceA <= maxDistance) {
                bonds.push({ from: atomA.sourceIndex, to: atomB.sourceIndex, type: 1, aromatic: Boolean(atomA.aromatic && atomB.aromatic) });
            }
        }
    }
    return bonds;
}

function covalentRadius(element) {
    const table = {
        H: 0.31, C: 0.76, N: 0.71, O: 0.66, F: 0.57, P: 1.07, S: 1.05, Cl: 1.02, Br: 1.2, I: 1.39,
    };
    return table[element] || 0.77;
}

function ligandElementColor(element) {
    const palette = {
        C: '#94a3b8',
        N: '#3b82f6',
        O: '#ef4444',
        S: '#eab308',
        P: '#f97316',
        F: '#22c55e',
        Cl: '#16a34a',
        Br: '#a16207',
        I: '#7c3aed',
    };
    return palette[element] || '#cbd5e1';
}

function ligandElementLabel(atom) {
    const element = atomElement(atom);
    return element === 'C' ? '' : element;
}

function normalize2D(point) {
    const length = Math.hypot(point[0], point[1]) || 1;
    return [point[0] / length, point[1] / length];
}

function renderInteractionLegend(candidate) {
    if (!dom.interactionLegend) return;
    const summary = summarizeInteractionTypes(candidate);
    const markup = Object.entries(INTERACTION_KIND_META).map(([kind, meta]) => {
        const count = summary.counts?.[kind] || 0;
        return `
            <div class="legend-item legend-item-interaction" style="--c: ${escapeHtml(meta.color)};">
              <span class="legend-swatch"></span>
              <span>${escapeHtml(meta.label)}${count ? ` · ${count}` : ''}</span>
            </div>
        `;
    }).join('');
    dom.interactionLegend.innerHTML = markup;
}

function buildTrajectoryExtraMetricCards(candidate, frame) {
    const trajectory = candidate?.trajectoryData;
    if (!trajectory) return [];
    const frameMetrics = frame?.extraMetrics || {};
    const cards = [];
    const preferred = ['radius_of_gyration', 'rg', 'rmsd', 'sasa_proxy', 'hbond_count', 'contact_occupancy', 'energy_std'];
    const seen = new Set();

    for (const key of preferred) {
        const value = Number.isFinite(frameMetrics[key]) ? frameMetrics[key] : trajectory.extraScalars?.[key];
        if (!Number.isFinite(value)) continue;
        seen.add(key);
        cards.push(kpiCard(trajectory.extraMetricLabels?.[key] || formatTrajectoryMetricLabel(key), formatNumber(value, 3)));
    }

    for (const [key, value] of Object.entries(frameMetrics)) {
        if (seen.has(key) || !Number.isFinite(value)) continue;
        cards.push(kpiCard(trajectory.extraMetricLabels?.[key] || formatTrajectoryMetricLabel(key), formatNumber(value, 3)));
    }

    return cards;
}

function renderSceneGuide(candidate) {
    if (!candidate) {
        dom.sceneGuidePanel.style.display = 'none';
        dom.sceneGuidePanel.innerHTML = '';
        return;
    }

    const frameIndex = state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null;
    const inspectionMode = describeInspectionSceneMode(candidate, frameIndex);
    const proteinStatusTone = candidate.proteinReferenceAligned ? 'good' : 'warn';
    const proteinStatusText = candidate.proteinReferenceAligned
        ? 'aligned native protein reference'
        : 'backmapped/coarse protein context';
    const sceneChips = [
        `<span class="scene-guide-chip ${proteinStatusTone}">${escapeHtml(proteinStatusText)}</span>`,
        `<span class="scene-guide-chip ${candidate.viewerProteinContextQualityGatePass ? 'good' : 'warn'}">${escapeHtml(candidate.viewerProteinContextQualityGatePass ? 'trajectory protein context pass' : `trajectory protein context ${candidate.viewerProteinContextReason || 'coarse'}`)}</span>`,
        `<span class="scene-guide-chip ${state.trajectorySceneMode === 'reference' ? 'good' : 'warn'}">${escapeHtml(state.trajectorySceneMode === 'reference' ? 'reference close-up' : `trajectory frame ${state.trajectoryFrameIndex + 1}`)}</span>`,
        `<span class="scene-guide-chip ${trajectoryUpdateModeTone(candidate)}">${escapeHtml(`ligand update ${describeTrajectoryUpdateMode(candidate)}`)}</span>`,
        `<span class="scene-guide-chip muted">${escapeHtml(`bvh ${describePocketBvhPath(candidate, frameIndex)}`)}</span>`,
        `<span class="scene-guide-chip muted">${escapeHtml(`geometry ${describePocketGeometryProbe(candidate, frameIndex)}`)}</span>`,
        `<span class="scene-guide-chip muted">${escapeHtml(`render ${describeTrajectoryRenderMode(candidate)}`)}</span>`,
        `<span class="scene-guide-chip muted">${escapeHtml(`miss ${describeFastPathMissReason(candidate)}`)}</span>`,
    ];
    const cautionText = !candidate.viewerProteinContextQualityGatePass && candidate.proteinReferenceAligned
        ? 'Trajectory protein context는 coarse해서 inspection은 aligned native pocket close-up을 기준으로 보여줍니다. 슬라이더를 움직이면 ligand만 frame-wise로 따라갑니다.'
        : 'Protein pocket과 ligand를 분리해 보여주므로 약물 결합 부위를 더 직관적으로 볼 수 있습니다.';

    dom.sceneGuidePanel.style.display = 'grid';
    dom.sceneGuidePanel.innerHTML = `
        <section class="scene-guide-card">
          <h4>Binding Close-up</h4>
          <p class="scene-guide-copy">${escapeHtml(inspectionMode)}</p>
          <div class="scene-guide-list">
            <div class="scene-guide-row">
              <span class="scene-guide-swatch protein">Protein</span>
              <div>
                <strong>Pocket backbone</strong>
                <span>리간드 주변 backbone trace와 근접 residue shell만 남겨서 전체 단백질 clutter를 줄였습니다.</span>
              </div>
            </div>
            <div class="scene-guide-row">
              <span class="scene-guide-swatch contact">Contact</span>
              <div>
                <strong>Contact sidechains</strong>
                <span>결합부에 직접 가까운 residue sidechain만 sticks로 유지합니다. 점선 overlay는 실제 contact 후보를 표시합니다.</span>
              </div>
            </div>
            <div class="scene-guide-row">
              <span class="scene-guide-swatch ligand">Ligand</span>
              <div>
                <strong>Ligand focus</strong>
                <span>리간드는 spacefill로 강조합니다. 결합부 확대를 누르면 reference pocket close-up으로 다시 정렬됩니다.</span>
              </div>
            </div>
          </div>
        </section>
        <section class="scene-guide-card">
          <h4>Scene Basis</h4>
          <p class="scene-guide-copy">${escapeHtml(cautionText)}</p>
          <div class="scene-guide-chip-row">
            ${sceneChips.join('')}
          </div>
        </section>
    `;
}

function describeInspectionSceneMode(candidate, frameIndex = null) {
    if (!candidate) return 'No inspection scene loaded.';
    if (Number.isFinite(frameIndex)) {
        if (!candidate.viewerProteinContextQualityGatePass && candidate.proteinReferenceAligned) {
            return 'Hybrid trajectory close-up: aligned native protein pocket + trajectory ligand frame.';
        }
        return 'Trajectory close-up: pocket residues are rebuilt around the current ligand frame.';
    }
    if (candidate.proteinReferenceAligned) {
        return 'Reference pocket close-up: aligned native protein pocket + viewer ligand pose.';
    }
    return 'Fallback close-up: available protein context + viewer ligand pose.';
}

function renderViewerAnnotations(candidate) {
    if (!candidate) {
        hideViewerAnnotations();
        return;
    }

    if (state.viewerMode !== 'single') {
        dom.viewerAnnotationLayer.style.display = 'grid';
        dom.annotationPanel.style.display = '';
        setViewerAnnotationExpanded(false, { silent: true });
        dom.annotationStrip.innerHTML = overlayPill('Mode', state.viewerMode, 'info');
        dom.annotationHero.innerHTML = `
            <h4>Viewer Overlay</h4>
            <div class="annotation-empty">비교 모드에서는 single-candidate wetlab/native annotation overlay를 단순화합니다.</div>
        `;
        dom.annotationContact.innerHTML = '';
        dom.annotationTranslation.innerHTML = '';
        dom.annotationBlockers.innerHTML = '';
        return;
    }

    const wetlab = getWetlabFocusSummary();
    const frame = getActiveTrajectoryFrame(candidate);
    const contactState = classifyContactState(candidate, frame);
    const interactionSummary = summarizeInteractionTypes(candidate, state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null);
    const blockers = uniqueTruthy([
        splitCodeText(candidate.blockerCodesText),
        wetlab.effectivePrimaryBlockingDomain,
        wetlab.rawClaimRequirementMode === 'not_reported' ? '' : `claim:${wetlab.rawClaimRequirementMode}`,
    ]);
    const actions = uniqueTruthy([
        splitCodeText(candidate.actionCodesText),
        wetlab.actionRecipeCodes,
        candidate.recommendedLaneAction,
    ]);
    const headerPills = [
        overlayPill('Surface', candidate.surfaceLabel || state.activeSurfaceLabel || '-', 'info'),
        overlayPill('Viewer', candidate.proteinReferenceViewerMode || 'none', candidate.proteinReferenceAligned ? 'good' : 'warn'),
        overlayPill('Alignment', candidate.proteinReferenceAlignmentMode || 'not_reported', candidate.proteinReferenceAligned ? 'good' : 'warn'),
        overlayPill('Wetlab', wetlab.actionabilityStatus || 'not_reported', toneForStatus(wetlab.actionabilityStatus)),
        overlayPill('Contact', contactState.label, contactState.tone),
    ];

    dom.viewerAnnotationLayer.style.display = 'grid';
    dom.annotationPanel.style.display = '';
    updateViewerAnnotationUi();
    dom.annotationStrip.innerHTML = headerPills.join('');
    dom.annotationHero.innerHTML = `
        <h4>Aligned Native Reference</h4>
        <div class="annotation-hero-header">
          <div>
            <p class="annotation-hero-title">${escapeHtml(candidate.title)}</p>
            <p class="annotation-hero-subtitle">
              ${escapeHtml(candidate.targetId)} · rank #${escapeHtml(String(candidate.packetRank))}
            </p>
          </div>
          <div class="annotation-pill-group">
            ${overlayPill('Final Gate', wetlab.finalGatePassLabel, wetlab.wetlabFinalGatePass ? 'good' : 'bad')}
            ${overlayPill('Claim', wetlab.rawClaimRequirementMode, toneForStatus(wetlab.rawClaimRequirementMode))}
          </div>
        </div>
        <div class="annotation-metric-grid">
          ${annotationMetric('Render', candidate.renderStructureKind || 'not_reported')}
          ${annotationMetric('Viewer Pose', candidate.viewerPosePdbReady ? basenameOf(candidate.viewerPosePdb) : 'not ready')}
          ${annotationMetric('Commercial v2', formatNumber(candidate.commercialOverallScoreV2, 1))}
          ${annotationMetric('Blocking Order', wetlab.blockingOrder || 'not_reported')}
        </div>
      `;
    dom.annotationContact.innerHTML = `
        <h4>Wetlab / Contact</h4>
        <div class="annotation-metric-grid">
          ${annotationMetric('Mean Distance', `${formatNumber(candidate.meanMinDistanceA, 3)} A`)}
          ${annotationMetric('Frame Distance', frame && Number.isFinite(frame.minDistanceA) ? `${formatNumber(frame.minDistanceA, 3)} A` : 'n/a')}
          ${annotationMetric('Contact Fraction', formatNumber(candidate.contactFraction, 3))}
          ${annotationMetric('Stability', formatNumber(candidate.stabilityScore, 3))}
          ${annotationMetric('Trajectory Frames', String(candidate.trajectoryFrames || 0))}
          ${annotationMetric('Protein CA Gate', candidate.viewerProteinContextQualityGatePass ? 'pass' : candidate.viewerProteinContextReason || 'fail')}
        </div>
        <div class="annotation-pill-group annotation-pill-group-compact">
          ${interactionSummary.items.length
            ? interactionSummary.items.map((item) => overlayPill(item.label, String(item.count), 'info')).join('')
            : overlayPill('Interaction', 'not_reported', 'muted')}
        </div>
        ${annotationList(
            interactionSummary.items.length
                ? interactionSummary.items.map((item) => `${item.label}: ${item.count}`)
                : [],
            'interaction typing data가 없습니다.',
        )}
      `;
    dom.annotationTranslation.innerHTML = `
        <h4>Translation / Lane</h4>
        <div class="annotation-metric-grid">
          ${annotationMetric('Translation', candidate.translationGateStatus || wetlab.translationFocusStatus || 'not_reported')}
          ${annotationMetric('Shortlist', candidate.shortlistTier || 'not_reported')}
          ${annotationMetric('Next Lane', candidate.recommendedLane || 'not_reported')}
          ${annotationMetric('Focus Score', Number.isFinite(wetlab.translationFocusScore) ? formatNumber(wetlab.translationFocusScore, 1) : 'n/a')}
        </div>
        ${annotationList(
            uniqueTruthy([
                candidate.translationGateReason,
                wetlab.translationFocusReason,
                candidate.recommendedLaneReason,
                candidate.renderStructureNote,
            ]),
            'translation/blocking note가 아직 없습니다.',
        )}
      `;
    dom.annotationDetailGrid.innerHTML = `
        <section class="annotation-card">
          <h4>Trajectory Render Diagnostics</h4>
          <div class="annotation-metric-grid">
            ${annotationMetric('Render', describeTrajectoryRenderMode(candidate))}
            ${annotationMetric('Ligand Update', describeTrajectoryUpdateMode(candidate))}
            ${annotationMetric('Protein Color', describeProteinFrameColorMode(candidate))}
            ${annotationMetric('Fast Miss', describeFastPathMissReason(candidate))}
            ${annotationMetric('Fast Miss Count', String(candidate?.trajectoryRenderStats?.fastPathMissCount || 0))}
            ${annotationMetric('Coalesced', String(candidate?.trajectoryRenderStats?.coalescedFrameCount || 0))}
          </div>
          ${annotationList(
              [describeFastPathMissBreakdown(candidate, { long: true })],
              'render diagnostics가 아직 없습니다.',
          )}
        </section>
        <section class="annotation-card">
          <h4>Protein Trajectory Schema</h4>
          <div class="annotation-metric-grid">
            ${annotationMetric('Trajectory', candidate?.trajectoryData ? `${candidate.trajectoryData.frameCount || 0} frames` : 'not loaded')}
            ${annotationMetric('Schema', describeProteinTrajectorySchemaLabel(candidate))}
            ${annotationMetric('Version', candidate?.trajectoryData?.proteinResidueSchemaVersion || 'not reported')}
            ${annotationMetric('Centroids', candidate?.trajectoryData?.proteinResidueCentroids?.data ? 'frame-wise ready' : 'missing')}
            ${annotationMetric('Residue Scalars', Array.isArray(candidate?.trajectoryData?.proteinResidueBFactors) && candidate.trajectoryData.proteinResidueBFactors.length ? 'bfactor/rmsf ready' : 'missing')}
            ${annotationMetric('Template Atoms', String(candidate?.proteinTemplateAtoms?.length || 0))}
          </div>
          ${annotationList(
              [describeProteinTrajectorySchemaPrerequisites(candidate)],
              'protein trajectory schema note가 없습니다.',
          )}
        </section>
      `;
    dom.annotationBlockers.innerHTML = `
        <h4>Blockers / Action Recipe</h4>
        ${annotationList(blockers, 'blocking code가 없습니다.')}
        <div class="annotation-pill-group" style="margin-top:0.7rem;">
          ${actions.length
            ? actions.map((code) => overlayPill('Action', code, 'warn')).join('')
            : overlayPill('Action', 'not_reported', 'muted')}
        </div>
      `;
}

function hideViewerAnnotations() {
    dom.viewerAnnotationLayer.style.display = 'none';
    dom.annotationPanel.style.display = 'none';
    dom.annotationStrip.innerHTML = '';
    dom.annotationHero.innerHTML = '';
    dom.annotationContact.innerHTML = '';
    dom.annotationTranslation.innerHTML = '';
    dom.annotationDetailGrid.innerHTML = '';
    dom.annotationBlockers.innerHTML = '';
}

function updateViewerAnnotationUi() {
    if (!dom.viewerAnnotationLayer) return;
    dom.annotationPanel?.classList.toggle('collapsed', !state.annotationExpanded);
    if (dom.btnToggleAnnotations) {
        dom.btnToggleAnnotations.textContent = state.annotationExpanded ? '상세 숨기기' : '상세 보기';
        dom.btnToggleAnnotations.setAttribute('aria-pressed', state.annotationExpanded ? 'true' : 'false');
        dom.btnToggleAnnotations.title = state.annotationExpanded
            ? 'viewer 상세 annotation 숨기기'
            : 'viewer 상세 annotation 보기';
    }
}

function setViewerAnnotationExpanded(expanded, options = {}) {
    state.annotationExpanded = Boolean(expanded);
    updateViewerAnnotationUi();
    if (!options.silent && state.selectedIndex >= 0) {
        renderViewerAnnotations(getSelectedCandidate());
    }
}

function renderQuickStats(candidate = null) {
    const summary = state.bundleSummary || {};
    const focus = candidate || state.candidates[state.selectedIndex] || null;
    const wetlabRow = getBlockerSurfaceRow('wetlab_execution_readiness');
    const wetlabSignal = parseSignalMap(wetlabRow?.source_signal);
    const wetlabSummary = state.blockerSurface.wetlabDashboard?.summary || {};
    const wetlabReadinessSummary = state.blockerSurface.wetlabReadiness?.summary || {};
    const queueSummary = state.blockerSurface.queue?.summary || {};
    const viewerRow = getBlockerSurfaceRow('viewer_usability');
    const blockerKpis = queueSummary.row_count
        ? [
            { label: 'Engine Queue', value: `${queueSummary.blocked_count || 0} blocked / ${queueSummary.partial_count || 0} partial` },
            { label: 'Viewer Lane', value: humanizeCompactToken(viewerRow?.status || 'not_reported') },
            { label: 'Wetlab Lane', value: humanizeCompactToken(wetlabRow?.status || 'not_reported') },
            {
                label: 'Exec Rows',
                value: wetlabReadinessSummary.row_count
                    ? `${wetlabReadinessSummary.ready_row_count || 0} ready / ${(wetlabReadinessSummary.blocked_row_count || 0) + (wetlabReadinessSummary.partial_row_count || 0)} blocked`
                    : '-',
            },
            {
                label: 'Exec Ready',
                value: String(
                    wetlabReadinessSummary.execution_ready_now_row_count
                    ?? wetlabSummary.broad_screen_execution_ready_now_row_count
                    ?? wetlabSignal.execution_ready_now_row_count
                    ?? '-',
                ),
            },
            {
                label: 'Watch Gap',
                value: String(
                    wetlabReadinessSummary.watch_gap_count
                    ?? wetlabSignal.watch_gap_count
                    ?? (
                        [wetlabSummary.broad_screen_primary_watch_liveness, wetlabSummary.broad_screen_antitarget_watch_liveness]
                            .filter((value) => ['stale', 'detached'].includes(String(value || '').trim().toLowerCase()))
                            .length || '-'
                    ),
                ),
            },
        ]
        : [];
    const kpis = [
        ...blockerKpis,
        { label: 'Top-K', value: summary.topk_count ?? state.candidates.length ?? 0 },
        { label: 'Figure', value: summary.figure_count ?? 0 },
        { label: 'Movie Plan', value: summary.movie_plan_count ?? 0 },
        { label: 'Binding Clip', value: summary.binding_event_candidate_count ?? 0 },
        { label: 'Focus Rank', value: focus ? `#${focus.packetRank}` : '-' },
        { label: 'Target', value: focus ? focus.targetId : summary.target_id || '-' },
        { label: 'Surface', value: focus ? focus.surfaceLabel : summary.selected_surface_label || '-' },
        { label: 'Trajectory', value: focus ? trajectoryStatusLabel(focus) : '-' },
        { label: 'Ligand Update', value: focus ? describeTrajectoryUpdateMode(focus) : '-' },
        { label: 'Render', value: focus ? describeTrajectoryRenderMode(focus) : '-' },
        { label: 'Protein Color', value: focus ? describeProteinFrameColorMode(focus) : '-' },
        { label: 'BVH', value: focus ? describePocketBvhPath(focus) : '-' },
        { label: 'Geometry', value: focus ? describePocketGeometryPresence(focus) : '-' },
        { label: 'Fast Miss', value: focus ? describeFastPathMissReason(focus) : '-' },
        { label: 'Coalesced', value: focus?.trajectoryRenderStats ? String(focus.trajectoryRenderStats.coalescedFrameCount || 0) : '-' },
        { label: 'Frame', value: focus && focus.trajectoryData ? `${state.trajectoryFrameIndex + 1}/${focus.trajectoryData.frameCount}` : '-' },
    ];
    dom.quickStats.style.display = kpis.length ? 'block' : 'none';
    dom.kpiMiniGrid.innerHTML = kpis.map(({ label, value }) => `
        <div class="mini-kpi">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(String(value))}</strong>
        </div>
    `).join('');
}

function renderMediaSection(candidate) {
    const movieState = resolveMovieUiState(candidate);
    const figureUrl = resolveAssetUrl(candidate.figurePath);
    const movieUrl = movieState.hasMovieMp4 ? resolveAssetUrl(candidate.movieMp4Path) : '';
    const dashboardUrl = resolveAssetUrl(candidate.dashboardPath);
    const hasVisualAssets = Boolean(figureUrl || movieUrl);
    const mediaStatusMessage = figureUrl
        ? movieState.hasMovieMp4
            ? 'Figure와 Movie MP4가 모두 준비되어 있습니다.'
            : `${movieState.message} Figure는 준비되어 있습니다.`
        : movieState.message;

    dom.mediaSection.style.display = 'block';
    dom.mediaMeta.innerHTML = `
        <div class="media-meta-row"><span>Figure</span><code>${escapeHtml(candidate.figurePath || '-')}</code></div>
        <div class="media-meta-row"><span>Movie</span><code>${escapeHtml(candidate.movieMp4Path || '-')}</code></div>
        <div class="media-meta-row"><span>Movie Script</span><code>${escapeHtml(candidate.movieScriptPath || '-')}</code></div>
        <div class="media-meta-row"><span>Movie State</span><code>${escapeHtml(movieState.assetStatus)}</code></div>
        <div class="media-meta-row"><span>Trajectory</span><code>${escapeHtml(candidate.trajectoryPath || '-')}</code></div>
        <div class="media-meta-row"><span>Trajectory State</span><code>${escapeHtml(trajectoryStatusLabel(candidate))}</code></div>
    `;
    dom.mediaStatus.className = `status-banner ${movieState.tone}`;
    dom.mediaStatus.textContent = mediaStatusMessage;
    dom.mediaStatus.style.display = 'block';

    if (figureUrl) {
        dom.figurePreview.src = figureUrl;
        dom.figurePreview.style.display = 'block';
    } else {
        dom.figurePreview.removeAttribute('src');
        dom.figurePreview.style.display = 'none';
    }

    if (movieUrl) {
        if (state.activePreviewUrl !== movieUrl) {
            dom.videoPreview.src = movieUrl;
            state.activePreviewUrl = movieUrl;
        }
        dom.videoPreview.style.display = 'block';
        dom.mediaEmpty.style.display = 'none';
    } else {
        dom.videoPreview.pause();
        dom.videoPreview.removeAttribute('src');
        dom.videoPreview.load();
        dom.videoPreview.style.display = 'none';
        state.activePreviewUrl = '';
        dom.mediaEmpty.textContent = movieState.hasMovieScript
            ? 'Movie MP4가 아직 렌더되지 않았습니다. Turntable script만 준비되어 있습니다.'
            : '선택된 후보의 피규어/영상 자산이 없습니다.';
        dom.mediaEmpty.style.display = hasVisualAssets ? 'none' : 'block';
    }

    dom.btnOpenFigure.disabled = !figureUrl;
    dom.btnOpenFigure.dataset.path = figureUrl || '';
    dom.btnFigureModal.disabled = !figureUrl;
    dom.btnFigureModal.dataset.path = figureUrl || '';
    dom.btnOpenMovie.disabled = !movieUrl;
    dom.btnOpenMovie.dataset.path = movieUrl || '';
    dom.btnOpenMovie.textContent = movieUrl
        ? 'Movie 열기'
        : movieState.hasMovieScript
            ? 'Movie 미렌더'
            : 'Movie 없음';
    dom.btnOpenMovie.title = mediaStatusMessage;
    dom.btnOpenDashboard.disabled = !dashboardUrl;
    dom.btnOpenDashboard.dataset.path = dashboardUrl || '';

    syncTrajectoryUi();
}

function populateMetricSelect() {
    if (dom.metricSelect.options.length) return;
    const metrics = [
        ['mean_min_distance_A', 'Mean Min Distance'],
        ['binding_energy_proxy', 'Binding Energy'],
        ['contact_fraction', 'Contact Fraction'],
        ['stability_score', 'Stability'],
        ['commercial_overall_score_v2', 'Commercial v2'],
        ['trajectory_frames', 'Trajectory Frames'],
    ];
    dom.metricSelect.innerHTML = metrics.map(([value, label]) => {
        const selected = DEFAULT_METRICS.includes(value) ? 'selected' : '';
        return `<option value="${value}" ${selected}>${label}</option>`;
    }).join('');
}

function renderCharts() {
    if (!state.candidates.length) {
        dom.chartsSection.style.display = 'none';
        return;
    }

    const selectedCandidate = getSelectedCandidate();
    const hasTrajectory = Boolean(selectedCandidate?.trajectoryData?.frameCount);
    dom.chartsSection.style.display = 'block';
    dom.chartsGrid.innerHTML = `
        <div class="chart-card"><div id="chartMetricsByRank" class="chart-host"></div></div>
        <div class="chart-card"><div id="chartDistanceEnergy" class="chart-host"></div></div>
        ${hasTrajectory ? '<div class="chart-card"><div id="chartTrajectoryDistance" class="chart-host"></div></div>' : ''}
        ${hasTrajectory ? '<div class="chart-card"><div id="chartTrajectoryDisplacement" class="chart-host"></div></div>' : ''}
        ${hasTrajectory && hasTrajectoryExtraSeries(selectedCandidate) ? '<div class="chart-card"><div id="chartTrajectoryAux" class="chart-host"></div></div>' : ''}
    `;

    const selectedMetrics = Array.from(dom.metricSelect.selectedOptions).map((option) => option.value);
    const x = state.candidates.map((candidate) => `#${candidate.packetRank}`);

    const traces = selectedMetrics.map((metric) => ({
        type: 'scatter',
        mode: 'lines+markers',
        name: metric,
        x,
        y: state.candidates.map((candidate) => toFloat(candidateValue(candidate, metric))),
    }));

    Plotly.newPlot('chartMetricsByRank', traces, {
        title: 'Top-k Metric Profile',
        margin: { t: 42, r: 18, b: 42, l: 42 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        legend: { orientation: 'h' },
    }, { responsive: true, displaylogo: false });

    Plotly.newPlot('chartDistanceEnergy', [{
        type: 'scatter',
        mode: 'markers+text',
        x: state.candidates.map((candidate) => candidate.meanMinDistanceA),
        y: state.candidates.map((candidate) => candidate.bindingEnergyProxy),
        text: state.candidates.map((candidate) => `#${candidate.packetRank}`),
        textposition: 'top center',
        marker: {
            size: state.candidates.map((candidate) => Math.max(14, candidate.contactFraction * 34)),
            color: state.candidates.map((candidate) => candidate.commercialOverallScoreV2),
            colorscale: 'Turbo',
            showscale: true,
            line: { color: '#0f172a', width: 1 },
        },
        customdata: state.candidates.map((candidate) => candidate.title),
        hovertemplate: '%{customdata}<br>distance=%{x:.3f}A<br>energy=%{y:.3f}<extra></extra>',
    }], {
        title: 'Distance vs Energy',
        margin: { t: 42, r: 18, b: 42, l: 52 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        xaxis: { title: 'Mean Min Distance (A)' },
        yaxis: { title: 'Binding Energy Proxy' },
    }, { responsive: true, displaylogo: false });

    if (hasTrajectory) {
        renderTrajectoryCharts(selectedCandidate);
    }
}

async function loadCandidateIntoViewer(candidate) {
    const attemptedCandidates = uniqueTruthy(candidate?.structurePathCandidates);
    const structurePath = await resolveFirstReadablePath(attemptedCandidates);
    if (!structurePath) {
        const attempted = attemptedCandidates
            .slice(0, 4)
            .map((pathLike) => basenameOf(resolveAssetUrl(pathLike) || pathLike))
            .filter(Boolean)
            .join(', ');
        const message = attempted
            ? `구조 경로 읽기 실패: ${attempted}`
            : '구조 경로가 없습니다.';
        clearViewerOverlay(true, message);
        toast(`${message}. 현재 탭을 강력 새로고침(Ctrl+Shift+R) 후 다시 시도하세요.`, 'warn');
        return;
    }

    try {
        const rawText = await fetchText(structurePath);
        const format = inferStructureFormat(structurePath);
        const normalized = normalizeStructureInput(rawText, format, structurePath);
        state.viewerMode = 'single';
        candidate.proteinTemplateAtoms = null;
        candidate.ligandTemplateAtoms = null;
        candidate.pocketContextCache = null;
        candidate.pocketAnalyticsCache = null;
        candidate.proteinResidueGroups = null;
        candidate.proteinResidueBFactorLookup = null;
        candidate.framePdbCache = new Map();
        candidate.ligandFramePdbCache = new Map();
        candidate.proteinFrameAtomCache = new Map();
        candidate.proteinFrameCoordCache = new Map();
        candidate.fastTrajectorySceneCache = null;
        candidate.fastTrajectorySceneSignatureCache = new Map();
        candidate.lastRenderedTrajectoryFrame = -1;
        candidate.activeStructureText = normalized.text;
        candidate.activeStructureFormat = normalized.format;
        candidate.activeStructureModel = normalized.model;
        const trajectory = await ensureTrajectoryRenderable(candidate);
        await loadFocusedCandidateScene(candidate, trajectory?.frameCount ? null : null);
        refreshInteractionOverlayData(candidate, trajectory?.frameCount ? null : state.trajectoryFrameIndex);
        candidate.activeStructurePath = structurePath;
        clearViewerOverlay(false);
    } catch (error) {
        console.error(error);
        clearViewerOverlay(true, `구조 로드 실패: ${basenameOf(structurePath)}`);
        toast(`구조 로드 실패: ${error.message}`, 'error');
    }
}

async function loadCandidatePairCompareMode(mode, beforeCandidate, afterCandidate, options = {}) {
    const {
        beforeRoleLabel = 'A',
        afterRoleLabel = 'B',
        compareSummaryLabel = mode === 'superpose' ? 'Real Superposition' : 'True Split-Screen Side-by-Side',
        compareToastPrefix = mode === 'superpose' ? '중첩' : '나란히',
    } = options;
    if (!beforeCandidate || !afterCandidate) return;
    stopTrajectoryPlayback();

    try {
        const [pathA, pathB] = await Promise.all([
            resolveFirstReadablePath([beforeCandidate.compareStructurePath, ...beforeCandidate.structurePathCandidates]),
            resolveFirstReadablePath([afterCandidate.compareStructurePath, ...afterCandidate.structurePathCandidates]),
        ]);
        if (!pathA || !pathB) {
            throw new Error('비교용 구조 파일을 찾지 못했습니다. visual bundle에 protein-containing PDB/mmCIF가 필요합니다.');
        }
        const [textA, textB] = await Promise.all([
            fetchText(pathA),
            fetchText(pathB),
        ]);
        const formatA = inferStructureFormat(pathA);
        const formatB = inferStructureFormat(pathB);

        if (formatA !== 'pdb' || formatB !== 'pdb') {
            throw new Error('현재 real superposition은 PDB 비교에만 지원됩니다.');
        }

        const modelA = parsePdbStructure(textA);
        const modelB = parsePdbStructure(textB);
        const alignment = alignPdbModels(modelA, modelB, { sideBySide: mode === 'side-by-side' });

        state.viewerMode = 'compare';
        state.cameraUserLocked = false;
        cancelMeasurementMode({ clearHighlights: true });
        clearInteractionOverlay();
        dom.sceneGuidePanel.style.display = 'none';
        dom.sceneGuidePanel.innerHTML = '';
        if (mode === 'side-by-side') {
            await ensureCompareViewers();
            showCompareSplitLayout();
            await clearViewer();
            await clearCompareViewers();
            await Promise.all([
                loadStructureIntoNamedViewer(state.compareViewers.A, textA, 'pdb'),
                loadStructureIntoNamedViewer(state.compareViewers.B, alignment.transformedPdbText, 'pdb'),
            ]);
            dom.compareViewerATitle.textContent = `${beforeRoleLabel} · #${beforeCandidate.packetRank} ${beforeCandidate.title}`;
            dom.compareViewerBTitle.textContent = `${afterRoleLabel} · #${afterCandidate.packetRank} ${afterCandidate.title}`;
            clearViewerOverlay(false);
        } else {
            showSingleViewerLayout();
            await loadStructureTextIntoViewer(textA, 'pdb');
            await state.viewer.loadStructureFromData(alignment.transformedPdbText, 'pdb', buildLoadOptions());
            clearViewerOverlay(false);
        }
        renderCompareConsole();
        setSmokeState(state.smokeState?.status || 'idle', state.smokeState?.checks || {}, state.smokeState?.message || '');

        const summary = [
            `${mode === 'superpose' ? '중첩 비교' : '나란히 비교'} 완료`,
            `${beforeRoleLabel} #${beforeCandidate.packetRank}: ${beforeCandidate.title}`,
            `${afterRoleLabel} #${afterCandidate.packetRank}: ${afterCandidate.title}`,
            `anchor_mode=${alignment.anchorMode}`,
            `anchors=${alignment.anchorCount}`,
            `RMSD=${formatNumber(alignment.rmsdA, 3)} A`,
            `Δdistance=${formatNumber((beforeCandidate.meanMinDistanceA || 0) - (afterCandidate.meanMinDistanceA || 0), 3)} A`,
            `Δcommercial=${formatNumber((beforeCandidate.commercialOverallScoreV2 || 0) - (afterCandidate.commercialOverallScoreV2 || 0), 1)}`,
        ];
        if (alignment.offsetAppliedA > 0) {
            summary.push(`offset=${formatNumber(alignment.offsetAppliedA, 2)} A`);
        }

        dom.rmsdResult.style.display = 'block';
        dom.rmsdResult.innerHTML = `
            <div class="compare-summary">
              <strong>${escapeHtml(compareSummaryLabel)}</strong>
              <div>${escapeHtml(summary.join(' | '))}</div>
            </div>
        `;
        renderViewerAnnotations(getSelectedCandidate());
        toast(`${compareToastPrefix} 비교 준비 완료: ${alignment.anchorMode} RMSD ${formatNumber(alignment.rmsdA, 3)} A`, 'success');
    } catch (error) {
        console.error(error);
        dom.rmsdResult.style.display = 'block';
        dom.rmsdResult.innerHTML = `
            <div class="compare-summary">
              <strong>비교 실패</strong>
              <div>${escapeHtml(error.message)}</div>
            </div>
        `;
        renderViewerAnnotations(getSelectedCandidate());
        toast(`비교 로드 실패: ${error.message}`, 'error');
    }
}

async function loadCompareMode(mode) {
    const a = state.candidates[state.compareSlots.A];
    const b = state.candidates[state.compareSlots.B];
    if (!a || !b) return;
    await loadCandidatePairCompareMode(mode, a, b, {
        beforeRoleLabel: 'A',
        afterRoleLabel: 'B',
    });
}

function assignCompareSlot(slot, index) {
    state.compareSlots[slot] = state.compareSlots[slot] === index ? null : index;
    updateCompareUi();
    renderFileList();
    persistViewerSession();
}

function updateCompareUi() {
    const a = state.candidates[state.compareSlots.A];
    const b = state.candidates[state.compareSlots.B];

    dom.slotA.className = `compare-slot ${a ? 'filled' : 'empty'}`;
    dom.slotA.innerHTML = `
        <span class="slot-label">A</span>
        <span class="slot-text">${escapeHtml(a ? `${a.packetRank}. ${a.title}` : 'A 핀으로 선택')}</span>
    `;
    dom.slotB.className = `compare-slot ${b ? 'filled' : 'empty'}`;
    dom.slotB.innerHTML = `
        <span class="slot-label">B</span>
        <span class="slot-text">${escapeHtml(b ? `${b.packetRank}. ${b.title}` : 'B 핀으로 선택')}</span>
    `;

    const ready = Boolean(a && b);
    dom.btnSuperpose.disabled = !ready;
    dom.btnSideBySide.disabled = !ready;
    void renderCompareConsole();
}

function formatCompareConsoleValue(candidate, metric) {
    const value = candidateValue(candidate, metric.key);
    if (!Number.isFinite(Number(value))) return 'n/a';
    const suffix = metric.unit ? ` ${metric.unit}` : '';
    return `${formatNumber(Number(value), metric.precision)}${suffix}`;
}

function inferDashboardJsonPath(candidate) {
    const raw = String(candidate?.dashboardPath || '').trim();
    if (!raw) return '';
    if (raw.toLowerCase().endsWith('.json')) return raw;
    if (raw.toLowerCase().endsWith('.html')) return raw.replace(/\.html$/i, '.json');
    return '';
}

async function ensureDashboardDecisionBoard(candidate) {
    if (!candidate) return null;
    if (Object.prototype.hasOwnProperty.call(candidate, 'dashboardDecisionBoard')) {
        return candidate.dashboardDecisionBoard;
    }
    const jsonPath = inferDashboardJsonPath(candidate);
    if (!jsonPath) {
        candidate.dashboardDecisionBoard = null;
        return null;
    }
    try {
        const payload = await fetchJson(jsonPath);
        const board = payload?.summary?.decision_board || null;
        candidate.dashboardDecisionBoard = board;
        return board;
    } catch (_error) {
        candidate.dashboardDecisionBoard = null;
        return null;
    }
}

function writebackCandidateMatchKeys(candidate) {
    return uniqueTruthy([
        String(candidate?.ligandId || '').trim().toLowerCase(),
        String(candidate?.title || '').trim().toLowerCase(),
        candidate?.ligandId && candidate?.targetId
            ? `${String(candidate.targetId).trim().toLowerCase()}::${String(candidate.ligandId).trim().toLowerCase()}`
            : '',
        Number.isFinite(candidate?.packetRank) ? `rank:${candidate.packetRank}` : '',
    ]);
}

function buildWritebackPairKey(beforeCandidate, afterCandidate, index = 0) {
    return uniqueTruthy([
        afterCandidate?.ligandId,
        beforeCandidate?.ligandId,
        afterCandidate?.title,
        beforeCandidate?.title,
        Number.isFinite(afterCandidate?.packetRank) ? `rank-${afterCandidate.packetRank}` : '',
        Number.isFinite(beforeCandidate?.packetRank) ? `rank-${beforeCandidate.packetRank}` : '',
        `pair-${index}`,
    ])[0] || `pair-${index}`;
}

function computeWritebackComparePairs(beforeCandidates, afterCandidates) {
    const beforeIndex = new Map();
    const beforeUsed = new Set();
    for (const candidate of beforeCandidates) {
        for (const key of writebackCandidateMatchKeys(candidate)) {
            if (!beforeIndex.has(key)) beforeIndex.set(key, []);
            beforeIndex.get(key).push(candidate);
        }
    }

    const pairs = [];
    for (const afterCandidate of afterCandidates) {
        let matchedBefore = null;
        for (const key of writebackCandidateMatchKeys(afterCandidate)) {
            const pool = beforeIndex.get(key) || [];
            matchedBefore = pool.find((candidate) => !beforeUsed.has(candidate.index));
            if (matchedBefore) break;
        }
        if (matchedBefore) beforeUsed.add(matchedBefore.index);
        pairs.push({
            key: buildWritebackPairKey(matchedBefore, afterCandidate, pairs.length),
            beforeCandidate: matchedBefore,
            afterCandidate,
            status: matchedBefore ? 'matched' : 'added_after',
        });
    }

    for (const beforeCandidate of beforeCandidates) {
        if (beforeUsed.has(beforeCandidate.index)) continue;
        pairs.push({
            key: buildWritebackPairKey(beforeCandidate, null, pairs.length),
            beforeCandidate,
            afterCandidate: null,
            status: 'removed_after',
        });
    }
    return pairs;
}

function syncWritebackCompareWithCurrentBundle() {
    const beforeCandidates = Array.isArray(state.writebackCompare.beforeCandidates)
        ? state.writebackCompare.beforeCandidates
        : [];
    state.writebackCompare.pairs = computeWritebackComparePairs(beforeCandidates, state.candidates);
    const activeKey = state.writebackCompare.selectedPairKey;
    if (activeKey && state.writebackCompare.pairs.some((pair) => pair.key === activeKey)) return;
    const preferred = state.writebackCompare.pairs.find((pair) => pair.status === 'matched')
        || state.writebackCompare.pairs[0]
        || null;
    state.writebackCompare.selectedPairKey = preferred?.key || '';
}

function getSelectedWritebackPair() {
    const pairKey = state.writebackCompare.selectedPairKey;
    return state.writebackCompare.pairs.find((pair) => pair.key === pairKey) || null;
}

async function handleWritebackBeforeBundleInput(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
        const payload = JSON.parse(await file.text());
        state.writebackCompare.beforePayload = payload;
        state.writebackCompare.beforeSummary = payload?.summary || {};
        state.writebackCompare.beforeCandidates = buildNormalizedCandidatesFromPayload(payload, `writeback before: ${file.name}`);
        state.writebackCompare.beforeSourceLabel = file.name;
        syncWritebackCompareWithCurrentBundle();
        await renderCompareConsole();
        toast(`Writeback before bundle 로드 완료: ${file.name}`, 'success');
    } catch (error) {
        console.error(error);
        toast(`Writeback before bundle 파싱 실패: ${error.message}`, 'error');
    } finally {
        event.target.value = '';
    }
}

function clearWritebackCompare() {
    state.writebackCompare.beforePayload = null;
    state.writebackCompare.beforeSummary = null;
    state.writebackCompare.beforeCandidates = [];
    state.writebackCompare.beforeSourceLabel = '';
    state.writebackCompare.pairs = [];
    state.writebackCompare.selectedPairKey = '';
}

function comparePairLabel(pair) {
    if (pair?.status === 'matched') return 'matched';
    if (pair?.status === 'added_after') return 'after only';
    if (pair?.status === 'removed_after') return 'before only';
    return pair?.status || 'unknown';
}

function compareConsoleWriteback(metric, beforeCandidate, afterCandidate) {
    const before = Number(candidateValue(beforeCandidate, metric.key));
    const after = Number(candidateValue(afterCandidate, metric.key));
    if (!Number.isFinite(before) || !Number.isFinite(after)) {
        return { label: 'review', className: 'review', winner: 'n/a' };
    }
    if (Math.abs(after - before) < 1e-9) {
        return { label: 'hold', className: 'review', winner: 'tie' };
    }
    const preferAfter = metric.direction === 'lower' ? after < before : after > before;
    return preferAfter
        ? { label: 'writeback B', className: 'prefer-b', winner: 'B' }
        : { label: 'keep A', className: 'prefer-a', winner: 'A' };
}

function compareConsoleDelta(metric, beforeCandidate, afterCandidate) {
    const before = Number(candidateValue(beforeCandidate, metric.key));
    const after = Number(candidateValue(afterCandidate, metric.key));
    if (!Number.isFinite(before) || !Number.isFinite(after)) {
        return { label: 'n/a', tone: 'muted' };
    }
    const delta = after - before;
    const better = metric.direction === 'lower' ? delta < 0 : delta > 0;
    const tone = Math.abs(delta) < 1e-9 ? 'muted' : (better ? 'good' : 'bad');
    const suffix = metric.unit ? ` ${metric.unit}` : '';
    return {
        label: `${delta >= 0 ? '+' : ''}${formatNumber(delta, metric.precision)}${suffix}`,
        tone,
    };
}

function renderCompareFieldValue(candidate, descriptor) {
    const value = descriptor.value(candidate);
    if (value === null || value === undefined || value === '') return 'not reported';
    return String(value);
}

function countCompareFieldChanges(beforeCandidate, afterCandidate) {
    if (!beforeCandidate || !afterCandidate) return 0;
    return COMPARE_RESULTS_EXPLORER_FIELDS.reduce((count, descriptor) => (
        renderCompareFieldValue(beforeCandidate, descriptor) !== renderCompareFieldValue(afterCandidate, descriptor)
            ? count + 1
            : count
    ), 0);
}

function renderCompareSnapshotCard(candidate, roleLabel, counterpart = null) {
    if (!candidate) {
        return `
            <article class="compare-snapshot-card empty">
              <div class="compare-snapshot-head">
                <span class="section-kicker">${escapeHtml(roleLabel)}</span>
                <strong>slot empty</strong>
              </div>
              <p class="compare-snapshot-copy">A/B 슬롯을 모두 채우면 before/after 카드가 표시됩니다.</p>
            </article>
        `;
    }
    const stats = [
        ['Distance', formatCompareConsoleValue(candidate, COMPARE_CONSOLE_METRICS[0])],
        ['Energy', formatCompareConsoleValue(candidate, COMPARE_CONSOLE_METRICS[1])],
        ['Contact', formatCompareConsoleValue(candidate, COMPARE_CONSOLE_METRICS[2])],
        ['Commercial', formatCompareConsoleValue(candidate, COMPARE_CONSOLE_METRICS[4])],
    ];
    const fieldRows = COMPARE_RESULTS_EXPLORER_FIELDS.map((descriptor) => {
        const value = renderCompareFieldValue(candidate, descriptor);
        const changed = counterpart ? value !== renderCompareFieldValue(counterpart, descriptor) : false;
        return `
            <div class="compare-snapshot-detail ${changed ? 'changed' : ''}">
              <span>${escapeHtml(descriptor.label)}</span>
              <strong>${escapeHtml(value)}</strong>
            </div>
        `;
    }).join('');
    const changedCount = counterpart ? countCompareFieldChanges(candidate, counterpart) : 0;
    return `
        <article class="compare-snapshot-card">
          <div class="compare-snapshot-head">
            <span class="section-kicker">${escapeHtml(roleLabel)}</span>
            <strong>#${escapeHtml(String(candidate.packetRank || '?'))} ${escapeHtml(candidate.title || candidate.ligandId || 'candidate')}</strong>
          </div>
          <div class="compare-snapshot-meta">
            <span>${escapeHtml(candidate.targetId || 'target n/a')}</span>
            <span>${escapeHtml(candidate.surfaceLabel || 'surface n/a')}</span>
          </div>
          <div class="compare-snapshot-stats">
            ${stats.map(([label, value]) => `
              <div class="compare-snapshot-stat">
                <span>${escapeHtml(label)}</span>
                <strong>${escapeHtml(value)}</strong>
              </div>
            `).join('')}
          </div>
          <div class="compare-snapshot-results-head">
            <span class="section-kicker">Results Explorer</span>
            <strong>${counterpart ? `${changedCount} field changes` : 'field summary'}</strong>
          </div>
          <div class="compare-snapshot-details">
            ${fieldRows}
          </div>
        </article>
    `;
}

function renderWritebackSourceBanner() {
    if (!dom.compareWritebackSource) return;
    const beforeReady = Array.isArray(state.writebackCompare.beforeCandidates) && state.writebackCompare.beforeCandidates.length > 0;
    if (!beforeReady) {
        dom.compareWritebackSource.innerHTML = `
            <div class="compare-diff-empty">현재 explorer bundle을 <strong>After</strong>로 보고 있습니다. <strong>Before Bundle</strong>을 불러오면 writeback 전/후 결과를 row 매칭해서 side-by-side로 비교합니다.</div>
        `;
        return;
    }
    const matchedCount = state.writebackCompare.pairs.filter((pair) => pair.status === 'matched').length;
    const addedCount = state.writebackCompare.pairs.filter((pair) => pair.status === 'added_after').length;
    const removedCount = state.writebackCompare.pairs.filter((pair) => pair.status === 'removed_after').length;
    dom.compareWritebackSource.innerHTML = `
        <div class="compare-writeback-banner">
          <span><strong>Before</strong> ${escapeHtml(state.writebackCompare.beforeSourceLabel || 'bundle')}</span>
          <span><strong>After</strong> ${escapeHtml(state.activeBundleSourceLabel || 'current bundle')}</span>
          <span><strong>Matched</strong> ${escapeHtml(String(matchedCount))}</span>
          <span><strong>After only</strong> ${escapeHtml(String(addedCount))}</span>
          <span><strong>Before only</strong> ${escapeHtml(String(removedCount))}</span>
        </div>
    `;
}

function renderWritebackDecisionBoard() {
    if (!dom.compareDecisionBoard) return;
    const pairs = state.writebackCompare.pairs;
    if (!pairs.length) {
        dom.compareDecisionBoard.innerHTML = '';
        return;
    }
    const rows = pairs.slice(0, 12).map((pair) => {
        const beforeCandidate = pair.beforeCandidate;
        const afterCandidate = pair.afterCandidate;
        const distanceDelta = beforeCandidate && afterCandidate
            ? compareConsoleDelta(COMPARE_CONSOLE_METRICS[0], beforeCandidate, afterCandidate).label
            : 'n/a';
        const commercialDelta = beforeCandidate && afterCandidate
            ? compareConsoleDelta(COMPARE_CONSOLE_METRICS[4], beforeCandidate, afterCandidate).label
            : 'n/a';
        const selected = state.writebackCompare.selectedPairKey === pair.key;
        return `
            <div class="compare-console-card ${selected ? 'selected' : ''}">
              <div class="compare-writeback-row-head">
                <div>
                  <strong>${escapeHtml(comparePairLabel(pair))}</strong>
                  <p class="compare-board-meta">${escapeHtml(beforeCandidate?.title || 'before missing')} → ${escapeHtml(afterCandidate?.title || 'after missing')}</p>
                </div>
                <span class="writeback-chip ${pair.status === 'matched' ? 'prefer-b' : 'review'}">${escapeHtml(comparePairLabel(pair))}</span>
              </div>
              <div class="compare-writeback-row-grid">
                <span>Δdistance ${escapeHtml(distanceDelta)}</span>
                <span>Δcommercial ${escapeHtml(commercialDelta)}</span>
                <span>Before #${escapeHtml(String(beforeCandidate?.packetRank || '-'))}</span>
                <span>After #${escapeHtml(String(afterCandidate?.packetRank || '-'))}</span>
              </div>
              <div class="compare-writeback-row-actions">
                <button class="btn-small ghost" data-action="writeback-select" data-pair-key="${escapeHtml(pair.key)}">Diff 보기</button>
                <button class="btn-small ghost" data-action="writeback-superpose" data-pair-key="${escapeHtml(pair.key)}" ${beforeCandidate && afterCandidate ? '' : 'disabled'}>중첩</button>
                <button class="btn-small ghost" data-action="writeback-side" data-pair-key="${escapeHtml(pair.key)}" ${beforeCandidate && afterCandidate ? '' : 'disabled'}>나란히</button>
              </div>
            </div>
        `;
    }).join('');
    dom.compareDecisionBoard.innerHTML = `
        <div class="compare-console-head">
          <div class="compare-console-head-copy">
            <span class="section-kicker">Writeback Pairing</span>
            <strong>Matched Results Explorer Rows</strong>
          </div>
        </div>
        <div class="compare-console-grid">${rows}</div>
    `;
}

async function renderCompareConsole() {
    if (!dom.compareBeforeAfter || !dom.compareDiffMatrix) return;
    const writebackPair = getSelectedWritebackPair();
    const hasWriteback = Boolean(writebackPair);
    const a = hasWriteback ? (writebackPair.beforeCandidate || null) : (state.candidates[state.compareSlots.A] || null);
    const b = hasWriteback ? (writebackPair.afterCandidate || null) : (state.candidates[state.compareSlots.B] || null);
    const aFrameIndex = resolveCompareConsoleFrameIndex(a);
    const bFrameIndex = resolveCompareConsoleFrameIndex(b);
    const ready = Boolean(a && b);
    renderWritebackSourceBanner();
    if (dom.compareConsoleStatus) {
        dom.compareConsoleStatus.textContent = hasWriteback
            ? (ready
                ? `writeback pair selected · ${comparePairLabel(writebackPair)} · diff row matrix ready`
                : `writeback pair selected · ${comparePairLabel(writebackPair)} · one-sided row`)
            : (ready
                ? `${state.viewerMode === 'compare' ? 'compare mode' : 'compare console'} · writeback diff row matrix ready · results explorer side-by-side ready`
                : 'A/B 슬롯을 채우면 before/after와 diff row matrix가 표시됩니다.');
    }
    dom.compareBeforeAfter.innerHTML = `
        <div class="compare-console-head">
          <div class="compare-console-head-copy">
            <span class="section-kicker">Results Explorer</span>
            <strong>Before / After Side-by-Side</strong>
          </div>
        </div>
        <div class="compare-before-after-grid">
          ${renderCompareSnapshotCard(a, hasWriteback ? 'Before · Writeback' : 'Before · A', b)}
          ${renderCompareSnapshotCard(b, hasWriteback ? 'After · Writeback' : 'After · B', a)}
        </div>
    `;
    if (!ready) {
        dom.compareDiffMatrix.innerHTML = `
            <div class="compare-diff-empty">${hasWriteback ? '선택한 writeback row가 before-only 또는 after-only 상태입니다. matched row를 고르면 diff row matrix가 활성화됩니다.' : 'A/B 슬롯을 모두 채우면 before/after diff row matrix가 활성화됩니다.'}</div>
        `;
        if (hasWriteback) renderWritebackDecisionBoard();
        else if (dom.compareDecisionBoard) dom.compareDecisionBoard.innerHTML = '';
        updateCompareWritebackSmokeState();
        return;
    }
    const rows = COMPARE_CONSOLE_METRICS.map((metric) => {
        const delta = compareConsoleDelta(metric, a, b);
        const writeback = compareConsoleWriteback(metric, a, b);
        return `
            <div class="compare-diff-row ${delta.tone}">
              <span class="compare-diff-metric">${escapeHtml(metric.label)}</span>
              <span class="compare-diff-value before">${escapeHtml(formatCompareConsoleValue(a, metric))}</span>
              <span class="compare-diff-value after">${escapeHtml(formatCompareConsoleValue(b, metric))}</span>
              <span class="compare-diff-value delta ${delta.tone}">${escapeHtml(delta.label)}</span>
              <span class="compare-diff-value writeback"><span class="writeback-chip ${writeback.className}">${escapeHtml(writeback.label)}</span></span>
            </div>
        `;
    }).join('');
    const aBvh = buildPocketContext(a, aFrameIndex)?.bvhDiagnostics || null;
    const bBvh = buildPocketContext(b, bFrameIndex)?.bvhDiagnostics || null;
    const compareProbeA = state.viewerMode === 'compare'
        ? collectPocketGeometryProbe(a, state.compareViewers.A)
        : (aBvh?.geometryProbe || collectPocketGeometryProbe(a));
    const compareProbeB = state.viewerMode === 'compare'
        ? collectPocketGeometryProbe(b, state.compareViewers.B)
        : (bBvh?.geometryProbe || collectPocketGeometryProbe(b));
    const compareDebugA = state.viewerMode === 'compare'
        ? collectViewerGeometryDebugState(state.compareViewers.A)
        : collectViewerGeometryDebugState(state.viewer);
    const compareDebugB = state.viewerMode === 'compare'
        ? collectViewerGeometryDebugState(state.compareViewers.B)
        : collectViewerGeometryDebugState(state.viewer);
    const compareGeometryA = compareProbeA?.canvas3d || collectCanvas3dGeometryProbe();
    const compareGeometryB = compareProbeB?.canvas3d || collectCanvas3dGeometryProbe();
    dom.compareDiffMatrix.innerHTML = `
        <div class="compare-console-head">
          <div class="compare-console-head-copy">
            <span class="section-kicker">Writeback Matrix</span>
            <strong>Diff Row Matrix</strong>
          </div>
        </div>
        <div class="compare-diff-table">
          <div class="compare-diff-head">
            <span>Metric</span>
            <span>Before</span>
            <span>After</span>
            <span>Δ</span>
            <span>Writeback</span>
          </div>
          ${rows}
        </div>
        <div class="compare-console-grid">
          <div class="compare-console-card">
            <strong>BVH / Geometry Path</strong>
            <p>before=${escapeHtml(describePocketBvhPath(a, aFrameIndex))} · after=${escapeHtml(describePocketBvhPath(b, bFrameIndex))} · query=${escapeHtml(describePocketBvhQuery(a, aFrameIndex))} → ${escapeHtml(describePocketBvhQuery(b, bFrameIndex))}</p>
          </div>
          <div class="compare-console-card">
            <strong>Mesh Compatibility</strong>
            <p>before=${escapeHtml(describePocketGeometryProbeForViewer(a, aFrameIndex, state.viewerMode === 'compare' ? state.compareViewers.A : null))} · after=${escapeHtml(describePocketGeometryProbeForViewer(b, bFrameIndex, state.viewerMode === 'compare' ? state.compareViewers.B : null))} · renderables=${escapeHtml(String((compareGeometryA?.renderableCount || 0) + (compareGeometryB?.renderableCount || 0)))} · tris~=${escapeHtml(String((compareGeometryA?.primitiveEstimate || 0) + (compareGeometryB?.primitiveEstimate || 0)))} · nodes=${escapeHtml(String((aBvh?.nodeCount || 0) + (bBvh?.nodeCount || 0)))} · leaves=${escapeHtml(String((aBvh?.leafCount || 0) + (bBvh?.leafCount || 0)))} · state=${escapeHtml(`${describeGeometryPresenceTierFromProbe(compareProbeA)} / ${describeGeometryPresenceTierFromProbe(compareProbeB)}`)} · cells=${escapeHtml(`${compareProbeA?.activeStateCellCount || 0}/${compareProbeA?.stateCellCount || 0} → ${compareProbeB?.activeStateCellCount || 0}/${compareProbeB?.stateCellCount || 0}`)} · viewer=${escapeHtml(`${compareDebugA.statusLabel} / ${compareDebugB.statusLabel}`)}</p>
          </div>
        </div>
    `;

    if (hasWriteback) {
        renderWritebackDecisionBoard();
        updateCompareWritebackSmokeState();
        return;
    }

    if (!dom.compareDecisionBoard) {
        return;
    }
    const [boardA, boardB] = await Promise.all([
        ensureDashboardDecisionBoard(a),
        ensureDashboardDecisionBoard(b),
    ]);
    const boardCards = [
        { slot: 'A', candidate: a, board: boardA },
        { slot: 'B', candidate: b, board: boardB },
    ].map(({ slot, candidate, board }) => {
        if (!board?.available) {
            return `
                <div class="compare-console-card">
                  <strong>${escapeHtml(slot)} · ${escapeHtml(candidate?.title || candidate?.ligandId || 'candidate')}</strong>
                  <p>${escapeHtml(board?.reason || 'dashboard decision_board not available')}</p>
                </div>
            `;
        }
        const rows = Array.isArray(board.metric_compare_rows) ? board.metric_compare_rows.slice(0, 4) : [];
        const table = rows.length
            ? `
                <table class="compare-board-table">
                  <thead><tr><th>Metric</th><th>Δ cand-base</th><th>Regression</th></tr></thead>
                  <tbody>
                    ${rows.map((row) => `
                        <tr>
                          <td>${escapeHtml(String(row.metric || '-'))}</td>
                          <td>${escapeHtml(formatNumber(Number(row.delta_candidate_minus_baseline || 0), 3))}</td>
                          <td>${escapeHtml(row.regression ? 'yes' : 'no')}</td>
                        </tr>
                    `).join('')}
                  </tbody>
                </table>
            `
            : `<p>No metric compare rows.</p>`;
        return `
            <div class="compare-console-card">
              <strong>${escapeHtml(slot)} · ${escapeHtml(candidate?.title || candidate?.ligandId || 'candidate')}</strong>
              <p class="compare-board-meta">baseline=${escapeHtml(board.baseline_label || '-')} | candidate=${escapeHtml(board.candidate_label || '-')} | regressions=${escapeHtml(String(board.metric_regression_count ?? 0))} | gate fails=${escapeHtml(String(board.gate_fail_count ?? 0))}</p>
              ${table}
            </div>
        `;
    }).join('');
    dom.compareDecisionBoard.innerHTML = `
        <div class="compare-console-head">
          <span class="section-kicker">Dashboard Context</span>
          <strong>Decision Board Rows</strong>
        </div>
        <div class="compare-console-grid">${boardCards}</div>
    `;
    updateCompareWritebackSmokeState();
}

function syncTrajectoryUi() {
    const candidate = getSelectedCandidate();
    const trajectory = candidate?.trajectoryData || null;
    const hasVideo = dom.videoPreview.style.display !== 'none' && Number.isFinite(dom.videoPreview.duration) && dom.videoPreview.duration > 0;
    const deckState = resolveTrajectoryDeckState(candidate, hasVideo);
    const hasTrajectory = deckState.hasTrajectory;
    const ready = deckState.ready;

    dom.trajectoryBar.style.display = ready ? 'flex' : 'none';
    dom.btnTrajPlay.disabled = !ready;
    dom.btnTrajPause.disabled = !ready;
    dom.trajSlider.disabled = !deckState.sliderReady;
    dom.trajectoryStatusNote.className = `status-banner ${deckState.tone}`;
    dom.trajectoryStatusNote.textContent = deckState.message;
    dom.trajectoryStatusNote.style.display = ready ? 'block' : 'none';
    if (!ready) return;

    if (hasTrajectory) {
        const maxIndex = Math.max(0, trajectory.frameCount - 1);
        const frameIndex = clamp(state.trajectoryFrameIndex, 0, maxIndex);
        const frameNumber = trajectory.frameIndices?.[frameIndex] ?? frameIndex;
        const frame = trajectory.frames[frameIndex] || null;
        state.trajectoryFrameIndex = frameIndex;
        dom.trajSlider.max = String(maxIndex);
        dom.trajSlider.step = '1';
        dom.trajSlider.value = String(frameIndex);
        const modePrefix = state.trajectorySceneMode === 'reference' ? 'Reference Pose' : 'Frame';
        dom.trajFrameLabel.textContent = frame
            ? `${modePrefix} ${frameIndex + 1} / ${trajectory.frameCount} | idx ${frameNumber} | d=${Number.isFinite(frame.minDistanceA) ? `${formatNumber(frame.minDistanceA, 3)}A` : 'n/a'}`
            : `${modePrefix} ${frameIndex + 1} / ${trajectory.frameCount}`;
        if (state.viewerMode === 'single' && state.trajectorySceneMode === 'trajectory') {
            queueTrajectoryFrameRender(candidate, frameIndex);
        }
        if (hasVideo) {
            syncVideoToTrajectoryFrame(trajectory, frameIndex);
        }
        updateTrajectoryChartCursor(candidate);
        return;
    }

    if (!hasVideo) {
        dom.trajSlider.max = '100';
        dom.trajSlider.step = '1';
        dom.trajSlider.value = '0';
        dom.trajFrameLabel.textContent = 'Movie metadata loading...';
        return;
    }

    const max = Math.max(1, Math.round(dom.videoPreview.duration * 100));
    const value = Math.round(dom.videoPreview.currentTime * 100);
    dom.trajSlider.max = String(max);
    dom.trajSlider.step = '1';
    dom.trajSlider.value = String(value);
    dom.trajFrameLabel.textContent = `t = ${dom.videoPreview.currentTime.toFixed(2)}s / ${dom.videoPreview.duration.toFixed(2)}s`;
    dom.videoPreview.playbackRate = Number(dom.trajSpeed.value || 1);
}

async function openSnapshotModal() {
    if (!state.viewer?.plugin?.helpers?.viewportScreenshot) {
        toast('스냅샷 helper를 사용할 수 없습니다.', 'error');
        return;
    }

    try {
        applyViewerRenderSettings();
        const canvas = state.viewer.plugin.canvas3d.webgl.canvas;
        const multiplier = Number(dom.snapshotRes.value || 2);
        const width = Math.max(512, Math.round(canvas.width * multiplier));
        const height = Math.max(512, Math.round(canvas.height * multiplier));
        const format = dom.snapshotFormat.value === 'jpeg' ? 'image/jpeg' : 'image/png';
        const transparent = dom.snapshotTransparent.checked;

        state.lastSnapshotDataUri = await state.viewer.plugin.helpers.viewportScreenshot.getImageDataUri({
            resolution: { name: 'custom', x: width, y: height },
            transparent,
            type: format,
            imagePassProps: {
                multiSample: { mode: 'on', sampleLevel: 4 },
            },
        });

        dom.snapshotImage.src = state.lastSnapshotDataUri;
        dom.snapshotModal.classList.add('active');
    } catch (error) {
        console.error(error);
        toast(`스냅샷 실패: ${error.message}`, 'error');
    }
}

function closeSnapshotModal() {
    dom.snapshotModal.classList.remove('active');
}

function openFigureModal() {
    const candidate = getSelectedCandidate();
    const figureUrl = resolveAssetUrl(candidate?.figurePath);
    if (!figureUrl) return;
    dom.figureModalImage.src = figureUrl;
    dom.figureModalCaption.textContent = `${candidate?.targetId || '-'} · rank #${candidate?.packetRank || '-'} · ${candidate?.surfaceLabel || '-'}`;
    dom.btnOpenFigureFromModal.dataset.path = figureUrl;
    dom.figureModal.classList.add('active');
}

function closeFigureModal() {
    dom.figureModal.classList.remove('active');
}

function downloadSnapshot() {
    if (!state.lastSnapshotDataUri) return;
    const link = document.createElement('a');
    link.href = state.lastSnapshotDataUri;
    link.download = `selected_allatom_snapshot.${dom.snapshotFormat.value === 'jpeg' ? 'jpg' : 'png'}`;
    link.click();
}

async function copySnapshot() {
    if (!state.lastSnapshotDataUri || !navigator.clipboard?.write) {
        toast('현재 브라우저는 이미지 복사를 지원하지 않습니다.', 'warn');
        return;
    }
    try {
        const blob = await (await fetch(state.lastSnapshotDataUri)).blob();
        await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
        toast('스냅샷을 클립보드로 복사했습니다.', 'success');
    } catch (error) {
        toast(`클립보드 복사 실패: ${error.message}`, 'error');
    }
}

function openAsset(path) {
    if (!path) return;
    const target = resolveAssetUrl(path);
    if (!target) return;
    window.open(target, '_blank', 'noopener,noreferrer');
}

async function fetchJson(pathLike) {
    const response = await fetchWithFallback(pathLike);
    return response.json();
}

async function fetchText(pathLike) {
    const local = resolveLocalFile(pathLike);
    if (local) return local.text();

    const response = await fetchWithFallback(pathLike);
    return response.text();
}

async function fetchArrayBuffer(pathLike) {
    const local = resolveLocalFile(pathLike);
    if (local?.arrayBuffer) return local.arrayBuffer();

    const response = await fetchWithFallback(pathLike);
    return response.arrayBuffer();
}

async function fetchWithFallback(pathLike) {
    const candidates = resolveAssetUrlCandidates(pathLike);
    let lastError = null;
    for (const url of candidates) {
        try {
            const response = await fetch(url, { cache: 'no-store' });
            if (!response.ok) {
                lastError = new Error(`${response.status} ${response.statusText}`);
                continue;
            }
            return response;
        } catch (error) {
            lastError = error;
        }
    }
    const attempted = candidates.join(' | ');
    throw new Error(`${lastError?.message || 'NetworkError'} :: attempted ${attempted}`);
}

async function loadCurrentBlockerSurface() {
    renderCurrentBlockerSurface();

    let queue = null;
    let viewerSmoke = null;
    let wetlabDashboard = null;
    let wetlabReadiness = null;
    const errors = [];

    try {
        queue = await fetchJson(DEFAULT_ENGINE_BLOCKER_QUEUE_PATH);
    } catch (error) {
        errors.push(`queue=${error.message}`);
    }

    const viewerArtifactPath = firstTruthy(queue?.summary?.viewer_artifact, DEFAULT_VIEWER_SMOKE_REFRESH_PATH);
    const wetlabArtifactPath = firstTruthy(queue?.summary?.wetlab_artifact, DEFAULT_WETLAB_MASTER_HANDOFF_PATH);
    const wetlabQueueRow = getBlockerSurfaceRowFromQueue(queue, 'wetlab_execution_readiness');
    const wetlabReadinessArtifactPath = firstTruthy(
        wetlabQueueRow?.source_artifact,
        queue?.summary?.wetlab_readiness_artifact,
        DEFAULT_WETLAB_READINESS_QUEUE_PATH,
    );

    try {
        viewerSmoke = await fetchJson(viewerArtifactPath);
    } catch (error) {
        errors.push(`viewer=${error.message}`);
    }

    try {
        wetlabDashboard = await fetchJson(wetlabArtifactPath);
    } catch (error) {
        errors.push(`wetlab=${error.message}`);
    }

    try {
        wetlabReadiness = await fetchJson(wetlabReadinessArtifactPath);
    } catch (error) {
        errors.push(`wetlab_readiness=${error.message}`);
    }

    state.blockerSurface.queue = queue;
    state.blockerSurface.viewerSmoke = viewerSmoke;
    state.blockerSurface.wetlabDashboard = wetlabDashboard;
    state.blockerSurface.wetlabReadiness = wetlabReadiness;
    state.blockerSurface.loadError = errors.join(' | ');

    renderCurrentBlockerSurface();
    renderQuickStats(getSelectedCandidate());
}

function renderCurrentBlockerSurface() {
    renderCurrentBlockerBadges();
    if (!dom.blockerSurfaceStatus || !dom.blockerSurfaceSummary || !dom.blockerSurfaceGrid) return;

    const queue = state.blockerSurface.queue;
    const viewerRow = getBlockerSurfaceRow('viewer_usability');
    const wetlabRow = getBlockerSurfaceRow('wetlab_execution_readiness');
    const loadError = state.blockerSurface.loadError;

    if (!queue && !viewerRow && !wetlabRow && !loadError) {
        dom.blockerSurfaceStatus.className = 'status-banner muted';
        dom.blockerSurfaceStatus.textContent = 'current artifact를 읽는 중...';
        dom.blockerSurfaceSummary.innerHTML = '';
        dom.blockerSurfaceGrid.innerHTML = '';
        return;
    }

    if (!queue && loadError) {
        dom.blockerSurfaceStatus.className = 'status-banner bad';
        dom.blockerSurfaceStatus.textContent = `current blocker artifact 로드 실패: ${loadError}`;
        dom.blockerSurfaceSummary.innerHTML = '';
        dom.blockerSurfaceGrid.innerHTML = '';
        return;
    }

    const queueSummary = queue?.summary || {};
    const engineRows = Array.isArray(queue?.rows)
        ? queue.rows.filter((row) => row?.blocker_domain === 'engine')
        : [];
    const engineOrder = engineRows
        .slice(0, 3)
        .map((row) => humanizeCompactToken(row.blocker_id))
        .join(' -> ');

    dom.blockerSurfaceStatus.className = `status-banner ${loadError ? 'warn' : 'good'}`;
    dom.blockerSurfaceStatus.textContent = loadError
        ? `current artifact 반영 완료, 일부 detail fetch는 누락되었습니다: ${loadError}`
        : `Queue order: ${engineOrder || 'nightly reliability -> viewer usability -> wetlab execution readiness'}`;

    const viewerGeometryCallout = buildViewerGeometryBlockerCallout(viewerRow, state.blockerSurface.viewerSmoke);
    dom.blockerSurfaceSummary.innerHTML = `
        ${viewerGeometryCallout}
        <div class="blocker-summary-card">
          <div class="blocker-summary-head">
            <div>
              <span class="section-kicker">Current Artifact</span>
              <strong>Local Engine Commercialization Queue</strong>
            </div>
            <div class="blocker-summary-pills">
              ${blockerTonePill('Engine', `${queueSummary.engine_blocker_count ?? engineRows.length ?? 0}`, 'bad')}
              ${blockerTonePill('Blocked', `${queueSummary.blocked_count ?? 0}`, (queueSummary.blocked_count || 0) > 0 ? 'bad' : 'good')}
              ${blockerTonePill('Partial', `${queueSummary.partial_count ?? 0}`, (queueSummary.partial_count || 0) > 0 ? 'warn' : 'muted')}
            </div>
          </div>
          <p class="blocker-summary-copy">${escapeHtml(queueSummary.next_required_step || 'current commercialization queue next step가 아직 보고되지 않았습니다.')}</p>
          <div class="blocker-summary-metrics">
            ${blockerMetric('Top Priority', humanizeCompactToken(queueSummary.top_priority_id || '-'))}
            ${blockerMetric('Top Status', humanizeCompactToken(queueSummary.top_priority_status || '-'))}
            ${blockerMetric('Mode', queueSummary.local_only_mode ? 'local-only' : 'mixed')}
            ${blockerMetric('Artifact', basenameOf(DEFAULT_ENGINE_BLOCKER_QUEUE_PATH))}
          </div>
        </div>
    `;

    const cards = [];
    if (viewerRow || state.blockerSurface.viewerSmoke) {
        cards.push(buildBlockerSurfaceCard({
            title: 'Viewer Usability',
            laneLabel: 'operator-facing surface',
            row: viewerRow,
            sourceHref: resolveAssetUrl(firstTruthy(viewerRow?.source_artifact, queueSummary.viewer_artifact, DEFAULT_VIEWER_SMOKE_REFRESH_PATH)),
            secondaryHref: resolveAssetUrl(viewerRow?.secondary_artifact),
            secondaryLabel: 'Smoke MD',
            metrics: buildViewerBlockerMetrics(viewerRow, state.blockerSurface.viewerSmoke),
            detailLines: buildViewerBlockerDetails(viewerRow, state.blockerSurface.viewerSmoke),
        }));
    }
    if (wetlabRow || state.blockerSurface.wetlabDashboard) {
        cards.push(buildBlockerSurfaceCard({
            title: 'Wetlab Execution Readiness',
            laneLabel: 'commercialization-facing surface',
            row: wetlabRow,
            sourceHref: resolveAssetUrl(firstTruthy(wetlabRow?.source_artifact, queueSummary.wetlab_artifact, DEFAULT_WETLAB_MASTER_HANDOFF_PATH)),
            secondaryHref: resolveAssetUrl(wetlabRow?.secondary_artifact),
            secondaryLabel: 'Handoff MD',
            metrics: buildWetlabBlockerMetrics(wetlabRow, state.blockerSurface.wetlabDashboard, state.blockerSurface.wetlabReadiness),
            detailLines: buildWetlabBlockerDetails(wetlabRow, state.blockerSurface.wetlabDashboard, state.blockerSurface.wetlabReadiness),
        }));
    }

    dom.blockerSurfaceGrid.innerHTML = cards.join('');
}

function renderCurrentBlockerBadges() {
    if (!dom.opsSurfaceStrip || !dom.engineQueueBadge || !dom.viewerUsabilityBadge || !dom.wetlabExecutionBadge) return;

    const queueSummary = state.blockerSurface.queue?.summary || null;
    const viewerRow = getBlockerSurfaceRow('viewer_usability');
    const wetlabRow = getBlockerSurfaceRow('wetlab_execution_readiness');
    const wetlabSignal = parseSignalMap(wetlabRow?.source_signal);
    const wetlabSummary = state.blockerSurface.wetlabDashboard?.summary || {};
    const wetlabReadinessSummary = state.blockerSurface.wetlabReadiness?.summary || {};

    if (!queueSummary && !viewerRow && !wetlabRow && !state.blockerSurface.loadError) {
        dom.opsSurfaceStrip.style.display = 'none';
        return;
    }

    dom.opsSurfaceStrip.style.display = 'inline-flex';

    if (queueSummary) {
        const queueTone = (queueSummary.blocked_count || 0) > 0 ? 'bad' : (queueSummary.partial_count || 0) > 0 ? 'warn' : 'good';
        setHeaderStatusBadge(
            dom.engineQueueBadge,
            `engine ${(queueSummary.blocked_count || 0)} blocked / ${(queueSummary.partial_count || 0)} partial`,
            queueTone,
        );
    } else {
        setHeaderStatusBadge(dom.engineQueueBadge, 'engine unavailable', state.blockerSurface.loadError ? 'bad' : 'muted');
    }

    if (viewerRow) {
        const viewerBadgeText = buildViewerUsabilityBadgeText(viewerRow, state.blockerSurface.viewerSmoke);
        setHeaderStatusBadge(
            dom.viewerUsabilityBadge,
            viewerBadgeText,
            blockerStatusTone(viewerRow.status),
        );
        dom.viewerUsabilityBadge.title = buildViewerUsabilityBadgeTitle(viewerRow, state.blockerSurface.viewerSmoke);
    } else {
        setHeaderStatusBadge(dom.viewerUsabilityBadge, 'viewer unavailable', state.blockerSurface.loadError ? 'bad' : 'muted');
        dom.viewerUsabilityBadge.title = '';
    }

    if (wetlabRow || wetlabSummary) {
        const executionReady = wetlabReadinessSummary.execution_ready_now_row_count ?? wetlabSummary.broad_screen_execution_ready_now_row_count ?? wetlabSignal.execution_ready_now_row_count ?? '-';
        const blockedRows = (wetlabReadinessSummary.blocked_row_count || 0) + (wetlabReadinessSummary.partial_row_count || 0);
        setHeaderStatusBadge(
            dom.wetlabExecutionBadge,
            `wetlab ${humanizeCompactToken(wetlabRow?.status || 'blocked')} / exec ${executionReady} / rows ${blockedRows || '-'}`,
            blockerStatusTone(wetlabRow?.status || 'blocked'),
        );
    } else {
        setHeaderStatusBadge(dom.wetlabExecutionBadge, 'wetlab unavailable', state.blockerSurface.loadError ? 'bad' : 'muted');
    }
}

function getBlockerSurfaceRowFromQueue(queue, blockerId) {
    return (queue?.rows || []).find((row) => row?.blocker_id === blockerId) || null;
}

function getBlockerSurfaceRow(blockerId) {
    return getBlockerSurfaceRowFromQueue(state.blockerSurface.queue, blockerId);
}

function getCompareWritebackGeometryStatusLine(row, viewerSmoke) {
    const summary = viewerSmoke?.summary || {};
    return firstTruthy(
        summary.compare_writeback_geometry_status_line,
        row?.status_line,
        signalFallbackLine(row?.source_signal, 'geometry_status_line'),
        state.blockerSurface.queue?.summary?.viewer_status_line,
        '',
    );
}

function getCompareWritebackDebugReadinessLine(row, viewerSmoke) {
    const summary = viewerSmoke?.summary || {};
    return firstTruthy(
        summary.compare_writeback_debug_readiness_line,
        '',
    );
}

function getCompareWritebackGeometryAccessLine(viewerSmoke) {
    const summary = viewerSmoke?.summary || {};
    return firstTruthy(
        summary.compare_writeback_geometry_access_line,
        '',
    );
}

function parseCompareWritebackGeometryStatusLine(geometryLine) {
    const snapshot = {};
    for (const part of String(geometryLine || '').split('|')) {
        const trimmed = part.trim();
        if (!trimmed) continue;
        const [rawLabel, ...rest] = trimmed.split('=');
        const label = String(rawLabel || '').trim();
        const text = rest.join('=').trim();
        if (!label || !text) continue;
        const stateMatch = text.match(/state reps\s+(\d+\/\d+)/i);
        snapshot[label] = {
            text,
            stateReps: stateMatch ? stateMatch[1] : '',
        };
    }
    return snapshot;
}

function buildViewerUsabilityBadgeText(row, viewerSmoke) {
    const geometryLine = getCompareWritebackGeometryStatusLine(row, viewerSmoke);
    const snapshot = parseCompareWritebackGeometryStatusLine(geometryLine);
    const singleReps = snapshot.single?.stateReps || '';
    const compareAReps = snapshot.compareA?.stateReps || '';
    const compareBReps = snapshot.compareB?.stateReps || '';
    if (singleReps || compareAReps || compareBReps) {
        return `viewer geometry / S ${singleReps || 'n/a'} A ${compareAReps || 'n/a'} B ${compareBReps || 'n/a'}`;
    }
    return `viewer ${humanizeCompactToken(row?.status || 'not_reported')} / ${humanizeCompactToken(row?.commercialization_impact || 'high')}`;
}

function buildViewerUsabilityBadgeTitle(row, viewerSmoke) {
    return uniqueTruthy([
        getCompareWritebackGeometryStatusLine(row, viewerSmoke),
        getCompareWritebackDebugReadinessLine(row, viewerSmoke),
        row?.next_required_action,
    ]).join('\n');
}

function buildViewerGeometryBlockerCallout(row, viewerSmoke) {
    const geometryLine = getCompareWritebackGeometryStatusLine(row, viewerSmoke);
    const readinessLine = getCompareWritebackDebugReadinessLine(row, viewerSmoke);
    const geometryAccessLine = getCompareWritebackGeometryAccessLine(viewerSmoke);
    const summary = viewerSmoke?.summary || {};
    if (!geometryLine && !readinessLine && !summary.compare_writeback_status_line && !row?.next_required_action) return '';

    const snapshot = parseCompareWritebackGeometryStatusLine(geometryLine);
    const singleReps = snapshot.single?.stateReps || 'n/a';
    const comparePaneReps = joinTruthy([
        snapshot.compareA?.stateReps ? `A ${snapshot.compareA.stateReps}` : '',
        snapshot.compareB?.stateReps ? `B ${snapshot.compareB.stateReps}` : '',
    ], ' / ') || 'n/a';
    const updatedAt = firstTruthy(viewerSmoke?.generated_at_local, 'not reported');
    const indexHref = resolveAssetUrl(DEFAULT_VIEWER_SMOKE_INDEX_MD_PATH);
    const refreshHref = resolveAssetUrl(firstTruthy(row?.secondary_artifact, DEFAULT_VIEWER_SMOKE_REFRESH_MD_PATH));
    const tone = blockerStatusTone(row?.status || 'warn');
    const copy = summary.compare_writeback_status_line
        ? `Smoke status: ${summary.compare_writeback_status_line}`
        : 'Compare/writeback UI is available, but the first-load geometry signal is still the commercialization blocker.';

    return `
        <article class="blocker-summary-card blocker-geometry-callout blocker-surface-card-${escapeHtml(tone)}">
          <div class="blocker-summary-head">
            <div>
              <span class="section-kicker">First-Load Blocker</span>
              <strong>Compare / Writeback Geometry</strong>
            </div>
            ${blockerTonePill('Viewer', singleReps === '0/0' ? 'single 0/0 reps' : humanizeCompactToken(row?.status || 'partial'), tone)}
          </div>
          <p class="blocker-summary-copy">${escapeHtml(copy)}</p>
          ${geometryLine ? `<div class="status-banner warn blocker-geometry-banner">compare_writeback_geometry_status_line: ${escapeHtml(geometryLine)}</div>` : ''}
          <div class="blocker-summary-metrics">
            ${blockerMetric('Single Pane', `state reps ${singleReps}`)}
            ${blockerMetric('Compare Panes', comparePaneReps)}
            ${blockerMetric('Readiness', readinessLine || 'not reported')}
            ${blockerMetric('Updated', updatedAt)}
          </div>
          ${geometryAccessLine || row?.next_required_action ? `<ul class="blocker-surface-notes">${uniqueTruthy([
              geometryAccessLine ? `Geometry access: ${geometryAccessLine}` : '',
              row?.next_required_action,
          ]).map((line) => `<li>${escapeHtml(line)}</li>`).join('')}</ul>` : ''}
          <div class="blocker-surface-actions">
            ${indexHref ? `<a class="btn-small ghost blocker-open-link" href="${escapeHtml(indexHref)}" target="_blank" rel="noopener noreferrer">${escapeHtml(basenameOf(DEFAULT_VIEWER_SMOKE_INDEX_MD_PATH))}</a>` : ''}
            ${refreshHref ? `<a class="btn-small ghost blocker-open-link" href="${escapeHtml(refreshHref)}" target="_blank" rel="noopener noreferrer">${escapeHtml(basenameOf(refreshHref))}</a>` : ''}
          </div>
        </article>
    `;
}

function buildViewerBlockerMetrics(row, viewerSmoke) {
    const signal = parseSignalMap(row?.source_signal);
    return [
        { label: 'Priority', value: row?.priority_rank ? `#${row.priority_rank}` : '-' },
        { label: 'Status', value: humanizeCompactToken(row?.status || 'not_reported') },
        { label: 'Impact', value: humanizeCompactToken(row?.commercialization_impact || 'not_reported') },
        { label: 'Smoke', value: viewerSmoke?.overall_ok === true ? 'green' : viewerSmoke?.overall_ok === false ? 'failed' : 'n/a' },
        {
            label: 'Canvas Probe',
            value: `single ${formatCompactBool(signal.single_canvas_probe_ready)} / A ${formatCompactBool(signal.compareA_canvas_probe_ready)} / B ${formatCompactBool(signal.compareB_canvas_probe_ready)}`,
        },
        {
            label: 'Renderables',
            value: `single ${signal.single_renderables || '0'} / A ${signal.compareA_renderables || '0'} / B ${signal.compareB_renderables || '0'}`,
        },
    ];
}

function buildViewerBlockerDetails(row, viewerSmoke) {
    return uniqueTruthy([
        viewerSmoke?.summary?.compare_writeback_debug_readiness_line
            ? `Compare readiness: ${viewerSmoke.summary.compare_writeback_debug_readiness_line}`
            : '',
        viewerSmoke?.summary?.compare_writeback_geometry_status_line
            ? `Geometry status: ${viewerSmoke.summary.compare_writeback_geometry_status_line}`
            : signalFallbackLine(row?.source_signal, 'geometry_status_line'),
        row?.next_required_action,
    ]);
}

function buildWetlabBlockerMetrics(row, wetlabDashboard, wetlabReadiness) {
    const signal = parseSignalMap(row?.source_signal);
    const summary = wetlabDashboard?.summary || {};
    const readinessSummary = wetlabReadiness?.summary || {};
    return [
        { label: 'Priority', value: row?.priority_rank ? `#${row.priority_rank}` : '-' },
        { label: 'Status', value: humanizeCompactToken(row?.status || 'not_reported') },
        { label: 'Ready Rows', value: readinessSummary.row_count ? `${readinessSummary.ready_row_count || 0}/${readinessSummary.row_count}` : '-' },
        {
            label: 'Execution Ready',
            value: String(readinessSummary.execution_ready_now_row_count ?? summary.broad_screen_execution_ready_now_row_count ?? signal.execution_ready_now_row_count ?? '-'),
        },
        { label: 'Primary Watch', value: firstTruthy(readinessSummary.primary_watch_liveness, summary.broad_screen_primary_watch_liveness, signal.primary_watch_liveness, '-') },
        { label: 'Anti Watch', value: firstTruthy(readinessSummary.antitarget_watch_liveness, summary.broad_screen_antitarget_watch_liveness, signal.antitarget_watch_liveness, '-') },
    ];
}

function buildWetlabBlockerDetails(row, wetlabDashboard, wetlabReadiness) {
    const signal = parseSignalMap(row?.source_signal);
    const summary = wetlabDashboard?.summary || {};
    const readinessSummary = wetlabReadiness?.summary || {};
    const selectedGate = boolLabel(toNullableBool(
        summary.selected_allatom_wetlab_gate_pass,
        readinessSummary.selected_allatom_wetlab_gate_pass,
        signal.selected_allatom_wetlab_gate_pass,
    ));
    return uniqueTruthy([
        readinessSummary.status_line ? `Execution summary: ${readinessSummary.status_line}` : '',
        ...buildWetlabReadinessRowLines(wetlabReadiness),
        `Selected all-atom wetlab gate: ${selectedGate}`,
        readinessSummary.measured_assay_artifact_count !== undefined
            ? `Measurement evidence: assays ${readinessSummary.measured_assay_artifact_count} / claim ${humanizeCompactToken(readinessSummary.therapeutic_claim_readiness || 'not_reported')}`
            : '',
        `Primary watch ${firstTruthy(summary.broad_screen_primary_watch_liveness, signal.primary_watch_liveness, 'not_reported')} / antitarget watch ${firstTruthy(summary.broad_screen_antitarget_watch_liveness, signal.antitarget_watch_liveness, 'not_reported')}`,
        summary.primary_surface_artifact ? `Primary surface: ${summary.primary_surface_artifact}` : '',
        row?.next_required_action,
    ]);
}

function buildWetlabReadinessRowLines(wetlabReadiness) {
    if (!Array.isArray(wetlabReadiness?.rows)) return [];
    return wetlabReadiness.rows
        .slice(0, 4)
        .map((readinessRow) => {
            const label = humanizeCompactToken(readinessRow?.row_id || 'readiness_row');
            const status = humanizeCompactToken(readinessRow?.status || 'not_reported');
            const summaryLine = firstTruthy(readinessRow?.summary_line, readinessRow?.next_required_action, '');
            return summaryLine ? `${label}: ${status} - ${summaryLine}` : `${label}: ${status}`;
        });
}

function buildBlockerSurfaceCard({ title, laneLabel, row, sourceHref, secondaryHref, secondaryLabel, metrics, detailLines }) {
    const tone = blockerStatusTone(row?.status || 'not_reported');
    const sourceLabel = basenameOf(row?.source_artifact || sourceHref || '');
    const secondaryText = secondaryLabel || 'Secondary';
    return `
        <article class="blocker-surface-card blocker-surface-card-${escapeHtml(tone)}">
          <div class="blocker-surface-head">
            <div>
              <span class="section-kicker">${escapeHtml(laneLabel)}</span>
              <strong>${escapeHtml(title)}</strong>
            </div>
            ${blockerTonePill('status', humanizeCompactToken(row?.status || 'not_reported'), tone)}
          </div>
          <div class="blocker-surface-metrics">
            ${metrics.map((metric) => blockerMetric(metric.label, metric.value)).join('')}
          </div>
          ${detailLines.length ? `<ul class="blocker-surface-notes">${detailLines.map((line) => `<li>${escapeHtml(line)}</li>`).join('')}</ul>` : ''}
          <div class="blocker-surface-actions">
            ${sourceHref ? `<a class="btn-small ghost blocker-open-link" href="${escapeHtml(sourceHref)}" target="_blank" rel="noopener noreferrer">${escapeHtml(sourceLabel || 'Artifact')}</a>` : ''}
            ${secondaryHref ? `<a class="btn-small ghost blocker-open-link" href="${escapeHtml(secondaryHref)}" target="_blank" rel="noopener noreferrer">${escapeHtml(secondaryText)}</a>` : ''}
          </div>
        </article>
    `;
}

function blockerMetric(label, value) {
    return `
        <div class="blocker-metric">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(String(value))}</strong>
        </div>
    `;
}

function blockerTonePill(label, value, tone = 'muted') {
    return `<span class="blocker-tone-pill blocker-tone-pill-${escapeHtml(tone)}">${escapeHtml(label)} ${escapeHtml(String(value))}</span>`;
}

function setHeaderStatusBadge(element, text, tone = 'muted') {
    if (!element) return;
    element.textContent = text;
    element.className = 'session-state-badge';
    if (tone) element.classList.add(tone);
}

function blockerStatusTone(status) {
    const normalized = String(status || '').trim().toLowerCase();
    if (!normalized || normalized === 'not_reported') return 'muted';
    if (normalized.includes('keep_green') || normalized.includes('pass') || normalized.includes('ready')) return 'good';
    if (normalized.includes('partial') || normalized.includes('warn')) return 'warn';
    if (normalized.includes('block') || normalized.includes('fail')) return 'bad';
    if (normalized.includes('parked')) return 'muted';
    return 'info';
}

function humanizeCompactToken(value) {
    return String(value || '-')
        .trim()
        .replace(/[_-]+/g, ' ')
        .replace(/\s+/g, ' ');
}

function parseSignalMap(text) {
    const entries = {};
    for (const rawPart of String(text || '').split(';')) {
        const part = rawPart.trim();
        if (!part.includes('=')) continue;
        const [key, ...rest] = part.split('=');
        const normalizedKey = String(key || '').trim();
        if (!normalizedKey) continue;
        entries[normalizedKey] = rest.join('=').trim();
    }
    return entries;
}

function formatCompactBool(value) {
    const parsed = toNullableBool(value);
    if (parsed === true) return 'yes';
    if (parsed === false) return 'no';
    return 'n/a';
}

function signalFallbackLine(text, key) {
    const signal = parseSignalMap(text);
    return signal[key] ? `${humanizeCompactToken(key)}: ${signal[key]}` : '';
}

function getWetlabFocusSummary() {
    const summary = state.bundleSummary || {};
    const focus = state.bundlePayload?.structured?.wetlab_focus || {};
    const translation = focus.translation || {};
    const commercial = focus.commercial || {};
    const actionability = focus.effective_actionability || {};

    const wetlabGatePass = toNullableBool(
        focus.wetlab_gate_pass,
        summary.wetlab_focus_wetlab_gate_pass,
    );
    const wetlabFinalGatePass = toNullableBool(
        focus.wetlab_final_gate_pass,
        summary.wetlab_focus_wetlab_final_gate_pass,
    );
    const actionabilityStatus = firstTruthy(
        focus.effective_actionability_status,
        summary.wetlab_focus_effective_actionability_status,
        'not_reported',
    );
    const blockingOrder = firstTruthy(
        focus.effective_blocking_order,
        summary.wetlab_focus_effective_blocking_order,
        'not_reported',
    );
    const translationSummary = firstTruthy(
        joinTruthy([
            firstTruthy(
                translation.focus_status,
                focus.translation_gate_focus_status,
                summary.wetlab_focus_translation_gate_focus_status,
            ),
            firstTruthy(
                translation.focus_reason,
                focus.translation_gate_focus_reason,
                summary.wetlab_focus_translation_gate_focus_reason,
            ),
        ]),
        firstTruthy(
            translation.focus_reason,
            focus.translation_gate_focus_reason,
            summary.wetlab_focus_translation_gate_focus_reason,
        ),
    );
    const commercialSummary = firstTruthy(
        commercial.human_summary_v2,
        summary.wetlab_focus_commercial_human_summary_v2,
        joinTruthy(
            [
                Number.isFinite(toFloat(focus.commercial_overall_score_v2, summary.wetlab_focus_commercial_overall_score_v2))
                    ? `score=${formatNumber(toFloat(focus.commercial_overall_score_v2, summary.wetlab_focus_commercial_overall_score_v2), 1)}`
                    : '',
                firstTruthy(commercial.risk_bucket_v2, focus.commercial_risk_bucket_v2, summary.wetlab_focus_commercial_risk_bucket_v2),
                firstTruthy(commercial.decision_class_v2, focus.commercial_decision_class_v2, summary.wetlab_focus_commercial_decision_class_v2),
            ],
        ),
    );
    const actionabilitySummary = firstTruthy(
        actionability.human_summary,
        joinTruthy([
            actionabilityStatus,
            firstTruthy(focus.effective_primary_blocking_domain, summary.wetlab_focus_effective_primary_blocking_domain),
            blockingOrder,
        ]),
    );

    return {
        wetlabGatePassLabel: boolLabel(wetlabGatePass),
        finalGatePassLabel: boolLabel(wetlabFinalGatePass),
        wetlabGatePass,
        wetlabFinalGatePass,
        rawClaimRequirementMode: firstTruthy(
            focus.raw_claim_requirement_mode,
            summary.wetlab_focus_raw_claim_requirement_mode,
            'not_reported',
        ),
        rawClaimRequirementReason: firstTruthy(
            focus.raw_claim_requirement_reason,
            summary.wetlab_focus_raw_claim_requirement_reason,
        ),
        actionabilityStatus,
        blockingOrder,
        effectivePrimaryBlockingDomain: firstTruthy(
            focus.effective_primary_blocking_domain,
            summary.wetlab_focus_effective_primary_blocking_domain,
        ),
        translationFocusStatus: firstTruthy(
            translation.focus_status,
            focus.translation_gate_focus_status,
            summary.wetlab_focus_translation_gate_focus_status,
            'not_reported',
        ),
        translationFocusReason: firstTruthy(
            translation.focus_reason,
            focus.translation_gate_focus_reason,
            summary.wetlab_focus_translation_gate_focus_reason,
        ),
        translationFocusScore: toFloat(
            translation.focus_score,
            toFloat(focus.translation_gate_focus_score, summary.wetlab_focus_translation_gate_focus_score),
        ),
        commercialOverallScoreV2: toFloat(
            commercial.overall_score_v2,
            toFloat(focus.commercial_overall_score_v2, summary.wetlab_focus_commercial_overall_score_v2),
        ),
        commercialRiskBucketV2: firstTruthy(
            commercial.risk_bucket_v2,
            focus.commercial_risk_bucket_v2,
            summary.wetlab_focus_commercial_risk_bucket_v2,
        ),
        commercialDecisionClassV2: firstTruthy(
            commercial.decision_class_v2,
            focus.commercial_decision_class_v2,
            summary.wetlab_focus_commercial_decision_class_v2,
        ),
        translationSummary,
        commercialSummary,
        actionabilitySummary,
        actionRecipeCodes: arrayFromAny(
            focus.action_recipe_codes,
            summary.wetlab_focus_action_recipe_codes,
        ),
        actionRecipeRollup: firstTruthy(
            focus.action_recipe_rollup_text,
            summary.wetlab_focus_action_recipe_rollup_text,
        ),
    };
}

async function ensureTrajectoryRenderable(candidate) {
    const trajectory = await ensureTrajectoryData(candidate);
    if (!trajectory) return null;
    await Promise.all([
        ensureProteinTemplateAtoms(candidate),
        ensureLigandTemplateAtoms(candidate),
    ]);
    return trajectory;
}

async function ensureProteinTemplateAtoms(candidate) {
    if (candidate?.proteinTemplateAtoms) return candidate.proteinTemplateAtoms;
    if (candidate?.proteinReferenceAlignedPath && inferStructureFormat(candidate.proteinReferenceAlignedPath) === 'pdb') {
        try {
            const model = parsePdbStructure(await fetchText(candidate.proteinReferenceAlignedPath));
            const atoms = model.atoms.filter((atom) => !isLigandAtom(atom));
            if (atoms.length) {
                candidate.proteinTemplateAtoms = atoms;
                return atoms;
            }
        } catch (error) {
            console.warn('aligned protein template load failed', candidate.proteinReferenceAlignedPath, error);
        }
    }

    if (candidate?.activeStructureModel?.atoms?.length) {
        const cachedAtoms = candidate.activeStructureModel.atoms.filter((atom) => !isLigandAtom(atom));
        if (cachedAtoms.length) {
            candidate.proteinTemplateAtoms = cachedAtoms;
            return cachedAtoms;
        }
    }

    const pathCandidates = uniqueTruthy([
        candidate.proteinReferenceAlignedPath,
        candidate.viewerReferencePdb,
        candidate.proteinReferenceReady && candidate.proteinReferenceAligned ? candidate.proteinReferencePath : '',
        candidate.activeStructureFormat === 'pdb' ? candidate.activeStructurePath : '',
    ]);
    for (const pathLike of pathCandidates) {
        if (inferStructureFormat(pathLike) !== 'pdb') continue;
        try {
            const model = parsePdbStructure(await fetchText(pathLike));
            const atoms = model.atoms.filter((atom) => !isLigandAtom(atom));
            if (atoms.length) {
                candidate.proteinTemplateAtoms = atoms;
                return atoms;
            }
        } catch (error) {
            console.warn('protein template load failed', pathLike, error);
        }
    }

    candidate.proteinTemplateAtoms = [];
    return candidate.proteinTemplateAtoms;
}

async function ensureLigandTemplateAtoms(candidate) {
    if (candidate?.ligandTemplateAtoms) return candidate.ligandTemplateAtoms;
    if (candidate?.activeStructureModel?.atoms?.length) {
        const cachedAtoms = candidate.activeStructureModel.atoms.filter((atom) => isLigandAtom(atom));
        if (cachedAtoms.length) {
            candidate.ligandTemplateAtoms = cachedAtoms;
            return cachedAtoms;
        }
    }

    const pathCandidates = uniqueTruthy([
        candidate.viewerPosePdbReady ? candidate.viewerPosePdb : '',
        candidate.fallbackStructurePath,
        candidate.viewerReferencePdb,
        candidate.activeStructureFormat === 'pdb' ? candidate.activeStructurePath : '',
        ...candidate.structurePathCandidates,
    ]);
    for (const pathLike of pathCandidates) {
        if (inferStructureFormat(pathLike) !== 'pdb') continue;
        try {
            const model = parsePdbStructure(await fetchText(pathLike));
            const atoms = model.atoms.filter((atom) => isLigandAtom(atom));
            if (atoms.length) {
                candidate.ligandTemplateAtoms = atoms;
                return atoms;
            }
        } catch (error) {
            console.warn('ligand template load failed', pathLike, error);
        }
    }

    candidate.ligandTemplateAtoms = buildDefaultLigandTemplateAtoms(
        candidate?.trajectoryData?.ligandAtomCount || 0,
    );
    return candidate.ligandTemplateAtoms;
}

function buildBoundsFromAtoms(atoms) {
    const bounds = {
        min: [Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY],
        max: [Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY],
    };
    let pointCount = 0;
    for (const atom of atoms || []) {
        if (!atom || isHydrogenAtom(atom)) continue;
        const point = atomToPoint(atom);
        if (!isVec3Like(point)) continue;
        for (let axis = 0; axis < 3; axis += 1) {
            bounds.min[axis] = Math.min(bounds.min[axis], point[axis]);
            bounds.max[axis] = Math.max(bounds.max[axis], point[axis]);
        }
        pointCount += 1;
    }
    if (!pointCount) {
        return {
            min: [0, 0, 0],
            max: [0, 0, 0],
            center: [0, 0, 0],
            size: [0, 0, 0],
            pointCount: 0,
        };
    }
    return finalizeBounds(bounds, pointCount);
}

function finalizeBounds(bounds, pointCount = 0) {
    const center = [
        (bounds.min[0] + bounds.max[0]) / 2,
        (bounds.min[1] + bounds.max[1]) / 2,
        (bounds.min[2] + bounds.max[2]) / 2,
    ];
    const size = [
        bounds.max[0] - bounds.min[0],
        bounds.max[1] - bounds.min[1],
        bounds.max[2] - bounds.min[2],
    ];
    return {
        min: bounds.min.slice(),
        max: bounds.max.slice(),
        center,
        size,
        pointCount,
    };
}

function mergeBounds(a, b) {
    return finalizeBounds({
        min: [
            Math.min(a.min[0], b.min[0]),
            Math.min(a.min[1], b.min[1]),
            Math.min(a.min[2], b.min[2]),
        ],
        max: [
            Math.max(a.max[0], b.max[0]),
            Math.max(a.max[1], b.max[1]),
            Math.max(a.max[2], b.max[2]),
        ],
    }, Number(a.pointCount || 0) + Number(b.pointCount || 0));
}

function distanceSqPointToBounds(point, bounds) {
    let distanceSq = 0;
    for (let axis = 0; axis < 3; axis += 1) {
        const value = point[axis];
        if (value < bounds.min[axis]) {
            const delta = bounds.min[axis] - value;
            distanceSq += delta * delta;
        } else if (value > bounds.max[axis]) {
            const delta = value - bounds.max[axis];
            distanceSq += delta * delta;
        }
    }
    return distanceSq;
}

function minDistanceSqPointsToBounds(points, bounds) {
    let best = Number.POSITIVE_INFINITY;
    for (const point of points || []) {
        best = Math.min(best, distanceSqPointToBounds(point, bounds));
    }
    return best;
}

function buildResidueSpatialScaffold(group) {
    return {
        key: group.key,
        group,
        bounds: buildBoundsFromAtoms(group.atoms),
    };
}

function buildResidueSpatialBvh(scaffolds, maxLeafSize = 6) {
    if (!Array.isArray(scaffolds) || !scaffolds.length) return null;
    const nodeStats = { nodeCount: 0, leafCount: 0, maxDepth: 0 };
    function build(items, depth = 0) {
        if (!items.length) return null;
        nodeStats.nodeCount += 1;
        nodeStats.maxDepth = Math.max(nodeStats.maxDepth, depth);
        const aggregateBounds = items.reduce(
            (acc, item) => (acc ? mergeBounds(acc, item.bounds) : item.bounds),
            null,
        );
        if (items.length <= maxLeafSize) {
            nodeStats.leafCount += 1;
            return {
                leaf: true,
                depth,
                bounds: aggregateBounds,
                items,
            };
        }
        const axis = aggregateBounds.size.indexOf(Math.max(...aggregateBounds.size));
        const sorted = items.slice().sort((left, right) => left.bounds.center[axis] - right.bounds.center[axis]);
        const midpoint = Math.max(1, Math.floor(sorted.length / 2));
        const leftItems = sorted.slice(0, midpoint);
        const rightItems = sorted.slice(midpoint);
        return {
            leaf: false,
            depth,
            axis,
            bounds: aggregateBounds,
            left: build(leftItems, depth + 1),
            right: build(rightItems, depth + 1),
        };
    }
    return {
        root: build(scaffolds),
        stats: nodeStats,
    };
}

function queryResidueSpatialBvh(tree, ligandPoints, cutoffA = 7.5) {
    if (!tree?.root || !Array.isArray(ligandPoints) || !ligandPoints.length) {
        return {
            items: [],
            stats: {
                visitedNodes: 0,
                matchedLeaves: 0,
                matchedItems: 0,
                cutoffA,
            },
        };
    }
    const cutoffSq = cutoffA * cutoffA;
    const stats = {
        visitedNodes: 0,
        matchedLeaves: 0,
        matchedItems: 0,
        cutoffA,
    };
    const matched = [];
    function visit(node) {
        if (!node) return;
        stats.visitedNodes += 1;
        if (minDistanceSqPointsToBounds(ligandPoints, node.bounds) > cutoffSq) return;
        if (node.leaf) {
            stats.matchedLeaves += 1;
            for (const item of node.items || []) {
                if (minDistanceSqPointsToBounds(ligandPoints, item.bounds) <= cutoffSq) {
                    matched.push(item);
                }
            }
            return;
        }
        visit(node.left);
        visit(node.right);
    }
    visit(tree.root);
    stats.matchedItems = matched.length;
    return { items: matched, stats };
}

function collectRenderableItems(container) {
    if (!container) return [];
    if (Array.isArray(container)) return container.filter(Boolean);
    if (typeof container.values === 'function') return Array.from(container.values()).filter(Boolean);
    if (typeof container[Symbol.iterator] === 'function') return Array.from(container).filter(Boolean);
    if (typeof container === 'object') return Object.values(container).filter(Boolean);
    return [];
}

function estimateRenderablePrimitiveCount(renderable) {
    const values = renderable?.values || {};
    const drawCount = Number(values.drawCount?.ref?.value ?? values.drawCount?.value ?? values.drawCount ?? NaN);
    if (Number.isFinite(drawCount) && drawCount > 0) {
        return Math.max(0, Math.round(drawCount / 3));
    }
    const elements = values.elements?.ref?.value ?? values.elements?.value ?? values.elements;
    if (elements && typeof elements.length === 'number') {
        return Math.max(0, Math.round(Number(elements.length) / 3));
    }
    return 0;
}

function collectCanvas3dGeometryProbeForViewer(viewerLike = null) {
    const canvas3d = viewerLike?.plugin?.canvas3d;
    const scene = canvas3d?.scene;
    if (!canvas3d) {
        return {
            canvasReady: false,
            sceneReady: false,
            sceneObjectCount: 0,
            renderableCount: 0,
            primitiveEstimate: 0,
            sceneKeySample: [],
            renderObjectKeySample: [],
        };
    }
    const renderables = collectRenderableItems(scene?.renderables);
    const primitives = collectRenderableItems(scene?.primitives);
    const objects = collectRenderableItems(scene?.objects);
    const renderObjectsFromApi = typeof canvas3d?.getRenderObjects === 'function'
        ? collectRenderableItems(canvas3d.getRenderObjects())
        : [];
    const combined = [...renderables, ...primitives, ...objects, ...renderObjectsFromApi];
    const seen = new Set();
    const uniqueRenderables = combined.filter((item) => {
        if (!item || seen.has(item)) return false;
        seen.add(item);
        return true;
    });
    const primitiveEstimate = uniqueRenderables.reduce((sum, item) => sum + estimateRenderablePrimitiveCount(item), 0);
    const firstRenderable = uniqueRenderables[0] || null;
    return {
        canvasReady: true,
        sceneReady: Boolean(scene) || uniqueRenderables.length > 0,
        sceneObjectCount: objects.length || renderables.length || primitives.length || renderObjectsFromApi.length || 0,
        renderableCount: uniqueRenderables.length,
        primitiveEstimate,
        sceneKeySample: scene ? Object.keys(scene).slice(0, 24) : [],
        renderObjectKeySample: firstRenderable ? Object.keys(firstRenderable).slice(0, 24) : [],
    };
}

function collectCanvas3dGeometryProbe() {
    return collectCanvas3dGeometryProbeForViewer(state.viewer);
}

function collectCompareCanvas3dGeometryProbe(slot = 'A') {
    return collectCanvas3dGeometryProbeForViewer(state.compareViewers?.[slot] || null);
}

function collectViewerGeometryDebugState(viewerLike = null) {
    const pluginReady = Boolean(viewerLike?.plugin);
    const canvasReady = Boolean(viewerLike?.plugin?.canvas3d);
    const canvas3dProbe = collectCanvas3dGeometryProbeForViewer(viewerLike);
    const stateProbe = collectViewerStateRepresentationProbeForViewer(viewerLike);
    const statePresenceLabel = stateProbe.stateRenderablePresenceLabel || 'not reported';
    const renderableCount = Number(canvas3dProbe?.renderableCount || 0);
    const primitiveEstimate = Number(canvas3dProbe?.primitiveEstimate || 0);
    let statusKind = 'viewer_not_ready';
    let statusLabel = 'viewer not ready';
    let failureKind = 'genuine_failure';
    if (pluginReady && !canvasReady) {
        statusKind = 'plugin_ready_canvas3d_missing';
        statusLabel = 'plugin ready / canvas3d missing';
    } else if (pluginReady && canvasReady && (renderableCount > 0 || primitiveEstimate > 0)) {
        statusKind = 'mesh_present';
        statusLabel = 'mesh present';
        failureKind = 'none';
    } else if (pluginReady && canvasReady && stateProbe.stateRenderablePresenceKind !== 'not_reported') {
        statusKind = 'viewer_ready_mesh_probe_unavailable';
        statusLabel = `viewer ready / mesh probe unavailable / ${statePresenceLabel}`;
        failureKind = 'mesh_probe_unavailable';
    } else if (pluginReady && canvasReady) {
        statusKind = 'viewer_ready_probe_not_reported';
        statusLabel = 'viewer ready / probe not reported';
        failureKind = 'mesh_probe_unavailable';
    }
    return {
        pluginReady,
        canvasReady,
        statusKind,
        statusLabel,
        failureKind,
        renderableCount,
        primitiveEstimate,
        stateCellCount: stateProbe.stateCellCount || 0,
        activeStateCellCount: stateProbe.activeStateCellCount || 0,
        stateRenderablePresenceKind: stateProbe.stateRenderablePresenceKind || 'not_reported',
        stateRenderablePresenceLabel: statePresenceLabel,
    };
}

function getStateDataCellsForViewer(viewerLike = null) {
    const cellsSource = viewerLike?.plugin?.state?.data?.cells;
    if (!cellsSource) return [];
    if (typeof cellsSource.values === 'function') {
        return Array.from(cellsSource.values()).filter(Boolean);
    }
    if (Array.isArray(cellsSource)) {
        return cellsSource.filter(Boolean);
    }
    if (typeof cellsSource === 'object') {
        return Object.values(cellsSource).filter(Boolean);
    }
    return [];
}

function collectViewerStateRepresentationProbeForViewer(viewerLike = null) {
    const cells = getStateDataCellsForViewer(viewerLike);
    if (!cells.length) {
        return {
            stateCellCount: 0,
            activeStateCellCount: 0,
            stateRepCount: 0,
            stateSurfaceRepCount: 0,
            stateGaussianRepCount: 0,
            stateMolecularSurfaceRepCount: 0,
            stateVolumeRepCount: 0,
            stateShapeRepCount: 0,
            stateStructureRepCount: 0,
            state3DRepCount: 0,
            stateRenderablePresenceKind: 'not_reported',
            stateRenderablePresenceLabel: 'not reported',
            stateTransformerSample: [],
            stateLabelSample: [],
        };
    }
    const transformerSample = [];
    const labelSample = [];
    let activeStateCellCount = 0;
    let stateRepCount = 0;
    let stateSurfaceRepCount = 0;
    let stateGaussianRepCount = 0;
    let stateMolecularSurfaceRepCount = 0;
    let stateVolumeRepCount = 0;
    let stateShapeRepCount = 0;
    let stateStructureRepCount = 0;
    let state3DRepCount = 0;
    for (const cell of cells) {
        const cellStatus = String(firstTruthy(cell?.status, cell?.state?.status, 'ok')).toLowerCase();
        if (/error|fail|disposed/.test(cellStatus)) continue;
        const transformerId = String(
            firstTruthy(
                cell?.transform?.transformer?.id,
                cell?.transform?.transformer?.definition?.name,
                cell?.transform?.transformer?.definition?.display?.name,
            ) || ''
        ).toLowerCase();
        const objLabel = String(firstTruthy(cell?.obj?.label, cell?.obj?.description, '') || '').toLowerCase();
        const objType = String(firstTruthy(cell?.obj?.type?.name, '') || '').toLowerCase();
        const combined = `${transformerId} ${objLabel} ${objType}`;
        if (!combined.trim()) continue;
        activeStateCellCount += 1;
        if (transformerSample.length < 6 && transformerId) transformerSample.push(transformerId);
        if (labelSample.length < 6 && (objLabel || objType)) labelSample.push(firstTruthy(objLabel, objType));
        if (/representation|repr/.test(combined)) stateRepCount += 1;
        if (/3d|representation-3d|shape representation|shape-representation|volume/.test(combined)) state3DRepCount += 1;
        if (/surface|isosurface|direct-volume/.test(combined)) stateSurfaceRepCount += 1;
        if (/gaussian/.test(combined)) stateGaussianRepCount += 1;
        if (/molecular-surface|molecular surface/.test(combined)) stateMolecularSurfaceRepCount += 1;
        if (/volume|isosurface|direct-volume/.test(combined)) stateVolumeRepCount += 1;
        if (/shape/.test(combined)) stateShapeRepCount += 1;
        if (/structure representation|structure-representation|structure/.test(combined)) stateStructureRepCount += 1;
    }
    const hasSurfaceState = (
        stateSurfaceRepCount > 0
        || stateGaussianRepCount > 0
        || stateMolecularSurfaceRepCount > 0
        || stateVolumeRepCount > 0
    );
    const hasRepresentationState = (
        stateRepCount > 0
        || state3DRepCount > 0
        || stateShapeRepCount > 0
        || stateStructureRepCount > 0
    );
    const stateRenderablePresenceKind = hasSurfaceState
        ? 'state_surface_present'
        : hasRepresentationState
            ? 'state_representation_present'
            : activeStateCellCount > 0
                ? 'state_tree_present'
                : 'not_reported';
    const stateRenderablePresenceLabel = stateRenderablePresenceKind === 'state_surface_present'
        ? 'state surface present'
        : stateRenderablePresenceKind === 'state_representation_present'
            ? 'state representation present'
            : stateRenderablePresenceKind === 'state_tree_present'
                ? 'state tree present'
                : 'not reported';
    return {
        stateCellCount: cells.length,
        activeStateCellCount,
        stateRepCount,
        stateSurfaceRepCount,
        stateGaussianRepCount,
        stateMolecularSurfaceRepCount,
        stateVolumeRepCount,
        stateShapeRepCount,
        stateStructureRepCount,
        state3DRepCount,
        stateRenderablePresenceKind,
        stateRenderablePresenceLabel,
        stateTransformerSample: transformerSample,
        stateLabelSample: labelSample,
    };
}

function collectViewerStateRepresentationProbe() {
    return collectViewerStateRepresentationProbeForViewer(state.viewer);
}

function collectCompareViewerStateRepresentationProbe(slot = 'A') {
    const key = String(slot || 'A').toUpperCase();
    return collectViewerStateRepresentationProbeForViewer(state.compareViewers?.[key] || null);
}

function describeGeometryPresenceTierFromProbe(probe = null) {
    const canvas = probe?.canvas3d || {};
    if ((canvas.renderableCount || 0) > 0 || (canvas.primitiveEstimate || 0) > 0) {
        return 'renderable mesh present';
    }
    const statePresence = probe?.stateRenderablePresenceKind || 'not_reported';
    if (statePresence === 'state_surface_present') return 'state surface present';
    if (statePresence === 'state_representation_present') return 'state representation present';
    if (statePresence === 'state_tree_present') return 'state tree present';
    return 'not reported';
}

function collectPocketGeometryProbe(candidate, viewerLike = null) {
    const cache = candidate?.fastTrajectorySceneCache;
    const targetViewer = viewerLike || state.viewer;
    const structures = getCurrentSceneStructuresForViewer(targetViewer);
    const isPrimaryViewer = !viewerLike || viewerLike === state.viewer;
    const refs = {
        backbone: firstTruthy(cache?.backboneRef),
        contact: firstTruthy(cache?.contactRef),
        surface: firstTruthy(cache?.surfaceRef),
        ligand: firstTruthy(cache?.ligandRef),
    };
    const readiness = isPrimaryViewer
        ? {
            backbone: Boolean(refs.backbone && getStructureEntryByRef(refs.backbone)),
            contact: Boolean(refs.contact && getStructureEntryByRef(refs.contact)),
            surface: Boolean(refs.surface && getStructureEntryByRef(refs.surface)),
            ligand: Boolean(refs.ligand && getStructureEntryByRef(refs.ligand)),
        }
        : {
            backbone: structures.length > 0,
            contact: false,
            surface: false,
            ligand: structures.length > 0,
        };
    const trackedRefCount = Object.values(readiness).filter(Boolean).length;
    const representation = mapRepresentation(dom.reprSelect?.value || 'cartoon');
    const pocketSurfaceRequested = Boolean(dom.togglePocketSurface?.checked);
    const stateRepProbe = collectViewerStateRepresentationProbeForViewer(targetViewer);
    const surfaceRepresentationActive = (
        readiness.surface
        || representation === 'molecular-surface'
        || representation === 'gaussian-surface'
        || pocketSurfaceRequested
        || stateRepProbe.stateSurfaceRepCount > 0
        || stateRepProbe.stateGaussianRepCount > 0
        || stateRepProbe.stateMolecularSurfaceRepCount > 0
        || stateRepProbe.stateVolumeRepCount > 0
    );
    const canvas3d = collectCanvas3dGeometryProbeForViewer(targetViewer);
    return {
        trackedRefCount,
        sceneStructureCount: Array.isArray(structures) ? structures.length : 0,
        surfaceRepresentationActive,
        pocketSurfaceRequested,
        representation,
        readiness,
        canvas3d,
        geometryPresenceLabel: describeGeometryPresenceTierFromProbe({
            canvas3d,
            ...stateRepProbe,
        }),
        ...stateRepProbe,
    };
}

function inferPocketBvhMode(candidate, frameIndex = null) {
    const atomReady = Boolean(candidate?.trajectoryData?.proteinAtomSchemaReady);
    const geometryProbe = collectPocketGeometryProbe(candidate);
    if (geometryProbe.surfaceRepresentationActive && atomReady && Number.isFinite(frameIndex)) {
        return 'surface_state_probed_deformed_residue_bvh';
    }
    if (geometryProbe.surfaceRepresentationActive && atomReady) {
        return 'surface_state_probed_instanced_residue_bvh';
    }
    if (atomReady && Number.isFinite(frameIndex)) return 'deformed_mesh_compatible_residue_bvh';
    if (atomReady) return 'instanced_mesh_compatible_residue_bvh';
    return 'static_residue_bvh';
}

function describePocketBvhPath(candidate, frameIndex = null) {
    const diagnostics = candidate?.pocketContextCache?.bvhDiagnostics;
    if (diagnostics?.pathLabel) return diagnostics.pathLabel;
    return inferPocketBvhMode(candidate, frameIndex);
}

function describePocketBvhQuery(candidate, frameIndex = null) {
    const diagnostics = candidate?.pocketContextCache?.bvhDiagnostics;
    if (!diagnostics) return 'not reported';
    return `${diagnostics.queryResidueCount}/${diagnostics.candidateResidueCount} residues`;
}

function describePocketGeometryProbe(candidate, frameIndex = null) {
    return describePocketGeometryProbeForViewer(candidate, frameIndex);
}

function describePocketGeometryPresence(candidate, frameIndex = null, viewerLike = null) {
    const probe = resolvePocketGeometryProbeForViewer(candidate, viewerLike);
    if (!probe) return 'not reported';
    return describeGeometryPresenceTierFromProbe(probe);
}

function resolvePocketGeometryProbeForViewer(candidate, viewerLike = null) {
    if (!candidate) return null;
    const diagnostics = candidate?.pocketContextCache?.bvhDiagnostics;
    if (!viewerLike && diagnostics?.geometryProbe) return diagnostics.geometryProbe;
    return collectPocketGeometryProbe(candidate, viewerLike);
}

function describePocketGeometryProbeForViewer(candidate, frameIndex = null, viewerLike = null) {
    const probe = resolvePocketGeometryProbeForViewer(candidate, viewerLike);
    if (!probe) return 'not reported';
    const diagnostics = candidate?.pocketContextCache?.bvhDiagnostics;
    const path = diagnostics?.pathLabel || inferPocketBvhMode(candidate, frameIndex);
    const canvas = probe.canvas3d || {};
    const statePresence = describeGeometryPresenceTierFromProbe(probe);
    return `${path} · ${statePresence} · refs ${probe.trackedRefCount}/${probe.sceneStructureCount} · cells ${probe.activeStateCellCount || 0}/${probe.stateCellCount || 0} · reps ${probe.stateRepCount}/${probe.state3DRepCount} · renderables ${canvas.renderableCount || 0} · tris~${canvas.primitiveEstimate || 0} · surface ${probe.surfaceRepresentationActive ? 'on' : 'off'}`;
}

function resolveCompareConsoleFrameIndex(candidate) {
    if (!candidate) return null;
    if (
        candidate.index === state.selectedIndex
        && state.trajectorySceneMode === 'trajectory'
        && Number.isFinite(state.trajectoryFrameIndex)
    ) {
        return state.trajectoryFrameIndex;
    }
    const referenceIndex = toInt(candidate.viewerReferenceFrameIndex, NaN);
    return Number.isFinite(referenceIndex) ? referenceIndex : null;
}

function buildPocketContext(candidate, frameIndex) {
    const trajectory = candidate?.trajectoryData;
    const proteinAtoms = getProteinAtomsForFrame(candidate, frameIndex);
    const key = `${candidate?.index ?? 'x'}:${Number.isFinite(frameIndex) ? frameIndex : 'ref'}:${proteinAtoms.length}`;
    if (candidate?.pocketContextCache?.key === key) {
        return candidate.pocketContextCache;
    }

    const ligandPoints = getCandidateLigandCoords(candidate, frameIndex);
    const fallbackProteinAtoms = proteinAtoms.filter((atom) => atom.atomName === 'CA');
    const emptyContext = {
        key,
        selectedAtoms: fallbackProteinAtoms.length ? fallbackProteinAtoms : proteinAtoms.slice(0, 240),
        backboneAtoms: fallbackProteinAtoms,
        contactAtoms: [],
        surfaceAtoms: [],
        residues: [],
        focusResidues: [],
        shellResidues: [],
        contactResidues: [],
        autoInteractions: [],
        fullResidueCount: 0,
        shellResidueCount: 0,
        bvhDiagnostics: null,
    };

    if (!ligandPoints.length || !proteinAtoms.length) {
        candidate.pocketContextCache = emptyContext;
        return emptyContext;
    }

    const residueGroups = getProteinResidueGroups(candidate, proteinAtoms);
    const residueScaffolds = residueGroups.map((group) => buildResidueSpatialScaffold(group));
    const residueBvh = buildResidueSpatialBvh(residueScaffolds);
    const bvhQuery = queryResidueSpatialBvh(residueBvh, ligandPoints, 7.8);
    const candidateGroups = bvhQuery.items.length
        ? bvhQuery.items.map((item) => item.group)
        : residueGroups;
    const residues = candidateGroups.map((group) => scorePocketResidue(group, ligandPoints)).sort((a, b) => a.minDistanceA - b.minDistanceA);
    if (!residues.length) {
        candidate.pocketContextCache = emptyContext;
        return emptyContext;
    }

    let fullResidues = residues.filter((entry) => entry.minDistanceA <= 5.2).slice(0, 16);
    if (!fullResidues.length) fullResidues = residues.slice(0, Math.min(8, residues.length));
    const fullKeys = new Set(fullResidues.map((entry) => entry.key));
    const shellResidues = residues
        .filter((entry) => !fullKeys.has(entry.key) && entry.minDistanceA <= 7.5)
        .slice(0, 8);
    let contactResidues = fullResidues.filter((entry) => entry.minDistanceA <= 4.5).slice(0, 6);
    if (!contactResidues.length) contactResidues = fullResidues.slice(0, Math.min(4, fullResidues.length));
    const contactKeys = new Set(contactResidues.map((entry) => entry.key));

    const selectedAtoms = [];
    const backboneAtoms = [];
    const contactAtoms = [];
    for (const entry of fullResidues.concat(shellResidues)) {
        for (const atom of entry.atoms) {
            if (isBackboneAtom(atom) || atom.atomName === 'CA') {
                backboneAtoms.push(atom);
            }
        }
    }
    for (const entry of contactResidues) {
        for (const atom of entry.atoms) {
            if (isHydrogenAtom(atom) || isBackboneAtom(atom)) continue;
            contactAtoms.push(atom);
        }
    }
    if (!backboneAtoms.length) {
        backboneAtoms.push(...fallbackProteinAtoms.slice(0, 48));
    }
    selectedAtoms.push(...backboneAtoms, ...contactAtoms);

    const surfaceAtoms = [];
    for (const entry of contactResidues) {
        for (const atom of entry.atoms) {
            if (!isHydrogenAtom(atom)) surfaceAtoms.push(atom);
        }
    }

    const autoInteractions = buildAutoInteractionSegments(candidate, contactResidues, frameIndex).slice(0, 6);

    const context = {
        key,
        selectedAtoms,
        backboneAtoms,
        contactAtoms,
        surfaceAtoms,
        residues,
        focusResidues: fullResidues,
        shellResidues,
        contactResidues,
        autoInteractions,
        fullResidueCount: fullResidues.length,
        shellResidueCount: shellResidues.length,
        bvhDiagnostics: {
            pathLabel: inferPocketBvhMode(candidate, frameIndex),
            candidateResidueCount: residueGroups.length,
            queryResidueCount: candidateGroups.length,
            queryCutoffA: bvhQuery.stats.cutoffA,
            visitedNodeCount: bvhQuery.stats.visitedNodes,
            matchedLeafCount: bvhQuery.stats.matchedLeaves,
            nodeCount: residueBvh?.stats?.nodeCount || 0,
            leafCount: residueBvh?.stats?.leafCount || 0,
            maxDepth: residueBvh?.stats?.maxDepth || 0,
            broadPhaseApplied: candidateGroups.length > 0 && candidateGroups.length < residueGroups.length,
            geometryProbe: collectPocketGeometryProbe(candidate),
        },
    };
    candidate.pocketContextCache = context;
    return context;
}

function getProteinResidueGroups(candidate, proteinAtoms) {
    if (proteinAtoms === candidate?.proteinTemplateAtoms && candidate?.proteinResidueGroups?.length) {
        return candidate.proteinResidueGroups;
    }
    const groups = new Map();
    for (const atom of proteinAtoms) {
        const key = proteinResidueKey(atom);
        if (!groups.has(key)) {
            groups.set(key, {
                key,
                label: `${atom.residueName || 'UNK'} ${atom.chainId || '_'}${atom.residueSeq || '?'}`,
                residueName: atom.residueName || 'UNK',
                atoms: [],
                caAtom: null,
                representativeAtom: null,
            });
        }
        const group = groups.get(key);
        group.atoms.push(atom);
        if (atom.atomName === 'CA') group.caAtom = atom;
        if (!group.representativeAtom && !isHydrogenAtom(atom)) group.representativeAtom = atom;
    }
    const resolvedGroups = Array.from(groups.values());
    if (proteinAtoms === candidate?.proteinTemplateAtoms) {
        candidate.proteinResidueGroups = resolvedGroups;
    }
    return resolvedGroups;
}

function scorePocketResidue(group, ligandPoints) {
    let minDistanceSq = Number.POSITIVE_INFINITY;
    let nearestProteinPoint = null;
    let nearestLigandPoint = null;
    for (const atom of group.atoms) {
        if (isHydrogenAtom(atom)) continue;
        const atomPoint = [atom.x, atom.y, atom.z];
        for (const ligandPoint of ligandPoints) {
            const distSq = squaredDistance(atomPoint, ligandPoint);
            if (distSq < minDistanceSq) {
                minDistanceSq = distSq;
                nearestProteinPoint = atomPoint;
                nearestLigandPoint = ligandPoint;
            }
        }
    }

    const representative = group.caAtom || group.representativeAtom || group.atoms[0] || null;
    return {
        ...group,
        minDistanceA: Number.isFinite(minDistanceSq) ? Math.sqrt(minDistanceSq) : Number.NaN,
        nearestProteinPoint: nearestProteinPoint || atomToPoint(representative),
        nearestLigandPoint: nearestLigandPoint || ligandPoints[0],
        representativePoint: atomToPoint(representative),
    };
}

function getLigandFrameCoords(trajectory, frameIndex) {
    if (!trajectory?.frameCount || !trajectory?.ligandAtomCount || !Number.isFinite(frameIndex)) return [];
    const clamped = clamp(frameIndex, 0, trajectory.frameCount - 1);
    const coords = [];
    for (let atomIndex = 0; atomIndex < trajectory.ligandAtomCount; atomIndex += 1) {
        const base = clamped * trajectory.ligandAtomCount * 3 + atomIndex * 3;
        coords.push([
            trajectory.ligandCoords[base],
            trajectory.ligandCoords[base + 1],
            trajectory.ligandCoords[base + 2],
        ]);
    }
    return coords;
}

function getProteinAtomFrameEligibility(candidate) {
    const trajectory = candidate?.trajectoryData;
    const templateAtoms = Array.isArray(candidate?.proteinTemplateAtoms) ? candidate.proteinTemplateAtoms : [];
    const payload = trajectory?.proteinAtomFrames;
    const shape = Array.isArray(payload?.shape) ? payload.shape : [];
    const templateIndex = Array.isArray(trajectory?.proteinAtomTemplateIndex) ? trajectory.proteinAtomTemplateIndex : [];
    const storedFrameCount = Number(shape?.[0] || 0);
    const storedAtomCount = Number(shape?.[1] || 0);

    if (!trajectory?.proteinAtomSchemaReady || !payload?.data || shape.length !== 3 || shape[2] !== 3) {
        return {
            ready: false,
            eligible: false,
            reason: 'schema_missing',
            storedFrameCount,
            storedAtomCount,
            templateAtomCount: templateAtoms.length,
            mappingMode: 'none',
        };
    }
    if (!templateAtoms.length) {
        return {
            ready: true,
            eligible: false,
            reason: 'template_missing',
            storedFrameCount,
            storedAtomCount,
            templateAtomCount: templateAtoms.length,
            mappingMode: 'none',
        };
    }
    if (storedFrameCount !== Number(trajectory?.frameCount || 0)) {
        return {
            ready: true,
            eligible: false,
            reason: 'frame_count_mismatch',
            storedFrameCount,
            storedAtomCount,
            templateAtomCount: templateAtoms.length,
            mappingMode: 'none',
        };
    }
    if (storedAtomCount === templateAtoms.length && !templateIndex.length) {
        return {
            ready: true,
            eligible: true,
            reason: 'direct_order',
            storedFrameCount,
            storedAtomCount,
            templateAtomCount: templateAtoms.length,
            mappingMode: 'direct',
        };
    }
    if (templateIndex.length !== storedAtomCount || storedAtomCount !== templateAtoms.length) {
        return {
            ready: true,
            eligible: false,
            reason: 'template_index_mismatch',
            storedFrameCount,
            storedAtomCount,
            templateAtomCount: templateAtoms.length,
            mappingMode: 'mapped',
        };
    }
    const seen = new Set();
    for (const rawIndex of templateIndex) {
        const templateAtomIndex = Math.trunc(Number(rawIndex));
        if (
            !Number.isFinite(templateAtomIndex)
            || templateAtomIndex < 0
            || templateAtomIndex >= templateAtoms.length
            || seen.has(templateAtomIndex)
        ) {
            return {
                ready: true,
                eligible: false,
                reason: 'template_index_invalid',
                storedFrameCount,
                storedAtomCount,
                templateAtomCount: templateAtoms.length,
                mappingMode: 'mapped',
            };
        }
        seen.add(templateAtomIndex);
    }
    return {
        ready: true,
        eligible: true,
        reason: 'mapped_order',
        storedFrameCount,
        storedAtomCount,
        templateAtomCount: templateAtoms.length,
        mappingMode: 'mapped',
    };
}

function getAlignedProteinAtomFrameCoords(candidate, frameIndex) {
    const trajectory = candidate?.trajectoryData;
    const templateAtoms = Array.isArray(candidate?.proteinTemplateAtoms) ? candidate.proteinTemplateAtoms : [];
    if (!trajectory?.proteinAtomSchemaReady || !Number.isFinite(frameIndex) || !templateAtoms.length) return null;
    const eligibility = getProteinAtomFrameEligibility(candidate);
    if (!eligibility.eligible) return null;

    if (!(candidate.proteinFrameCoordCache instanceof Map)) {
        candidate.proteinFrameCoordCache = new Map();
    }
    const clampedFrameIndex = clamp(frameIndex, 0, trajectory.frameCount - 1);
    if (candidate.proteinFrameCoordCache.has(clampedFrameIndex)) {
        return candidate.proteinFrameCoordCache.get(clampedFrameIndex);
    }

    const payload = trajectory.proteinAtomFrames;
    const storedAtomCount = payload.shape[1];
    const frameBase = clampedFrameIndex * storedAtomCount * 3;
    const alignedCoords = new Array(templateAtoms.length).fill(null);
    const templateIndex = Array.isArray(trajectory.proteinAtomTemplateIndex) ? trajectory.proteinAtomTemplateIndex : [];
    const directOrder = eligibility.mappingMode === 'direct';

    for (let storedIndex = 0; storedIndex < storedAtomCount; storedIndex += 1) {
        const targetIndex = directOrder ? storedIndex : Math.trunc(Number(templateIndex[storedIndex]));
        if (targetIndex < 0 || targetIndex >= templateAtoms.length) continue;
        const base = frameBase + storedIndex * 3;
        alignedCoords[targetIndex] = [
            payload.data[base],
            payload.data[base + 1],
            payload.data[base + 2],
        ];
    }

    candidate.proteinFrameCoordCache.set(clampedFrameIndex, alignedCoords);
    if (candidate.proteinFrameCoordCache.size > 16) {
        const firstKey = candidate.proteinFrameCoordCache.keys().next().value;
        candidate.proteinFrameCoordCache.delete(firstKey);
    }
    return alignedCoords;
}

function getProteinAtomsForFrame(candidate, frameIndex) {
    const templateAtoms = Array.isArray(candidate?.proteinTemplateAtoms) ? candidate.proteinTemplateAtoms : [];
    if (!templateAtoms.length || !Number.isFinite(frameIndex)) return templateAtoms;
    const alignedCoords = getAlignedProteinAtomFrameCoords(candidate, frameIndex);
    if (!alignedCoords) return templateAtoms;

    if (!(candidate.proteinFrameAtomCache instanceof Map)) {
        candidate.proteinFrameAtomCache = new Map();
    }
    const clampedFrameIndex = clamp(frameIndex, 0, candidate.trajectoryData.frameCount - 1);
    if (candidate.proteinFrameAtomCache.has(clampedFrameIndex)) {
        return candidate.proteinFrameAtomCache.get(clampedFrameIndex);
    }

    const frameAtoms = templateAtoms.map((atom, atomIndex) => {
        const coords = alignedCoords[atomIndex];
        return Array.isArray(coords)
            ? { ...atom, x: coords[0], y: coords[1], z: coords[2] }
            : atom;
    });
    candidate.proteinFrameAtomCache.set(clampedFrameIndex, frameAtoms);
    if (candidate.proteinFrameAtomCache.size > 16) {
        const firstKey = candidate.proteinFrameAtomCache.keys().next().value;
        candidate.proteinFrameAtomCache.delete(firstKey);
    }
    return frameAtoms;
}

function getCandidateLigandCoords(candidate, frameIndex) {
    const trajectoryCoords = getLigandFrameCoords(candidate?.trajectoryData, frameIndex);
    if (trajectoryCoords.length) return trajectoryCoords;
    const ligandAtoms = Array.isArray(candidate?.ligandTemplateAtoms) ? candidate.ligandTemplateAtoms : [];
    return ligandAtoms.map((atom) => atomToPoint(atom)).filter((point) => isVec3Like(point));
}

function getLigandFrameAtoms(candidate, frameIndex) {
    const ligandAtoms = Array.isArray(candidate?.ligandTemplateAtoms) ? candidate.ligandTemplateAtoms : [];
    const ligandCoords = getCandidateLigandCoords(candidate, frameIndex);
    const fallbackLigandAtoms = buildDefaultLigandTemplateAtoms(Math.max(ligandAtoms.length, ligandCoords.length));
    const atoms = [];
    const count = Math.max(ligandAtoms.length, ligandCoords.length);
    for (let atomIndex = 0; atomIndex < count; atomIndex += 1) {
        const template = ligandAtoms[atomIndex] || fallbackLigandAtoms[atomIndex] || {};
        atoms.push({
            ...template,
            x: ligandCoords[atomIndex]?.[0] ?? Number(template.x || 0),
            y: ligandCoords[atomIndex]?.[1] ?? Number(template.y || 0),
            z: ligandCoords[atomIndex]?.[2] ?? Number(template.z || 0),
            aromatic: Boolean(template.aromatic),
        });
    }
    return atoms;
}

function buildAutoInteractionSegments(candidate, residues, frameIndex) {
    const ligandAtoms = getLigandFrameAtoms(candidate, frameIndex);
    const ligandAromatic = computeLigandAromaticDescriptor(ligandAtoms, candidate?.activeStructureModel?.bonds || []);
    const typedReady = supportsTypedInteractionClassification(candidate, residues);
    return residues
        .filter((entry) => Number.isFinite(entry.minDistanceA))
        .map((entry) => classifyPocketInteraction(entry, ligandAtoms, ligandAromatic, typedReady))
        .filter(Boolean);
}

function classifyPocketInteraction(entry, ligandAtoms, ligandAromatic, typedReady = true) {
    const hbond = typedReady ? detectHydrogenBond(entry, ligandAtoms) : null;
    if (hbond) return hbond;
    const pipi = typedReady ? detectPiPiInteraction(entry, ligandAromatic) : null;
    if (pipi) return pipi;
    const hydrophobic = typedReady ? detectHydrophobicInteraction(entry, ligandAtoms) : null;
    if (hydrophobic) return hydrophobic;
    return {
        kind: 'contact',
        label: `Contact · ${entry.label} · ${formatNumber(entry.minDistanceA, 2)}A`,
        residueLabel: entry.label,
        entryLabel: entry.label,
        residueKey: entry.key,
        residueAtoms: entry.atoms,
        tone: toneForInteractionDistance(entry.minDistanceA),
        start: entry.nearestProteinPoint,
        end: entry.nearestLigandPoint,
        distanceA: entry.minDistanceA,
    };
}

function supportsTypedInteractionClassification(candidate, residues) {
    if (candidate?.proteinReferenceAligned) return true;
    if (!candidate?.viewerProteinContextQualityGatePass) return false;
    const sampleResidue = (residues || []).find((entry) => Array.isArray(entry?.atoms) && entry.atoms.length);
    if (!sampleResidue) return false;
    return sampleResidue.atoms.some((atom) => !isBackboneAtom(atom) && !isHydrogenAtom(atom));
}

function detectHydrogenBond(entry, ligandAtoms) {
    const proteinAtoms = entry.atoms.filter((atom) => isPotentialHbondAtom(atom));
    const ligandPolarAtoms = ligandAtoms.filter((atom) => isPotentialHbondAtom(atom));
    let best = null;
    for (const proteinAtom of proteinAtoms) {
        for (const ligandAtom of ligandPolarAtoms) {
            const distanceA = distanceBetween(atomToPoint(proteinAtom), atomToPoint(ligandAtom));
            if (!Number.isFinite(distanceA) || distanceA > 3.6) continue;
            const angleScore = estimateInteractionAngleScore(proteinAtom, entry.atoms, ligandAtom, ligandAtoms);
            if (distanceA > 3.2 && angleScore < 95) continue;
            const score = distanceA - angleScore * 0.0025;
            if (!best || score < best.score) {
                best = {
                    score,
                    kind: 'hbond',
                    label: `Putative H-bond · ${entry.label} · ${formatNumber(distanceA, 2)}A`,
                    residueLabel: entry.label,
                    entryLabel: entry.label,
                    residueKey: entry.key,
                    residueAtoms: entry.atoms,
                    tone: 'good',
                    start: atomToPoint(proteinAtom),
                    end: atomToPoint(ligandAtom),
                    distanceA,
                };
            }
        }
    }
    return best;
}

function detectPiPiInteraction(entry, ligandAromatic) {
    if (!ligandAromatic) return null;
    const proteinAromatic = computeProteinAromaticDescriptor(entry);
    if (!proteinAromatic) return null;
    const centroidDistance = distanceBetween(proteinAromatic.centroid, ligandAromatic.centroid);
    if (!Number.isFinite(centroidDistance) || centroidDistance > 5.8) return null;
    const normalAlignment = Math.abs(dotVec3(proteinAromatic.normal, ligandAromatic.normal));
    if (Number.isFinite(normalAlignment) && normalAlignment < 0.55) return null;
    return {
        kind: 'pipi',
        label: `Putative Pi-Pi · ${entry.label} · ${formatNumber(centroidDistance, 2)}A`,
        residueLabel: entry.label,
        entryLabel: entry.label,
        residueKey: entry.key,
        residueAtoms: entry.atoms,
        tone: 'info',
        start: proteinAromatic.centroid,
        end: ligandAromatic.centroid,
        distanceA: centroidDistance,
    };
}

function detectHydrophobicInteraction(entry, ligandAtoms) {
    if (!isHydrophobicResidue(entry.residueName)) return null;
    const proteinAtoms = entry.atoms.filter((atom) => isHydrophobicAtom(atom));
    const ligandCarbons = ligandAtoms.filter((atom) => isHydrophobicAtom(atom));
    let best = null;
    for (const proteinAtom of proteinAtoms) {
        for (const ligandAtom of ligandCarbons) {
            const distanceA = distanceBetween(atomToPoint(proteinAtom), atomToPoint(ligandAtom));
            if (!Number.isFinite(distanceA) || distanceA > 4.6) continue;
            if (!best || distanceA < best.distanceA) {
                best = {
                    kind: 'hydrophobic',
                    label: `Hydrophobic Contact · ${entry.label} · ${formatNumber(distanceA, 2)}A`,
                    residueLabel: entry.label,
                    entryLabel: entry.label,
                    residueKey: entry.key,
                    residueAtoms: entry.atoms,
                    tone: 'warn',
                    start: atomToPoint(proteinAtom),
                    end: atomToPoint(ligandAtom),
                    distanceA,
                };
            }
        }
    }
    return best;
}

function isPotentialHbondAtom(atom) {
    const element = atomElement(atom);
    return element === 'N' || element === 'O' || element === 'S';
}

function isHydrophobicAtom(atom) {
    return atomElement(atom) === 'C';
}

function atomElement(atom) {
    const raw = String(atom?.element || atom?.atomName || '').trim();
    if (!raw) return '';
    const normalized = raw[0].toUpperCase() + raw.slice(1).toLowerCase();
    return normalized.length > 1 && ['Cl', 'Br', 'Si', 'Na', 'Ca', 'Fe', 'Zn', 'Mg'].includes(normalized)
        ? normalized
        : normalized[0];
}

function estimateInteractionAngleScore(atomA, groupA, atomB, groupB) {
    const anchorA = estimateLocalHeavyNeighbor(atomA, groupA);
    const anchorB = estimateLocalHeavyNeighbor(atomB, groupB);
    const pointA = atomToPoint(atomA);
    const pointB = atomToPoint(atomB);
    const scores = [];
    if (anchorA) scores.push(angleBetween(anchorA, pointA, pointB));
    if (anchorB) scores.push(angleBetween(pointA, pointB, anchorB));
    if (!scores.length) return 180;
    return Math.max(...scores.filter((value) => Number.isFinite(value)));
}

function estimateLocalHeavyNeighbor(atom, atoms) {
    let best = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (const candidate of atoms || []) {
        if (candidate === atom || isHydrogenAtom(candidate)) continue;
        const distanceA = distanceBetween(atomToPoint(atom), atomToPoint(candidate));
        if (!Number.isFinite(distanceA) || distanceA < 0.2 || distanceA > 1.95) continue;
        if (distanceA < bestDistance) {
            bestDistance = distanceA;
            best = atomToPoint(candidate);
        }
    }
    return best;
}

function computeProteinAromaticDescriptor(entry) {
    const residueName = String(entry?.residueName || '').toUpperCase();
    const ringAtoms = (entry?.atoms || []).filter((atom) => isAromaticProteinAtom(atom, residueName));
    if (ringAtoms.length < 3) return null;
    return {
        centroid: computeCentroid(ringAtoms.map((atom) => atomToPoint(atom))),
        normal: computePlaneNormalFromAtoms(ringAtoms),
    };
}

function computeLigandAromaticDescriptor(ligandAtoms, bonds = []) {
    const aromaticIndices = new Set();
    for (const bond of bonds || []) {
        if (bond?.aromatic) {
            aromaticIndices.add(bond.from);
            aromaticIndices.add(bond.to);
        }
    }
    const ringAtoms = ligandAtoms.filter((atom) => atom.aromatic || aromaticIndices.has(atom.sourceIndex));
    if (ringAtoms.length < 3) return null;
    return {
        centroid: computeCentroid(ringAtoms.map((atom) => atomToPoint(atom))),
        normal: computePlaneNormalFromAtoms(ringAtoms),
    };
}

function isAromaticProteinAtom(atom, residueName) {
    const aromaticMap = {
        PHE: new Set(['CG', 'CD1', 'CD2', 'CE1', 'CE2', 'CZ']),
        TYR: new Set(['CG', 'CD1', 'CD2', 'CE1', 'CE2', 'CZ']),
        TRP: new Set(['CD2', 'CE2', 'CE3', 'CZ2', 'CZ3', 'CH2']),
        HIS: new Set(['CG', 'ND1', 'CD2', 'CE1', 'NE2']),
    };
    return aromaticMap[residueName]?.has(String(atom?.atomName || '').trim().toUpperCase()) || false;
}

function isHydrophobicResidue(residueName) {
    return new Set(['ALA', 'VAL', 'LEU', 'ILE', 'MET', 'PHE', 'TRP', 'TYR', 'PRO']).has(String(residueName || '').toUpperCase());
}

function computePlaneNormalFromAtoms(atoms) {
    const points = (atoms || []).map((atom) => atomToPoint(atom)).filter((point) => isVec3Like(point));
    if (points.length < 3) return [0, 0, 1];
    const v1 = subtractVector(points[1], points[0]);
    const v2 = subtractVector(points[2], points[0]);
    return normalizeVec3(crossVec3(v1, v2));
}

function dotVec3(a, b) {
    if (!isVec3Like(a) || !isVec3Like(b)) return Number.NaN;
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function crossVec3(a, b) {
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ];
}

function normalizeVec3(v) {
    const norm = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / norm, v[1] / norm, v[2] / norm];
}

function selectProteinCaProxyPoints(trajectory, frameIndex) {
    if (!trajectory?.proteinCount || !trajectory?.proteinCoords) return [];
    const ligandPoints = getLigandFrameCoords(trajectory, frameIndex);
    const scored = [];
    for (let proteinIndex = 0; proteinIndex < trajectory.proteinCount; proteinIndex += 1) {
        const base = proteinIndex * 3;
        const point = [
            trajectory.proteinCoords[base],
            trajectory.proteinCoords[base + 1],
            trajectory.proteinCoords[base + 2],
        ];
        let minDistanceSq = Number.POSITIVE_INFINITY;
        for (const ligandPoint of ligandPoints) {
            minDistanceSq = Math.min(minDistanceSq, squaredDistance(point, ligandPoint));
        }
        scored.push({ point, minDistanceSq });
    }
    return scored
        .sort((a, b) => a.minDistanceSq - b.minDistanceSq)
        .slice(0, 64)
        .map((entry) => entry.point);
}

function buildPocketSurfacePdb(candidate, frameIndex) {
    const pocketContext = buildPocketContext(candidate, frameIndex);
    if (!pocketContext.surfaceAtoms.length) return '';
    const lines = [
        `REMARK POCKET_SURFACE ${candidate?.ligandId || 'ligand'}`,
        `REMARK POCKET_SURFACE_RESIDUES ${pocketContext.fullResidueCount}`,
    ];
    let serial = 1;
    for (const atom of pocketContext.surfaceAtoms) {
        lines.push(formatPdbAtomLine(atom, [atom.x, atom.y, atom.z], serial));
        serial += 1;
    }
    lines.push('END');
    return lines.join('\n');
}

function buildStaticFocusedScenePdb(candidate) {
    const proteinAtoms = Array.isArray(candidate?.proteinTemplateAtoms) ? candidate.proteinTemplateAtoms : [];
    const ligandAtoms = Array.isArray(candidate?.ligandTemplateAtoms) ? candidate.ligandTemplateAtoms : [];
    if (!proteinAtoms.length && !ligandAtoms.length) return '';
    const pocketContext = buildPocketContext(candidate, null);
    const selectedProteinAtoms = pocketContext.selectedAtoms.length ? pocketContext.selectedAtoms : proteinAtoms.slice(0, 240);
    const ligandCoords = getCandidateLigandCoords(candidate, null);
    const fallbackLigandAtoms = buildDefaultLigandTemplateAtoms(ligandCoords.length || ligandAtoms.length);
    const lines = [
        `REMARK STATIC_FOCUSED_SCENE ${candidate?.ligandId || 'ligand'}`,
        `REMARK VIEWER_CONTEXT static_binding_focus`,
    ];
    let serial = 1;
    for (const atom of selectedProteinAtoms) {
        lines.push(formatPdbAtomLine(normalizeProteinAtomForView(applyProteinBFactorForView(atom, candidate, null)), atomToPoint(atom), serial));
        serial += 1;
    }
    if (selectedProteinAtoms.length) lines.push('TER');
    const ligandCount = Math.max(ligandAtoms.length, ligandCoords.length);
    for (let atomIndex = 0; atomIndex < ligandCount; atomIndex += 1) {
        const atomTemplate = normalizeLigandAtomForView(ligandAtoms[atomIndex] || fallbackLigandAtoms[atomIndex] || {});
        const coords = ligandCoords[atomIndex] || atomToPoint(atomTemplate);
        lines.push(formatPdbAtomLine(atomTemplate, coords, serial, true));
        serial += 1;
    }
    lines.push('END');
    return lines.join('\n');
}

function buildFocusedSceneParts(candidate, frameIndex = null) {
    const pocketContext = buildPocketContext(candidate, frameIndex);
    const backboneAtoms = pocketContext.backboneAtoms.length
        ? pocketContext.backboneAtoms
        : (Array.isArray(candidate?.proteinTemplateAtoms) ? candidate.proteinTemplateAtoms.filter((atom) => atom.atomName === 'CA').slice(0, 64) : []);
    const contactAtoms = pocketContext.contactAtoms.length ? pocketContext.contactAtoms : [];
    const ligandAtoms = Array.isArray(candidate?.ligandTemplateAtoms) ? candidate.ligandTemplateAtoms : [];
    const ligandCoords = getCandidateLigandCoords(candidate, frameIndex);
    const fallbackLigandAtoms = buildDefaultLigandTemplateAtoms(Math.max(ligandAtoms.length, ligandCoords.length));

    const proteinBackbonePdb = backboneAtoms.length
        ? buildPdbFromAtoms(
            backboneAtoms.map((atom) => ({
                atom: normalizeProteinAtomForView(applyProteinBFactorForView(atom, candidate, frameIndex), 'P'),
                coords: atomToPoint(atom),
                hetatm: false,
            })),
            [`REMARK FOCUSED_PROTEIN_BACKBONE ${candidate?.ligandId || 'ligand'}`],
        )
        : '';

    const proteinContactPdb = contactAtoms.length
        ? buildPdbFromAtoms(
            contactAtoms.map((atom) => ({
                atom: normalizeProteinAtomForView(applyProteinBFactorForView(atom, candidate, frameIndex), 'Q'),
                coords: atomToPoint(atom),
                hetatm: false,
            })),
            [`REMARK FOCUSED_PROTEIN_CONTACTS ${candidate?.ligandId || 'ligand'}`],
        )
        : '';

    const ligandEntries = [];
    const ligandCount = Math.max(ligandAtoms.length, ligandCoords.length);
    for (let atomIndex = 0; atomIndex < ligandCount; atomIndex += 1) {
        ligandEntries.push({
            atom: normalizeLigandAtomForView(ligandAtoms[atomIndex] || fallbackLigandAtoms[atomIndex] || {}, 'L'),
            coords: ligandCoords[atomIndex] || atomToPoint(ligandAtoms[atomIndex] || fallbackLigandAtoms[atomIndex]),
            hetatm: true,
        });
    }
    const ligandPdb = Number.isFinite(frameIndex)
        ? buildTrajectoryLigandPdb(candidate, frameIndex)
        : (ligandEntries.length
            ? buildPdbFromAtoms(ligandEntries, [`REMARK FOCUSED_LIGAND ${candidate?.ligandId || 'ligand'}`])
            : '');

    return {
        proteinBackbonePdb,
        proteinContactPdb,
        ligandPdb,
        surfacePdb: buildPocketSurfacePdb(candidate, frameIndex),
    };
}

function buildTrajectoryLigandPdb(candidate, frameIndex) {
    const trajectory = candidate?.trajectoryData;
    if (!trajectory?.frameCount) return '';
    const clampedFrameIndex = clamp(frameIndex, 0, trajectory.frameCount - 1);
    if (!(candidate.ligandFramePdbCache instanceof Map)) {
        candidate.ligandFramePdbCache = new Map();
    }
    if (candidate.ligandFramePdbCache.has(clampedFrameIndex)) {
        return candidate.ligandFramePdbCache.get(clampedFrameIndex);
    }
    const ligandAtoms = Array.isArray(candidate?.ligandTemplateAtoms) ? candidate.ligandTemplateAtoms : [];
    const ligandCoords = getCandidateLigandCoords(candidate, clampedFrameIndex);
    const fallbackLigandAtoms = buildDefaultLigandTemplateAtoms(Math.max(ligandAtoms.length, ligandCoords.length));
    const ligandEntries = [];
    const ligandCount = Math.max(ligandAtoms.length, ligandCoords.length);
    for (let atomIndex = 0; atomIndex < ligandCount; atomIndex += 1) {
        ligandEntries.push({
            atom: normalizeLigandAtomForView(ligandAtoms[atomIndex] || fallbackLigandAtoms[atomIndex] || {}, 'L'),
            coords: ligandCoords[atomIndex] || atomToPoint(ligandAtoms[atomIndex] || fallbackLigandAtoms[atomIndex]),
            hetatm: true,
        });
    }
    const ligandPdb = ligandEntries.length
        ? buildPdbFromAtoms(ligandEntries, [`REMARK FOCUSED_LIGAND ${candidate?.ligandId || 'ligand'}`, `REMARK TRAJECTORY_FRAME ${clampedFrameIndex}`])
        : '';
    candidate.ligandFramePdbCache.set(clampedFrameIndex, ligandPdb);
    if (candidate.ligandFramePdbCache.size > 24) {
        const firstKey = candidate.ligandFramePdbCache.keys().next().value;
        candidate.ligandFramePdbCache.delete(firstKey);
    }
    return ligandPdb;
}

function buildPdbFromAtoms(entries, remarks = []) {
    if (!Array.isArray(entries) || !entries.length) return '';
    const lines = [...remarks];
    let serial = 1;
    for (const entry of entries) {
        lines.push(formatPdbAtomLine(entry.atom, entry.coords, serial, Boolean(entry.hetatm)));
        serial += 1;
    }
    lines.push('END');
    return lines.join('\n');
}

function computeBindingFocusSphere(candidate, frameIndex = null, { tight = false } = {}) {
    if (!candidate) return null;
    const ligandPoints = getCandidateLigandCoords(candidate, frameIndex);
    if (!ligandPoints.length) return null;
    const pocketContext = buildPocketContext(candidate, frameIndex);
    const supportEntries = (pocketContext.contactResidues.length ? pocketContext.contactResidues : pocketContext.residues)
        .slice(0, tight ? 2 : 4);
    const supportPoints = ligandPoints.concat(
        supportEntries
            .map((entry) => tight ? entry.nearestProteinPoint : (entry.nearestProteinPoint || entry.representativePoint))
            .filter((point) => isVec3Like(point)),
    );
    const center = tight ? computeCentroid(ligandPoints) : computeCentroid(supportPoints);
    let radius = 0;
    for (const point of supportPoints) {
        radius = Math.max(radius, distanceBetween(point, center));
    }
    const ligandRadius = ligandPoints.reduce(
        (maxRadius, point) => Math.max(maxRadius, distanceBetween(point, center)),
        0,
    );
    const nearestContactDistance = supportEntries.length
        ? supportEntries.reduce((minDistance, entry) => {
            const point = entry.nearestProteinPoint || entry.representativePoint;
            return isVec3Like(point)
                ? Math.min(minDistance, distanceBetween(point, center))
                : minDistance;
        }, Number.POSITIVE_INFINITY)
        : Number.POSITIVE_INFINITY;
    return {
        center,
        radius: tight
            ? Math.max(
                1.65,
                ligandRadius + 0.8,
                Number.isFinite(nearestContactDistance) ? nearestContactDistance * 0.52 : 0,
            )
            : Math.max(2.6, radius + 0.95),
    };
}

function normalizeProteinAtomForView(atom, chainId = 'P') {
    return {
        ...atom,
        chainId,
        residueName: (atom?.residueName || 'PRT').slice(0, 3),
    };
}

function proteinResidueKey(atom) {
    return [
        atom?.chainId || '_',
        atom?.residueSeq || '',
        atom?.insertionCode || '',
        atom?.residueName || 'UNK',
    ].join(':');
}

function buildProteinResidueBFactorLookup(candidate, frameIndex = null) {
    if (!candidate) return null;
    if (!Number.isFinite(frameIndex) && candidate.proteinResidueBFactorLookup instanceof Map) return candidate.proteinResidueBFactorLookup;
    const values = Array.isArray(candidate?.trajectoryData?.proteinResidueBFactors)
        ? candidate.trajectoryData.proteinResidueBFactors
        : [];
    const proteinAtoms = Array.isArray(candidate?.proteinTemplateAtoms) ? candidate.proteinTemplateAtoms : [];
    if (!values.length || !proteinAtoms.length) return null;
    const groups = getProteinResidueGroups(candidate, proteinAtoms);
    const lookup = new Map();
    const centroidsPayload = candidate?.trajectoryData?.proteinResidueCentroids;
    const centroidReady = centroidsPayload?.data && Array.isArray(centroidsPayload.shape) && centroidsPayload.shape.length === 3;
    const proteinCount = groups.length;
    groups.forEach((group, index) => {
        let value = values[index];
        if (centroidReady && Number.isFinite(frameIndex) && index < proteinCount) {
            const currentOffset = ((frameIndex * proteinCount) + index) * 3;
            const baselineOffset = index * 3;
            const current = [
                centroidsPayload.data[currentOffset],
                centroidsPayload.data[currentOffset + 1],
                centroidsPayload.data[currentOffset + 2],
            ];
            const baseline = [
                centroidsPayload.data[baselineOffset],
                centroidsPayload.data[baselineOffset + 1],
                centroidsPayload.data[baselineOffset + 2],
            ];
            const displacement = distanceBetween(current, baseline);
            if (Number.isFinite(displacement)) {
                value = value + Math.min(35, displacement * 18);
            }
        }
        if (Number.isFinite(value)) lookup.set(group.key, value);
    });
    if (!Number.isFinite(frameIndex)) {
        candidate.proteinResidueBFactorLookup = lookup;
    }
    return lookup;
}

function applyProteinBFactorForView(atom, candidate, frameIndex = null) {
    if (!atom || !candidate) return atom;
    const lookup = buildProteinResidueBFactorLookup(candidate, frameIndex);
    if (!lookup) return atom;
    const key = proteinResidueKey(atom);
    const bFactor = lookup.get(key);
    return Number.isFinite(bFactor) ? { ...atom, bFactor } : atom;
}

function normalizeLigandAtomForView(atom, chainId = 'L') {
    return {
        ...atom,
        record: 'HETATM',
        chainId,
        residueName: 'LIG',
        residueSeq: '1',
    };
}

function atomToPoint(atom) {
    if (!atom) return [0, 0, 0];
    return [Number(atom.x || 0), Number(atom.y || 0), Number(atom.z || 0)];
}

function isHydrogenAtom(atom) {
    const element = String(atom?.element || atom?.atomName || '').trim().toUpperCase();
    return element === 'H' || element.startsWith('H');
}

function isBackboneAtom(atom) {
    const atomName = String(atom?.atomName || '').trim().toUpperCase();
    return atomName === 'N' || atomName === 'CA' || atomName === 'C' || atomName === 'O';
}

function toneForInteractionDistance(distanceA) {
    if (distanceA <= 3.2) return 'good';
    if (distanceA <= 4.2) return 'warn';
    return 'bad';
}

async function ensureTrajectoryData(candidate) {
    if (!candidate?.trajectoryPath) {
        candidate.trajectoryState = 'trajectory_not_reported';
        return null;
    }
    if (candidate.trajectoryData) return candidate.trajectoryData;
    if (candidate.trajectoryState === 'loading') return null;

    candidate.trajectoryState = 'loading';
    try {
        const arrayBuffer = await fetchArrayBuffer(candidate.trajectoryPath);
        const payload = await parseTrajectoryNpz(arrayBuffer);
        candidate.trajectoryData = payload;
        candidate.pocketContextCache = null;
        candidate.proteinFrameAtomCache = new Map();
        candidate.proteinFrameCoordCache = new Map();
        candidate.framePdbCache = new Map();
        candidate.ligandFramePdbCache = new Map();
        candidate.lastRenderedTrajectoryFrame = -1;
        candidate.trajectoryState = 'trajectory_ready';
        return payload;
    } catch (error) {
        console.error(error);
        candidate.trajectoryError = error.message;
        candidate.trajectoryState = 'trajectory_error';
        return null;
    }
}

async function parseTrajectoryNpz(arrayBuffer) {
    if (!window.JSZip) {
        throw new Error('JSZip is not available');
    }
    const zip = await window.JSZip.loadAsync(arrayBuffer);
    const npyEntries = {};
    const parsedEntries = {};
    for (const [name, entry] of Object.entries(zip.files)) {
        if (!name.endsWith('.npy')) continue;
        npyEntries[name] = await entry.async('arraybuffer');
        const key = name.replace(/\.npy$/i, '').split('/').pop();
        parsedEntries[key] = parseNpyArray(npyEntries[name]);
    }

    const protein = parsedEntries.protein_ca;
    const ligand = parsedEntries.ligand_frames;
    const indices = parsedEntries.frame_indices;
    if (!protein || !ligand) {
        throw new Error('trajectory npz is missing protein_ca or ligand_frames');
    }

    const extraMetrics = collectTrajectoryExtraMetrics(parsedEntries, ligand.shape[0] || 0);
    const proteinResidueSchema = extractProteinResidueSchema(parsedEntries, protein.shape[0] || 0, ligand.shape[0] || 0);
    return buildTrajectoryFrameSeries(protein, ligand, indices, extraMetrics, proteinResidueSchema);
}

function parseNpyArray(buffer) {
    if (!buffer) return null;
    const view = new DataView(buffer);
    const magic = String.fromCharCode(...new Uint8Array(buffer.slice(0, 6)));
    if (magic !== '\x93NUMPY') {
        throw new Error('unsupported npy magic header');
    }

    const major = view.getUint8(6);
    let offset = 8;
    let headerLength = 0;
    if (major === 1) {
        headerLength = view.getUint16(offset, true);
        offset += 2;
    } else if (major === 2 || major === 3) {
        headerLength = view.getUint32(offset, true);
        offset += 4;
    } else {
        throw new Error(`unsupported npy version: ${major}`);
    }

    const headerText = new TextDecoder('latin1').decode(buffer.slice(offset, offset + headerLength));
    offset += headerLength;
    const descrMatch = headerText.match(/'descr':\s*'([^']+)'/);
    const shapeMatch = headerText.match(/'shape':\s*\(([^)]*)\)/);
    const fortranMatch = headerText.match(/'fortran_order':\s*(True|False)/);
    if (!descrMatch || !shapeMatch) {
        throw new Error('could not parse npy header');
    }
    if (fortranMatch?.[1] === 'True') {
        throw new Error('fortran-order arrays are not supported');
    }

    const descr = descrMatch[1];
    const shape = shapeMatch[1]
        .split(',')
        .map((part) => part.trim())
        .filter(Boolean)
        .map((part) => parseInt(part, 10));

    let data;
    if (descr === '<f4' || descr === '|f4') {
        data = new Float32Array(buffer, offset);
    } else if (descr === '<i4' || descr === '|i4') {
        data = new Int32Array(buffer, offset);
    } else if (descr === '<u4' || descr === '|u4') {
        data = new Uint32Array(buffer, offset);
    } else if (descr === '|u1' || descr === '<u1') {
        data = new Uint8Array(buffer, offset);
    } else {
        throw new Error(`unsupported npy dtype: ${descr}`);
    }

    return { descr, shape, data };
}

function buildTrajectoryFrameSeries(protein, ligand, indices, extraMetrics = null, proteinResidueSchema = null) {
    const proteinData = protein.data;
    const ligandData = ligand.data;
    const proteinCount = protein.shape[0] || 0;
    const frameCount = ligand.shape[0] || 0;
    const ligandAtomCount = ligand.shape[1] || 0;
    const frameIndices = indices?.data ? Array.from(indices.data) : Array.from({ length: frameCount }, (_, i) => i);
    const proteinContextMeaningful = isMeaningfulProteinContext(proteinData, proteinCount);

    const frames = [];
    let firstCentroid = null;
    for (let frameIndex = 0; frameIndex < frameCount; frameIndex += 1) {
        let minDistanceSq = Number.POSITIVE_INFINITY;
        let cx = 0;
        let cy = 0;
        let cz = 0;
        for (let atomIndex = 0; atomIndex < ligandAtomCount; atomIndex += 1) {
            const base = frameIndex * ligandAtomCount * 3 + atomIndex * 3;
            const lx = ligandData[base];
            const ly = ligandData[base + 1];
            const lz = ligandData[base + 2];
            cx += lx;
            cy += ly;
            cz += lz;

            if (proteinContextMeaningful) {
                for (let proteinIndex = 0; proteinIndex < proteinCount; proteinIndex += 1) {
                    const pBase = proteinIndex * 3;
                    const dx = lx - proteinData[pBase];
                    const dy = ly - proteinData[pBase + 1];
                    const dz = lz - proteinData[pBase + 2];
                    const distSq = dx * dx + dy * dy + dz * dz;
                    if (distSq < minDistanceSq) minDistanceSq = distSq;
                }
            }
        }

        const centroid = ligandAtomCount
            ? [cx / ligandAtomCount, cy / ligandAtomCount, cz / ligandAtomCount]
            : [0, 0, 0];
        if (!firstCentroid) firstCentroid = centroid;
        const dx0 = centroid[0] - firstCentroid[0];
        const dy0 = centroid[1] - firstCentroid[1];
        const dz0 = centroid[2] - firstCentroid[2];
        frames.push({
            frameIndex,
            trajectoryIndex: frameIndices[frameIndex] ?? frameIndex,
            minDistanceA: proteinContextMeaningful ? Math.sqrt(minDistanceSq) : Number.NaN,
            centroid,
            centroidShiftA: Math.sqrt(dx0 * dx0 + dy0 * dy0 + dz0 * dz0),
            extraMetrics: buildFrameExtraMetricSnapshot(extraMetrics?.series || {}, frameIndex),
        });
    }

    return {
        frameCount,
        ligandAtomCount,
        proteinCount,
        proteinContextMeaningful,
        frameIndices,
        proteinCoords: proteinData,
        ligandCoords: ligandData,
        frames,
        extraSeries: extraMetrics?.series || {},
        extraScalars: extraMetrics?.scalars || {},
        extraMetricLabels: extraMetrics?.labels || {},
        proteinResidueRmsf: proteinResidueSchema?.rmsf || [],
        proteinResidueBFactors: proteinResidueSchema?.bFactors || [],
        proteinResidueCentroids: proteinResidueSchema?.centroids || null,
        proteinResidueSchemaReady: Boolean(proteinResidueSchema?.ready),
        proteinResidueSchemaVersion: proteinResidueSchema?.version || '',
        proteinAtomFrames: proteinResidueSchema?.atomFrames || null,
        proteinAtomTemplateIndex: proteinResidueSchema?.atomTemplateIndex || [],
        proteinAtomSchemaReady: Boolean(proteinResidueSchema?.atomReady),
        proteinAtomSchemaVersion: proteinResidueSchema?.atomVersion || '',
    };
}

function collectTrajectoryExtraMetrics(parsedEntries, frameCount) {
    const reserved = new Set([
        'protein_ca',
        'ligand_frames',
        'frame_indices',
        'protein_residue_rmsf',
        'protein_residue_bfactor',
        'protein_residue_bfactor_equivalent',
        'protein_residue_centroids',
        'protein_residue_schema_version',
        'protein_atom_frames',
        'protein_atom_template_index',
        'protein_atom_schema_version',
    ]);
    const series = {};
    const scalars = {};
    const labels = {};

    for (const [key, payload] of Object.entries(parsedEntries || {})) {
        if (reserved.has(key) || !payload?.data) continue;
        const normalizedKey = normalizeTrajectoryMetricKey(key);
        const label = formatTrajectoryMetricLabel(normalizedKey);
        const values = flattenNpyValues(payload);
        if (!values.length) continue;
        if (frameCount && values.length === frameCount) {
            series[normalizedKey] = values;
            labels[normalizedKey] = label;
        } else if (values.length === 1) {
            scalars[normalizedKey] = values[0];
            labels[normalizedKey] = label;
        }
    }

    return { series, scalars, labels };
}

function extractProteinResidueSchema(parsedEntries, proteinCount, frameCount) {
    const rmsf = flattenNpyValues(parsedEntries?.protein_residue_rmsf).slice(0, proteinCount);
    const bFactors = flattenNpyValues(
        parsedEntries?.protein_residue_bfactor_equivalent || parsedEntries?.protein_residue_bfactor,
    ).slice(0, proteinCount);
    const centroidsPayload = parsedEntries?.protein_residue_centroids;
    const centroids = (
        centroidsPayload?.data &&
        Array.isArray(centroidsPayload.shape) &&
        centroidsPayload.shape.length === 3 &&
        centroidsPayload.shape[0] === frameCount &&
        centroidsPayload.shape[1] === proteinCount &&
        centroidsPayload.shape[2] === 3
    )
        ? centroidsPayload
        : null;
    const versionValue = flattenNpyValues(parsedEntries?.protein_residue_schema_version)?.[0];
    const atomFramesPayload = parsedEntries?.protein_atom_frames;
    const atomFrames = (
        atomFramesPayload?.data &&
        Array.isArray(atomFramesPayload.shape) &&
        atomFramesPayload.shape.length === 3 &&
        atomFramesPayload.shape[0] === frameCount &&
        atomFramesPayload.shape[2] === 3
    )
        ? atomFramesPayload
        : null;
    const atomTemplateIndex = flattenNpyValues(parsedEntries?.protein_atom_template_index);
    const atomVersionValue = flattenNpyValues(parsedEntries?.protein_atom_schema_version)?.[0];
    const ready = Boolean(rmsf.length || bFactors.length || centroids);
    return {
        ready,
        version: ready ? `protein_residue_rmsf_contract_v1${Number.isFinite(versionValue) ? `.${Math.trunc(versionValue)}` : ''}` : '',
        rmsf,
        bFactors: bFactors.length ? bFactors : rmsf,
        centroids,
        atomReady: Boolean(atomFrames),
        atomVersion: atomFrames ? `protein_atom_frames_contract_v1${Number.isFinite(atomVersionValue) ? `.${Math.trunc(atomVersionValue)}` : ''}` : '',
        atomFrames,
        atomTemplateIndex,
    };
}

function flattenNpyValues(payload) {
    if (!payload?.data) return [];
    const raw = Array.from(payload.data).map((value) => Number(value));
    if (!raw.length) return [];
    if (payload.shape?.length === 2 && payload.shape[1] === 1) {
        return raw;
    }
    return raw;
}

function normalizeTrajectoryMetricKey(key) {
    return String(key || '')
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '');
}

function formatTrajectoryMetricLabel(key) {
    const labels = {
        radius_of_gyration: 'Radius of Gyration',
        rg: 'Radius of Gyration',
        rmsd: 'Ligand RMSD',
        sasa_proxy: 'SASA Proxy',
        hbond_count: 'H-Bond Count',
        contact_occupancy: 'Contact Occupancy',
        energy_std: 'Energy Std',
        binding_energy: 'Binding Energy',
        energy_proxy: 'Energy Proxy',
    };
    return labels[key] || String(key || '')
        .split('_')
        .filter(Boolean)
        .map((token) => token[0].toUpperCase() + token.slice(1))
        .join(' ');
}

function buildFrameExtraMetricSnapshot(seriesMap, frameIndex) {
    const snapshot = {};
    for (const [key, values] of Object.entries(seriesMap || {})) {
        if (!Array.isArray(values) || !Number.isFinite(frameIndex) || frameIndex < 0 || frameIndex >= values.length) continue;
        snapshot[key] = values[frameIndex];
    }
    return snapshot;
}

function renderTrajectoryCharts(candidate) {
    const trajectory = candidate?.trajectoryData;
    if (!trajectory?.frameCount) return;

    const x = trajectory.frames.map((frame) => frame.frameIndex + 1);
    const distanceTrace = [{
        type: 'scatter',
        mode: 'lines',
        name: 'min_distance_A',
        x,
        y: trajectory.frames.map((frame) => frame.minDistanceA),
        line: { color: '#0ea5e9', width: 2.2 },
    }];

    const displacementTrace = [{
        type: 'scatter',
        mode: 'lines',
        name: 'centroid_shift_A',
        x,
        y: trajectory.frames.map((frame) => frame.centroidShiftA),
        line: { color: '#f97316', width: 2.2 },
    }];

    const currentFrame = clamp(state.trajectoryFrameIndex, 0, trajectory.frameCount - 1) + 1;
    const shape = {
        type: 'line',
        x0: currentFrame,
        x1: currentFrame,
        y0: 0,
        y1: 1,
        xref: 'x',
        yref: 'paper',
        line: { color: '#ef4444', width: 2, dash: 'dot' },
    };

    Plotly.newPlot('chartTrajectoryDistance', distanceTrace, {
        title: 'Trajectory Min Distance',
        margin: { t: 42, r: 18, b: 42, l: 52 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        xaxis: { title: 'Frame' },
        yaxis: { title: 'Min Distance (A)' },
        shapes: [shape],
    }, { responsive: true, displaylogo: false });

    Plotly.newPlot('chartTrajectoryDisplacement', displacementTrace, {
        title: 'Ligand Centroid Shift',
        margin: { t: 42, r: 18, b: 42, l: 52 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        xaxis: { title: 'Frame' },
        yaxis: { title: 'Centroid Shift (A)' },
        shapes: [shape],
    }, { responsive: true, displaylogo: false });

    if (hasTrajectoryExtraSeries(candidate) && document.getElementById('chartTrajectoryAux')) {
        const extraTraces = Object.entries(trajectory.extraSeries || {}).map(([key, values], idx) => ({
            type: 'scatter',
            mode: 'lines',
            name: trajectory.extraMetricLabels?.[key] || formatTrajectoryMetricLabel(key),
            x,
            y: values,
            line: { width: 2, color: ['#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4'][idx % 5] },
        }));
        Plotly.newPlot('chartTrajectoryAux', extraTraces, {
            title: 'Trajectory Auxiliary Metrics',
            margin: { t: 42, r: 18, b: 42, l: 52 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            xaxis: { title: 'Frame' },
            yaxis: { title: 'Metric Value' },
            shapes: [shape],
            legend: { orientation: 'h' },
        }, { responsive: true, displaylogo: false });
    }
}

function updateTrajectoryChartCursor(candidate) {
    const trajectory = candidate?.trajectoryData;
    if (!trajectory?.frameCount) return;
    const currentFrame = clamp(state.trajectoryFrameIndex, 0, trajectory.frameCount - 1) + 1;
    const layoutUpdate = {
        shapes: [{
            type: 'line',
            x0: currentFrame,
            x1: currentFrame,
            y0: 0,
            y1: 1,
            xref: 'x',
            yref: 'paper',
            line: { color: '#ef4444', width: 2, dash: 'dot' },
        }],
    };

    if (document.getElementById('chartTrajectoryDistance')) {
        Plotly.relayout('chartTrajectoryDistance', layoutUpdate);
    }
    if (document.getElementById('chartTrajectoryDisplacement')) {
        Plotly.relayout('chartTrajectoryDisplacement', layoutUpdate);
    }
    if (document.getElementById('chartTrajectoryAux')) {
        Plotly.relayout('chartTrajectoryAux', layoutUpdate);
    }
}

function hasTrajectoryExtraSeries(candidate) {
    return Boolean(candidate?.trajectoryData?.extraSeries && Object.keys(candidate.trajectoryData.extraSeries).length);
}

function onTrajectorySliderInput() {
    const candidate = getSelectedCandidate();
    if (candidate?.trajectoryData?.frameCount) {
        state.trajectorySceneMode = 'trajectory';
        state.trajectoryFrameIndex = clamp(Number(dom.trajSlider.value), 0, candidate.trajectoryData.frameCount - 1);
        syncTrajectoryUi();
        renderBindingInfo(candidate);
        renderQuickStats(candidate);
        persistViewerSession({ badgeText: 'session: frame updated' });
        return;
    }

    if (!Number.isFinite(dom.videoPreview.duration) || dom.videoPreview.duration <= 0) return;
    const ratio = Number(dom.trajSlider.value) / Number(dom.trajSlider.max || 1);
    dom.videoPreview.currentTime = Math.max(0, ratio * dom.videoPreview.duration);
}

function handleVideoTimeUpdate() {
    const candidate = getSelectedCandidate();
    if (candidate?.trajectoryData?.frameCount) return;
    syncTrajectoryUi();
}

function startTrajectoryPlayback() {
    stopTrajectoryPlayback();
    const candidate = getSelectedCandidate();
    if (candidate?.trajectoryData?.frameCount) {
        state.trajectorySceneMode = 'trajectory';
        state.lastPlaybackPanelRefreshAt = 0;
        const speed = Number(dom.trajSpeed.value || 1);
        const intervalMs = Math.max(30, 140 / speed);
        state.trajectoryTimer = window.setInterval(() => {
            if (!candidate.trajectoryData) return;
            const next = state.trajectoryFrameIndex + 1;
            if (next >= candidate.trajectoryData.frameCount) {
                stopTrajectoryPlayback();
                return;
            }
            state.trajectoryFrameIndex = next;
            syncTrajectoryUi();
            refreshPlaybackPanelsMaybe(candidate, next >= candidate.trajectoryData.frameCount - 1);
        }, intervalMs);
        if (dom.videoPreview.style.display !== 'none') {
            dom.videoPreview.play().catch(() => {});
        }
        return;
    }

    if (dom.videoPreview.style.display !== 'none') {
        dom.videoPreview.play().catch(() => {});
    }
}

function stopTrajectoryPlayback() {
    if (state.trajectoryTimer) {
        window.clearInterval(state.trajectoryTimer);
        state.trajectoryTimer = null;
    }
    if (dom.videoPreview.style.display !== 'none') {
        dom.videoPreview.pause();
    }
    state.lastPlaybackPanelRefreshAt = 0;
    persistViewerSession({ badgeText: 'session: playback stopped' });
}

function refreshPlaybackPanelsMaybe(candidate, force = false) {
    const now = performance.now();
    if (!force && now - state.lastPlaybackPanelRefreshAt < 140) return;
    state.lastPlaybackPanelRefreshAt = now;
    renderBindingInfo(candidate);
    renderQuickStats(candidate);
}

function syncVideoToTrajectoryFrame(trajectory, frameIndex) {
    if (dom.videoPreview.style.display === 'none') return;
    if (!Number.isFinite(dom.videoPreview.duration) || dom.videoPreview.duration <= 0) return;
    const ratio = trajectory.frameCount <= 1 ? 0 : frameIndex / (trajectory.frameCount - 1);
    const nextTime = ratio * dom.videoPreview.duration;
    if (Math.abs(dom.videoPreview.currentTime - nextTime) > 0.08) {
        dom.videoPreview.currentTime = nextTime;
    }
    dom.videoPreview.playbackRate = Number(dom.trajSpeed.value || 1);
}

function resolveLocalFile(pathLike) {
    const raw = String(pathLike || '').replace(/\\/g, '/');
    if (!raw) return null;

    if (state.localFilesByPath.has(raw)) return state.localFilesByPath.get(raw);
    const basename = basenameOf(raw);
    if (state.localFilesByBasename.has(basename)) return state.localFilesByBasename.get(basename);
    return null;
}

async function resolveFirstReadablePath(pathCandidates) {
    const queue = uniqueTruthy(pathCandidates);
    for (const pathLike of queue) {
        try {
            await fetchText(pathLike);
            return pathLike;
        } catch (_error) {
            // try next candidate
        }
    }
    return '';
}

function resolveAssetUrl(pathLike) {
    return resolveAssetUrlCandidates(pathLike)[0] || '';
}

function resolveAssetUrlCandidates(pathLike) {
    const local = resolveLocalFile(pathLike);
    if (local) return [local.objectUrl];

    const raw = String(pathLike || '').trim();
    if (!raw) return [];
    if (/^(https?:|blob:|data:)/i.test(raw)) return [raw];

    const normalized = raw.replace(/\\/g, '/');
    const candidates = [];
    const protocol = window.location?.protocol || 'http:';
    const addCandidate = (value) => {
        if (value && !candidates.includes(value)) candidates.push(value);
    };
    const repoMarkers = ['/runs/', '/viewer/', '/data/', '/docs/'];
    for (const marker of repoMarkers) {
        const idx = normalized.indexOf(marker);
        if (idx >= 0) {
            const repoPath = normalized.slice(idx);
            if (protocol === 'file:') {
                addCandidate(`..${repoPath}`);
                addCandidate(`.${repoPath}`);
            } else {
                addCandidate(repoPath);
                addCandidate(`..${repoPath}`);
            }
            return candidates;
        }
    }

    if (normalized.startsWith('../') || normalized.startsWith('./')) {
        addCandidate(normalized);
        if (normalized.startsWith('../runs/')) {
            const repoPath = `/${normalized.slice('../'.length)}`;
            if (protocol !== 'file:') addCandidate(repoPath);
            else {
                addCandidate(`..${repoPath}`);
                addCandidate(`.${repoPath}`);
            }
        }
        if (normalized.startsWith('./runs/')) {
            const repoPath = `/${normalized.slice('./'.length)}`;
            if (protocol !== 'file:') addCandidate(repoPath);
            else {
                addCandidate(`..${repoPath}`);
                addCandidate(`.${repoPath}`);
            }
        }
        return candidates;
    }
    if (normalized.startsWith('/')) {
        if (protocol === 'file:') {
            addCandidate(`..${normalized}`);
            addCandidate(`.${normalized}`);
        }
        addCandidate(normalized);
        return candidates;
    }
    if (normalized.startsWith('runs/') || normalized.startsWith('viewer/') || normalized.startsWith('data/') || normalized.startsWith('docs/')) {
        addCandidate(`./${normalized}`);
        addCandidate(`../${normalized}`);
        addCandidate(`/${normalized}`);
        return candidates;
    }
    addCandidate(normalized);
    return candidates;
}

function inferStructureFormat(pathLike) {
    const lower = String(pathLike || '').toLowerCase();
    if (lower.endsWith('.cif') || lower.endsWith('.mmcif')) return 'mmcif';
    if (lower.endsWith('.sdf') || lower.endsWith('.sd')) return 'sdf';
    if (lower.endsWith('.mol2')) return 'mol2';
    return 'pdb';
}

function buildLoadOptions() {
    const theme = mapColorTheme(dom.colorSelect.value);
    const representation = mapRepresentation(dom.reprSelect.value);
    return buildLoadOptionsForPreset({ theme, representation });
}

function buildLoadOptionsForPreset({ theme = mapColorTheme(dom.colorSelect.value), representation = mapRepresentation(dom.reprSelect.value) } = {}) {
    return {
        representationParams: {
            type: { name: representation },
            theme: { globalName: theme },
        },
    };
}

function focusedProteinTheme() {
    return dom.colorSelect?.value === 'bfactor' ? 'uncertainty' : 'chain-id';
}

function focusedSurfaceTheme() {
    return dom.colorSelect?.value === 'bfactor' ? 'uncertainty' : 'hydrophobicity';
}

function shouldDynamicProteinFrameRefresh(candidate) {
    return Boolean(
        candidate?.trajectoryData?.proteinResidueSchemaReady
        && dom.colorSelect?.value === 'bfactor',
    );
}

function ensureTrajectoryRenderStats(candidate) {
    if (!candidate) return null;
    if (!candidate.trajectoryRenderStats) {
        candidate.trajectoryRenderStats = {
            lastMode: 'not_run',
            lastFrameMs: Number.NaN,
            totalFrames: 0,
            fastPathHits: 0,
            fullReloads: 0,
            proteinFrameRefreshes: 0,
            inPlaceHits: 0,
            ligandReloadHits: 0,
            reloadOnlyHits: 0,
            coalescedFrameCount: 0,
            fastPathMissCount: 0,
            lastFastPathMissReason: 'not_run',
            missReasonCounts: {},
            lastProteinColorMode: 'static',
        };
    }
    return candidate.trajectoryRenderStats;
}

function recordTrajectoryRenderStats(candidate, details = {}) {
    const stats = ensureTrajectoryRenderStats(candidate);
    if (!stats) return;
    stats.lastMode = details.mode || stats.lastMode || 'not_run';
    stats.lastFrameMs = Number.isFinite(details.elapsedMs) ? details.elapsedMs : stats.lastFrameMs;
    stats.totalFrames += 1;
    if (details.fastPath) stats.fastPathHits += 1;
    if (details.mode === 'full_scene_reload') stats.fullReloads += 1;
    if (details.mode === 'in_place_atomic_conformation') stats.inPlaceHits += 1;
    if (details.mode === 'ligand_structure_reload') stats.ligandReloadHits += 1;
    if (details.mode === 'reload_only_locked') stats.reloadOnlyHits += 1;
    if (details.proteinFrameRefresh) stats.proteinFrameRefreshes += 1;
    if (details.proteinColorMode) stats.lastProteinColorMode = details.proteinColorMode;
    if (details.coalescedFrameCountDelta) stats.coalescedFrameCount += details.coalescedFrameCountDelta;
    if (details.fastPathMissReason && details.fastPathMissReason !== 'none') {
        stats.fastPathMissCount += 1;
        stats.lastFastPathMissReason = details.fastPathMissReason;
        stats.missReasonCounts[details.fastPathMissReason] = (stats.missReasonCounts[details.fastPathMissReason] || 0) + 1;
    }
}

function describeTrajectoryRenderMode(candidate) {
    const stats = candidate?.trajectoryRenderStats;
    if (!stats?.lastMode || stats.lastMode === 'not_run') return 'pending';
    const modeMap = {
        in_place_atomic_conformation: 'in-place',
        ligand_structure_reload: 'ligand reload',
        reload_only_locked: 'reload-only',
        full_scene_reload: 'full reload',
    };
    const label = modeMap[stats.lastMode] || stats.lastMode;
    const ms = Number.isFinite(stats.lastFrameMs) ? `${formatNumber(stats.lastFrameMs, 1)}ms` : 'n/a';
    return `${label} · ${ms}`;
}

function describeFastPathMissReason(candidate) {
    const stats = candidate?.trajectoryRenderStats;
    if (!stats?.lastFastPathMissReason || stats.lastFastPathMissReason === 'not_run') return 'pending';
    const mapping = {
        none: 'none',
        no_cache: 'no cache',
        candidate_switch: 'candidate switch',
        signature_mismatch: 'signature mismatch',
        viewer_mode: 'viewer mode',
        duplicate_frame: 'duplicate frame',
    };
    return mapping[stats.lastFastPathMissReason] || stats.lastFastPathMissReason;
}

function describeProteinFrameColorMode(candidate) {
    const stats = candidate?.trajectoryRenderStats;
    if (shouldDynamicProteinFrameRefresh(candidate)) {
        return stats?.lastProteinColorMode === 'dynamic_bfactor_reload' ? 'dynamic bfactor' : 'bfactor pending';
    }
    return dom.colorSelect?.value === 'bfactor' ? 'static bfactor' : 'static';
}

function describeProteinTrajectorySchemaLabel(candidate) {
    const trajectory = candidate?.trajectoryData;
    if (!trajectory) return 'trajectory not loaded';
    const atomState = getProteinAtomFrameEligibility(candidate);
    const atomReady = Boolean(trajectory.proteinAtomSchemaReady);
    const hasCentroids = Boolean(trajectory.proteinResidueCentroids?.data);
    const hasBFactors = Array.isArray(trajectory.proteinResidueBFactors) && trajectory.proteinResidueBFactors.length > 0;
    const hasRmsf = Array.isArray(trajectory.proteinResidueRmsf) && trajectory.proteinResidueRmsf.length > 0;
    if (atomState.eligible && hasCentroids && hasBFactors) return 'full motion + frame-aware color';
    if (atomState.eligible) return 'full motion ready';
    if (atomReady) return 'full motion schema partial';
    if (hasCentroids && hasBFactors) return 'frame-aware ready';
    if (hasCentroids && hasRmsf) return 'frame-aware rmsf';
    if (hasBFactors) return 'static bfactor only';
    if (hasRmsf) return 'static rmsf only';
    if (trajectory.proteinResidueSchemaReady) return 'schema partial';
    return 'schema missing';
}

function describeProteinTrajectorySchemaPrerequisites(candidate) {
    const trajectory = candidate?.trajectoryData;
    const atomState = getProteinAtomFrameEligibility(candidate);
    if (!trajectory) {
        return 'Needs NPZ trajectory plus protein_ca anchors. For frame-aware protein overlays add protein_residue_centroids[T,P,3] with protein_residue_bfactor(_equivalent)|protein_residue_rmsf and protein_residue_schema_version. For full protein frame mutation add protein_atom_frames[T,A,3] with protein_atom_template_index[A] and protein_atom_schema_version.';
    }
    const missing = [];
    if (!trajectory.proteinResidueSchemaReady) {
        missing.push('protein_residue_schema');
    }
    if (!trajectory.proteinResidueCentroids?.data) {
        missing.push('protein_residue_centroids[T,P,3]');
    }
    const hasBFactors = Array.isArray(trajectory.proteinResidueBFactors) && trajectory.proteinResidueBFactors.length > 0;
    const hasRmsf = Array.isArray(trajectory.proteinResidueRmsf) && trajectory.proteinResidueRmsf.length > 0;
    if (!hasBFactors && !hasRmsf) {
        missing.push('protein_residue_bfactor(_equivalent)|protein_residue_rmsf');
    }
    if (!trajectory.proteinResidueSchemaVersion) {
        missing.push('protein_residue_schema_version');
    }
    if (!trajectory.proteinAtomSchemaReady) {
        missing.push('protein_atom_frames[T,A,3]');
    }
    if (trajectory.proteinAtomSchemaReady && atomState.mappingMode === 'mapped'
        && (!Array.isArray(trajectory.proteinAtomTemplateIndex) || !trajectory.proteinAtomTemplateIndex.length)) {
        missing.push('protein_atom_template_index[A]');
    }
    if (!trajectory.proteinAtomSchemaVersion) {
        missing.push('protein_atom_schema_version');
    }
    if (trajectory.proteinAtomSchemaReady && !atomState.eligible) {
        missing.push(`protein_atom eligibility:${atomState.reason}`);
    }
    if (!missing.length) {
        return `Ready for full protein frame mutation via ${trajectory.proteinAtomSchemaVersion || 'protein_atom schema'} and frame-aware residue overlays via ${trajectory.proteinResidueSchemaVersion || 'protein_residue schema'}.`;
    }
    return `Frame-aware protein overlays need ${missing.join(', ')}. Current mode stays ${describeProteinHeatmapMode(candidate)}.`;
}

function describeFastPathMissBreakdown(candidate, options = {}) {
    const counts = candidate?.trajectoryRenderStats?.missReasonCounts || {};
    const entries = Object.entries(counts)
        .filter(([, value]) => Number(value) > 0)
        .sort((left, right) => Number(right[1]) - Number(left[1]));
    if (!entries.length) {
        return options.long ? 'No fast-path miss has been recorded yet.' : 'none';
    }
    const formatted = entries.map(([key, value]) => `${describeFastPathMissReason({ trajectoryRenderStats: { lastFastPathMissReason: key } })} ${value}`);
    return options.long
        ? `Observed miss counts: ${formatted.join(', ')}.`
        : formatted.join(' · ');
}

function mapColorTheme(value) {
    const mapping = {
        'binding-focus': 'chain-id',
        'alphafold-confidence': 'plddt',
        'secondary-structure': 'secondary-structure',
        'chain-id': 'chain-id',
        'residue-index': 'residue-index',
        'element': 'element-symbol',
        'bfactor': 'uncertainty',
        'hydrophobicity': 'hydrophobicity',
    };
    return mapping[value] || 'chain-id';
}

function mapRepresentation(value) {
    const mapping = {
        cartoon: 'cartoon',
        'ball-and-stick': 'ball-and-stick',
        spacefill: 'spacefill',
        'gaussian-surface': 'gaussian-surface',
        'molecular-surface': 'molecular-surface',
    };
    return mapping[value] || 'cartoon';
}

async function clearViewer() {
    clearInteractionOverlay();
    if (state.residueHighlightTimer) {
        window.clearTimeout(state.residueHighlightTimer);
        state.residueHighlightTimer = 0;
    }
    if (state.localFocusOverlayTimer) {
        window.clearTimeout(state.localFocusOverlayTimer);
        state.localFocusOverlayTimer = 0;
    }
    state.localFocusOverlay = null;
    state.residueHighlightRef = '';
    if (state.viewer?.plugin) await state.viewer.plugin.clear();
}

async function clearCompareViewers() {
    for (const viewer of [state.compareViewers.A, state.compareViewers.B]) {
        if (!viewer?.plugin) continue;
        try {
            await viewer.plugin.clear();
        } catch (error) {
            console.warn('compare viewer clear failed', error);
        }
    }
}

function showSingleViewerLayout() {
    dom.compareSplitLayout.style.display = 'none';
    dom.molstarViewer.style.display = 'block';
    dom.viewerOverlay.style.display = dom.viewerOverlay.innerHTML ? dom.viewerOverlay.style.display : 'none';
    dom.interactionOverlay.style.display = dom.interactionOverlay.innerHTML ? dom.interactionOverlay.style.display : 'none';
    dom.viewerAnnotationLayer.style.display = dom.viewerMode === 'single' ? 'flex' : 'none';
}

function showCompareSplitLayout() {
    dom.compareSplitLayout.style.display = 'grid';
    dom.molstarViewer.style.display = 'none';
    dom.viewerOverlay.style.display = 'none';
    dom.interactionOverlay.style.display = 'none';
    dom.viewerAnnotationLayer.style.display = 'none';
}

async function loadStructureTextIntoViewer(text, format = 'pdb') {
    const ticket = ++state.viewerRenderTicket;
    showSingleViewerLayout();
    await clearViewer();
    if (ticket !== state.viewerRenderTicket) return;
    await state.viewer.loadStructureFromData(text, format, buildLoadOptions());
    applyViewerRenderSettings();
    requestViewerCameraReset();
}

async function loadSceneIntoViewer(text, format = 'pdb', candidate = null, { frameIndex = null } = {}) {
    const ticket = ++state.viewerRenderTicket;
    await clearViewer();
    if (candidate) candidate.fastTrajectorySceneCache = null;
    if (ticket !== state.viewerRenderTicket) return;
    await state.viewer.loadStructureFromData(text, format, buildLoadOptions());
    applyViewerRenderSettings();
    if (candidate) {
        requestBindingFocus(candidate, frameIndex);
    } else {
        requestViewerCameraReset();
    }
    if (ticket !== state.viewerRenderTicket || !candidate) return;

    const shouldOverlayNative = candidate.proteinReferenceViewerMode === 'unaligned_overlay'
        && candidate.proteinReferenceReady
        && candidate.proteinReferencePath;
    if (shouldOverlayNative) {
        const overlayPath = await resolveFirstReadablePath([candidate.proteinReferencePath]);
        if (overlayPath) {
            try {
                const overlayText = await fetchText(overlayPath);
                const overlayFormat = inferStructureFormat(overlayPath);
                if (ticket !== state.viewerRenderTicket) return;
                await state.viewer.loadStructureFromData(overlayText, overlayFormat, buildLoadOptions());
                candidate.activeOverlayPath = overlayPath;
                applyViewerRenderSettings();
                requestBindingFocus(candidate, frameIndex);
            } catch (error) {
                console.warn('native overlay load failed', overlayPath, error);
            }
        }
    }

    await maybeLoadPocketSurfaceOverlay(candidate, frameIndex);
    await maybeLoadElectrostaticSurfaceOverlay(candidate);
    await refreshNativeScoreLabels(candidate, frameIndex);
}

function requestViewerCameraReset() {
    const plugin = state.viewer?.plugin;
    if (!plugin) return;
    try {
        plugin.managers?.camera?.reset?.(undefined, 0);
    } catch (_error) {
    }
    try {
        plugin.canvas3d?.requestCameraReset?.({ durationMs: 0 });
    } catch (_error) {
    }
}

async function loadStructureIntoNamedViewer(viewer, text, format = 'pdb') {
    if (!viewer?.plugin) return;
    await viewer.plugin.clear();
    await viewer.loadStructureFromData(text, format, buildLoadOptions());
    const canvas = viewer.plugin?.canvas3d;
    if (canvas) {
        try {
            canvas.setProps({
                renderer: { backgroundColor: parseHexColor(dom.bgSelect.value) },
                trackball: { spin: Boolean(dom.toggleSpin.checked) },
                postprocessing: buildPostprocessingPreset(dom.aoPresetSelect?.value || 'analysis', Boolean(dom.toggleFog?.checked)),
            });
        } catch (error) {
            console.warn('named viewer render preset apply failed', error);
        }
    }
    try {
        viewer.plugin?.managers?.camera?.reset?.(undefined, 0);
    } catch (_error) {
    }
}

function getStructureEntryRef(entry) {
    return entry?.cell?.transform?.ref || '';
}

async function loadStructureWithRef(text, format, loadOptions) {
    const before = new Set(getCurrentSceneStructures().map(getStructureEntryRef).filter(Boolean));
    await state.viewer.loadStructureFromData(text, format, loadOptions);
    const added = getCurrentSceneStructures().find((entry) => {
        const ref = getStructureEntryRef(entry);
        return ref && !before.has(ref);
    });
    return getStructureEntryRef(added);
}

async function deleteViewerStateRefs(refs) {
    const plugin = state.viewer?.plugin;
    if (!plugin?.state?.data) return;
    const builder = plugin.state.data.build();
    for (const ref of refs.filter(Boolean)) {
        builder.delete(ref);
    }
    if (builder.editInfo.count > 0) {
        await builder.commit();
    }
}

function requestViewerRedraw() {
    try {
        state.viewer?.plugin?.canvas3d?.requestDraw?.();
    } catch (_error) {
    }
}

function describeTrajectoryUpdateMode(candidate) {
    const mode = candidate?.fastTrajectorySceneCache?.ligandUpdateMode || 'not_initialized';
    const mapping = {
        in_place_atomic_conformation: 'in-place',
        ligand_structure_reload: 'ligand reload',
        reload_only_locked: 'reload-only',
        none: 'not loaded',
        not_initialized: 'pending',
    };
    return mapping[mode] || mode;
}

function trajectoryUpdateModeTone(candidate) {
    const mode = candidate?.fastTrajectorySceneCache?.ligandUpdateMode || 'not_initialized';
    if (mode === 'in_place_atomic_conformation') return 'good';
    if (mode === 'reload_only_locked') return 'bad';
    if (mode === 'ligand_structure_reload') return 'warn';
    return 'muted';
}

async function clearNativeScoreLabels() {
    const measurementState = state.viewer?.plugin?.managers?.structure?.measurement?.state;
    const labels = Array.isArray(measurementState?.labels) ? measurementState.labels : [];
    if (!labels.length) return;
    const builder = state.viewer.plugin.state.data.build();
    for (const cell of labels) {
        builder.delete(cell);
    }
    if (builder.editInfo.count > 0) {
        await builder.commit();
    }
}

function buildFocusedSceneSignature(candidate, frameIndex = null) {
    if (!(candidate?.fastTrajectorySceneSignatureCache instanceof Map)) {
        candidate.fastTrajectorySceneSignatureCache = new Map();
    }
    const signatureKey = [
        Number.isFinite(frameIndex) ? frameIndex : 'ref',
        dom.togglePocketSurface?.checked ? 'surface:1' : 'surface:0',
    ].join('|');
    if (candidate.fastTrajectorySceneSignatureCache.has(signatureKey)) {
        return candidate.fastTrajectorySceneSignatureCache.get(signatureKey);
    }
    const pocketContext = buildPocketContext(candidate, frameIndex);
    const signature = [
        candidate?.index ?? 'x',
        pocketContext.focusResidues.map((entry) => entry.key).join(','),
        pocketContext.shellResidues.map((entry) => entry.key).join(','),
        pocketContext.contactResidues.map((entry) => entry.key).join(','),
        dom.togglePocketSurface?.checked ? 'surface:1' : 'surface:0',
    ].join('|');
    candidate.fastTrajectorySceneSignatureCache.set(signatureKey, signature);
    if (candidate.fastTrajectorySceneSignatureCache.size > 96) {
        const firstKey = candidate.fastTrajectorySceneSignatureCache.keys().next().value;
        candidate.fastTrajectorySceneSignatureCache.delete(firstKey);
    }
    return signature;
}

function collectStructureConformationBindings(entry, atomCountHint = 0) {
    const candidates = collectAtomicConformationCandidates(entry)
        .map((atomic) => ({
            x: atomic.x,
            y: atomic.y,
            z: atomic.z,
            atomCount: Math.min(atomic.x.length, atomic.y.length, atomic.z.length),
        }));
    if (!candidates.length) return null;
    if (!atomCountHint) return candidates[0];
    return candidates.find((item) => item.atomCount >= atomCountHint) || null;
}

function bindCacheStructureConformation(cache, refKey, atomCountHint = 0) {
    if (!cache?.[refKey]) return null;
    const bindingKey = `${refKey}ConformationBinding`;
    if (cache[bindingKey] === false) return null;
    if (cache[bindingKey]?.atomCount) return cache[bindingKey];
    const entry = getStructureEntryByRef(cache[refKey]);
    if (!entry) {
        cache[bindingKey] = false;
        return null;
    }
    const binding = collectStructureConformationBindings(entry, atomCountHint);
    cache[bindingKey] = binding || false;
    return binding || null;
}

function tryInPlaceStructureCoordinateUpdate(cache, refKey, points) {
    if (!Array.isArray(points) || !points.length) return false;
    const binding = bindCacheStructureConformation(cache, refKey, points.length);
    if (!binding) return false;
    try {
        for (let atomIndex = 0; atomIndex < points.length; atomIndex += 1) {
            const coords = points[atomIndex];
            binding.x[atomIndex] = coords[0];
            binding.y[atomIndex] = coords[1];
            binding.z[atomIndex] = coords[2];
        }
        return true;
    } catch (error) {
        console.warn(`in-place ${refKey} coordinate update failed`, error);
        cache[`${refKey}ConformationBinding`] = false;
        return false;
    }
}

function collectFocusedProteinCoords(candidate, frameIndex = null) {
    const pocketContext = buildPocketContext(candidate, frameIndex);
    return {
        backbonePoints: (pocketContext.backboneAtoms || []).map((atom) => atomToPoint(atom)),
        contactPoints: (pocketContext.contactAtoms || []).map((atom) => atomToPoint(atom)),
        surfacePoints: (pocketContext.surfaceAtoms || []).map((atom) => [atom.x, atom.y, atom.z]),
    };
}

function getProteinAtomFrameCoords(trajectory, frameIndex) {
    const payload = trajectory?.proteinAtomFrames;
    if (!payload?.data || !Array.isArray(payload.shape) || payload.shape.length !== 3) return [];
    const frameCount = payload.shape[0] || 0;
    const atomCount = payload.shape[1] || 0;
    if (!frameCount || !atomCount) return [];
    const clampedFrameIndex = clamp(frameIndex, 0, frameCount - 1);
    const baseOffset = clampedFrameIndex * atomCount * 3;
    const coords = [];
    for (let atomIndex = 0; atomIndex < atomCount; atomIndex += 1) {
        const base = baseOffset + atomIndex * 3;
        coords.push([
            payload.data[base],
            payload.data[base + 1],
            payload.data[base + 2],
        ]);
    }
    return coords;
}

function applyProteinAtomFrameToTemplate(candidate, frameIndex) {
    const trajectory = candidate?.trajectoryData;
    if (!trajectory?.proteinAtomSchemaReady) return false;
    const eligibility = getProteinAtomFrameEligibility(candidate);
    if (!eligibility.eligible) return false;
    const frameAtoms = getProteinAtomsForFrame(candidate, frameIndex);
    return Array.isArray(frameAtoms) && frameAtoms.length > 0;
}

async function refreshFastTrajectoryProteinLayers(cache, candidate, frameIndex) {
    const parts = buildFocusedSceneParts(candidate, frameIndex);
    const proteinTheme = focusedProteinTheme();
    const surfaceTheme = focusedSurfaceTheme();
    await deleteViewerStateRefs([cache.backboneRef, cache.contactRef, cache.surfaceRef]);
    cache.backboneRef = '';
    cache.contactRef = '';
    cache.surfaceRef = '';

    if (parts.proteinBackbonePdb) {
        cache.backboneRef = await loadStructureWithRef(
            parts.proteinBackbonePdb,
            'pdb',
            buildLoadOptionsForPreset({ theme: proteinTheme, representation: 'cartoon' }),
        );
    }
    if (parts.proteinContactPdb) {
        cache.contactRef = await loadStructureWithRef(
            parts.proteinContactPdb,
            'pdb',
            buildLoadOptionsForPreset({ theme: proteinTheme, representation: 'ball-and-stick' }),
        );
    }
    if (dom.togglePocketSurface?.checked && parts.surfacePdb) {
        cache.surfaceRef = await loadStructureWithRef(
            parts.surfacePdb,
            'pdb',
            buildLoadOptionsForPreset({ theme: surfaceTheme, representation: 'molecular-surface' }),
        );
    }
    applyViewerRenderSettings();
}

function tryFastTrajectoryProteinInPlaceUpdate(cache, candidate, frameIndex) {
    const { backbonePoints, contactPoints, surfacePoints } = collectFocusedProteinCoords(candidate, frameIndex);
    if (!backbonePoints.length && !contactPoints.length && !surfacePoints.length) return false;
    const backboneOk = backbonePoints.length ? tryInPlaceStructureCoordinateUpdate(cache, 'backboneRef', backbonePoints) : true;
    const contactOk = contactPoints.length ? tryInPlaceStructureCoordinateUpdate(cache, 'contactRef', contactPoints) : true;
    const surfaceOk = surfacePoints.length && dom.togglePocketSurface?.checked
        ? tryInPlaceStructureCoordinateUpdate(cache, 'surfaceRef', surfacePoints)
        : true;
    if (backboneOk && contactOk && surfaceOk) {
        requestViewerRedraw();
        return true;
    }
    return false;
}

async function tryFastTrajectoryFrameUpdate(candidate, frameIndex) {
    const proteinAtomFrameApplied = applyProteinAtomFrameToTemplate(candidate, frameIndex);
    const cache = candidate?.fastTrajectorySceneCache;
    if (!cache || state.viewerMode !== 'single') return { ok: false, mode: 'none', proteinFrameRefresh: false, missReason: 'no_cache' };
    if (cache.candidateIndex !== candidate.index) return { ok: false, mode: 'none', proteinFrameRefresh: false, missReason: 'candidate_switch' };
    if (cache.sceneSignature !== buildFocusedSceneSignature(candidate, frameIndex)) return { ok: false, mode: 'none', proteinFrameRefresh: false, missReason: 'signature_mismatch' };

    let proteinFrameRefresh = false;
    const updatedInPlace = tryInPlaceLigandCoordinateUpdate(cache, candidate, frameIndex);
    if (!updatedInPlace) {
        const ligandPdb = buildTrajectoryLigandPdb(candidate, frameIndex);
        await deleteViewerStateRefs([cache.ligandRef]);
        cache.ligandRef = ligandPdb
            ? await loadStructureWithRef(
                ligandPdb,
                'pdb',
                buildLoadOptionsForPreset({ theme: 'chain-id', representation: 'spacefill' }),
            )
            : '';
        cache.ligandConformationBinding = null;
        cache.ligandUpdateMode = cache.ligandRef ? 'ligand_structure_reload' : 'none';
    }
    if (shouldDynamicProteinFrameRefresh(candidate)) {
        await refreshFastTrajectoryProteinLayers(cache, candidate, frameIndex);
        proteinFrameRefresh = true;
    } else if (tryFastTrajectoryProteinInPlaceUpdate(cache, candidate, frameIndex)) {
        proteinFrameRefresh = false;
    } else if (proteinAtomFrameApplied) {
        await refreshFastTrajectoryProteinLayers(cache, candidate, frameIndex);
        proteinFrameRefresh = true;
    }
    if (state.trajectorySceneMode === 'trajectory') {
        await clearNativeScoreLabels();
    }
    if (!state.cameraUserLocked) {
        requestBindingFocus(candidate, frameIndex, { force: false, tight: true });
    }
    if (state.trajectorySceneMode !== 'trajectory') {
        await refreshNativeScoreLabels(candidate, frameIndex);
    }
    cache.frameIndex = frameIndex;
    return {
        ok: true,
        mode: cache.ligandUpdateMode || 'none',
        proteinFrameRefresh,
        missReason: 'none',
    };
}

async function loadFocusedCandidateScene(candidate, frameIndex = null) {
    const parts = buildFocusedSceneParts(candidate, frameIndex);
    if (!parts.proteinBackbonePdb && !parts.proteinContactPdb && !parts.ligandPdb) {
        const fallbackText = candidate?.activeStructureText || '';
        const fallbackFormat = candidate?.activeStructureFormat || 'pdb';
        if (fallbackText) {
            await loadSceneIntoViewer(fallbackText, fallbackFormat, candidate, { frameIndex });
        }
        return;
    }

    const ticket = ++state.viewerRenderTicket;
    await clearViewer();
    candidate.fastTrajectorySceneCache = null;
    if (ticket !== state.viewerRenderTicket) return;

    let backboneRef = '';
    let contactRef = '';
    let surfaceRef = '';
    let ligandRef = '';
    const proteinTheme = focusedProteinTheme();
    const surfaceTheme = focusedSurfaceTheme();
    if (parts.proteinBackbonePdb) {
        backboneRef = await loadStructureWithRef(
            parts.proteinBackbonePdb,
            'pdb',
            buildLoadOptionsForPreset({
                theme: proteinTheme,
                representation: 'cartoon',
            }),
        );
    }
    if (ticket !== state.viewerRenderTicket) return;

    if (parts.proteinContactPdb) {
        contactRef = await loadStructureWithRef(
            parts.proteinContactPdb,
            'pdb',
            buildLoadOptionsForPreset({
                theme: proteinTheme,
                representation: 'ball-and-stick',
            }),
        );
    }
    if (ticket !== state.viewerRenderTicket) return;

    if (dom.togglePocketSurface?.checked && parts.surfacePdb) {
        surfaceRef = await loadStructureWithRef(
            parts.surfacePdb,
            'pdb',
            buildLoadOptionsForPreset({ theme: surfaceTheme, representation: 'molecular-surface' }),
        );
    }
    if (ticket !== state.viewerRenderTicket) return;

    if (parts.ligandPdb) {
        ligandRef = await loadStructureWithRef(
            parts.ligandPdb,
            'pdb',
            buildLoadOptionsForPreset({ theme: 'chain-id', representation: 'spacefill' }),
        );
    }
    applyViewerRenderSettings();
    requestBindingFocus(candidate, frameIndex);
    await maybeLoadElectrostaticSurfaceOverlay(candidate);
    if (state.trajectorySceneMode !== 'trajectory') {
        await refreshNativeScoreLabels(candidate, frameIndex);
    } else {
        await clearNativeScoreLabels();
    }
    candidate.fastTrajectorySceneCache = {
        candidateIndex: candidate.index,
        frameIndex,
        sceneSignature: buildFocusedSceneSignature(candidate, frameIndex),
        backboneRef,
        contactRef,
        surfaceRef,
        ligandRef,
        ligandConformationBinding: null,
        ligandUpdateMode: ligandRef ? 'ligand_structure_reload' : 'none',
    };
}

async function maybeLoadPocketSurfaceOverlay(candidate, frameIndex = null) {
    if (!candidate || !dom.togglePocketSurface?.checked) return;
    if (state.viewerMode !== 'single') return;
    const currentRepresentation = mapRepresentation(dom.reprSelect.value);
    if (currentRepresentation === 'molecular-surface' || currentRepresentation === 'gaussian-surface') return;
    const surfacePdb = buildPocketSurfacePdb(candidate, frameIndex ?? state.trajectoryFrameIndex);
    if (!surfacePdb) return;
    try {
        await state.viewer.loadStructureFromData(
            surfacePdb,
            'pdb',
            buildLoadOptionsForPreset({ theme: focusedSurfaceTheme(), representation: 'molecular-surface' }),
        );
        applyViewerRenderSettings();
        requestBindingFocus(candidate, frameIndex);
    } catch (error) {
        console.warn('pocket surface overlay load failed', error);
    }
}

async function maybeLoadElectrostaticSurfaceOverlay(candidate) {
    if (!candidate || !dom.toggleElectroSurface?.checked) return;
    const rawPath = firstTruthy(candidate.surfaceMapPath);
    if (!rawPath) return;
    const surfacePath = await resolveFirstReadablePath([rawPath]);
    if (!surfacePath) return;
    const format = firstTruthy(candidate.surfaceMapFormat, inferVolumeFormat(surfacePath));
    if (!format) return;
    const isoValue = Number.isFinite(candidate.surfaceMapIsoValue) ? candidate.surfaceMapIsoValue : 1.0;
    try {
        await state.viewer.loadVolumeFromUrl(
            {
                url: resolveAssetUrl(surfacePath),
                format,
                isBinary: false,
            },
            [
                { type: 'absolute', value: Math.abs(isoValue), color: 0x2563eb, alpha: 0.18 },
                { type: 'absolute', value: -Math.abs(isoValue), color: 0xef4444, alpha: 0.18 },
            ],
            { entryId: basenameOf(surfacePath) },
        );
    } catch (error) {
        console.warn('electrostatic volume load failed', surfacePath, error);
    }
}

function buildPostprocessingPreset(presetName, depthBoost = false) {
    const presets = {
        analysis: {
            occlusion: { name: 'off', params: {} },
            outline: { name: 'off', params: {} },
            shadow: { name: 'off', params: {} },
            sharpening: { name: 'off', params: {} },
            antialiasing: { name: 'fxaa', params: { edgeThresholdMin: 0.0312, edgeThresholdMax: 0.125, iterations: 12, subpixelQuality: 0.3 } },
        },
        illustrative: {
            occlusion: {
                name: 'on',
                params: {
                    samples: 32,
                    multiScale: { name: 'off', params: {} },
                    radius: 5,
                    bias: 0.8,
                    blurKernelSize: 15,
                    blurDepthBias: 0.5,
                    resolutionScale: 1,
                    color: 0x000000,
                },
            },
            outline: {
                name: 'on',
                params: {
                    scale: 1,
                    threshold: 0.33,
                    color: 0x111827,
                    includeTransparent: true,
                },
            },
            shadow: depthBoost
                ? { name: 'on', params: { steps: 1, bias: 0.6, maxDistance: 3, tolerance: 1 } }
                : { name: 'off', params: {} },
            sharpening: { name: 'off', params: {} },
            antialiasing: { name: 'fxaa', params: { edgeThresholdMin: 0.0312, edgeThresholdMax: 0.125, iterations: 12, subpixelQuality: 0.3 } },
        },
        snapshot: {
            occlusion: {
                name: 'on',
                params: {
                    samples: 32,
                    multiScale: { name: 'off', params: {} },
                    radius: depthBoost ? 6 : 5,
                    bias: 0.8,
                    blurKernelSize: 15,
                    blurDepthBias: 0.5,
                    resolutionScale: 1,
                    color: 0x000000,
                },
            },
            outline: {
                name: 'on',
                params: {
                    scale: 1,
                    threshold: 0.33,
                    color: 0x000000,
                    includeTransparent: true,
                },
            },
            shadow: { name: 'on', params: { steps: depthBoost ? 2 : 1, bias: 0.6, maxDistance: 3, tolerance: 1 } },
            sharpening: { name: 'on', params: { sharpness: depthBoost ? 0.55 : 0.35, denoise: true } },
            antialiasing: { name: 'fxaa', params: { edgeThresholdMin: 0.0312, edgeThresholdMax: 0.125, iterations: 12, subpixelQuality: 0.3 } },
        },
    };
    return presets[presetName] || presets.analysis;
}

function applyViewerRenderSettings() {
    const viewers = [state.viewer, state.compareViewers.A, state.compareViewers.B].filter(Boolean);
    if (!viewers.length) return;
    const props = {
        renderer: { backgroundColor: parseHexColor(dom.bgSelect.value) },
        trackball: { spin: Boolean(dom.toggleSpin.checked) },
        postprocessing: buildPostprocessingPreset(dom.aoPresetSelect?.value || 'analysis', Boolean(dom.toggleFog?.checked)),
    };
    for (const viewer of viewers) {
        const canvas = viewer?.plugin?.canvas3d;
        if (!canvas) continue;
        try {
            canvas.setProps(props);
        } catch (error) {
            console.warn('viewer render preset apply failed', error);
        }
    }
}

async function focusSelectedBindingPocket() {
    const candidate = getSelectedCandidate();
    if (!candidate || state.viewerMode !== 'single') return;
    state.cameraUserLocked = false;
    if (state.trajectorySceneMode !== 'reference') {
        state.trajectorySceneMode = 'reference';
        candidate.lastRenderedTrajectoryFrame = -1;
        await loadFocusedCandidateScene(candidate, null);
    }
    refreshInteractionOverlayData(candidate, null);
    syncTrajectoryUi();
    requestBindingFocus(candidate, null, { force: true, tight: true });
}

function noteUserCameraInteraction() {
    if (state.viewerMode !== 'single') return;
    state.cameraUserLocked = true;
}

function requestBindingFocus(candidate, frameIndex = null, { force = false, tight = false } = {}) {
    if (state.cameraUserLocked && !force) return;
    const focusSphere = computeBindingFocusSphere(candidate, frameIndex, { tight });
    if (!focusSphere) {
        requestViewerCameraReset();
        return;
    }
    const focusTicket = ++state.bindingFocusTicket;
    const candidateIndex = candidate?.index ?? -1;
    const apply = () => {
        if (focusTicket !== state.bindingFocusTicket) return;
        if (state.viewerMode !== 'single') return;
        if (getSelectedCandidate()?.index !== candidateIndex) return;
        const canvas3d = state.viewer?.plugin?.canvas3d;
        if (!canvas3d?.camera?.getFocus || !canvas3d?.requestCameraReset) {
            requestViewerCameraReset();
            return;
        }
        try {
            const snapshot = canvas3d.camera.getFocus(
                focusSphere.center,
                tight ? Math.max(1.55, focusSphere.radius) : Math.max(2.8, focusSphere.radius),
            );
            canvas3d.requestCameraReset({ durationMs: 0, snapshot });
        } catch (error) {
            console.warn('binding focus failed', error);
            requestViewerCameraReset();
        }
    };
    apply();
}

function computeAtomGroupFocusSphere(atomGroups, candidate = null, frameIndex = null) {
    const atomPoints = (atomGroups || [])
        .flat()
        .filter(Boolean)
        .map((atom) => atomToPoint(atom))
        .filter((point) => isVec3Like(point));
    if (!atomPoints.length) return null;
    const ligandPoints = candidate ? getCandidateLigandCoords(candidate, frameIndex) : [];
    const supportPoints = atomPoints.concat(
        ligandPoints.length ? [computeCentroid(ligandPoints)] : [],
    );
    const center = computeCentroid(supportPoints);
    let radius = 0;
    for (const point of supportPoints) {
        radius = Math.max(radius, distanceBetween(point, center));
    }
    return {
        center,
        radius: Math.max(1.9, Math.min(5.2, radius + 1.15)),
    };
}

function setLocalFocusOverlay(center, label = 'Local Focus', radius = 2.2) {
    if (!isVec3Like(center)) return;
    if (state.localFocusOverlayTimer) {
        window.clearTimeout(state.localFocusOverlayTimer);
        state.localFocusOverlayTimer = 0;
    }
    state.localFocusOverlay = {
        center: [center[0], center[1], center[2]],
        label,
        radius: Number.isFinite(radius) ? radius : 2.2,
    };
    renderInteractionOverlay();
    state.localFocusOverlayTimer = window.setTimeout(() => {
        state.localFocusOverlayTimer = 0;
        state.localFocusOverlay = null;
        renderInteractionOverlay();
    }, 1000);
}

function requestAtomGroupLocalFocus(atomGroups, candidate = null, frameIndex = null, label = 'Local Focus') {
    if (state.viewerMode !== 'single') return;
    const focusSphere = computeAtomGroupFocusSphere(atomGroups, candidate, frameIndex);
    if (!focusSphere) return;
    setLocalFocusOverlay(focusSphere.center, label, focusSphere.radius);
    const canvas3d = state.viewer?.plugin?.canvas3d;
    if (!canvas3d?.camera?.getFocus || !canvas3d?.requestCameraReset) {
        requestViewerCameraReset();
        return;
    }
    try {
        const snapshot = canvas3d.camera.getFocus(
            focusSphere.center,
            Math.max(1.9, focusSphere.radius),
        );
        canvas3d.requestCameraReset({ durationMs: 140, snapshot });
    } catch (error) {
        console.warn('atom-group local focus failed', error);
    }
}

function getCurrentSceneStructuresForViewer(viewerLike = null) {
    return viewerLike?.plugin?.managers?.structure?.hierarchy?.current?.structures || [];
}

function getCurrentSceneStructures() {
    return getCurrentSceneStructuresForViewer(state.viewer);
}

function getStructureEntryByRef(ref) {
    if (!ref) return null;
    return getCurrentSceneStructures().find((entry) => getStructureEntryRef(entry) === ref) || null;
}

function collectAtomicConformationCandidates(entry) {
    const structure = entry?.cell?.obj?.data;
    const models = [];
    const pushModel = (model) => {
        if (!model || models.includes(model)) return;
        models.push(model);
    };
    pushModel(structure?.model);
    pushModel(structure?.representativeModel);
    if (Array.isArray(structure?.models)) structure.models.forEach(pushModel);
    if (Array.isArray(structure?.units)) structure.units.forEach((unit) => pushModel(unit?.model));
    return models
        .map((model) => model?.atomicConformation)
        .filter((atomic) => atomic?.x && atomic?.y && atomic?.z);
}

function bindLigandConformationUpdater(cache, candidate, atomCountHint = 0) {
    if (!cache?.ligandRef) return null;
    if (candidate?.ligandForceReloadOnly) return null;
    if (cache.ligandConformationBinding === false) return null;
    if (cache.ligandConformationBinding?.atomCount) return cache.ligandConformationBinding;
    const entry = getStructureEntryByRef(cache.ligandRef);
    if (!entry) {
        cache.ligandConformationBinding = false;
        return null;
    }
    const atomCount = Math.max(
        atomCountHint || 0,
        Array.isArray(candidate?.ligandTemplateAtoms) ? candidate.ligandTemplateAtoms.length : 0,
    );
    if (!atomCount) {
        cache.ligandConformationBinding = false;
        return null;
    }
    const binding = collectAtomicConformationCandidates(entry)
        .map((atomic) => ({
            x: atomic.x,
            y: atomic.y,
            z: atomic.z,
            atomCount: Math.min(atomic.x.length, atomic.y.length, atomic.z.length),
        }))
        .find((item) => item.atomCount >= atomCount);
    cache.ligandConformationBinding = binding || false;
    return binding || null;
}

function tryInPlaceLigandCoordinateUpdate(cache, candidate, frameIndex) {
    if (!cache?.ligandRef) return false;
    if (candidate?.ligandForceReloadOnly) {
        cache.ligandUpdateMode = 'reload_only_locked';
        return false;
    }
    const ligandCoords = getCandidateLigandCoords(candidate, frameIndex);
    if (!ligandCoords.length) return false;
    const binding = bindLigandConformationUpdater(cache, candidate, ligandCoords.length);
    if (!binding) {
        if (!candidate?.ligandForceReloadOnly) {
            candidate.ligandInPlaceFailureCount = Math.max(0, Number(candidate?.ligandInPlaceFailureCount || 0)) + 1;
            if (candidate.ligandInPlaceFailureCount >= 3) {
                candidate.ligandForceReloadOnly = true;
                cache.ligandUpdateMode = 'reload_only_locked';
            }
        }
        return false;
    }
    try {
        for (let atomIndex = 0; atomIndex < ligandCoords.length; atomIndex += 1) {
            const coords = ligandCoords[atomIndex];
            binding.x[atomIndex] = coords[0];
            binding.y[atomIndex] = coords[1];
            binding.z[atomIndex] = coords[2];
        }
        candidate.ligandInPlaceFailureCount = 0;
        cache.ligandUpdateMode = 'in_place_atomic_conformation';
        requestViewerRedraw();
        return true;
    } catch (error) {
        console.warn('in-place ligand coordinate update failed', error);
        cache.ligandConformationBinding = false;
        candidate.ligandInPlaceFailureCount = Math.max(0, Number(candidate?.ligandInPlaceFailureCount || 0)) + 1;
        if (candidate.ligandInPlaceFailureCount >= 3) {
            candidate.ligandForceReloadOnly = true;
            cache.ligandUpdateMode = 'reload_only_locked';
        }
        return false;
    }
}

function buildSingletonStructureLoci(structure, elementIndex = 0, unitIndex = 0) {
    if (!structure?.units?.length) return null;
    const unit = structure.units[unitIndex] || structure.units[0];
    if (!unit?.elements?.length) return null;
    const clampedIndex = clamp(elementIndex, 0, unit.elements.length - 1);
    return {
        kind: 'element-loci',
        structure,
        elements: [{ unit, indices: [clampedIndex] }],
    };
}

function buildNativeScoreLabelText(candidate, frameIndex = null) {
    if (!candidate) return '';
    const wetlab = getWetlabFocusSummary();
    const trajectory = candidate?.trajectoryData;
    const frame = (
        Number.isFinite(frameIndex) &&
        trajectory?.frameCount &&
        frameIndex >= 0 &&
        frameIndex < trajectory.frameCount
    )
        ? { ...trajectory.frames[frameIndex], frameCount: trajectory.frameCount }
        : null;
    const interactionSummary = summarizeInteractionTypes(candidate, frameIndex);
    const pieces = [
        `#${candidate.packetRank}`,
        `d ${formatNumber(frame?.minDistanceA ?? candidate.meanMinDistanceA, 2)}A`,
        `Cv2 ${formatNumber(candidate.commercialOverallScoreV2, 0)}`,
    ];
    if (interactionSummary.items.length) {
        const dominant = interactionSummary.items[0];
        pieces.push(`${dominant.shortLabel} ${dominant.count}`);
    }
    if (wetlab.actionabilityStatus && wetlab.actionabilityStatus !== 'not_reported') {
        pieces.push(wetlab.actionabilityStatus);
    }
    return pieces.join(' | ');
}

async function refreshNativeScoreLabels(candidate, frameIndex = null) {
    if (!candidate || state.viewerMode !== 'single') return;
    const manager = state.viewer?.plugin?.managers?.structure?.measurement;
    const structures = getCurrentSceneStructures();
    if (!manager || !structures.length) return;
    const ligandEntry = getStructureEntryByRef(candidate.fastTrajectorySceneCache?.ligandRef) || structures[structures.length - 1];
    const ligandStructure = ligandEntry?.cell?.obj?.data;
    const ligandElementCount = ligandStructure?.units?.[0]?.elements?.length || 0;
    const loci = buildSingletonStructureLoci(
        ligandStructure,
        Math.max(0, Math.floor((ligandElementCount - 1) / 2)),
        0,
    );
    const customText = buildNativeScoreLabelText(candidate, frameIndex);
    if (!loci || !customText) return;
    try {
        await manager.addLabel(loci, {
            labelParams: {
                customText,
                textSize: 0.56,
                offsetY: 0.12,
                background: true,
                backgroundOpacity: 0.32,
            },
            reprTags: ['viewer-native-score-label'],
            selectionTags: ['viewer-native-score-label'],
        });
    } catch (error) {
        console.warn('native score label add failed', error);
    }
}

function installMeasurementClickHandler() {
    const clickBehavior = state.viewer?.plugin?.behaviors?.interaction?.click;
    if (!clickBehavior || state.measurementClickSub) return;
    state.measurementClickSub = clickBehavior.subscribe((event) => {
        handleMeasurementClick(event).catch((error) => {
            console.error(error);
            toast(`측정 처리 실패: ${error.message}`, 'error');
            cancelMeasurementMode({ clearHighlights: true });
        });
    });
}

function startMeasurementMode(mode) {
    if (state.viewerMode !== 'single') {
        toast('측정은 single viewer에서만 지원합니다.', 'warn');
        return;
    }
    state.measurementMode = mode;
    state.measurementPicks = [];
    state.viewer?.plugin?.managers?.interactivity?.setProps?.({ granularity: 'element' });
    updateMeasurementUi();
}

function cancelMeasurementMode({ clearHighlights = false } = {}) {
    state.measurementMode = '';
    state.measurementPicks = [];
    state.measurementBusy = false;
    if (clearHighlights) {
        state.viewer?.plugin?.managers?.interactivity?.lociHighlights?.clearHighlights?.();
    }
    updateMeasurementUi();
}

async function clearAllMeasurements() {
    const plugin = state.viewer?.plugin;
    cancelMeasurementMode({ clearHighlights: true });
    state.measurementRecords = [];
    refreshInteractionOverlayData(getSelectedCandidate(), state.trajectoryFrameIndex);
    updateMeasurementUi();
    if (!plugin?.managers?.structure?.measurement?.state) return;
    const measurementState = plugin.managers.structure.measurement.state;
    const builder = plugin.state.data.build();
    [
        ...measurementState.distances,
        ...measurementState.angles,
        ...measurementState.labels,
        ...measurementState.dihedrals,
        ...measurementState.orientations,
        ...measurementState.planes,
    ].forEach((cell) => builder.delete(cell));
    if (builder.editInfo.count > 0) {
        await builder.commit();
    }
    await refreshNativeScoreLabels(getSelectedCandidate(), state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null);
}

async function handleMeasurementClick(event) {
    if (!state.measurementMode || state.measurementBusy) return;
    const reprLoci = event?.current;
    const loci = reprLoci?.loci;
    if (!loci?.structure || !Array.isArray(loci.elements) || !loci.elements.length) return;

    const pick = {
        reprLoci,
        loci,
        position: isVec3Like(event?.position) ? [event.position[0], event.position[1], event.position[2]] : null,
    };
    state.measurementPicks.push(pick);
    state.viewer?.plugin?.managers?.interactivity?.lociHighlights?.highlightOnly?.(reprLoci, true);
    updateMeasurementUi();

    const requiredCount = state.measurementMode === 'angle'
        ? 3
        : (state.measurementMode === 'dihedral' ? 4 : 2);
    if (state.measurementPicks.length < requiredCount) return;

    state.measurementBusy = true;
    try {
        const manager = state.viewer?.plugin?.managers?.structure?.measurement;
        if (!manager) throw new Error('Mol* measurement manager is unavailable');
        const activeCandidate = getSelectedCandidate();
        const capturedFrameIndex = activeCandidate?.trajectoryData?.frameCount ? state.trajectoryFrameIndex : null;
        if (state.measurementMode === 'distance') {
            const [a, b] = state.measurementPicks;
            const distanceA = distanceBetween(a.position, b.position);
            await manager.addDistance(a.loci, b.loci, {
                lineParams: { linesColor: 0x2563eb, linesSize: 0.18, dashLength: 0.18 },
                labelParams: { textSize: 0.95, offsetY: 0.2, background: true, backgroundOpacity: 0.72 },
                reprTags: ['viewer-manual-measurement'],
                selectionTags: ['viewer-manual-measurement'],
            });
            state.measurementRecords.unshift({
                type: 'distance',
                label: 'Distance',
                valueLabel: Number.isFinite(distanceA)
                    ? `${formatNumber(distanceA, 3)} A`
                    : 'added',
                candidateIndex: activeCandidate?.index ?? -1,
                candidateLabel: activeCandidate?.title || '',
                targetId: activeCandidate?.targetId || '',
                frameIndex: capturedFrameIndex,
                positions: [cloneVec3(a.position), cloneVec3(b.position)].filter(Boolean),
            });
        } else if (state.measurementMode === 'angle') {
            const [a, b, c] = state.measurementPicks;
            const angleDeg = angleBetween(a.position, b.position, c.position);
            await manager.addAngle(a.loci, b.loci, c.loci, {
                lineParams: { linesColor: 0xf59e0b, linesSize: 0.16, dashLength: 0.18 },
                labelParams: { textSize: 0.9, offsetY: 0.2, background: true, backgroundOpacity: 0.72 },
                reprTags: ['viewer-manual-measurement'],
                selectionTags: ['viewer-manual-measurement'],
            });
            state.measurementRecords.unshift({
                type: 'angle',
                label: 'Angle',
                valueLabel: Number.isFinite(angleDeg)
                    ? `${formatNumber(angleDeg, 1)}°`
                    : 'added',
                candidateIndex: activeCandidate?.index ?? -1,
                candidateLabel: activeCandidate?.title || '',
                targetId: activeCandidate?.targetId || '',
                frameIndex: capturedFrameIndex,
                positions: [cloneVec3(a.position), cloneVec3(b.position), cloneVec3(c.position)].filter(Boolean),
            });
        } else {
            const [a, b, c, d] = state.measurementPicks;
            const dihedralDeg = dihedralBetween(a.position, b.position, c.position, d.position);
            await manager.addDihedral?.(a.loci, b.loci, c.loci, d.loci, {
                lineParams: { linesColor: 0x8b5cf6, linesSize: 0.16, dashLength: 0.18 },
                labelParams: { textSize: 0.9, offsetY: 0.2, background: true, backgroundOpacity: 0.72 },
                reprTags: ['viewer-manual-measurement'],
                selectionTags: ['viewer-manual-measurement'],
            });
            state.measurementRecords.unshift({
                type: 'dihedral',
                label: 'Dihedral',
                valueLabel: Number.isFinite(dihedralDeg)
                    ? `${formatNumber(dihedralDeg, 1)}°`
                    : 'added',
                candidateIndex: activeCandidate?.index ?? -1,
                candidateLabel: activeCandidate?.title || '',
                targetId: activeCandidate?.targetId || '',
                frameIndex: capturedFrameIndex,
                positions: [cloneVec3(a.position), cloneVec3(b.position), cloneVec3(c.position), cloneVec3(d.position)].filter(Boolean),
            });
        }
        state.measurementRecords = state.measurementRecords.slice(0, 6);
        refreshInteractionOverlayData(activeCandidate, state.trajectoryFrameIndex);
        toast(
            state.measurementMode === 'distance'
                ? '거리 측정을 추가했습니다.'
                : (state.measurementMode === 'angle' ? '각도 측정을 추가했습니다.' : 'dihedral 측정을 추가했습니다.'),
            'success',
        );
    } finally {
        cancelMeasurementMode({ clearHighlights: true });
        updateMeasurementUi();
    }
}

function updateMeasurementUi() {
    const activeDistance = state.measurementMode === 'distance';
    const activeAngle = state.measurementMode === 'angle';
    const activeDihedral = state.measurementMode === 'dihedral';
    dom.btnMeasureDist?.classList.toggle('active', activeDistance);
    dom.btnMeasureAngle?.classList.toggle('active', activeAngle);
    dom.btnMeasureDihedral?.classList.toggle('active', activeDihedral);

    let text = '측정 비활성';
    let tone = 'muted';
    if (activeDistance) {
        text = `거리 측정: 원자 2개 선택 (${state.measurementPicks.length}/2)`;
        tone = 'warn';
    } else if (activeAngle) {
        text = `각도 측정: 원자 3개 선택 (${state.measurementPicks.length}/3)`;
        tone = 'warn';
    } else if (activeDihedral) {
        text = `dihedral 측정: 원자 4개 선택 (${state.measurementPicks.length}/4)`;
        tone = 'warn';
    } else if (state.measurementRecords.length) {
        text = `최근 측정 ${state.measurementRecords.length}개`;
        tone = 'good';
    }
    dom.measurementStatus.className = `measure-status ${tone}`;
    dom.measurementStatus.textContent = text;
    dom.measurementList.innerHTML = state.measurementRecords.length
        ? state.measurementRecords.map((record) => `
            <div class="measure-record">
              <strong>${escapeHtml(record.label)}</strong>
              <span>${escapeHtml(record.valueLabel)}</span>
              <span class="measure-record-meta">${escapeHtml(describeMeasurementRecord(record))}</span>
            </div>
        `).join('')
        : '';
}

function refreshInteractionOverlayData(candidate, frameIndex = null) {
    if (!candidate || state.viewerMode !== 'single') {
        clearInteractionOverlay();
        return;
    }
    const overlayFrameIndex = frameIndex ?? (state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null);
    const pocketContext = buildPocketContext(candidate, overlayFrameIndex);
    state.autoInteractionSegments = pocketContext.autoInteractions;
    const manualSegments = getManualMeasurementOverlaySegments(candidate, overlayFrameIndex);
    if (state.autoInteractionSegments.length || manualSegments.length || hasLigandFocusOverlay(candidate, overlayFrameIndex)) {
        dom.interactionOverlay.style.display = 'block';
        ensureInteractionOverlayLoop();
    } else {
        clearInteractionOverlay();
    }
}

function ensureInteractionOverlayLoop() {
    if (state.interactionOverlayFrame) return;
    const tick = () => {
        state.interactionOverlayFrame = 0;
        renderInteractionOverlay();
        const candidate = getSelectedCandidate();
        const overlayFrameIndex = candidate?.trajectoryData?.frameCount && state.trajectorySceneMode === 'trajectory'
            ? state.trajectoryFrameIndex
            : null;
        const manualCount = getManualMeasurementOverlaySegments(
            candidate,
            overlayFrameIndex,
        ).length;
        if ((state.autoInteractionSegments.length || manualCount || hasLigandFocusOverlay(candidate, overlayFrameIndex)) && state.viewerMode === 'single') {
            state.interactionOverlayFrame = window.requestAnimationFrame(tick);
        }
    };
    state.interactionOverlayFrame = window.requestAnimationFrame(tick);
}

function clearInteractionOverlay() {
    if (state.interactionOverlayFrame) {
        window.cancelAnimationFrame(state.interactionOverlayFrame);
        state.interactionOverlayFrame = 0;
    }
    state.autoInteractionSegments = [];
    state.overlayInteractionSegments.clear();
    if (dom.interactionOverlay) {
        dom.interactionOverlay.innerHTML = '';
        dom.interactionOverlay.style.display = 'none';
    }
}

function renderOverlayLineSegment(segment, width, height) {
    const start = projectWorldPointToOverlay(segment.start, width, height);
    const end = projectWorldPointToOverlay(segment.end, width, height);
    if (!start || !end) return '';
    const midX = (start[0] + end[0]) / 2;
    const midY = (start[1] + end[1]) / 2;
    const labelText = String(segment.overlayLabel || segment.label || '').trim();
    const showLabel = Boolean(labelText) && segment.showLabel !== false;
    const labelWidth = Math.max(58, labelText.length * 5.6);
    const segmentAttr = segment.segmentId ? `data-segment-id="${escapeHtml(segment.segmentId)}"` : '';
    return `
        <line ${segmentAttr} class="interaction-line ${escapeHtml(segment.kind || '')} ${escapeHtml(segment.tone || '')} ${segment.manual ? 'manual' : 'auto'} ${segment.stale ? 'stale' : ''}" x1="${start[0].toFixed(1)}" y1="${start[1].toFixed(1)}" x2="${end[0].toFixed(1)}" y2="${end[1].toFixed(1)}"></line>
        ${showLabel ? `<rect ${segmentAttr} class="interaction-label ${escapeHtml(segment.kind || '')} ${segment.stale ? 'stale' : ''}" x="${(midX - labelWidth / 2).toFixed(1)}" y="${(midY - 10).toFixed(1)}" width="${labelWidth.toFixed(1)}" height="16" rx="8"></rect>` : ''}
        ${showLabel ? `<text ${segmentAttr} class="interaction-label-text ${escapeHtml(segment.kind || '')} ${segment.stale ? 'stale' : ''}" x="${midX.toFixed(1)}" y="${(midY + 1).toFixed(1)}" text-anchor="middle">${escapeHtml(labelText)}</text>` : ''}
    `;
}

function renderOverlayAngleSegment(segment, width, height) {
    const a = projectWorldPointToOverlay(segment.points?.[0], width, height);
    const b = projectWorldPointToOverlay(segment.points?.[1], width, height);
    const c = projectWorldPointToOverlay(segment.points?.[2], width, height);
    if (!a || !b || !c) return '';
    const labelWidth = Math.max(92, String(segment.label || '').length * 6.4);
    return `
        <line class="interaction-line warn manual ${segment.stale ? 'stale' : ''}" x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${b[0].toFixed(1)}" y2="${b[1].toFixed(1)}"></line>
        <line class="interaction-line warn manual ${segment.stale ? 'stale' : ''}" x1="${b[0].toFixed(1)}" y1="${b[1].toFixed(1)}" x2="${c[0].toFixed(1)}" y2="${c[1].toFixed(1)}"></line>
        <rect class="interaction-label ${segment.stale ? 'stale' : ''}" x="${(b[0] - labelWidth / 2).toFixed(1)}" y="${(b[1] - 28).toFixed(1)}" width="${labelWidth.toFixed(1)}" height="18" rx="9"></rect>
        <text class="interaction-label-text ${segment.stale ? 'stale' : ''}" x="${b[0].toFixed(1)}" y="${(b[1] - 14.5).toFixed(1)}" text-anchor="middle">${escapeHtml(segment.label)}</text>
    `;
}

function renderOverlayDihedralSegment(segment, width, height) {
    const points = (segment.points || []).map((point) => projectWorldPointToOverlay(point, width, height));
    if (points.some((point) => !point)) return '';
    const [a, b, c, d] = points;
    const labelWidth = Math.max(98, String(segment.label || '').length * 6.2);
    return `
        <line class="interaction-line pipi manual ${segment.stale ? 'stale' : ''}" x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${b[0].toFixed(1)}" y2="${b[1].toFixed(1)}"></line>
        <line class="interaction-line pipi manual ${segment.stale ? 'stale' : ''}" x1="${b[0].toFixed(1)}" y1="${b[1].toFixed(1)}" x2="${c[0].toFixed(1)}" y2="${c[1].toFixed(1)}"></line>
        <line class="interaction-line pipi manual ${segment.stale ? 'stale' : ''}" x1="${c[0].toFixed(1)}" y1="${c[1].toFixed(1)}" x2="${d[0].toFixed(1)}" y2="${d[1].toFixed(1)}"></line>
        <rect class="interaction-label pipi ${segment.stale ? 'stale' : ''}" x="${(((b[0] + c[0]) / 2) - labelWidth / 2).toFixed(1)}" y="${(((b[1] + c[1]) / 2) - 24).toFixed(1)}" width="${labelWidth.toFixed(1)}" height="18" rx="9"></rect>
        <text class="interaction-label-text pipi ${segment.stale ? 'stale' : ''}" x="${(((b[0] + c[0]) / 2)).toFixed(1)}" y="${(((b[1] + c[1]) / 2) - 10.5).toFixed(1)}" text-anchor="middle">${escapeHtml(segment.label)}</text>
    `;
}

function renderLigandFocusCallout(candidate, frameIndex, width, height) {
    if (!candidate) return '';
    const ligandPoints = getCandidateLigandCoords(candidate, frameIndex);
    if (!ligandPoints.length) return '';
    const centroid = computeCentroid(ligandPoints);
    const projected = projectWorldPointToOverlay(centroid, width, height);
    if (!projected) return '';
    const [x, y] = projected;
    const labelWidth = 94;
    return `
        <circle class="interaction-focus-ring" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="20"></circle>
        <circle class="interaction-focus-dot" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5.2"></circle>
        <rect class="interaction-focus-label" x="${(x + 14).toFixed(1)}" y="${(y - 15).toFixed(1)}" width="${labelWidth}" height="22" rx="11"></rect>
        <text class="interaction-focus-label-text" x="${(x + 61).toFixed(1)}" y="${(y - 0.5).toFixed(1)}" text-anchor="middle">Ligand Focus</text>
    `;
}

function renderLocalFocusContextOverlay(candidate, frameIndex, width, height) {
    const focus = state.localFocusOverlay;
    if (!focus?.center) return '';
    const projected = projectWorldPointToOverlay(focus.center, width, height);
    if (!projected) return '';
    const [x, y] = projected;
    const radius = Math.max(18, Math.min(34, (focus.radius || 2.2) * 8.4));
    let ligandGuide = '';
    const ligandPoints = candidate ? getCandidateLigandCoords(candidate, frameIndex) : [];
    if (ligandPoints.length) {
        const ligandCentroid = computeCentroid(ligandPoints);
        const ligandProjected = projectWorldPointToOverlay(ligandCentroid, width, height);
        if (ligandProjected) {
            const [lx, ly] = ligandProjected;
            const separation = Math.hypot(lx - x, ly - y);
            if (separation > 14) {
                ligandGuide = `
                    <line class="local-focus-link" x1="${x.toFixed(1)}" y1="${y.toFixed(1)}" x2="${lx.toFixed(1)}" y2="${ly.toFixed(1)}"></line>
                    <circle class="local-focus-ligand-dot" cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="4.2"></circle>
                `;
            }
        }
    }
    return `
        ${ligandGuide}
        <circle class="local-focus-ring" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${radius.toFixed(1)}"></circle>
        <circle class="local-focus-dot" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4.6"></circle>
        <rect class="local-focus-label" x="${(x - 48).toFixed(1)}" y="${(y - radius - 28).toFixed(1)}" width="96" height="20" rx="10"></rect>
        <text class="local-focus-label-text" x="${x.toFixed(1)}" y="${(y - radius - 14).toFixed(1)}" text-anchor="middle">${escapeHtml(focus.label || 'Local Focus')}</text>
    `;
}

function hasLigandFocusOverlay(candidate, frameIndex) {
    return Boolean(candidate && getCandidateLigandCoords(candidate, frameIndex).length);
}

function renderScoreAnchor(candidate, frameIndex, width, height) {
    if (!candidate) return '';
    if (state.trajectorySceneMode === 'trajectory') return '';
    const ligandPoints = getCandidateLigandCoords(candidate, frameIndex);
    if (!ligandPoints.length) return '';
    const centroid = computeCentroid(ligandPoints);
    const projected = projectWorldPointToOverlay(centroid, width, height);
    if (!projected) return '';
    const [x, y] = projected;
    const frame = Number.isFinite(frameIndex) ? candidate?.trajectoryData?.frames?.[frameIndex] || null : null;
    const lines = [
        `d ${Number.isFinite(frame?.minDistanceA) ? formatNumber(frame.minDistanceA, 2) : formatNumber(candidate.meanMinDistanceA, 2)}A`,
        `Cv2 ${formatNumber(candidate.commercialOverallScoreV2, 0)} | CF ${formatNumber(candidate.contactFraction, 2)}`,
    ];
    const widthBox = 126;
    const baseX = x - widthBox - 18;
    const baseY = y + 18;
    const texts = lines.map((line, idx) => `
        <text class="score-anchor-text" x="${(baseX + 10).toFixed(1)}" y="${(baseY + 15 + idx * 13).toFixed(1)}">${escapeHtml(line)}</text>
    `).join('');
    return `
        <rect class="score-anchor-box" x="${baseX.toFixed(1)}" y="${baseY.toFixed(1)}" width="${widthBox}" height="40" rx="10"></rect>
        ${texts}
    `;
}

function getManualMeasurementOverlaySegments(candidate, frameIndex) {
    if (!candidate) return [];
    return state.measurementRecords
        .filter((record) => record.candidateIndex === candidate.index)
        .map((record) => {
            const stale = Number.isFinite(record.frameIndex) && Number.isFinite(frameIndex) && record.frameIndex !== frameIndex;
            const frameTag = Number.isFinite(record.frameIndex) ? `f${record.frameIndex + 1}` : 'static';
            if (record.type === 'angle' && record.positions?.length >= 3) {
                return {
                    type: 'angle',
                    manual: true,
                    stale,
                    label: stale ? `${record.valueLabel} · ${frameTag}` : record.valueLabel,
                    points: record.positions,
                };
            }
            if (record.type === 'dihedral' && record.positions?.length >= 4) {
                return {
                    type: 'dihedral',
                    manual: true,
                    stale,
                    label: stale ? `${record.valueLabel} · ${frameTag}` : record.valueLabel,
                    points: record.positions,
                };
            }
            if (record.positions?.length >= 2) {
                return {
                    type: 'distance',
                    manual: true,
                    stale,
                    tone: stale ? 'muted' : 'info',
                    label: stale ? `${record.valueLabel} · ${frameTag}` : record.valueLabel,
                    start: record.positions[0],
                    end: record.positions[1],
                };
            }
            return null;
        })
        .filter(Boolean);
}

function describeMeasurementRecord(record) {
    const target = record.targetId || '-';
    if (Number.isFinite(record.frameIndex)) {
        return `${target} · captured frame ${record.frameIndex + 1}`;
    }
    return `${target} · static scene`;
}

function cloneVec3(value) {
    return isVec3Like(value) ? [value[0], value[1], value[2]] : null;
}

function renderInteractionOverlay() {
    if (!dom.interactionOverlay || state.viewerMode !== 'single') {
        return;
    }
    const bounds = dom.viewerContainer.getBoundingClientRect();
    const width = Math.max(1, Math.round(bounds.width));
    const height = Math.max(1, Math.round(bounds.height));
    dom.interactionOverlay.setAttribute('viewBox', `0 0 ${width} ${height}`);
    dom.interactionOverlay.setAttribute('width', String(width));
    dom.interactionOverlay.setAttribute('height', String(height));

    const candidate = getSelectedCandidate();
    const currentFrameIndex = candidate?.trajectoryData?.frameCount && state.trajectorySceneMode === 'trajectory'
        ? state.trajectoryFrameIndex
        : null;
    const fragments = [];
    const localFocus = renderLocalFocusContextOverlay(candidate, currentFrameIndex, width, height);
    if (localFocus) fragments.push(localFocus);
    const ligandCallout = renderLigandFocusCallout(candidate, currentFrameIndex, width, height);
    if (ligandCallout) fragments.push(ligandCallout);
    const scoreAnchor = renderScoreAnchor(candidate, currentFrameIndex, width, height);
    if (scoreAnchor) fragments.push(scoreAnchor);
    state.overlayInteractionSegments.clear();
    const autoSegments = state.autoInteractionSegments
        .slice()
        .sort((a, b) => (a.distanceA || Number.POSITIVE_INFINITY) - (b.distanceA || Number.POSITIVE_INFINITY))
        .map((segment, index) => {
            const segmentId = `auto-${index}`;
            const nextSegment = {
                ...segment,
                segmentId,
                overlayLabel: buildCompactOverlayLabel(segment),
                showLabel: index < 2,
            };
            state.overlayInteractionSegments.set(segmentId, nextSegment);
            return nextSegment;
        });
    for (const segment of autoSegments) {
        fragments.push(renderOverlayLineSegment(segment, width, height));
    }
    for (const segment of getManualMeasurementOverlaySegments(candidate, currentFrameIndex)) {
        if (segment.type === 'angle') {
            fragments.push(renderOverlayAngleSegment(segment, width, height));
        } else if (segment.type === 'dihedral') {
            fragments.push(renderOverlayDihedralSegment(segment, width, height));
        } else {
            fragments.push(renderOverlayLineSegment(segment, width, height));
        }
    }
    const markup = fragments.filter(Boolean).join('');
    dom.interactionOverlay.innerHTML = markup;
    dom.interactionOverlay.style.display = markup ? 'block' : 'none';
}

function buildCompactOverlayLabel(segment) {
    const meta = INTERACTION_KIND_META[segment?.kind] || INTERACTION_KIND_META.contact;
    const distance = Number.isFinite(segment?.distanceA) ? `${formatNumber(segment.distanceA, 1)}A` : '';
    return [meta.shortLabel, distance].filter(Boolean).join(' ');
}

async function handleInteractionOverlayClick(event) {
    const target = event.target?.closest?.('[data-segment-id]');
    const segmentId = target?.getAttribute?.('data-segment-id');
    if (!segmentId) return;
    const segment = state.overlayInteractionSegments.get(segmentId);
    if (!segment?.residueAtoms?.length) return;
    await flashResidueAtomGroup({
        label: segment.residueLabel || segment.entryLabel || 'contact residue',
        atomGroups: [segment.residueAtoms],
    });
}

async function handleSequenceViewerClick(event) {
    const button = event.target?.closest?.('[data-residue-key]');
    const residueKey = button?.getAttribute?.('data-residue-key');
    if (!residueKey) return;
    const candidate = getSelectedCandidate();
    if (!candidate) return;
    const proteinAtoms = Array.isArray(candidate.proteinTemplateAtoms) ? candidate.proteinTemplateAtoms : [];
    const group = getProteinResidueGroups(candidate, proteinAtoms).find((entry) => entry.key === residueKey);
    if (!group?.atoms?.length) return;
    await flashResidueAtomGroup({
        label: `${group.residueName || 'UNK'} ${group.atoms?.[0]?.chainId || '_'}${group.atoms?.[0]?.residueSeq || '?'}`,
        atomGroups: [group.atoms],
    });
}

async function handleResidueHeatmapClick(event) {
    const cell = event.target?.closest?.('[data-row-index][data-col-index]');
    if (!cell) return;
    const rowIndex = toInt(cell.getAttribute('data-row-index'), -1);
    const colIndex = toInt(cell.getAttribute('data-col-index'), -1);
    if (rowIndex < 0 || colIndex < 0) return;
    const candidate = getSelectedCandidate();
    if (!candidate) return;
    const frameIndex = state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null;
    const analytics = buildPocketAnalytics(candidate, frameIndex);
    const residueA = analytics.residues[rowIndex];
    const residueB = analytics.residues[colIndex];
    if (!residueA || !residueB) return;
    const label = rowIndex === colIndex
        ? `${residueA.residueName || 'UNK'} ${residueA.residueSeq || '?'}`
        : `${residueA.residueName || 'UNK'} ${residueA.residueSeq || '?'} ↔ ${residueB.residueName || 'UNK'} ${residueB.residueSeq || '?'}`;
    await flashResidueAtomGroup({
        label,
        atomGroups: rowIndex === colIndex ? [residueA.atoms] : [residueA.atoms, residueB.atoms],
    });
}

async function flashResidueAtomGroup({ label, atomGroups }) {
    if (!state.viewer || state.viewerMode !== 'single') return;
    if (state.residueHighlightTimer) {
        window.clearTimeout(state.residueHighlightTimer);
        state.residueHighlightTimer = 0;
    }
    await deleteViewerStateRefs([state.residueHighlightRef]);
    const residuePdb = buildResidueHighlightPdb(atomGroups);
    if (!residuePdb) return;
    state.residueHighlightRef = await loadStructureWithRef(
        residuePdb,
        'pdb',
        buildLoadOptionsForPreset({ theme: 'chain-id', representation: 'ball-and-stick' }),
    );
    applyViewerRenderSettings();
    const candidate = getSelectedCandidate();
    const frameIndex = state.trajectorySceneMode === 'trajectory' ? state.trajectoryFrameIndex : null;
    requestAtomGroupLocalFocus(atomGroups, candidate, frameIndex, label || 'Local Focus');
    state.residueHighlightTimer = window.setTimeout(async () => {
        const ref = state.residueHighlightRef;
        state.residueHighlightRef = '';
        state.residueHighlightTimer = 0;
        await deleteViewerStateRefs([ref]);
    }, 1800);
    toast(`residue highlight: ${label || 'residue'}`, 'info');
}

function buildResidueHighlightPdb(atomGroups) {
    const atoms = (atomGroups || [])
        .flat()
        .filter((atom) => atom && !isHydrogenAtom(atom));
    if (!atoms.length) return '';
    return buildPdbFromAtoms(
        atoms.map((atom) => ({
            atom: normalizeProteinAtomForView({ ...atom, chainId: 'R' }, 'R'),
            coords: atomToPoint(atom),
            hetatm: false,
        })),
        ['REMARK INTERACTION_RESIDUE_HIGHLIGHT residue_group'],
    );
}

function projectWorldPointToOverlay(point, width, height) {
    if (!Array.isArray(point) || point.length < 3) return null;
    const camera = state.viewer?.plugin?.canvas3d?.camera;
    const pixelRatio = state.viewer?.plugin?.canvas3d?.webgl?.pixelRatio || window.devicePixelRatio || 1;
    if (!camera?.project) return null;
    const projected = camera.project([0, 0, 0, 0], point);
    if (!projected || !Number.isFinite(projected[0]) || !Number.isFinite(projected[1])) return null;
    const x = projected[0] / pixelRatio;
    const y = height - projected[1] / pixelRatio;
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    return [x, y];
}

async function queueTrajectoryFrameRender(candidate, frameIndex) {
    if (!candidate?.trajectoryData?.frameCount) return;
    if (state.viewerMode !== 'single') return;
    if (getSelectedCandidate()?.index !== candidate.index) return;

    const nextFrame = clamp(frameIndex, 0, candidate.trajectoryData.frameCount - 1);
    if (candidate.renderingTrajectoryFrame && candidate.requestedTrajectoryFrame != null && candidate.requestedTrajectoryFrame !== nextFrame) {
        recordTrajectoryRenderStats(candidate, { coalescedFrameCountDelta: 1 });
    }
    candidate.requestedTrajectoryFrame = nextFrame;
    if (candidate.renderingTrajectoryFrame) return;

    candidate.renderingTrajectoryFrame = true;
    try {
        while (candidate.requestedTrajectoryFrame != null) {
            const nextFrame = candidate.requestedTrajectoryFrame;
            candidate.requestedTrajectoryFrame = null;
            await renderTrajectoryFrameInViewer(candidate, nextFrame);
        }
    } finally {
        candidate.renderingTrajectoryFrame = false;
    }
}

async function renderTrajectoryFrameInViewer(candidate, frameIndex) {
    if (!candidate?.trajectoryData?.frameCount) return;
    if (state.viewerMode !== 'single') {
        recordTrajectoryRenderStats(candidate, { fastPathMissReason: 'viewer_mode' });
        return;
    }
    if (getSelectedCandidate()?.index !== candidate.index) {
        recordTrajectoryRenderStats(candidate, { fastPathMissReason: 'candidate_switch' });
        return;
    }
    if (candidate.lastRenderedTrajectoryFrame === frameIndex) {
        recordTrajectoryRenderStats(candidate, { fastPathMissReason: 'duplicate_frame' });
        return;
    }

    const startedAt = performance.now();
    await ensureTrajectoryRenderable(candidate);
    const fastResult = await tryFastTrajectoryFrameUpdate(candidate, frameIndex);
    if (!fastResult.ok) {
        await loadFocusedCandidateScene(candidate, frameIndex);
    }
    const elapsedMs = performance.now() - startedAt;
    if (fastResult.ok) {
        recordTrajectoryRenderStats(candidate, {
            mode: fastResult.mode || 'none',
            elapsedMs,
            fastPath: true,
            proteinFrameRefresh: fastResult.proteinFrameRefresh,
            proteinColorMode: fastResult.proteinFrameRefresh ? 'dynamic_bfactor_reload' : 'static',
            fastPathMissReason: 'none',
        });
    } else {
        recordTrajectoryRenderStats(candidate, {
            mode: 'full_scene_reload',
            elapsedMs,
            fastPath: false,
            proteinColorMode: shouldDynamicProteinFrameRefresh(candidate) ? 'dynamic_bfactor_reload' : 'static',
            fastPathMissReason: fastResult.missReason || 'no_cache',
        });
    }
    candidate.lastRenderedTrajectoryFrame = frameIndex;
    refreshInteractionOverlayData(candidate, frameIndex);
    const neighborFrames = [frameIndex + 1, frameIndex - 1]
        .filter((value) => value >= 0 && value < candidate.trajectoryData.frameCount);
    for (const neighbor of neighborFrames) {
        if (!candidate.framePdbCache?.has(neighbor)) {
            buildTrajectoryFramePdb(candidate, neighbor);
        }
    }
}

function buildTrajectoryFramePdb(candidate, frameIndex) {
    const trajectory = candidate?.trajectoryData;
    if (!trajectory?.frameCount) return '';

    const clampedFrameIndex = clamp(frameIndex, 0, trajectory.frameCount - 1);
    if (!(candidate.framePdbCache instanceof Map)) {
        candidate.framePdbCache = new Map();
    }
    if (candidate.framePdbCache.has(clampedFrameIndex)) {
        return candidate.framePdbCache.get(clampedFrameIndex);
    }
    const pocketContext = buildPocketContext(candidate, clampedFrameIndex);
    const proteinAtoms = pocketContext.selectedAtoms;
    const ligandAtoms = Array.isArray(candidate?.ligandTemplateAtoms) ? candidate.ligandTemplateAtoms : [];
    const wetlab = getWetlabFocusSummary();
    const lines = [
        `REMARK TRAJECTORY_FRAME ${clampedFrameIndex}`,
        `REMARK TRAJECTORY_INDEX ${trajectory.frameIndices?.[clampedFrameIndex] ?? clampedFrameIndex}`,
        `REMARK VIEWER_CONTEXT ${candidate?.viewerStructureContextMode || 'trajectory'}`,
        `REMARK WETLAB_ACTIONABILITY ${wetlab.actionabilityStatus || 'not_reported'}`,
        `REMARK POCKET_RESIDUES ${pocketContext.fullResidueCount}`,
        `REMARK POCKET_SHELL_RESIDUES ${pocketContext.shellResidueCount}`,
    ];

    let serial = 1;
    if (proteinAtoms.length) {
        for (const atom of proteinAtoms) {
            lines.push(formatPdbAtomLine(normalizeProteinAtomForView(applyProteinBFactorForView(atom, candidate, clampedFrameIndex)), [atom.x, atom.y, atom.z], serial));
            serial += 1;
        }
    } else if (trajectory.proteinContextMeaningful) {
        for (const [proxyIndex, coords] of selectProteinCaProxyPoints(trajectory, clampedFrameIndex).entries()) {
            lines.push(formatPdbAtomLine({
                record: 'ATOM',
                atomName: 'CA',
                residueName: 'GLY',
                chainId: 'P',
                residueSeq: String(proxyIndex + 1),
                insertionCode: '',
                element: 'C',
                bFactor: Array.isArray(trajectory.proteinResidueBFactors) ? trajectory.proteinResidueBFactors[proxyIndex] : undefined,
            }, coords, serial));
            serial += 1;
        }
    }

    if (serial > 1) {
        lines.push('TER');
    }

    const ligandAtomCount = trajectory.ligandAtomCount || 0;
    const fallbackLigandAtoms = buildDefaultLigandTemplateAtoms(ligandAtomCount);
    for (let atomIndex = 0; atomIndex < ligandAtomCount; atomIndex += 1) {
        const base = clampedFrameIndex * ligandAtomCount * 3 + atomIndex * 3;
        const atomTemplate = normalizeLigandAtomForView(ligandAtoms[atomIndex] || fallbackLigandAtoms[atomIndex] || {});
        lines.push(formatPdbAtomLine(atomTemplate, [
            trajectory.ligandCoords[base],
            trajectory.ligandCoords[base + 1],
            trajectory.ligandCoords[base + 2],
        ], serial, true));
        serial += 1;
    }

    lines.push('END');
    const pdbText = lines.join('\n');
    candidate.framePdbCache.set(clampedFrameIndex, pdbText);
    if (candidate.framePdbCache.size > 18) {
        const firstKey = candidate.framePdbCache.keys().next().value;
        candidate.framePdbCache.delete(firstKey);
    }
    return pdbText;
}

function clearViewerOverlay(show = true, message = 'PDB 파일을 로드하면 3D 뷰어가 여기에 표시됩니다') {
    dom.viewerOverlay.style.display = show ? 'block' : 'none';
    if (show) {
        hideViewerAnnotations();
        clearInteractionOverlay();
    }
    if (show) {
        dom.viewerOverlay.innerHTML = `
            <p>${escapeHtml(message)}</p>
            <p class="sub">🧬 현재 Bundle 또는 구조 파일을 로드하세요</p>
        `;
    }
}

function candidateValue(candidate, metric) {
    return {
        mean_min_distance_A: candidate.meanMinDistanceA,
        binding_energy_proxy: candidate.bindingEnergyProxy,
        contact_fraction: candidate.contactFraction,
        stability_score: candidate.stabilityScore,
        commercial_overall_score_v2: candidate.commercialOverallScoreV2,
        trajectory_frames: candidate.trajectoryFrames,
    }[metric];
}

function getSelectedCandidate() {
    return state.selectedIndex >= 0 ? state.candidates[state.selectedIndex] || null : null;
}

function getActiveTrajectoryFrame(candidate) {
    const trajectory = candidate?.trajectoryData;
    if (!trajectory?.frameCount) return null;
    const frameIndex = clamp(state.trajectoryFrameIndex, 0, trajectory.frameCount - 1);
    return {
        ...trajectory.frames[frameIndex],
        frameCount: trajectory.frameCount,
    };
}

function trajectoryStatusLabel(candidate) {
    const mapping = {
        loading: 'loading',
        trajectory_ready: 'npz ready',
        trajectory_npz_available: 'npz advertised',
        trajectory_not_reported: 'not reported',
        trajectory_error: candidate?.trajectoryError ? `error: ${candidate.trajectoryError}` : 'error',
    };
    return mapping[candidate?.trajectoryState] || candidate?.trajectoryState || 'unknown';
}

function isMeaningfulProteinContext(proteinCoords, proteinCount) {
    if (!proteinCoords || !Number.isFinite(proteinCount) || proteinCount < 3) return false;
    for (let index = 0; index < proteinCount * 3; index += 1) {
        if (Math.abs(Number(proteinCoords[index] || 0)) > 1e-6) return true;
    }
    return false;
}

function isLigandAtom(atom) {
    if (!atom) return false;
    return atom.record === 'HETATM' || atom.chainId === 'L' || atom.residueName === 'LIG';
}

function buildDefaultLigandTemplateAtoms(count) {
    return Array.from({ length: Math.max(0, count) }, (_, index) => ({
        record: 'HETATM',
        atomName: `C${index + 1}`.slice(0, 4),
        residueName: 'LIG',
        chainId: 'L',
        residueSeq: '1',
        insertionCode: '',
        element: 'C',
    }));
}

function formatPdbAtomLine(atom, coords, serial, forceHetatm = false) {
    const record = ((forceHetatm || atom?.record === 'HETATM') ? 'HETATM' : 'ATOM').padEnd(6, ' ');
    const atomName = String(atom?.atomName || 'C').slice(0, 4).padEnd(4, ' ');
    const altLoc = String(atom?.altLoc || ' ').slice(0, 1);
    const residueName = String(atom?.residueName || 'LIG').slice(0, 3).padStart(3, ' ');
    const chainId = String(atom?.chainId || 'A').slice(0, 1);
    const residueSeq = String(atom?.residueSeq || '1').slice(-4).padStart(4, ' ');
    const insertionCode = String(atom?.insertionCode || ' ').slice(0, 1);
    const element = String(atom?.element || atom?.atomName || 'C').slice(0, 2).trim().padStart(2, ' ');
    const occupancy = Number.isFinite(Number(atom?.occupancy)) ? Number(atom.occupancy) : 1.0;
    const bFactor = Number.isFinite(Number(atom?.bFactor)) ? Number(atom.bFactor) : 30.0;
    const [x, y, z] = coords.map((value) => Number(value || 0));
    return `${record}${String(serial).padStart(5, ' ')} ${atomName}${altLoc}${residueName} ${chainId}${residueSeq}${insertionCode}   ${x.toFixed(3).padStart(8, ' ')}${y.toFixed(3).padStart(8, ' ')}${z.toFixed(3).padStart(8, ' ')}${occupancy.toFixed(2).padStart(6, ' ')}${bFactor.toFixed(2).padStart(6, ' ')}          ${element}`;
}

function clamp(value, min, max) {
    if (!Number.isFinite(value)) return min;
    return Math.min(max, Math.max(min, value));
}

function parsePdbStructure(text) {
    const atoms = [];
    const lines = String(text || '').split(/\r?\n/);

    for (let index = 0; index < lines.length; index += 1) {
        const line = lines[index];
        if (!/^(ATOM  |HETATM)/.test(line)) continue;
        const x = Number.parseFloat(line.slice(30, 38));
        const y = Number.parseFloat(line.slice(38, 46));
        const z = Number.parseFloat(line.slice(46, 54));
        if (![x, y, z].every(Number.isFinite)) continue;

        atoms.push({
            lineIndex: index,
            record: line.slice(0, 6).trim(),
            atomName: line.slice(12, 16).trim(),
            altLoc: line.slice(16, 17).trim(),
            residueName: line.slice(17, 20).trim(),
            chainId: line.slice(21, 22).trim() || '_',
            residueSeq: line.slice(22, 26).trim(),
            insertionCode: line.slice(26, 27).trim(),
            element: line.slice(76, 78).trim(),
            occupancy: Number.parseFloat(line.slice(54, 60)),
            bFactor: Number.parseFloat(line.slice(60, 66)),
            x,
            y,
            z,
            raw: line,
        });
    }

    return { text, lines, atoms };
}

function normalizeStructureInput(text, format, sourcePath = '') {
    if (format === 'pdb') {
        return { text, format: 'pdb', model: parsePdbStructure(text) };
    }
    if (format === 'sdf') {
        const model = parseSdfStructure(text, sourcePath);
        return {
            text: buildPdbTextFromGenericModel(model),
            format: 'pdb',
            model,
        };
    }
    if (format === 'mol2') {
        const model = parseMol2Structure(text, sourcePath);
        return {
            text: buildPdbTextFromGenericModel(model),
            format: 'pdb',
            model,
        };
    }
    return { text, format, model: null };
}

function parseSdfStructure(text, sourcePath = '') {
    const blocks = String(text || '').split(/\${4}\s*/);
    const block = String(blocks[0] || '').trimEnd();
    const lines = block.split(/\r?\n/);
    if (lines.length < 4) throw new Error(`SDF parse failed: insufficient lines in ${basenameOf(sourcePath) || 'input'}`);
    if (/V3000/i.test(lines[3] || '')) {
        throw new Error('SDF V3000 is not supported yet. Convert to V2000 or PDB/MOL2 first.');
    }

    const counts = lines[3] || '';
    const atomCount = Number.parseInt(counts.slice(0, 3), 10);
    const bondCount = Number.parseInt(counts.slice(3, 6), 10);
    if (!Number.isFinite(atomCount) || !Number.isFinite(bondCount)) {
        throw new Error(`SDF parse failed: invalid counts line in ${basenameOf(sourcePath) || 'input'}`);
    }

    const atoms = [];
    for (let i = 0; i < atomCount; i += 1) {
        const line = lines[4 + i] || '';
        const x = Number.parseFloat(line.slice(0, 10));
        const y = Number.parseFloat(line.slice(10, 20));
        const z = Number.parseFloat(line.slice(20, 30));
        const symbol = line.slice(31, 34).trim() || 'C';
        atoms.push({
            lineIndex: 4 + i,
            record: 'HETATM',
            atomName: `${symbol}${i + 1}`.slice(0, 4),
            altLoc: '',
            residueName: 'LIG',
            chainId: 'L',
            residueSeq: '1',
            insertionCode: '',
            element: symbol.slice(0, 2),
            x,
            y,
            z,
            raw: line,
            sourceIndex: i + 1,
            formalCharge: 0,
        });
    }

    const bonds = [];
    const aromaticIndices = new Set();
    for (let i = 0; i < bondCount; i += 1) {
        const line = lines[4 + atomCount + i] || '';
        const from = Number.parseInt(line.slice(0, 3), 10);
        const to = Number.parseInt(line.slice(3, 6), 10);
        const type = Number.parseInt(line.slice(6, 9), 10);
        if (!Number.isFinite(from) || !Number.isFinite(to)) continue;
        const bond = { from, to, type: Number.isFinite(type) ? type : 1, aromatic: type === 4 };
        bonds.push(bond);
        if (bond.aromatic) {
            aromaticIndices.add(from);
            aromaticIndices.add(to);
        }
    }

    for (const atom of atoms) {
        atom.aromatic = aromaticIndices.has(atom.sourceIndex);
    }

    return {
        text,
        lines,
        atoms,
        bonds,
        sourceFormat: 'sdf',
    };
}

function parseMol2Structure(text, sourcePath = '') {
    const lines = String(text || '').split(/\r?\n/);
    const atomStart = lines.findIndex((line) => /^@<TRIPOS>ATOM/i.test(line));
    const bondStart = lines.findIndex((line) => /^@<TRIPOS>BOND/i.test(line));
    if (atomStart < 0) throw new Error(`MOL2 parse failed: missing ATOM section in ${basenameOf(sourcePath) || 'input'}`);

    const atoms = [];
    for (let i = atomStart + 1; i < lines.length; i += 1) {
        const line = lines[i];
        if (!line || /^@<TRIPOS>/i.test(line)) break;
        const parts = line.trim().split(/\s+/);
        if (parts.length < 6) continue;
        const sourceIndex = Number.parseInt(parts[0], 10);
        const atomName = parts[1] || `C${atoms.length + 1}`;
        const x = Number.parseFloat(parts[2]);
        const y = Number.parseFloat(parts[3]);
        const z = Number.parseFloat(parts[4]);
        const atomType = parts[5] || 'C';
        const element = inferElementFromMol2AtomType(atomType, atomName);
        atoms.push({
            lineIndex: i,
            record: 'HETATM',
            atomName: atomName.slice(0, 4),
            altLoc: '',
            residueName: 'LIG',
            chainId: 'L',
            residueSeq: '1',
            insertionCode: '',
            element,
            x,
            y,
            z,
            raw: line,
            sourceIndex,
            mol2Type: atomType,
            aromatic: /\.ar$/i.test(atomType),
            formalCharge: Number.parseFloat(parts[8] || '0') || 0,
        });
    }

    const bonds = [];
    const aromaticIndices = new Set(atoms.filter((atom) => atom.aromatic).map((atom) => atom.sourceIndex));
    if (bondStart >= 0) {
        for (let i = bondStart + 1; i < lines.length; i += 1) {
            const line = lines[i];
            if (!line || /^@<TRIPOS>/i.test(line)) break;
            const parts = line.trim().split(/\s+/);
            if (parts.length < 4) continue;
            const from = Number.parseInt(parts[1], 10);
            const to = Number.parseInt(parts[2], 10);
            const type = parts[3];
            const aromatic = /^ar$/i.test(type);
            bonds.push({ from, to, type, aromatic });
            if (aromatic) {
                aromaticIndices.add(from);
                aromaticIndices.add(to);
            }
        }
    }

    for (const atom of atoms) {
        atom.aromatic = aromaticIndices.has(atom.sourceIndex);
    }

    return {
        text,
        lines,
        atoms,
        bonds,
        sourceFormat: 'mol2',
    };
}

function inferElementFromMol2AtomType(atomType, atomName = '') {
    const cleanType = String(atomType || '').split('.')[0].replace(/[^A-Za-z]/g, '');
    const token = cleanType || String(atomName || '').replace(/[^A-Za-z]/g, '');
    const normalized = token.slice(0, 2);
    if (!normalized) return 'C';
    const candidate = normalized[0].toUpperCase() + normalized.slice(1).toLowerCase();
    if (candidate.length === 2 && ['Cl', 'Br', 'Si', 'Na', 'Ca', 'Fe', 'Zn', 'Mg'].includes(candidate)) return candidate;
    return candidate[0];
}

function buildPdbTextFromGenericModel(model) {
    const lines = [];
    let serial = 1;
    for (const atom of model?.atoms || []) {
        lines.push(formatPdbAtomLine({
            ...atom,
            record: 'HETATM',
            residueName: atom.residueName || 'LIG',
            chainId: atom.chainId || 'L',
            residueSeq: atom.residueSeq || '1',
        }, [atom.x, atom.y, atom.z], serial, true));
        serial += 1;
    }
    lines.push('END');
    return lines.join('\n');
}

function alignPdbModels(referenceModel, mobileModel, { sideBySide = false } = {}) {
    const anchorResult = buildAnchorPairs(referenceModel, mobileModel);
    if (anchorResult.anchors.length < anchorResult.minimumRequired) {
        throw new Error(`구조 정렬용 anchor가 부족합니다. mode=${anchorResult.anchorMode} matched=${anchorResult.anchors.length}`);
    }

    const transform = computeBestFitTransform(
        anchorResult.anchors.map((item) => item.mobile),
        anchorResult.anchors.map((item) => item.reference),
    );

    let transformedAtoms = mobileModel.atoms.map((atom) => {
        const [x, y, z] = applyTransform([atom.x, atom.y, atom.z], transform.rotation, transform.translation);
        return { ...atom, x, y, z };
    });

    let offsetAppliedA = 0;
    if (sideBySide) {
        const refBox = computeBoundingBox(referenceModel.atoms);
        const mobileBox = computeBoundingBox(transformedAtoms);
        offsetAppliedA = (refBox.maxX - mobileBox.minX) + 12;
        transformedAtoms = transformedAtoms.map((atom) => ({
            ...atom,
            x: atom.x + offsetAppliedA,
        }));
    }

    return {
        anchorCount: anchorResult.anchors.length,
        anchorMode: anchorResult.anchorMode,
        rmsdA: transform.rmsd,
        offsetAppliedA,
        transformedPdbText: rewritePdbCoordinates(mobileModel.lines, transformedAtoms),
    };
}

function buildAnchorPairs(referenceModel, mobileModel) {
    const proteinAnchors = collectAnchors(referenceModel, mobileModel, (atom) => {
        if (atom.altLoc === 'B') return '';
        if (atom.atomName !== 'CA') return '';
        return `${atom.chainId}:${atom.residueSeq}:${atom.insertionCode}:${atom.residueName}`;
    });
    if (proteinAnchors.length >= 3) {
        return {
            anchorMode: 'protein_ca',
            minimumRequired: 3,
            anchors: proteinAnchors,
        };
    }

    const ligandAnchors = collectAnchors(referenceModel, mobileModel, (atom) => {
        if (atom.altLoc === 'B') return '';
        if ((atom.element || atom.atomName || '').toUpperCase().startsWith('H')) return '';
        return `${atom.chainId}:${atom.residueSeq}:${atom.insertionCode}:${atom.residueName}:${atom.atomName}`;
    });
    return {
        anchorMode: 'ligand_atom_fallback',
        minimumRequired: 2,
        anchors: ligandAnchors,
    };
}

function collectAnchors(referenceModel, mobileModel, keyFn) {
    const referenceAnchors = new Map();
    for (const atom of referenceModel.atoms) {
        const key = keyFn(atom);
        if (!key) continue;
        referenceAnchors.set(key, [atom.x, atom.y, atom.z]);
    }

    const anchors = [];
    for (const atom of mobileModel.atoms) {
        const key = keyFn(atom);
        if (!key) continue;
        const reference = referenceAnchors.get(key);
        if (!reference) continue;
        anchors.push({
            reference,
            mobile: [atom.x, atom.y, atom.z],
        });
    }
    return anchors;
}

function computeBestFitTransform(mobilePoints, referencePoints) {
    const mobileCenter = computeCentroid(mobilePoints);
    const referenceCenter = computeCentroid(referencePoints);

    const covariance = [
        [0, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
    ];

    for (let index = 0; index < mobilePoints.length; index += 1) {
        const mobile = subtractVector(mobilePoints[index], mobileCenter);
        const reference = subtractVector(referencePoints[index], referenceCenter);
        for (let row = 0; row < 3; row += 1) {
            for (let col = 0; col < 3; col += 1) {
                covariance[row][col] += mobile[row] * reference[col];
            }
        }
    }

    const [sxx, sxy, sxz] = covariance[0];
    const [syx, syy, syz] = covariance[1];
    const [szx, szy, szz] = covariance[2];

    const hornMatrix = [
        [sxx + syy + szz, syz - szy, szx - sxz, sxy - syx],
        [syz - szy, sxx - syy - szz, sxy + syx, szx + sxz],
        [szx - sxz, sxy + syx, -sxx + syy - szz, syz + szy],
        [sxy - syx, szx + sxz, syz + szy, -sxx - syy + szz],
    ];

    const quaternion = dominantEigenvector(hornMatrix);
    const rotation = quaternionToRotationMatrix(quaternion);
    const translation = subtractVector(referenceCenter, applyRotation(mobileCenter, rotation));

    let errorSum = 0;
    for (let index = 0; index < mobilePoints.length; index += 1) {
        const moved = applyTransform(mobilePoints[index], rotation, translation);
        errorSum += squaredDistance(moved, referencePoints[index]);
    }

    return {
        rotation,
        translation,
        rmsd: Math.sqrt(errorSum / mobilePoints.length),
    };
}

function computeCentroid(points) {
    const center = [0, 0, 0];
    for (const point of points) {
        center[0] += point[0];
        center[1] += point[1];
        center[2] += point[2];
    }
    return center.map((value) => value / points.length);
}

function subtractVector(a, b) {
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function applyTransform(point, rotation, translation) {
    const rotated = applyRotation(point, rotation);
    return [
        rotated[0] + translation[0],
        rotated[1] + translation[1],
        rotated[2] + translation[2],
    ];
}

function applyRotation(point, rotation) {
    return [
        rotation[0][0] * point[0] + rotation[0][1] * point[1] + rotation[0][2] * point[2],
        rotation[1][0] * point[0] + rotation[1][1] * point[1] + rotation[1][2] * point[2],
        rotation[2][0] * point[0] + rotation[2][1] * point[1] + rotation[2][2] * point[2],
    ];
}

function squaredDistance(a, b) {
    const dx = a[0] - b[0];
    const dy = a[1] - b[1];
    const dz = a[2] - b[2];
    return dx * dx + dy * dy + dz * dz;
}

function distanceBetween(a, b) {
    if (!isVec3Like(a) || !isVec3Like(b)) return Number.NaN;
    return Math.sqrt(squaredDistance(a, b));
}

function angleBetween(a, b, c) {
    if (!isVec3Like(a) || !isVec3Like(b) || !isVec3Like(c)) return Number.NaN;
    const ba = [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
    const bc = [c[0] - b[0], c[1] - b[1], c[2] - b[2]];
    const normA = Math.hypot(...ba);
    const normC = Math.hypot(...bc);
    if (!normA || !normC) return Number.NaN;
    const dot = ba[0] * bc[0] + ba[1] * bc[1] + ba[2] * bc[2];
    const cosine = clamp(dot / (normA * normC), -1, 1);
    return Math.acos(cosine) * (180 / Math.PI);
}

function dihedralBetween(a, b, c, d) {
    if (!isVec3Like(a) || !isVec3Like(b) || !isVec3Like(c) || !isVec3Like(d)) return Number.NaN;
    const b1 = subtractVector(b, a);
    const b2 = subtractVector(c, b);
    const b3 = subtractVector(d, c);
    const n1 = normalizeVec3(crossVec3(b1, b2));
    const n2 = normalizeVec3(crossVec3(b2, b3));
    const m1 = crossVec3(n1, normalizeVec3(b2));
    const x = dotVec3(n1, n2);
    const y = dotVec3(m1, n2);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return Number.NaN;
    return Math.atan2(y, x) * (180 / Math.PI);
}

function isVec3Like(value) {
    return value && Number.isFinite(value[0]) && Number.isFinite(value[1]) && Number.isFinite(value[2]);
}

function dominantEigenvector(matrix) {
    let vector = [1, 0, 0, 0];
    for (let iter = 0; iter < 32; iter += 1) {
        const next = [
            matrix[0][0] * vector[0] + matrix[0][1] * vector[1] + matrix[0][2] * vector[2] + matrix[0][3] * vector[3],
            matrix[1][0] * vector[0] + matrix[1][1] * vector[1] + matrix[1][2] * vector[2] + matrix[1][3] * vector[3],
            matrix[2][0] * vector[0] + matrix[2][1] * vector[1] + matrix[2][2] * vector[2] + matrix[2][3] * vector[3],
            matrix[3][0] * vector[0] + matrix[3][1] * vector[1] + matrix[3][2] * vector[2] + matrix[3][3] * vector[3],
        ];
        const norm = Math.hypot(...next) || 1;
        vector = next.map((value) => value / norm);
    }
    return vector;
}

function quaternionToRotationMatrix(quaternion) {
    const [w, x, y, z] = quaternion;
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ];
}

function computeBoundingBox(atoms) {
    return atoms.reduce((box, atom) => ({
        minX: Math.min(box.minX, atom.x),
        maxX: Math.max(box.maxX, atom.x),
    }), { minX: Number.POSITIVE_INFINITY, maxX: Number.NEGATIVE_INFINITY });
}

function rewritePdbCoordinates(lines, atoms) {
    const patched = [...lines];
    for (const atom of atoms) {
        const line = patched[atom.lineIndex] || atom.raw;
        const xyz = [
            atom.x.toFixed(3).padStart(8),
            atom.y.toFixed(3).padStart(8),
            atom.z.toFixed(3).padStart(8),
        ];
        patched[atom.lineIndex] = `${line.slice(0, 30)}${xyz[0]}${xyz[1]}${xyz[2]}${line.slice(54)}`;
    }
    return patched.join('\n');
}

function kpiCard(label, value, extraClass = '') {
    return `
        <div class="kpi-card ${extraClass}">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(String(value))}</strong>
        </div>
    `;
}

function isStructureFile(name) {
    return /\.(pdb|cif|mmcif|ent|xyz|sdf|sd|mol2)$/i.test(name || '');
}

function isVolumeMapFile(name) {
    return /\.(dx|cube|cub)$/i.test(name || '');
}

function inferVolumeFormat(pathLike) {
    const lower = String(pathLike || '').toLowerCase();
    if (lower.endsWith('.dx')) return 'dx';
    if (lower.endsWith('.cube') || lower.endsWith('.cub')) return 'cube';
    return '';
}

function basenameOf(pathLike) {
    return String(pathLike || '').replace(/\\/g, '/').split('/').pop() || '';
}

function arrayFromAny(...values) {
    for (const value of values) {
        if (Array.isArray(value)) {
            return uniqueTruthy(value);
        }
        if (typeof value === 'string' && value.trim()) {
            return uniqueTruthy(value.split(/[|,;]/g).map((token) => token.trim()));
        }
    }
    return [];
}

function splitCodeText(value) {
    if (!String(value || '').trim()) return [];
    return uniqueTruthy(String(value).split(/[|,;]/g).map((token) => token.trim()));
}

function toneForStatus(value) {
    const normalized = String(value || '').trim().toLowerCase();
    if (!normalized || normalized === 'not_reported') return 'muted';
    if (['pass', 'passed', 'ready', 'available', 'aligned_replace', 'tier1_gold'].includes(normalized)) return 'good';
    if (
        normalized.includes('block')
        || normalized.includes('fail')
        || normalized.includes('defer')
        || normalized.includes('critical')
        || normalized.includes('review_only')
    ) return 'bad';
    if (
        normalized.includes('warn')
        || normalized.includes('near')
        || normalized.includes('borderline')
        || normalized.includes('semi_hard')
        || normalized.includes('review')
        || normalized.includes('silver')
        || normalized.includes('bronze')
    ) return 'warn';
    return 'info';
}

function classifyContactState(candidate, frame) {
    const contact = toFloat(candidate?.contactFraction);
    const distance = Number.isFinite(frame?.minDistanceA) ? frame.minDistanceA : toFloat(candidate?.meanMinDistanceA);
    if (Number.isFinite(distance) && distance <= 2.5 && contact >= 0.5) {
        return { label: 'tight_contact', tone: 'good' };
    }
    if (Number.isFinite(distance) && distance <= 3.0 && contact >= 0.35) {
        return { label: 'engaged_contact', tone: 'warn' };
    }
    return { label: 'weak_contact', tone: 'bad' };
}

function overlayPill(label, value, tone = 'muted') {
    return `
        <span class="annotation-pill ${escapeHtml(tone)}">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(String(value || '-'))}</strong>
        </span>
    `;
}

function annotationMetric(label, value) {
    return `
        <div class="annotation-metric">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(String(value || '-'))}</strong>
        </div>
    `;
}

function annotationList(items, emptyText) {
    if (!items.length) {
        return `<div class="annotation-empty">${escapeHtml(emptyText)}</div>`;
    }
    return `<ul class="annotation-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function firstTruthy(...values) {
    for (const value of values) {
        if (String(value || '').trim()) return String(value).trim();
    }
    return '';
}

function uniqueTruthy(values) {
    const seen = new Set();
    const output = [];
    for (const value of values.flat()) {
        const normalized = String(value || '').trim();
        if (!normalized || seen.has(normalized)) continue;
        seen.add(normalized);
        output.push(normalized);
    }
    return output;
}

function joinTruthy(values, sep = ' | ') {
    return values.filter((value) => String(value || '').trim()).join(sep);
}

function toFloat(value, fallback = NaN) {
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
}

function toNullableBool(...values) {
    for (const value of values) {
        if (value === '' || value == null) continue;
        if (typeof value === 'boolean') return value;
        if (typeof value === 'number') return value !== 0;
        const normalized = String(value).trim().toLowerCase();
        if (!normalized) continue;
        if (['1', 'true', 't', 'yes', 'y', 'ready', 'pass', 'passed', 'available'].includes(normalized)) return true;
        if (['0', 'false', 'f', 'no', 'n', 'blocked', 'fail', 'failed', 'missing'].includes(normalized)) return false;
    }
    return null;
}

function toBool(...values) {
    return Boolean(toNullableBool(...values));
}

function boolLabel(value) {
    if (value == null) return 'not_reported';
    return value ? 'pass' : 'blocked';
}

function toInt(value, fallback = 0) {
    const num = parseInt(value, 10);
    return Number.isFinite(num) ? num : fallback;
}

function formatNumber(value, digits = 2) {
    return Number.isFinite(value) ? Number(value).toFixed(digits) : '-';
}

function parseHexColor(hex) {
    return parseInt(String(hex || '#ffffff').replace('#', ''), 16);
}

function toast(message, type = 'info') {
    const node = document.createElement('div');
    node.className = `toast toast-${type}`;
    node.textContent = message;
    dom.toastContainer.appendChild(node);
    requestAnimationFrame(() => node.classList.add('show'));
    window.setTimeout(() => {
        node.classList.remove('show');
        window.setTimeout(() => node.remove(), 180);
    }, 2600);
}
