// Configuration
const API_ENDPOINT = '/process-pdf-upload-redis';
const REQUEST_TIMEOUT = 60000; // 60 seconds
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

// Animation Configuration
const ANIMATION_CONFIG = {
    stages: [
        { name: 'Uploading document', duration: 8000, progressStart: 0, progressEnd: 25 },
        { name: 'Extracting text', duration: 8000, progressStart: 25, progressEnd: 50 },
        { name: 'AI Processing', duration: 8000, progressStart: 50, progressEnd: 90 },
        { name: 'Generating results', duration: 8000, progressStart: 90, progressEnd: 100 }
    ],
    particleCount: 25
};

// State Management (in-memory)
let selectedFile = null;
let currentResponse = null;
let isProcessing = false;
let processingStartTime = null;
let animationInterval = null;
let stageTimeout = null;

// DOM Elements
const elements = {
    uploadZone: document.getElementById('uploadZone'),
    fileInput: document.getElementById('fileInput'),
    fileInfo: document.getElementById('fileInfo'),
    fileName: document.getElementById('fileName'),
    fileSize: document.getElementById('fileSize'),
    removeFile: document.getElementById('removeFile'),
    processBtn: document.getElementById('processBtn'),
    processingOverlay: document.getElementById('processingOverlay'),
    spinnerPercentage: document.getElementById('spinnerPercentage'),
    processingStage: document.getElementById('processingStage'),
    progressBar: document.getElementById('progressBar'),
    particles: document.getElementById('particles'),
    resultsCard: document.getElementById('resultsCard'),
    jsonViewer: document.getElementById('jsonViewer'),
    copyBtn: document.getElementById('copyBtn'),
    downloadBtn: document.getElementById('downloadBtn'),
    resetBtn: document.getElementById('resetBtn'),
    processingTime: document.getElementById('processingTime'),
    fieldCount: document.getElementById('fieldCount'),
    notificationContainer: document.getElementById('notification-container')
};

// Initialize Application
function init() {
    setupEventListeners();
    createParticles();
    addSVGGradient();
}

// Event Listeners Setup
function setupEventListeners() {
    // File upload events
    elements.uploadZone.addEventListener('click', () => elements.fileInput.click());
    elements.fileInput.addEventListener('change', handleFileSelect);
    elements.removeFile.addEventListener('click', handleFileRemove);
    elements.processBtn.addEventListener('click', handleProcess);
    
    // Drag and drop
    elements.uploadZone.addEventListener('dragover', handleDragOver);
    elements.uploadZone.addEventListener('dragleave', handleDragLeave);
    elements.uploadZone.addEventListener('drop', handleDrop);
    
    // Results actions
    elements.copyBtn.addEventListener('click', handleCopyToClipboard);
    elements.downloadBtn.addEventListener('click', handleDownloadJSON);
    elements.resetBtn.addEventListener('click', handleReset);
}

// Add SVG Gradient Definition
function addSVGGradient() {
    const svg = document.querySelector('.spinner-ring');
    if (!svg) return;
    
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    const gradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
    gradient.setAttribute('id', 'redGradient');
    gradient.setAttribute('x1', '0%');
    gradient.setAttribute('y1', '0%');
    gradient.setAttribute('x2', '100%');
    gradient.setAttribute('y2', '100%');
    
    const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
    stop1.setAttribute('offset', '0%');
    stop1.setAttribute('style', 'stop-color:#ef4444;stop-opacity:1');
    
    const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
    stop2.setAttribute('offset', '100%');
    stop2.setAttribute('style', 'stop-color:#dc2626;stop-opacity:1');
    
    gradient.appendChild(stop1);
    gradient.appendChild(stop2);
    defs.appendChild(gradient);
    svg.insertBefore(defs, svg.firstChild);
}

// Create Particle System
function createParticles() {
    const container = elements.particles;
    if (!container) return;
    
    for (let i = 0; i < ANIMATION_CONFIG.particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        
        const angle = (360 / ANIMATION_CONFIG.particleCount) * i;
        const delay = (i / ANIMATION_CONFIG.particleCount) * 3;
        
        particle.style.animation = `particle-orbit 3s linear infinite ${delay}s`;
        particle.style.transformOrigin = '200px 200px';
        particle.style.left = '50%';
        particle.style.top = '50%';
        
        container.appendChild(particle);
    }
}

// File Selection Handlers
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        validateAndSetFile(file);
    }
}

function handleDragOver(e) {
    e.preventDefault();
    elements.uploadZone.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    elements.uploadZone.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    elements.uploadZone.classList.remove('drag-over');
    
    const file = e.dataTransfer.files[0];
    if (file) {
        validateAndSetFile(file);
    }
}

