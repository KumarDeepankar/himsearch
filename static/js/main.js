// Global variables
let currentEngineType = '';
let searchTimeout;
let suggestionTimeout;
let currentHighlightIndex = -1;
let suggestions = [];

// DOM Elements
const elements = {
    searchForm: null,
    searchQuery: null,
    searchButton: null,
    loadingDiv: null,
    resultsContainer: null,
    resultsSection: null,
    clearBtn: null,
    engineInfo: null,
    scrollToTop: null,
    suggestionTags: null,
    navButtons: null,
    autocompleteDropdown: null,
    autocompleteLoading: null,
    autocompleteSuggestions: null
};

// Initialize DOM elements
function initializeElements() {
    elements.searchForm = document.getElementById('searchForm');
    elements.searchQuery = document.getElementById('searchQuery');
    elements.searchButton = document.getElementById('searchButton');
    elements.loadingDiv = document.getElementById('loadingDiv');
    elements.resultsContainer = document.getElementById('resultsContainer');
    elements.resultsSection = document.getElementById('resultsSection');
    elements.clearBtn = document.getElementById('clearBtn');
    elements.engineInfo = document.getElementById('engineInfo');
    elements.scrollToTop = document.getElementById('scrollToTop');
    elements.suggestionTags = document.querySelectorAll('.suggestion-tag');
    elements.searchSection = document.getElementById('searchSection');
    elements.autocompleteDropdown = document.getElementById('autocompleteDropdown');
    elements.autocompleteLoading = document.getElementById('autocompleteLoading');
    elements.autocompleteSuggestions = document.getElementById('autocompleteSuggestions');
}

// Enhanced search functionality
function setupSearch() {
    elements.searchForm.addEventListener('submit', handleSearch);
    
    // Real-time search input handling
    elements.searchQuery.addEventListener('input', handleSearchInput);
    elements.searchQuery.addEventListener('keydown', handleKeydown);
    
    // Clear button functionality
    elements.clearBtn.addEventListener('click', clearSearch);
    
    // Suggestion tags
    elements.suggestionTags.forEach(tag => {
        tag.addEventListener('click', (e) => {
            const query = e.target.getAttribute('data-query');
            elements.searchQuery.value = query;
            updateClearButton();
            handleSearch(new Event('submit'));
        });
    });
}

// Handle search input changes
function handleSearchInput(e) {
    const query = e.target.value;
    updateClearButton();
    
    // Clear existing timeout
    if (suggestionTimeout) {
        clearTimeout(suggestionTimeout);
    }
    
    // Hide dropdown if query is too short
    if (!query || query.length < 2) {
        hideAutocomplete();
        return;
    }
    
    // Show suggestions after a short delay
    suggestionTimeout = setTimeout(() => {
        if (query.length >= 2) {
            showSuggestions(query);
        }
    }, 300);
}

// Handle keyboard shortcuts
function handleKeydown(e) {
    const isDropdownVisible = elements.autocompleteDropdown.style.display !== 'none';
    
    if (e.key === 'Escape') {
        if (isDropdownVisible) {
            hideAutocomplete();
            e.preventDefault();
        } else {
            clearSearch();
        }
        return;
    }
    
    if (!isDropdownVisible) {
        return;
    }
    
    // Handle arrow keys for navigation
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        navigateAutocomplete(1);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        navigateAutocomplete(-1);
    } else if (e.key === 'Enter' && currentHighlightIndex >= 0) {
        e.preventDefault();
        selectSuggestion(suggestions[currentHighlightIndex]);
    }
}

// Update clear button visibility
function updateClearButton() {
    const hasValue = elements.searchQuery.value.trim().length > 0;
    elements.clearBtn.style.display = hasValue ? 'block' : 'none';
}

// Clear search
function clearSearch() {
    elements.searchQuery.value = '';
    elements.clearBtn.style.display = 'none';
    elements.resultsSection.style.display = 'none';
    hideAutocomplete();
    elements.searchQuery.focus();
}

// Autocomplete Functions
async function showSuggestions(query) {
    if (!query || query.length < 2) {
        hideAutocomplete();
        return;
    }
    
    // Show loading state
    elements.autocompleteLoading.style.display = 'block';
    elements.autocompleteSuggestions.innerHTML = '';
    elements.autocompleteDropdown.style.display = 'block';
    currentHighlightIndex = -1;
    
    try {
        const response = await fetch(`/api/suggestions?q=${encodeURIComponent(query)}`);
        if (!response.ok) {
            throw new Error('Failed to fetch suggestions');
        }
        
        const data = await response.json();
        suggestions = data.suggestions || [];
        
        elements.autocompleteLoading.style.display = 'none';
        
        if (suggestions.length === 0) {
            elements.autocompleteSuggestions.innerHTML = `
                <div class="autocomplete-no-results">
                    <i class="fas fa-search"></i> No suggestions found
                </div>
            `;
        } else {
            renderSuggestions(suggestions);
        }
        
    } catch (error) {
        console.error('Error fetching suggestions:', error);
        elements.autocompleteLoading.style.display = 'none';
        elements.autocompleteSuggestions.innerHTML = `
            <div class="autocomplete-no-results">
                <i class="fas fa-exclamation-triangle"></i> Unable to load suggestions
            </div>
        `;
    }
}

