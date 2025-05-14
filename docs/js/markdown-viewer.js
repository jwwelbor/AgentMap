/**
 * Markdown handling functionality with Mermaid support
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
     * Render the current markdown content with Mermaid support
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
                <div class="markdown-content">${this.processMarkdown(this.markdownContent)}</div>
            </div>
        `;
        
        // Initialize Mermaid diagrams after the content is rendered
        this.initMermaid();
    }
    
    /**
     * Process markdown content before rendering
     * This allows us to handle special content like Mermaid diagrams
     */
    processMarkdown(content) {
        if (!content) return '';
        
        try {
            // Process the markdown content
            const processedContent = marked.parse(content);
            return processedContent;
        } catch (error) {
            console.error('Error processing markdown:', error);
            return `<p>Error processing markdown: ${error.message}</p><pre>${content}</pre>`;
        }
    }
    
    /**
     * Initialize Mermaid diagrams after content is rendered
     */
    initMermaid() {
        if (window.mermaid) {
            try {
                console.log('Initializing Mermaid diagrams in markdown content');
                
                // Reset Mermaid configuration
                window.mermaid.initialize({
                    startOnLoad: false,
                    theme: 'dark',
                    flowchart: {
                        curve: 'basis',
                        useMaxWidth: true
                    },
                    securityLevel: 'loose'
                });
                
                // Find all pre.mermaid and div.mermaid elements
                const mermaidElements = document.querySelectorAll('.markdown-content pre.mermaid, .markdown-content .mermaid');
                console.log(`Found ${mermaidElements.length} Mermaid diagrams`);
                
                // Initialize each Mermaid diagram
                window.mermaid.init(undefined, mermaidElements);
            } catch (error) {
                console.error('Error initializing Mermaid in markdown:', error);
            }
        } else {
            console.warn('Mermaid library not loaded');
        }
    }
}

// Create global markdown viewer instance
const markdownViewer = new MarkdownViewer();
