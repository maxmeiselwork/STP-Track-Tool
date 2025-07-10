// Table filtering functionality
function initializeTableFilters() {
    const originalTable = document.querySelector('#tableContainer table');
    if (!originalTable) return;
    
    const originalRows = Array.from(originalTable.querySelectorAll('tbody tr'));
    
    // Populate filters
    const gatewayFilter = document.getElementById('gatewayFilter');
    const satelliteFilter = document.getElementById('satelliteFilter');
    
    if (gatewayFilter && satelliteFilter) {
        // Both gateway and satellite filters (plan analysis)
        const gateways = [...new Set(originalRows.map(row => row.cells[0].textContent))];
        const satellites = [...new Set(originalRows.map(row => row.cells[1].textContent))];
        
        gateways.sort().forEach(gateway => {
            const option = document.createElement('option');
            option.value = gateway;
            option.textContent = gateway;
            gatewayFilter.appendChild(option);
        });
        
        satellites.sort().forEach(satellite => {
            const option = document.createElement('option');
            option.value = satellite;
            option.textContent = satellite;
            satelliteFilter.appendChild(option);
        });
        
        // Filter functionality for both
        function filterTable() {
            const gatewayValue = gatewayFilter.value;
            const satelliteValue = satelliteFilter.value;
            const tbody = originalTable.querySelector('tbody');
            
            tbody.innerHTML = '';
            
            originalRows.forEach(row => {
                const gatewayCell = row.cells[0].textContent;
                const satelliteCell = row.cells[1].textContent;
                
                const gatewayMatch = !gatewayValue || gatewayCell === gatewayValue;
                const satelliteMatch = !satelliteValue || satelliteCell === satelliteValue;
                
                if (gatewayMatch && satelliteMatch) {
                    tbody.appendChild(row.cloneNode(true));
                }
            });
            
            const visibleRows = tbody.querySelectorAll('tr').length;
            console.log(`Showing ${visibleRows} of ${originalRows.length} rows`);
        }
        
        gatewayFilter.addEventListener('change', filterTable);
        satelliteFilter.addEventListener('change', filterTable);
        
    } else if (satelliteFilter) {
        // Only satellite filter (XML analysis)
        const satellites = [...new Set(originalRows.map(row => row.cells[0].textContent))];
        
        satellites.sort().forEach(satellite => {
            const option = document.createElement('option');
            option.value = satellite;
            option.textContent = satellite;
            satelliteFilter.appendChild(option);
        });
        
        function filterTable() {
            const satelliteValue = satelliteFilter.value;
            const tbody = originalTable.querySelector('tbody');
            
            tbody.innerHTML = '';
            
            originalRows.forEach(row => {
                const satelliteCell = row.cells[0].textContent;
                const satelliteMatch = !satelliteValue || satelliteCell === satelliteValue;
                
                if (satelliteMatch) {
                    tbody.appendChild(row.cloneNode(true));
                }
            });
            
            const visibleRows = tbody.querySelectorAll('tr').length;
            console.log(`Showing ${visibleRows} of ${originalRows.length} rows`);
        }
        
        satelliteFilter.addEventListener('change', filterTable);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeTableFilters);