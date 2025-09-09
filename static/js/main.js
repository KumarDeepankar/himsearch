// Global variables
let currentEngineType = '';
let searchTimeout;
let suggestionTimeout;
let currentHighlightIndex = -1;
let suggestions = [];

// Dynamic field configuration
const fieldConfig = {
    // Known field configurations
    document_id: { 
        label: 'Document ID', 
        icon: 'fas fa-id-card', 
        type: 'id',
        order: 1,
        displayInPreview: true
    },
    indexed_at: { 
        label: 'Indexed At', 
        icon: 'fas fa-calendar', 
        type: 'datetime',
        order: 2,
        displayInPreview: false
    },
    story_summary: { 
        label: 'Summary', 
        icon: 'fas fa-align-left', 
        type: 'text',
        order: 3,
        displayInPreview: true,
        fullWidth: true
    },
    story: { 
        label: 'Full Content', 
        icon: 'fas fa-file-text', 
        type: 'text',
        order: 4,
        displayInPreview: false,
        fullWidth: true,
        scrollable: true
    },
    doc_subject: { 
        label: 'Vector Embedding', 
        icon: 'fas fa-vector-square', 
        type: 'vector',
        order: 5,
        displayInPreview: false,
        fullWidth: true
    },
    // Default configuration for unknown fields
    _default: {
        label: null, // Will use field name
        icon: 'fas fa-file-alt',
        type: 'auto',
        order: 999,
        displayInPreview: false,
        fullWidth: false
    }
};

// Field type handlers
const fieldHandlers = {
    id: (value) => value || 'N/A',
    datetime: (value) => value ? new Date(value).toLocaleString() : 'N/A',
    text: (value, highlight) => highlight || value || 'No content available',
    vector: (value) => {
        const hasVector = value && Array.isArray(value);
        const vectorPreview = hasVector ? `[${value.slice(0, 5).map(v => v.toFixed(3)).join(', ')}...]` : 'Not available';
        return { hasVector, vectorPreview, vector: value };
    },
    auto: (value) => {
        if (Array.isArray(value)) {
            if (value.length > 10 && typeof value[0] === 'number') {
                return fieldHandlers.vector(value);
            }
            return value.join(', ');
        }
        if (typeof value === 'object' && value !== null) {
            return JSON.stringify(value, null, 2);
        }
        if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
            return fieldHandlers.datetime(value);
        }
        return value?.toString() || 'N/A';
    }
};

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
    searchInputContainer: null,
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
    elements.searchInputContainer = document.getElementById('searchInputContainer');
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

    // Auto-configure new fields based on the received data
    if (data.hits.length > 0) {
        autoConfigureFields(data.hits);
    }

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
            ${data.hits.map((hit, index) => {
                const source = hit._source;
                const { previewContent, expandedContent } = generateDynamicFields(source, hit.highlight, hit._score_breakdown);
                
                return `
                <div class="story-item expandable-item" data-expanded="false" style="animation: fadeInUp 0.5s ease ${index * 0.1}s both;">
                    <div class="story-header" onclick="toggleExpand(this)">
                        <div class="story-title">
                            <i class="fas fa-file-alt story-icon"></i>
                            <span class="document-title">${generateDocumentTitle(source)}</span>
                            <div class="expand-indicator">
                                <i class="fas fa-chevron-down"></i>
                            </div>
                        </div>
                        <div class="story-score">
                            Score: ${hit._score ? hit._score.toFixed(3) : 'N/A'}
                            ${hit._score_breakdown ? `
                                <span class="score-breakdown-preview" title="Text: ${hit._score_breakdown.text_score.toFixed(3)}, Vector: ${hit._score_breakdown.vector_score.toFixed(3)}">
                                    (Hybrid)
                                </span>
                            ` : ''}
                        </div>
                    </div>
                    
                    <div class="story-preview">
                        ${previewContent}
                    </div>
                    
                    <div class="story-details" style="display: none;">
                        <div class="field-group">
                            ${expandedContent}
                        </div>
                    </div>
                </div>
            `;
            }).join('')}
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
        if (elements.searchInputContainer && !elements.searchInputContainer.contains(e.target)) {
            hideAutocomplete();
        }
    });
    
    // Prevent hiding when clicking inside the dropdown
    if (elements.autocompleteDropdown) {
        elements.autocompleteDropdown.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    }
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