function validateAndSetFile(file) {
    // Validate file type
    if (file.type !== 'application/pdf') {
        showNotification('Please select a PDF file', 'error');
        return;
    }
    
    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
        showNotification(`File size must be less than ${MAX_FILE_SIZE / 1024 / 1024}MB`, 'error');
        return;
    }
    
    selectedFile = file;
    displayFileInfo(file);
    elements.processBtn.disabled = false;
}

function displayFileInfo(file) {
    elements.fileName.textContent = file.name;
    elements.fileSize.textContent = formatFileSize(file.size);
    elements.fileInfo.classList.remove('hidden');
    elements.uploadZone.style.display = 'none';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function handleFileRemove() {
    selectedFile = null;
    elements.fileInput.value = '';
    elements.fileInfo.classList.add('hidden');
    elements.uploadZone.style.display = 'flex';
    elements.processBtn.disabled = true;
}

// Handle Process Button
async function handleProcess() {
    if (isProcessing || !selectedFile) return;
    
    isProcessing = true;
    processingStartTime = Date.now();
    elements.processBtn.disabled = true;
    elements.resultsCard.classList.add('hidden');
    
    // Start animation
    showProcessingAnimation();
    
    try {
        const response = await processDocument(selectedFile);
        const processingTime = Date.now() - processingStartTime;
        
        // Complete animation before showing results
        await completeAnimation();
        
        currentResponse = response;
        hideProcessingAnimation();
        displayResults(response, processingTime);
        showNotification('Invoice processed successfully!', 'success');
        
    } catch (error) {
        hideProcessingAnimation();
        handleError(error);
    } finally {
        isProcessing = false;
    }
}

// Process Document API Call
async function processDocument(file) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        console.log('Uploading file:', file.name);
        
        const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            body: formData,
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            let errorMessage;
            
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorJson.message || errorText;
            } catch {
                errorMessage = errorText;
            }
            
            throw new Error(`API Error (${response.status}): ${errorMessage}`);
        }
        
        const data = await response.json();
        console.log('Response data:', data);
        
        if (!data || typeof data !== 'object') {
            throw new Error('Invalid response format');
        }
        
        return data;
        
    } catch (error) {
        clearTimeout(timeoutId);
        
        if (error.name === 'AbortError') {
            throw new Error('Request timeout: Processing took too long. Please try again.');
        }
        
        throw error;
    }
}

// Processing Animation
function showProcessingAnimation() {
    elements.processingOverlay.classList.remove('hidden');
    
    let currentStage = 0;
    let currentProgress = 0;
    
    const updateStage = () => {
        if (currentStage < ANIMATION_CONFIG.stages.length) {
            const stage = ANIMATION_CONFIG.stages[currentStage];
            elements.processingStage.textContent = stage.name;
            
            // Update stage indicators
            document.querySelectorAll('.stage-dot').forEach((dot, index) => {
                dot.classList.remove('active');
                if (index < currentStage) {
                    dot.classList.add('completed');
                } else if (index === currentStage) {
                    dot.classList.add('active');
                }
            });
            
            // Animate progress within stage
            const startProgress = stage.progressStart;
            const endProgress = stage.progressEnd;
            const duration = stage.duration;
            const startTime = Date.now();
            
            const animateProgress = () => {
                const elapsed = Date.now() - startTime;
                const progress = Math.min(elapsed / duration, 1);
                
                currentProgress = startProgress + (endProgress - startProgress) * progress;
                
                elements.spinnerPercentage.textContent = `${Math.round(currentProgress)}%`;
                elements.progressBar.style.width = `${currentProgress}%`;
                
                if (progress < 1) {
                    animationInterval = requestAnimationFrame(animateProgress);
                } else {
                    currentStage++;
                    if (currentStage < ANIMATION_CONFIG.stages.length) {
                        setTimeout(updateStage, 100);
                    }
                }
            };
            
            animateProgress();
        }
    };
    
    updateStage();
}

function completeAnimation() {
    return new Promise(resolve => {
        // Ensure we reach 100%
        elements.spinnerPercentage.textContent = '100%';
        elements.progressBar.style.width = '100%';
        
        // Mark all stages as completed
        document.querySelectorAll('.stage-dot').forEach(dot => {
            dot.classList.remove('active');
            dot.classList.add('completed');
        });
        
        // Show success state briefly
        elements.processingStage.textContent = 'Complete';
        
        setTimeout(resolve, 500);
    });
}

function hideProcessingAnimation() {
    if (animationInterval) {
        cancelAnimationFrame(animationInterval);
    }
    if (stageTimeout) {
        clearTimeout(stageTimeout);
    }
    
    elements.processingOverlay.classList.add('hidden');
    
    // Reset animation state
    elements.spinnerPercentage.textContent = '0%';
    elements.progressBar.style.width = '0%';
    document.querySelectorAll('.stage-dot').forEach(dot => {
        dot.classList.remove('active', 'completed');
    });
}

