# AgentMap Documentation (Docusaurus)

This is the new Docusaurus-based documentation site for AgentMap.

## Setup Instructions

1. **Install dependencies:**
   ```bash
   cd docs-docusaurus
   npm install
   ```

2. **Copy actual images:** 
   **IMPORTANT**: Replace placeholder with real AgentMap hero image:
   - Copy `docs/images/agentmap-hero.png` to `static/img/agentmap-hero.png`
   - Copy `docs/images/favicon.ico` to `static/img/favicon.ico`
   - Update `src/pages/index.tsx` to reference `.png` instead of `.svg` after copying
   
   The site currently uses a placeholder SVG - replace with the actual PNG for proper branding.

3. **Start development server:**
   ```bash
   npm start
   ```

4. **Build for production:**
   ```bash
   npm run build
   ```

## Configuration

The site is configured for:
- **URL:** https://jwwelbor.github.io
- **Base URL:** /AgentMap/
- **GitHub Pages deployment**
- **Dark mode support**
- **Mermaid diagram support**

## Features

- 📝 Documentation with sidebar navigation
- 📰 Blog functionality  
- 🌙 Dark/light mode toggle
- 📊 Mermaid diagrams
- 🎨 Custom AgentMap branding
- 📱 Mobile responsive
- 🔍 Built-in search

## Structure

```
docs-docusaurus/
├── docs/           # Documentation files
├── blog/           # Blog posts
├── src/            # React components and pages
├── static/         # Static assets (images, etc.)
├── docusaurus.config.ts  # Main configuration
└── sidebars.ts     # Sidebar configuration
```

## Deployment

This site is configured for GitHub Pages deployment. The build will be automatically deployed when merged to main branch.
