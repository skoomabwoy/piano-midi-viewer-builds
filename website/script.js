// ── OS Detection ──
function detectOS() {
    const ua = navigator.userAgent.toLowerCase();
    const platform = navigator.platform?.toLowerCase() || '';

    if (ua.includes('win') || platform.includes('win')) return 'windows';
    if (ua.includes('mac') || platform.includes('mac')) return 'macos';
    if (ua.includes('linux') || platform.includes('linux')) return 'linux';
    return 'linux'; // default fallback
}

// ── Platform Tabs ──
function initTabs(urls) {
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.platform-content');
    const btn = document.getElementById('hero-download-btn');

    if (!tabs.length) return () => {};

    function activate(platform) {
        tabs.forEach(t => t.classList.toggle('active', t.dataset.platform === platform));
        contents.forEach(c => c.classList.toggle('active', c.dataset.platform === platform));

        if (btn) {
            btn.textContent = OS_LABELS[platform] || OS_LABELS.linux;
            if (urls) btn.href = urls[platform] || urls.linux;
        }
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', () => activate(tab.dataset.platform));
    });

    return activate;
}

// ── Fetch latest release from Codeberg API ──
const REPO_API = 'https://codeberg.org/api/v1/repos/skoomabwoy/piano-midi-viewer/releases/latest';

const FALLBACK_TAG = 'v9.3.2';
const FALLBACK_BASE = `https://codeberg.org/skoomabwoy/piano-midi-viewer/releases/download/${FALLBACK_TAG}/`;

const FILE_NAMES = {
    windows: 'WIN_PianoMIDIViewer.exe',
    macos: 'MAC_PianoMIDIViewer.dmg',
    linux: 'LINUX_PianoMIDIViewer.AppImage'
};

const OS_LABELS = {
    windows: 'Download for Windows',
    macos: 'Download for macOS',
    linux: 'Download for Linux'
};

async function fetchLatestRelease() {
    try {
        const resp = await fetch(REPO_API);
        if (!resp.ok) throw new Error(`API returned ${resp.status}`);
        const data = await resp.json();

        const urls = {};
        for (const asset of data.assets || []) {
            for (const [os, fileName] of Object.entries(FILE_NAMES)) {
                if (asset.name === fileName) {
                    urls[os] = asset.browser_download_url;
                }
            }
        }

        return { version: data.tag_name || null, urls };
    } catch (e) {
        console.warn('Could not fetch latest release, using fallback:', e.message);
        return null;
    }
}

// Single place that writes the version — fills every .js-version slot on the page
// (hero + footers), so the version text lives in exactly one variable, not in markup.
function applyVersion(version) {
    document.querySelectorAll('.js-version').forEach(el => { el.textContent = version; });
}

function getFallbackURLs() {
    const urls = {};
    for (const [os, fileName] of Object.entries(FILE_NAMES)) {
        urls[os] = FALLBACK_BASE + fileName;
    }
    return urls;
}

// ── Equalize platform content heights ──
function equalizePlatformHeights() {
    const container = document.querySelector('.platform-container');
    const contents = document.querySelectorAll('.platform-content');
    if (!container || !contents.length) return;

    // Temporarily show all, measure, find tallest
    container.style.minHeight = 'auto';
    let maxHeight = 0;
    contents.forEach(c => {
        c.style.display = 'block';
        c.style.position = 'absolute';
        c.style.visibility = 'hidden';
        maxHeight = Math.max(maxHeight, c.offsetHeight);
    });

    // Reset and apply
    contents.forEach(c => {
        c.style.display = '';
        c.style.position = '';
        c.style.visibility = '';
    });
    container.style.minHeight = maxHeight + 'px';
}

// ── Copy to Clipboard ──
function initCopyButtons() {
    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const code = btn.closest('.command-wrapper').querySelector('.command').textContent;
            navigator.clipboard.writeText(code).then(() => {
                btn.classList.add('copied');
                setTimeout(() => btn.classList.remove('copied'), 1500);
            });
        });
    });
}

// ── Lightbox ──
function initLightbox() {
    const overlay = document.createElement('div');
    overlay.className = 'lightbox-overlay';
    const img = document.createElement('img');
    img.className = 'lightbox-img';
    overlay.appendChild(img);
    document.body.appendChild(overlay);

    document.querySelectorAll('.app-steps-img img, .guide-step-img img, .guide-explainer-img img').forEach(el => {
        el.addEventListener('click', () => {
            img.src = el.src;
            img.alt = el.alt;
            overlay.classList.add('active');
        });
    });

    overlay.addEventListener('click', () => overlay.classList.remove('active'));
    document.addEventListener('keydown', e => { if (e.key === 'Escape') overlay.classList.remove('active'); });
}

// ── Contact form (Web3Forms, no backend needed) ──
function initContactForm() {
    const form = document.getElementById('contact-form');
    if (!form) return;

    const status = document.getElementById('contact-status');
    const submitBtn = form.querySelector('.contact-submit');

    function setStatus(text, kind) {
        status.textContent = text;
        status.className = 'contact-status' + (kind ? ' ' + kind : '');
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Guard: remind the maintainer if the access key hasn't been set yet.
        const key = form.querySelector('[name="access_key"]').value;
        if (!key || key.includes('YOUR_WEB3FORMS')) {
            setStatus('Contact form isn’t set up yet (missing Web3Forms access key).', 'error');
            return;
        }

        setStatus('Sending…', '');
        submitBtn.disabled = true;

        try {
            const resp = await fetch('https://api.web3forms.com/submit', {
                method: 'POST',
                body: new FormData(form),
            });
            const data = await resp.json();
            if (data.success) {
                form.reset();
                setStatus('✓ Thanks! Your message has been sent.', 'success');
            } else {
                setStatus('✗ ' + (data.message || 'Something went wrong. Please try again.'), 'error');
            }
        } catch {
            setStatus('✗ Network error — please check your connection and try again.', 'error');
        } finally {
            submitBtn.disabled = false;
        }
    });
}

// ── Init ──
document.addEventListener('DOMContentLoaded', async () => {
    const os = detectOS();

    // Resolve the version + download URLs from the latest release, falling back
    // to FALLBACK_TAG (injected from the app's VERSION at deploy time) if the
    // API is unreachable. One resolved version drives every .js-version slot.
    const release = await fetchLatestRelease();
    applyVersion((release && release.version) || FALLBACK_TAG);
    const urls = (release && release.urls) || getFallbackURLs();

    const activate = initTabs(urls);
    activate(os);

    equalizePlatformHeights();
    window.addEventListener('resize', equalizePlatformHeights);

    initCopyButtons();
    initLightbox();
    initContactForm();
});
