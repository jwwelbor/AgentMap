/**
 * Markdown handling functionality
 */
class MarkdownViewer {
    constructor() {
        this.markdownContent = '';
        this.markdownTitle = '';
    }
    
    /**
     * Fetch a markdown file and display its contents
     */
async fetchMarkdown(path, title) {
    try {
        console.log(`Attempting to fetch markdown from: ${path}`);
        const response = await fetch(path);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        this.markdownContent = await response.text();
        this.markdownTitle = title;
        app.setActiveTab('markdown');
        console.log(`Successfully loaded markdown: ${title}`);
    } catch (error) {
        console.error('Error fetching markdown:', error);
        this.markdownContent = `Error loading markdown content from ${path}. ${error.message}`;
        this.markdownTitle = 'Error';
        app.setActiveTab('markdown');
    }
}
    
    /**
     * Render the current markdown content
     */
    renderMarkdown() {
        const markdownSection = document.getElementById('markdown-section');
        if (!markdownSection) return;
        
        markdownSection.innerHTML = `
            <div class="content-card">
                <div class="markdown-header">
                    <h2 class="card-title">${this.markdownTitle}</h2>
                    <button class="back-button" onclick="app.setActiveTab('documentation')">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M19 12H5M12 19l-7-7 7-7"/>
                        </svg>
                        Back to Documentation
                    </button>
                </div>
                <div class="markdown-content">${marked.parse(this.markdownContent)}</div>
            </div>
        `;
    }
}

// Create global markdown viewer instance
const markdownViewer = new MarkdownViewer();