/**
 * Custom Marked.js configuration to properly handle Mermaid diagrams
 * This should be loaded before the Markdown viewer
 */
document.addEventListener('DOMContentLoaded', function() {
    if (window.marked) {
        // Configure Marked.js renderer to handle Mermaid code blocks
        console.log('Configuring Marked.js renderer for Mermaid');
        
        // Save the original code renderer
        const originalRenderer = new marked.Renderer();
        const originalCodeRenderer = originalRenderer.code.bind(originalRenderer);
        
        // Create a custom renderer that handles Mermaid blocks
        const customRenderer = new marked.Renderer();
        
        // Override the code block renderer
        customRenderer.code = function(code, language) {
            // If this is a Mermaid code block, render it as a Mermaid diagram
            if (language === 'mermaid') {
                return `<div class="mermaid">${code}</div>`;
            }
            
            // Otherwise, use the original renderer
            return originalCodeRenderer(code, language);
        };
        
        // Set the custom renderer
        marked.use({ renderer: customRenderer });
        
        console.log('Marked.js configured for Mermaid diagrams');
    } else {
        console.warn('Marked.js not found, cannot configure for Mermaid');
    }
});
