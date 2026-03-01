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
function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.platform-content');

    function activate(platform) {
        tabs.forEach(t => t.classList.toggle('active', t.dataset.platform === platform));
        contents.forEach(c => c.classList.toggle('active', c.dataset.platform === platform));
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', () => activate(tab.dataset.platform));
    });

    return activate;
}

// ── Fetch latest release from Codeberg API ──
const REPO_API = 'https://codeberg.org/api/v1/repos/skoomabwoy/piano-midi-viewer/releases/latest';

// Fallback URLs if API fails (hardcoded to a known good version)
const FALLBACK_TAG = 'v8.6.2';
const FALLBACK_BASE = `https://codeberg.org/skoomabwoy/piano-midi-viewer/releases/download/${FALLBACK_TAG}/`;

const FILE_NAMES = {
    windows: 'WIN_PianoMIDIViewer.exe',
    macos: 'MAC_PianoMIDIViewer.dmg',
    linux: 'LINUX_PianoMIDIViewer.AppImage'
};

async function fetchDownloadURLs() {
    try {
        const resp = await fetch(REPO_API);
        if (!resp.ok) throw new Error(`API returned ${resp.status}`);
        const data = await resp.json();

        // Build URL map from release assets
        const urls = {};
        for (const asset of data.assets || []) {
            for (const [os, fileName] of Object.entries(FILE_NAMES)) {
                if (asset.name === fileName) {
                    urls[os] = asset.browser_download_url;
                }
            }
        }

        // Update footer version from API
        const version = data.tag_name;
        if (version) {
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

function applyDownloadURLs(urls) {
    document.querySelectorAll('.btn-download[data-file]').forEach(link => {
        const fileName = link.dataset.file;
        for (const [os, name] of Object.entries(FILE_NAMES)) {
            if (name === fileName && urls[os]) {
                link.href = urls[os];
            }
        }
    });
}

function getFallbackURLs() {
    const urls = {};
    for (const [os, fileName] of Object.entries(FILE_NAMES)) {
        urls[os] = FALLBACK_BASE + fileName;
    }
    return urls;
}

// ── Init ──
document.addEventListener('DOMContentLoaded', async () => {
    const os = detectOS();
    const activate = initTabs();
    activate(os);

    // Fetch real URLs, fall back to hardcoded if API fails
    const urls = (await fetchDownloadURLs()) || getFallbackURLs();
    applyDownloadURLs(urls);
});
