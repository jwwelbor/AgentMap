/**
 * Main application logic
 */
class AgentMapApp {
    constructor() {
        this.currentStep = 0;
        this.activeTab = 'workflow';
    }
    
    /**
     * Initialize the application
     */
    init() {
        this.renderHeader();
        this.renderTabs();
        this.renderContentSections();
        this.renderFooter();
        this.updateContent();
        
        // Add event listeners to tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.setActiveTab(tab.dataset.tab);
            });
        });
    }
    
    /**
     * Render the header with hero banner
     */
    renderHeader() {
        const container = document.getElementById('app-container');
        container.innerHTML = `
            <header>
                <div class="hero-banner">
                    <img src="images/agentmap-hero.png" alt="AgentMap - Declarative AI Workflow Orchestration">
                    <div class="hero-overlay">
                        <h1 class="hero-title">AgentMap</h1>
                        <p class="hero-subtitle">Declarative AI Workflow Orchestration</p>
                    </div>
                </div>
                <p class="hero-description">A step-by-step explanation of how AgentMap processes workflows</p>
            </header>
        `;
    }
    
    /**
     * Render the tab navigation
     */
    renderTabs() {
        const container = document.getElementById('app-container');
        container.innerHTML += `
            <div class="tabs">
                <div class="tab ${this.activeTab === 'workflow' ? 'active' : ''}" data-tab="workflow">Workflow Visualization</div>
                <div class="tab ${this.activeTab === 'documentation' ? 'active' : ''}" data-tab="documentation">Documentation</div>
            </div>
        `;
    }
    
    /**
     * Render the content section containers
     */
    renderContentSections() {
        const container = document.getElementById('app-container');
        container.innerHTML += `
            <div id="workflow-section" class="content-section ${this.activeTab === 'workflow' ? 'active' : ''}"></div>
            <div id="documentation-section" class="content-section ${this.activeTab === 'documentation' ? 'active' : ''}"></div>
            <div id="markdown-section" class="content-section ${this.activeTab === 'markdown' ? 'active' : ''}"></div>
        `;
    }
    
    /**
     * Render the footer
     */
    renderFooter() {
        const container = document.getElementById('app-container');
        container.innerHTML += `
            <footer>
                <p class="cmd-line">agentmap run -task WorldDomination -state {"input":"Greetings, AgentMap!"}</p>
                <p>Made for GitHub Pages</p>
                <p>&copy; ${new Date().getFullYear()} | AgentMap Workflow Visualization</p>
            </footer>
        `;
    }
    
    /**
     * Set the active tab
     */
    setActiveTab(tab) {
        this.activeTab = tab;
        
        // Update tab classes
        document.querySelectorAll('.tab').forEach(el => {
            el.classList.toggle('active', el.dataset.tab === this.activeTab);
        });
        
        // Update content section visibility
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });
        
        if (this.activeTab === 'workflow') {
            document.getElementById('workflow-section').classList.add('active');
        } else if (this.activeTab === 'documentation') {
            document.getElementById('documentation-section').classList.add('active');
        } else if (this.activeTab === 'markdown') {
            document.getElementById('markdown-section').classList.add('active');
        }
        
        // Update content
        this.updateContent();
    }
    
    /**
     * Update content based on active tab
     */
    updateContent() {
        if (this.activeTab === 'workflow') {
            this.renderWorkflowStep();
        } else if (this.activeTab === 'documentation') {
            this.renderDocumentationList();
        } else if (this.activeTab === 'markdown') {
            markdownViewer.renderMarkdown();
        }
    }
    
    /**
     * Render current workflow step
     */
    renderWorkflowStep() {
        const workflowSection = document.getElementById('workflow-section');
        const step = stepsData[this.currentStep];
        
        if (!workflowSection || !step) return;
        
        // Render progress bar
        let progressBar = `
            <div class="progress-bar">
                <div class="progress-bar-fill" style="width: ${((this.currentStep + 1) / stepsData.length) * 100}%"></div>
            </div>
        `;
        
        // Render navigation buttons ABOVE content
        let navButtons = `
            <div class="nav-buttons">
                <button 
                    onclick="app.handlePrev()"
                    class="btn-nav ${this.currentStep === 0 ? 'btn-nav-disabled' : 'btn-nav-active'}"
                    ${this.currentStep === 0 ? 'disabled' : ''}
                >
                    Previous
                </button>
                
                <div class="step-counter">
                    Step ${this.currentStep + 1} of ${stepsData.length}
                </div>
                
                <button 
                    onclick="app.handleNext()"
                    class="btn-nav ${this.currentStep === stepsData.length - 1 ? 'btn-nav-disabled' : 'btn-nav-active'}"
                    ${this.currentStep === stepsData.length - 1 ? 'disabled' : ''}
                >
                    Next
                </button>
            </div>
        `;
        
        // Render step content
        let stepContent = `
            <div class="content-card">
                <h2 class="card-title">${step.title}</h2>
                <p class="card-description">${step.description}</p>
                <p class="card-details">${step.details}</p>
                
                <div class="flex-row">
                    <div class="flex-col-50">
                        <h3 class="section-title">Visual Representation</h3>
                        ${step.visual}
                    </div>
                    
                    ${step.code ? `
                        <div class="flex-col-50">
                            <h3 class="section-title">Code Example</h3>
                            <div class="code-block">
                                <pre class="code-text">${step.code}</pre>
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
        
        // Combine sections - note nav buttons are now ABOVE the content
        workflowSection.innerHTML = progressBar + navButtons + stepContent;
        
        // Initialize Mermaid diagrams
        this.initMermaid();
    }
    
    /**
     * Initialize Mermaid diagrams after DOM update
     */
    initMermaid() {
        if (window.mermaid) {
            try {
                window.mermaid.init(undefined, document.querySelectorAll('.mermaid'));
            } catch (error) {
                console.error('Error initializing Mermaid:', error);
            }
        } else {
            console.warn('Mermaid library not loaded');
        }
    }
    
    /**
     * Handle navigation to previous step
     */
    handlePrev() {
        if (this.currentStep > 0) {
            this.currentStep--;
            this.renderWorkflowStep();
        }
    }
    
    /**
     * Handle navigation to next step
     */
    handleNext() {
        if (this.currentStep < stepsData.length - 1) {
            this.currentStep++;
            this.renderWorkflowStep();
        }
    }
    
    /**
     * Render documentation list
     */
    renderDocumentationList() {
        const documentationSection = document.getElementById('documentation-section');
        if (!documentationSection) return;
        
        let docListHTML = `
            <div class="content-card">
                <h2 class="card-title">Project Documentation</h2>
                <p class="card-description">
                    The AgentMap project includes several README files that document different aspects of the system.
                    Click on any of the links below to view the documentation.
                </p>
                
                <div class="doc-grid">
        `;
        
        // Add documentation cards
        documentationFiles.forEach(doc => {
            docListHTML += `
                <div class="doc-card">
                    <h3 class="doc-title">${doc.title}</h3>
                    <p class="doc-path">${doc.path}</p>
                    <button class="btn btn-cyan" onclick="markdownViewer.fetchMarkdown('${doc.path}', '${doc.title}')">
                        View Documentation
                    </button>
                </div>
            `;
        });
        
        docListHTML += `
                </div>
            </div>
        `;
        
        documentationSection.innerHTML = docListHTML;
    }
}

// Create and initialize the app when DOM is loaded
const app = new AgentMapApp();
document.addEventListener('DOMContentLoaded', () => app.init());