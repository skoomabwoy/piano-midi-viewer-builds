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

const FALLBACK_TAG = 'v8.6.2';
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

function getFallbackURLs() {
    const urls = {};
    for (const [os, fileName] of Object.entries(FILE_NAMES)) {
        urls[os] = FALLBACK_BASE + fileName;
    }
    return urls;
}

// ── Hero Download Button + Alt Links ──
function initHeroButton(os, urls, activate) {
    const btn = document.getElementById('hero-download-btn');
    btn.textContent = OS_LABELS[os] || OS_LABELS.linux;
    btn.href = urls[os] || urls.linux;

    // Hide detected OS from "also available" links, set URLs on the others
    document.querySelectorAll('.alt-download').forEach(link => {
        const platform = link.dataset.platform;
        if (platform === os) {
            // Hide this link and surrounding text (comma/and)
            link.style.display = 'none';
        } else {
            link.href = urls[platform] || '#';
            link.addEventListener('click', (e) => {
                // Let the browser follow the download href naturally
                // but also switch the install tab
                activate(platform);
            });
        }
    });

    // Clean up "also available" text (remove double commas, leading commas, etc.)
    const container = document.querySelector('.also-available');
    if (container) {
        // Rebuild text with only visible links
        const visibleLinks = [...container.querySelectorAll('.alt-download')]
            .filter(l => l.style.display !== 'none');
        if (visibleLinks.length === 2) {
            container.innerHTML = 'Also available for ';
            container.appendChild(visibleLinks[0]);
            container.appendChild(document.createTextNode(' and '));
            container.appendChild(visibleLinks[1]);
        }
    }
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

// ── Init ──
document.addEventListener('DOMContentLoaded', async () => {
    const os = detectOS();
    const activate = initTabs();
    activate(os);

    equalizePlatformHeights();
    window.addEventListener('resize', equalizePlatformHeights);

    const urls = (await fetchDownloadURLs()) || getFallbackURLs();
    initHeroButton(os, urls, activate);
});