// Display Results
function displayResults(data, processingTime) {
    const formattedJSON = formatJSON(data);
    elements.jsonViewer.innerHTML = formattedJSON;
    
    elements.processingTime.textContent = `${(processingTime / 1000).toFixed(2)}s`;
    const fieldCount = countFields(data);
    elements.fieldCount.textContent = `${fieldCount} fields`;
    
    elements.resultsCard.classList.remove('hidden');
    
    setTimeout(() => {
        elements.resultsCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 300);
}

function countFields(obj) {
    let count = 0;
    for (let key in obj) {
        if (obj.hasOwnProperty(key)) {
            count++;
            if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
                count += countFields(obj[key]);
            }
        }
    }
    return count;
}

// Format JSON with Syntax Highlighting
function formatJSON(obj, indent = 0) {
    const indentStr = '  '.repeat(indent);
    let html = '';
    
    if (obj === null) {
        return `<span class="json-null">null</span>`;
    }
    
    if (typeof obj === 'string') {
        return `<span class="json-string">"${escapeHtml(obj)}"</span>`;
    }
    
    if (typeof obj === 'number') {
        return `<span class="json-number">${obj}</span>`;
    }
    
    if (typeof obj === 'boolean') {
        return `<span class="json-boolean">${obj}</span>`;
    }
    
    if (Array.isArray(obj)) {
        if (obj.length === 0) return '[]';
        
        html += '[\n';
        obj.forEach((item, index) => {
            html += indentStr + '  ' + formatJSON(item, indent + 1);
            if (index < obj.length - 1) html += ',';
            html += '\n';
        });
        html += indentStr + ']';
        return html;
    }
    
    if (typeof obj === 'object') {
        const keys = Object.keys(obj);
        if (keys.length === 0) return '{}';
        
        html += '{\n';
        keys.forEach((key, index) => {
            html += indentStr + '  ';
            html += `<span class="json-key">"${escapeHtml(key)}"</span>: `;
            html += formatJSON(obj[key], indent + 1);
            if (index < keys.length - 1) html += ',';
            html += '\n';
        });
        html += indentStr + '}';
        return html;
    }
    
    return String(obj);
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Handle Copy to Clipboard
async function handleCopyToClipboard() {
    if (!currentResponse) return;
    
    try {
        const jsonString = JSON.stringify(currentResponse, null, 2);
        await navigator.clipboard.writeText(jsonString);
        showNotification('Copied to clipboard!', 'success');
    } catch (error) {
        showNotification('Failed to copy to clipboard', 'error');
    }
}

// Handle Download JSON
function handleDownloadJSON() {
    if (!currentResponse) return;
    
    const jsonString = JSON.stringify(currentResponse, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `document-processing-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showNotification('JSON downloaded!', 'success');
}

// Handle Toggle JSON Collapse/Expand
function handleToggleJSON() {
    elements.jsonViewer.classList.toggle('collapsed');
    elements.toggleJsonBtn.classList.toggle('collapsed');
}

// Handle Reset
function handleReset() {
    handleFileRemove();
    elements.resultsCard.classList.add('hidden');
    currentResponse = null;
    elements.processBtn.disabled = true;
    showNotification('Ready for new document', 'info');
}



// Notification System
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    
    const icon = getNotificationIcon(type);
    notification.innerHTML = `
        ${icon}
        <span>${escapeHtml(message)}</span>
    `;
    
    elements.notificationContainer.appendChild(notification);
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100px)';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

function getNotificationIcon(type) {
    const icons = {
        success: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>',
        error: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
        warning: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
        info: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
    };
    return icons[type] || icons.info;
}

// Error Handling
function handleError(error) {
    console.error('Error processing document:', error);
    
    let errorMessage = 'An unexpected error occurred';
    
    if (error.message) {
        errorMessage = error.message;
    }
    
    showNotification(errorMessage, 'error');
    
    // Show retry button in UI
    const retryHTML = `
        <div style="text-align: center; padding: 2rem; background: var(--card-bg); border-radius: 16px; box-shadow: 0 4px 20px var(--shadow); margin-bottom: 2rem;">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--error-color)" stroke-width="2" style="margin: 0 auto 1rem;">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="15" y1="9" x2="9" y2="15"></line>
                <line x1="9" y1="9" x2="15" y2="15"></line>
            </svg>
            <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">Processing Failed</h3>
            <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">${escapeHtml(errorMessage)}</p>
            <button onclick="location.reload()" class="btn btn-primary">
                <span class="btn-text">Retry</span>
            </button>
        </div>
    `;
    
    if (elements.resultsCard.classList.contains('hidden')) {
        const errorDiv = document.createElement('div');
        errorDiv.innerHTML = retryHTML;
        errorDiv.id = 'error-container';
        elements.loadingState.insertAdjacentElement('afterend', errorDiv);
        
        // Remove after 10 seconds
        setTimeout(() => {
            const errorContainer = document.getElementById('error-container');
            if (errorContainer) errorContainer.remove();
        }, 10000);
    }
}

// Initialize on DOM Load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}