// Toggle expand/collapse for search results
function toggleExpand(headerElement) {
    const storyItem = headerElement.closest('.story-item');
    const storyDetails = storyItem.querySelector('.story-details');
    const expandIndicator = headerElement.querySelector('.expand-indicator i');
    const isExpanded = storyItem.getAttribute('data-expanded') === 'true';
    
    if (isExpanded) {
        // Collapse
        storyDetails.style.display = 'none';
        expandIndicator.className = 'fas fa-chevron-down';
        storyItem.setAttribute('data-expanded', 'false');
        storyItem.classList.remove('expanded');
    } else {
        // Expand
        storyDetails.style.display = 'block';
        expandIndicator.className = 'fas fa-chevron-up';
        storyItem.setAttribute('data-expanded', 'true');
        storyItem.classList.add('expanded');
        
        // Smooth scroll to keep the header visible
        setTimeout(() => {
            headerElement.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest'
            });
        }, 100);
    }
}

// Toggle vector display
function toggleVector(button) {
    const vectorFull = button.closest('.vector-preview').querySelector('.vector-full');
    const icon = button.querySelector('i');
    const isVisible = vectorFull.style.display !== 'none';
    
    if (isVisible) {
        vectorFull.style.display = 'none';
        button.innerHTML = '<i class="fas fa-eye"></i> Show Full Vector';
    } else {
        vectorFull.style.display = 'block';
        button.innerHTML = '<i class="fas fa-eye-slash"></i> Hide Full Vector';
    }
}

// Dynamic field generation functions
function getFieldConfig(fieldName) {
    return fieldConfig[fieldName] || { 
        ...fieldConfig._default, 
        label: formatFieldName(fieldName) 
    };
}

function formatFieldName(fieldName) {
    return fieldName
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
}

function getFieldValue(fieldName, value, highlight = null) {
    const config = getFieldConfig(fieldName);
    const handler = fieldHandlers[config.type] || fieldHandlers.auto;
    return handler(value, highlight);
}

function generateDynamicFields(source, highlight = {}, scoreBreakdown = null) {
    // Only use fields that actually exist in the source data
    const sortedFields = Object.keys(source)
        .map(fieldName => ({
            name: fieldName,
            config: getFieldConfig(fieldName),
            value: source[fieldName],
            highlight: highlight[fieldName]
        }))
        .filter(field => field.value !== undefined && field.value !== null)
        .sort((a, b) => a.config.order - b.config.order);

    // Generate preview content
    const previewFields = sortedFields.filter(field => field.config.displayInPreview);
    const previewContent = previewFields.length > 0 
        ? previewFields.map(field => generateFieldPreview(field)).join('')
        : generateDefaultPreview(source, highlight);

    // Generate expanded content
    const expandedContent = sortedFields.map(field => generateFieldItem(field)).join('') +
        (scoreBreakdown ? generateScoreBreakdown(scoreBreakdown) : '');

    return { previewContent, expandedContent };
}

function generateDocumentTitle(source) {
    // Try to find appropriate title field
    const titleCandidates = ['title', 'name', 'document_title', 'filename', 'subject'];
    const idCandidates = ['document_id', 'id', '_id', 'doc_id'];
    
    // First try title fields
    for (const candidate of titleCandidates) {
        if (source[candidate] && typeof source[candidate] === 'string') {
            return source[candidate].length > 50 
                ? source[candidate].substring(0, 50) + '...'
                : source[candidate];
        }
    }
    
    // Then try ID fields with "Document #" prefix
    for (const candidate of idCandidates) {
        if (source[candidate] !== undefined && source[candidate] !== null) {
            return `Document #${source[candidate]}`;
        }
    }
    
    // Last resort: use first available field or generic title
    const firstField = Object.entries(source).find(([key, value]) => 
        value !== null && value !== undefined && String(value).length > 0
    );
    
    if (firstField) {
        const [fieldName, value] = firstField;
        const displayValue = typeof value === 'string' ? value : String(value);
        return displayValue.length > 30 
            ? `${formatFieldName(fieldName)}: ${displayValue.substring(0, 30)}...`
            : `${formatFieldName(fieldName)}: ${displayValue}`;
    }
    
    return 'Untitled Document';
}