function renderSuggestions(suggestionList) {
    const html = suggestionList.map((suggestion, index) => `
        <div class="autocomplete-suggestion" data-index="${index}" onclick="selectSuggestion('${suggestion.replace(/'/g, "\\'")}')">
            <div class="autocomplete-suggestion-icon">
                <i class="fas fa-search"></i>
            </div>
            <div class="autocomplete-suggestion-text">${suggestion}</div>
        </div>
    `).join('');
    
    elements.autocompleteSuggestions.innerHTML = html;
    
    // Add event listeners for hover effects
    const suggestionElements = elements.autocompleteSuggestions.querySelectorAll('.autocomplete-suggestion');
    suggestionElements.forEach((el, index) => {
        el.addEventListener('mouseenter', () => {
            highlightSuggestion(index);
        });
        el.addEventListener('mouseleave', () => {
            clearHighlight();
        });
    });
}

function navigateAutocomplete(direction) {
    const suggestionElements = elements.autocompleteSuggestions.querySelectorAll('.autocomplete-suggestion');
    if (suggestionElements.length === 0) return;
    
    // Remove current highlight
    if (currentHighlightIndex >= 0) {
        suggestionElements[currentHighlightIndex].classList.remove('highlighted');
    }
    
    // Update index
    currentHighlightIndex += direction;
    
    // Handle wrapping
    if (currentHighlightIndex < 0) {
        currentHighlightIndex = suggestionElements.length - 1;
    } else if (currentHighlightIndex >= suggestionElements.length) {
        currentHighlightIndex = 0;
    }
    
    // Highlight new selection
    suggestionElements[currentHighlightIndex].classList.add('highlighted');
    
    // Scroll into view if needed
    suggestionElements[currentHighlightIndex].scrollIntoView({
        block: 'nearest',
        behavior: 'smooth'
    });
}

function highlightSuggestion(index) {
    const suggestionElements = elements.autocompleteSuggestions.querySelectorAll('.autocomplete-suggestion');
    
    // Clear all highlights
    suggestionElements.forEach(el => el.classList.remove('highlighted'));
    
    // Highlight the specified suggestion
    if (index >= 0 && index < suggestionElements.length) {
        suggestionElements[index].classList.add('highlighted');
        currentHighlightIndex = index;
    }
}

function clearHighlight() {
    const suggestionElements = elements.autocompleteSuggestions.querySelectorAll('.autocomplete-suggestion');
    suggestionElements.forEach(el => el.classList.remove('highlighted'));
    currentHighlightIndex = -1;
}

function selectSuggestion(suggestion) {
    elements.searchQuery.value = suggestion;
    hideAutocomplete();
    updateClearButton();
    
    // Trigger search
    handleSearch(new Event('submit'));
}

function hideAutocomplete() {
    elements.autocompleteDropdown.style.display = 'none';
    elements.autocompleteLoading.style.display = 'none';
    currentHighlightIndex = -1;
    suggestions = [];
}

// Enhanced search handler
async function handleSearch(e) {
    e.preventDefault();

    const query = elements.searchQuery.value.trim();
    // Always use 'all' fields for searching
    const selectedField = 'all';

    if (!query) {
        elements.searchQuery.focus();
        return;
    }

    // Hide autocomplete dropdown
    hideAutocomplete();

    // Transform to compact layout on first search
    transformToCompactSearch();

    // Show loading state with enhanced animation
    showLoadingState();

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                field: selectedField,
                size: 10
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        displayResults(data);

    } catch (error) {
        console.error('Search error:', error);
        displayError(error.message);
    } finally {
        hideLoadingState();
    }
}

// Enhanced loading state
function showLoadingState() {
    elements.searchButton.disabled = true;
    elements.searchButton.innerHTML = `
        <i class="fas fa-spinner fa-spin search-icon"></i>
    `;
    elements.loadingDiv.style.display = 'block';
    elements.resultsSection.style.display = 'none';
}

// Hide loading state
function hideLoadingState() {
    elements.searchButton.disabled = false;
    elements.searchButton.innerHTML = `
        <i class="fas fa-search search-icon"></i>
    `;
    elements.loadingDiv.style.display = 'none';
}

