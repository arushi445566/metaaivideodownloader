// If hosting the frontend on Hostinger and backend on Render, set this to your Render URL:
// const BACKEND_URL = 'https://meta-ai-video-downloader-backend.onrender.com';
// If hosting everything on Render, keep it empty:
const BACKEND_URL = '';

document.addEventListener('DOMContentLoaded', () => {
    // Homepage Elements
    const downloadForm = document.getElementById('downloadForm');
    const videoUrlInput = document.getElementById('videoUrl');
    const pasteBtn = document.getElementById('pasteBtn');
    
    // Status Elements
    const statusContainer = document.getElementById('statusContainer');
    const loaderIcon = document.getElementById('loaderIcon');
    const statusMessage = document.getElementById('statusMessage');
    const progressWrapper = document.getElementById('progressWrapper');
    const progressFill = document.getElementById('progressFill');
    const resultActions = document.getElementById('resultActions');
    
    // Video Preview & Quality Options Elements
    const previewWrapper = document.getElementById('previewWrapper');
    const videoPreview = document.getElementById('videoPreview');
    const qualityOptionsContainer = document.getElementById('qualityOptionsContainer');
    const formatsList = document.getElementById('formatsList');
    
    // Action buttons
    const downloadFileBtn = document.getElementById('downloadFileBtn');
    const downloadAnotherBtn = document.getElementById('downloadAnotherBtn');

    // Handle Paste button (Conditional check)
    if (pasteBtn && videoUrlInput) {
        pasteBtn.addEventListener('click', async () => {
            try {
                const text = await navigator.clipboard.readText();
                videoUrlInput.value = text;
            } catch (err) {
                alert('Failed to read clipboard contents. Please paste manually.');
            }
        });
    }

    // Handle Form Submission (Conditional check)
    if (downloadForm) {
        downloadForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            const url = videoUrlInput.value.trim();
            if (!url) return;

            // Basic validation
            if (!url.startsWith('http://') && !url.startsWith('https://')) {
                alert('Please enter a valid URL starting with http:// or https://');
                return;
            }

            startDownloadProcess();
        });
    }

    // Reset UI state to start new download (Conditional check)
    if (downloadAnotherBtn) {
        downloadAnotherBtn.addEventListener('click', () => {
            if (videoUrlInput) videoUrlInput.value = '';
            if (statusContainer) statusContainer.classList.add('hidden');
            if (resultActions) resultActions.classList.add('hidden');
            if (progressWrapper) progressWrapper.classList.add('hidden');
            if (loaderIcon) loaderIcon.classList.add('hidden');
            
            // Reset Video Preview & Quality Options
            if (previewWrapper) previewWrapper.classList.add('hidden');
            if (videoPreview) {
                videoPreview.pause();
                videoPreview.src = '';
            }
            if (qualityOptionsContainer) qualityOptionsContainer.classList.add('hidden');
            if (formatsList) formatsList.innerHTML = '';
            
            if (progressFill) {
                progressFill.style.width = '0%';
                progressFill.style.transition = 'none'; // reset without animation
                
                // Let transition clear before re-enabling
                setTimeout(() => {
                    progressFill.style.transition = 'width 0.3s ease';
                }, 50);
            }
        });
    }

    // Actual Download Process via Python Backend
    async function startDownloadProcess() {
        if (!videoUrlInput) return;
        const url = videoUrlInput.value.trim();
        
        // Show status container
        if (statusContainer) statusContainer.classList.remove('hidden');
        if (resultActions) resultActions.classList.add('hidden');
        if (previewWrapper) previewWrapper.classList.add('hidden');
        if (qualityOptionsContainer) qualityOptionsContainer.classList.add('hidden');
        
        // Show loader
        if (loaderIcon) loaderIcon.classList.remove('hidden');
        if (progressWrapper) progressWrapper.classList.add('hidden');
        if (statusMessage) {
            statusMessage.textContent = 'Extracting video formats...';
            statusMessage.style.color = 'var(--text-secondary)';
        }

        try {
            const response = await fetch(`${BACKEND_URL}/api/download`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: url })
            });

            const data = await response.json();

            if (data.success && data.download_url) {
                // Hide loader, show success
                if (loaderIcon) loaderIcon.classList.add('hidden');
                showSuccessState(data.formats, data.title, data.download_url);
            } else {
                throw new Error(data.error || 'Failed to extract video.');
            }

        } catch (error) {
            if (loaderIcon) loaderIcon.classList.add('hidden');
            if (statusMessage) {
                statusMessage.textContent = 'Error: ' + error.message;
                statusMessage.style.color = 'var(--error)';
            }
            // Show retry action
            if (resultActions) resultActions.classList.remove('hidden');
            if (downloadFileBtn) downloadFileBtn.classList.add('hidden'); // Hide standard download button
        }
    }

    function showSuccessState(formats, title, defaultDownloadUrl) {
        if (statusMessage) {
            statusMessage.textContent = 'Video successfully extracted! Preview ready.';
            statusMessage.style.color = 'var(--success)';
        }
        if (progressWrapper) progressWrapper.classList.add('hidden');
        
        // Setup Video Preview
        if (defaultDownloadUrl && videoPreview && previewWrapper) {
            let previewUrl = defaultDownloadUrl;
            if (previewUrl.startsWith('/')) {
                previewUrl = `${BACKEND_URL}${previewUrl}`;
            }
            videoPreview.src = previewUrl;
            previewWrapper.classList.remove('hidden');
            videoPreview.muted = true;
            videoPreview.play().catch(e => console.log('Autoplay muted blocked:', e));
        }

        // Render Dynamic Quality Option Buttons
        if (formatsList && qualityOptionsContainer) {
            formatsList.innerHTML = '';
            if (formats && formats.length > 0) {
                formats.forEach(fmt => {
                    const btn = document.createElement('button');
                    btn.className = 'format-btn';
                    btn.type = 'button';
                    
                    btn.innerHTML = `
                        <div class="format-btn-info">
                            <span>${fmt.quality}</span>
                            <span class="format-btn-resolution">Format: ${fmt.ext.toUpperCase()} • Resolution: ${fmt.resolution}</span>
                        </div>
                        <svg class="format-btn-icon" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                        </svg>
                    `;
                    
                    btn.addEventListener('click', () => {
                        let downloadUrl = fmt.url;
                        if (downloadUrl.startsWith('/api/download/file')) {
                            downloadUrl = `${BACKEND_URL}${downloadUrl}`;
                        }
                        if (fmt.url.includes('/api/download/file')) {
                            if (statusMessage && loaderIcon) {
                                statusMessage.textContent = 'Downloading and compiling highest quality streams on the server... (this may take a few seconds)';
                                statusMessage.style.color = 'var(--primary)';
                                loaderIcon.classList.remove('hidden');
                                
                                setTimeout(() => {
                                    statusMessage.textContent = 'Video successfully extracted! Preview ready.';
                                    statusMessage.style.color = 'var(--success)';
                                    loaderIcon.classList.add('hidden');
                                }, 8000);
                            }
                        }
                        triggerDownload(downloadUrl, `${title}_${fmt.resolution}.${fmt.ext}`);
                    });
                    
                    formatsList.appendChild(btn);
                });
                qualityOptionsContainer.classList.remove('hidden');
            }
        }
        
        if (resultActions) resultActions.classList.remove('hidden');
        if (downloadFileBtn) downloadFileBtn.classList.add('hidden'); // Hide original download button
    }

    function triggerDownload(downloadUrl, filename) {
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = filename;
        a.target = '_blank';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    // Cookie Consent Banner Logic
    const cookieConsent = document.getElementById('cookieConsent');
    const acceptCookiesBtn = document.getElementById('acceptCookiesBtn');
    const declineCookiesBtn = document.getElementById('declineCookiesBtn');
    
    if (cookieConsent && acceptCookiesBtn && declineCookiesBtn) {
        const consentAccepted = localStorage.getItem('cookieConsentAccepted');
        const consentDeclined = localStorage.getItem('cookieConsentDeclined');
        
        if (!consentAccepted && !consentDeclined) {
            cookieConsent.classList.remove('hidden');
        }
        
        acceptCookiesBtn.addEventListener('click', () => {
            localStorage.setItem('cookieConsentAccepted', 'true');
            cookieConsent.classList.add('hidden');
        });
        
        declineCookiesBtn.addEventListener('click', () => {
            localStorage.setItem('cookieConsentDeclined', 'true');
            cookieConsent.classList.add('hidden');
        });
    }

    // Contact Form Logic
    const contactForm = document.getElementById('contactForm');
    const contactStatus = document.getElementById('contactStatus');
    const contactStatusMessage = document.getElementById('contactStatusMessage');
    
    if (contactForm && contactStatus && contactStatusMessage) {
        contactForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            contactStatus.classList.remove('hidden');
            contactStatusMessage.textContent = 'Thank you for reaching out! Your message has been sent successfully.';
            contactStatusMessage.style.color = 'var(--success)';
            
            contactForm.reset();
        });
    }
});