function generateDefaultPreview(source, highlight) {
    // Try common summary field names (flexible for schema changes)
    const summaryFieldCandidates = ['story_summary', 'summary', 'description', 'title', 'content', 'text', 'body'];
    const highlightFieldCandidates = ['story_summary', 'summary', 'description', 'title', 'content', 'text', 'body'];
    
    // Find first available summary field
    const summaryField = summaryFieldCandidates.find(field => source[field])?.valueOf();
    const summaryValue = summaryField ? source[summaryField] : null;
    
    // Find first available highlighted field
    const highlightField = highlightFieldCandidates.find(field => highlight[field]);
    const highlightedValue = highlightField ? highlight[highlightField] : null;
    
    if (summaryValue || highlightedValue) {
        const content = highlightedValue 
            ? highlightedValue.join(' ... ')
            : (typeof summaryValue === 'string' ? summaryValue.substring(0, 200) + (summaryValue.length > 200 ? '...' : '') : String(summaryValue));
        
        return `<div class="story-summary-preview">${content}</div>`;
    }
    
    // If no summary, show first available text field (any field with substantial text)
    const textFields = Object.entries(source)
        .filter(([key, value]) => typeof value === 'string' && value.length > 20)
        .sort(([keyA], [keyB]) => {
            // Prioritize fields that likely contain main content
            const contentWords = ['title', 'name', 'subject', 'content', 'text', 'body', 'message'];
            const aScore = contentWords.some(word => keyA.toLowerCase().includes(word)) ? 0 : 1;
            const bScore = contentWords.some(word => keyB.toLowerCase().includes(word)) ? 0 : 1;
            return aScore - bScore;
        });
    
    if (textFields.length > 0) {
        const [fieldName, value] = textFields[0];
        const truncated = value.substring(0, 200) + (value.length > 200 ? '...' : '');
        return `<div class="story-summary-preview"><strong>${formatFieldName(fieldName)}:</strong> ${truncated}</div>`;
    }
    
    // Last resort: show any available field
    const anyFields = Object.entries(source).filter(([key, value]) => 
        value !== null && value !== undefined && String(value).length > 0
    );
    
    if (anyFields.length > 0) {
        const [fieldName, value] = anyFields[0];
        const displayValue = typeof value === 'object' ? JSON.stringify(value).substring(0, 100) + '...' : String(value).substring(0, 100);
        return `<div class="story-summary-preview"><strong>${formatFieldName(fieldName)}:</strong> ${displayValue}</div>`;
    }
    
    return '<div class="story-summary-preview">No preview available</div>';
}

function generateFieldPreview(field) {
    const processedValue = getFieldValue(field.name, field.value, field.highlight);
    
    if (field.config.type === 'vector') {
        return ''; // Vectors don't show in preview
    }
    
    const content = field.highlight 
        ? field.highlight.join(' ... ')
        : (typeof processedValue === 'string' ? processedValue.substring(0, 200) + (processedValue.length > 200 ? '...' : '') : processedValue);
    
    return `<div class="story-summary-preview">${content}</div>`;
}

function generateFieldItem(field) {
    const config = field.config;
    const processedValue = getFieldValue(field.name, field.value, field.highlight);
    
    if (config.type === 'vector' && typeof processedValue === 'object') {
        return generateVectorField(field.name, config, processedValue);
    }
    
    const content = field.highlight && config.type === 'text'
        ? field.highlight.join(' ... ')
        : processedValue;
    
    const fieldClass = config.fullWidth ? 'field-item full-width' : 'field-item';
    const contentClass = config.scrollable ? 'field-value content-text' : 'field-value';
    
    return `
        <div class="${fieldClass}">
            <div class="field-label">
                <i class="${config.icon}"></i>
                ${config.label}
            </div>
            <div class="${contentClass}">${content}</div>
        </div>
    `;
}

