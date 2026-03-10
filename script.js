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

    function activate(platform) {
        tabs.forEach(t => t.classList.toggle('active', t.dataset.platform === platform));
        contents.forEach(c => c.classList.toggle('active', c.dataset.platform === platform));

        // Update download button to match selected platform
        btn.textContent = OS_LABELS[platform] || OS_LABELS.linux;
        if (urls) {
            btn.href = urls[platform] || urls.linux;
        }
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', () => activate(tab.dataset.platform));
    });

    return activate;
}

// ── Fetch latest release from Codeberg API ──
const REPO_API = 'https://codeberg.org/api/v1/repos/skoomabwoy/piano-midi-viewer/releases/latest';

const FALLBACK_TAG = 'v9.1.0';
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

async function fetchDownloadURLs() {
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

        // Update version from API (hero + footer)
        const version = data.tag_name;
        if (version) {
            const heroVersion = document.getElementById('hero-version');
            if (heroVersion) heroVersion.textContent = version;
            const footer = document.querySelector('footer p');
            if (footer) {
                footer.innerHTML = footer.innerHTML.replace(/v[\d.]+/, version);
            }
        }

        return urls;
    } catch (e) {
        console.warn('Could not fetch latest release, using fallback URLs:', e.message);
        return null;
    }
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

// ── Init ──
document.addEventListener('DOMContentLoaded', async () => {
    const os = detectOS();
    const urls = (await fetchDownloadURLs()) || getFallbackURLs();
    const activate = initTabs(urls);
    activate(os);

    equalizePlatformHeights();
    window.addEventListener('resize', equalizePlatformHeights);

    initCopyButtons();
});