// Enhanced results display
function displayResults(data) {
    currentEngineType = data.engine_type;
    updateEngineInfo();

    if (data.hits.length === 0) {
        elements.resultsContainer.innerHTML = `
            <div class="no-results">
                <i class="fas fa-search" style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.3;"></i>
                <h3>No documents found</h3>
                <p>Try different search terms or explore our suggested queries above.</p>
            </div>
        `;
    } else {
        const resultsHtml = `
            <div class="results-header">
                <h2 class="results-title">
                    <i class="fas fa-file-alt" style="margin-right: 0.5rem; opacity: 0.7;"></i>
                    Search Results
                </h2>
                <div class="results-meta">
                    <i class="fas fa-clock" style="margin-right: 0.25rem;"></i>
                    Found ${data.total} result(s) in ${data.took}ms
                </div>
            </div>
            ${data.hits.map((hit, index) => `
                <div class="story-item" style="animation: fadeInUp 0.5s ease ${index * 0.1}s both;">
                    <div class="story-id">
                        <i class="fas fa-file" style="margin-right: 0.5rem;"></i>
                        Document #${hit._source.id}
                    </div>
                    <div class="story-summary">
                        ${hit.highlight && hit.highlight.story_summary 
                            ? hit.highlight.story_summary.join(' ... ')
                            : hit._source.story_summary}
                    </div>
                    <div class="story-content">
                        ${hit.highlight && hit.highlight.story 
                            ? hit.highlight.story.join(' ... ')
                            : hit._source.story}
                    </div>
                </div>
            `).join('')}
        `;
        elements.resultsContainer.innerHTML = resultsHtml;
    }

    elements.resultsSection.style.display = 'block';
    
    // Smooth scroll to results with offset for fixed header
    setTimeout(() => {
        const resultsTop = elements.resultsSection.offsetTop - 100;
        window.scrollTo({
            top: resultsTop,
            behavior: 'smooth'
        });
    }, 100);
}

// Enhanced error display
function displayError(message) {
    elements.resultsContainer.innerHTML = `
        <div class="no-results">
            <i class="fas fa-exclamation-triangle" style="font-size: 3rem; margin-bottom: 1rem; color: #f56565;"></i>
            <h3>Search Error</h3>
            <p>Failed to search: ${message}</p>
            <button onclick="location.reload()" style="
                margin-top: 1rem; 
                padding: 0.5rem 1rem; 
                background: #374151; 
                color: white; 
                border: none; 
                border-radius: 8px; 
                cursor: pointer;
                transition: background 0.2s ease;" onmouseover="this.style.background='#4b5563'" onmouseout="this.style.background='#374151'
            ">
                <i class="fas fa-redo" style="margin-right: 0.5rem;"></i>
                Try Again
            </button>
        </div>
    `;
    elements.resultsSection.style.display = 'block';
}

// Enhanced engine info display
function updateEngineInfo() {
    const statusText = elements.engineInfo.querySelector('.status-text');
    if (statusText) {
        statusText.textContent = `Connected to ${currentEngineType || 'Unknown'} • ${window.location.origin}`;
    }
}

// Scroll to top functionality
function setupScrollToTop() {
    window.addEventListener('scroll', () => {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        elements.scrollToTop.style.display = scrollTop > 500 ? 'block' : 'none';
    });

    elements.scrollToTop.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}



// Transform to compact search layout
function transformToCompactSearch() {
    if (!elements.searchSection.classList.contains('compact')) {
        // Add compact class to search section
        elements.searchSection.classList.add('compact');
        
        // Remove large-search class from input
        elements.searchQuery.classList.remove('large-search');
        
        // Add fixed search class to results section
        if (elements.resultsSection) {
            elements.resultsSection.classList.add('with-fixed-search');
        }
        
        // Update placeholder
        elements.searchQuery.placeholder = 'Search documents...';
    }
}

// Add CSS animations
function addAnimations() {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes slideInUp {
            from { 
                transform: translateY(30px); 
                opacity: 0; 
            }
            to { 
                transform: translateY(0); 
                opacity: 1; 
            }
        }
        
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    `;
    document.head.appendChild(style);
}

// Load engine info on page load
async function loadEngineInfo() {
    try {
        const response = await fetch('/api/info');
        const data = await response.json();
        currentEngineType = data.engine_type;
        updateEngineInfo();
    } catch (error) {
        console.error('Failed to load engine info:', error);
        const statusText = elements.engineInfo.querySelector('.status-text');
        if (statusText) {
            statusText.textContent = 'Unable to connect to search engine';
        }
    }
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeElements();
    setupSearch();
    setupScrollToTop();
    addAnimations();
    loadEngineInfo();
    setupAutocomplete();
    
    // Focus on search input with slight delay for better UX
    setTimeout(() => {
        elements.searchQuery.focus();
    }, 500);
    
    // Update clear button state on load
    updateClearButton();
});

// Setup autocomplete event handlers
function setupAutocomplete() {
    // Hide autocomplete when clicking outside
    document.addEventListener('click', (e) => {
        if (!elements.searchInputContainer.contains(e.target)) {
            hideAutocomplete();
        }
    });
    
    // Prevent hiding when clicking inside the dropdown
    elements.autocompleteDropdown.addEventListener('click', (e) => {
        e.stopPropagation();
    });
}

// Handle keyboard shortcuts globally
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K to focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        elements.searchQuery.focus();
        elements.searchQuery.select();
    }
});