function generateVectorField(fieldName, config, vectorData) {
    const { hasVector, vectorPreview, vector } = vectorData;
    
    return `
        <div class="field-item full-width">
            <div class="field-label">
                <i class="${config.icon}"></i>
                ${config.label}
                <span class="vector-info" title="Vector used for semantic search">
                    <i class="fas fa-info-circle"></i>
                </span>
            </div>
            <div class="field-value vector-preview">
                <div class="vector-summary">
                    Dimensions: ${hasVector ? vector.length : 0} | 
                    Preview: ${vectorPreview}
                </div>
                ${hasVector ? `
                    <div class="vector-toggle">
                        <button class="vector-show-btn" onclick="toggleVector(this)">
                            <i class="fas fa-eye"></i> Show Full Vector
                        </button>
                    </div>
                    <div class="vector-full" style="display: none;">
                        <code class="vector-data">[${vector.map(v => v.toFixed(6)).join(', ')}]</code>
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

function generateScoreBreakdown(scoreBreakdown) {
    return `
        <div class="field-item full-width">
            <div class="field-label">
                <i class="fas fa-chart-bar"></i>
                Score Breakdown
            </div>
            <div class="field-value">
                <div class="score-breakdown">
                    <div class="score-item">
                        <span class="score-type">Text Score:</span>
                        <span class="score-value">${scoreBreakdown.text_score.toFixed(4)}</span>
                    </div>
                    <div class="score-item">
                        <span class="score-type">Vector Score:</span>
                        <span class="score-value">${scoreBreakdown.vector_score.toFixed(4)}</span>
                    </div>
                    <div class="score-item">
                        <span class="score-type">Hybrid Score:</span>
                        <span class="score-value">${scoreBreakdown.hybrid_score.toFixed(4)}</span>
                    </div>
                    <div class="score-item">
                        <span class="score-type">Semantic Boost:</span>
                        <span class="score-value">${(scoreBreakdown.semantic_boost * 100).toFixed(1)}%</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Dynamic field configuration management
function updateFieldConfig(fieldName, config) {
    fieldConfig[fieldName] = { ...fieldConfig[fieldName], ...config };
    console.log(`Updated configuration for field: ${fieldName}`, fieldConfig[fieldName]);
}

function addFieldType(typeName, handler) {
    fieldHandlers[typeName] = handler;
    console.log(`Added new field type: ${typeName}`);
}

// Auto-detect and configure new fields based on data patterns
function autoConfigureFields(allDocuments) {
    const fieldAnalysis = {};
    
    // Analyze all documents to detect field patterns
    allDocuments.forEach(doc => {
        Object.entries(doc._source || {}).forEach(([fieldName, value]) => {
            if (!fieldAnalysis[fieldName]) {
                fieldAnalysis[fieldName] = {
                    types: new Set(),
                    samples: [],
                    isArray: false,
                    hasNumbers: false,
                    hasText: false,
                    avgLength: 0,
                    isDateTime: false
                };
            }
            
            const analysis = fieldAnalysis[fieldName];
            analysis.samples.push(value);
            
            if (Array.isArray(value)) {
                analysis.isArray = true;
                if (value.length > 0) {
                    analysis.types.add(typeof value[0]);
                    if (typeof value[0] === 'number') {
                        analysis.hasNumbers = true;
                    }
                }
            } else {
                analysis.types.add(typeof value);
                if (typeof value === 'string') {
                    analysis.hasText = true;
                    analysis.avgLength += value.length;
                    // Check if it looks like a date
                    if (/^\d{4}-\d{2}-\d{2}T/.test(value)) {
                        analysis.isDateTime = true;
                    }
                }
            }
        });
    });
    
    // Auto-configure fields based on analysis
    Object.entries(fieldAnalysis).forEach(([fieldName, analysis]) => {
        if (!fieldConfig[fieldName] || fieldConfig[fieldName] === fieldConfig._default) {
            const avgLength = analysis.avgLength / analysis.samples.length;
            
            let detectedConfig = { ...fieldConfig._default };
            
            // Detect field type and configuration
            if (analysis.isDateTime) {
                detectedConfig = {
                    ...detectedConfig,
                    type: 'datetime',
                    icon: 'fas fa-calendar',
                    order: 100
                };
            } else if (analysis.isArray && analysis.hasNumbers && analysis.samples[0]?.length > 100) {
                // Likely a vector embedding
                detectedConfig = {
                    ...detectedConfig,
                    type: 'vector',
                    icon: 'fas fa-vector-square',
                    fullWidth: true,
                    order: 200
                };
            } else if (analysis.hasText && avgLength > 100) {
                // Long text content
                detectedConfig = {
                    ...detectedConfig,
                    type: 'text',
                    icon: 'fas fa-file-text',
                    fullWidth: true,
                    scrollable: true,
                    order: 150
                };
            } else if (analysis.hasText && avgLength < 100) {
                // Short text or summary
                detectedConfig = {
                    ...detectedConfig,
                    type: 'text',
                    icon: 'fas fa-align-left',
                    displayInPreview: fieldName.includes('summary') || fieldName.includes('title'),
                    order: 50
                };
            } else if (fieldName.includes('id')) {
                detectedConfig = {
                    ...detectedConfig,
                    type: 'id',
                    icon: 'fas fa-id-card',
                    displayInPreview: true,
                    order: 10
                };
            }
            
            detectedConfig.label = formatFieldName(fieldName);
            updateFieldConfig(fieldName, detectedConfig);
        }
    });
    
    return fieldAnalysis;
}

// API to customize field display (can be called from browser console)
window.configureField = function(fieldName, config) {
    updateFieldConfig(fieldName, config);
    console.log(`Field "${fieldName}" configured:`, fieldConfig[fieldName]);
    console.log('Refresh the search results to see changes.');
};

// Example usage (can be called from browser console):
// configureField('new_field', { label: 'Custom Label', icon: 'fas fa-star', type: 'text', order: 25 });