// Download button functionality
function initializeDownloadButtons() {
    // Handle download button
    const downloadBtn = document.getElementById('downloadBtn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function(e) {
            setTimeout(() => {
                this.disabled = true;
                this.textContent = 'Downloaded';
                this.classList.remove('btn-primary');
                this.classList.add('btn-secondary');
            }, 100);
        });
    }
    
    // Handle merged plan download button
    const downloadMergedBtn = document.getElementById('downloadMergedBtn');
    if (downloadMergedBtn) {
        downloadMergedBtn.addEventListener('click', function(e) {
            setTimeout(() => {
                this.disabled = true;
                this.textContent = 'Downloaded';
                this.classList.remove('btn-primary');
                this.classList.add('btn-secondary');
            }, 100);
        });
    }
    
    // Handle updated plan download button
    const downloadUpdatedPlanBtn = document.getElementById('downloadUpdatedPlanBtn');
    if (downloadUpdatedPlanBtn) {
        downloadUpdatedPlanBtn.addEventListener('click', function(e) {
            setTimeout(() => {
                this.disabled = true;
                this.textContent = 'Downloaded';
                this.classList.remove('btn-primary');
                this.classList.add('btn-secondary');
            }, 100);
        });
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeDownloadButtons);