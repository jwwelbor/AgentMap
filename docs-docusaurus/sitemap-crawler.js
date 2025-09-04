const { chromium } = require('playwright');
const fs = require('fs').promises;
const path = require('path');

async function crawlDocsSite(startUrl = 'http://localhost:3000/AgentMap/docs/intro') {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  const visited = new Set();
  const sitemap = [];
  const brokenLinks = [];
  const baseUrl = 'http://localhost:3000/AgentMap';
  
  async function crawlPage(url) {
    if (visited.has(url)) return;
    visited.add(url);
    
    console.log(`Crawling: ${url}`);
    
    try {
      const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 10000 });
      
      if (!response || response.status() !== 200) {
        brokenLinks.push({
          url,
          status: response ? response.status() : 'No response'
        });
        return;
      }
      
      // Get page title
      const title = await page.title();
      
      // Check if sidebar exists
      const hasSidebar = await page.locator('.theme-doc-sidebar-container').count() > 0;
      
      // Get all internal links
      const links = await page.evaluate(() => {
        const anchors = Array.from(document.querySelectorAll('a'));
        return anchors
          .map(a => ({
            href: a.href,
            text: a.textContent.trim(),
            hasHref: a.hasAttribute('href')
          }))
          .filter(link => link.href && link.href.startsWith(window.location.origin));
      });
      
      // Get sidebar structure if it exists
      let sidebarStructure = null;
      if (hasSidebar) {
        sidebarStructure = await page.evaluate(() => {
          const sidebar = document.querySelector('.theme-doc-sidebar-menu');
          if (!sidebar) return null;
          
          function extractStructure(element) {
            const items = [];
            const menuItems = element.querySelectorAll(':scope > li');
            
            menuItems.forEach(item => {
              const link = item.querySelector('a');
              const label = item.querySelector('.menu__link, .menu__list-item-collapsible');
              const submenu = item.querySelector('.menu__list');
              
              if (label) {
                const itemData = {
                  label: label.textContent.trim(),
                  href: link ? link.href : null,
                  isActive: link ? link.classList.contains('menu__link--active') : false,
                  children: submenu ? extractStructure(submenu) : []
                };
                items.push(itemData);
              }
            });
            
            return items;
          }
          
          return extractStructure(sidebar);
        });
      }
      
      sitemap.push({
        url,
        title,
        hasSidebar,
        sidebarStructure,
        linksCount: links.length
      });
      
      // Crawl linked pages
      for (const link of links) {
        if (link.href.startsWith(baseUrl + '/docs/') && !visited.has(link.href)) {
          await crawlPage(link.href);
        }
      }
      
    } catch (error) {
      console.error(`Error crawling ${url}:`, error.message);
      brokenLinks.push({
        url,
        error: error.message
      });
    }
  }
  
  await crawlPage(startUrl);
  
  await browser.close();
  
  // Generate report
  const report = {
    timestamp: new Date().toISOString(),
    totalPages: sitemap.length,
    pagesWithSidebar: sitemap.filter(p => p.hasSidebar).length,
    pagesWithoutSidebar: sitemap.filter(p => !p.hasSidebar).length,
    brokenLinks: brokenLinks.length,
    sitemap: sitemap.sort((a, b) => a.url.localeCompare(b.url)),
    brokenLinksDetail: brokenLinks
  };
  
  // Save report
  await fs.writeFile(
    'docs-sitemap-report.json',
    JSON.stringify(report, null, 2)
  );
  
  // Generate visual tree
  let visualTree = '# Documentation Site Map\n\n';
  visualTree += `Generated: ${new Date().toLocaleString()}\n\n`;
  visualTree += `## Summary\n`;
  visualTree += `- Total Pages: ${report.totalPages}\n`;
  visualTree += `- Pages with Sidebar: ${report.pagesWithSidebar}\n`;
  visualTree += `- Pages WITHOUT Sidebar: ${report.pagesWithoutSidebar}\n`;
  visualTree += `- Broken Links: ${report.brokenLinks}\n\n`;
  
  visualTree += `## Pages Structure\n\n`;
  
  // Group pages by sidebar status
  visualTree += `### ✅ Pages WITH Sidebar\n`;
  report.sitemap.filter(p => p.hasSidebar).forEach(page => {
    const shortUrl = page.url.replace('http://localhost:3000/AgentMap/docs/', '');
    visualTree += `- **${shortUrl}** - "${page.title}"\n`;
  });
  
  visualTree += `\n### ❌ Pages WITHOUT Sidebar (Navigation Lost!)\n`;
  report.sitemap.filter(p => !p.hasSidebar).forEach(page => {
    const shortUrl = page.url.replace('http://localhost:3000/AgentMap/docs/', '');
    visualTree += `- **${shortUrl}** - "${page.title}"\n`;
  });
  
  if (brokenLinks.length > 0) {
    visualTree += `\n### 🚨 Broken Links\n`;
    brokenLinks.forEach(link => {
      visualTree += `- ${link.url} - ${link.status || link.error}\n`;
    });
  }
  
  // Show sidebar structure from first page
  const pageWithSidebar = report.sitemap.find(p => p.hasSidebar && p.sidebarStructure);
  if (pageWithSidebar && pageWithSidebar.sidebarStructure) {
    visualTree += `\n## Sidebar Navigation Structure\n\n`;
    
    function renderTree(items, indent = '') {
      items.forEach(item => {
        visualTree += `${indent}- ${item.label}`;
        if (item.isActive) visualTree += ' ⚡ (active)';
        if (item.href) {
          const shortHref = item.href.replace('http://localhost:3000/AgentMap/docs/', '');
          visualTree += ` → ${shortHref}`;
        }
        visualTree += '\n';
        if (item.children && item.children.length > 0) {
          renderTree(item.children, indent + '  ');
        }
      });
    }
    
    renderTree(pageWithSidebar.sidebarStructure);
  }
  
  await fs.writeFile('docs-sitemap-visual.md', visualTree);
  
  console.log('\n📊 Sitemap generation complete!');
  console.log('- Full report: docs-sitemap-report.json');
  console.log('- Visual tree: docs-sitemap-visual.md');
  
  return report;
}

// Run the crawler
if (require.main === module) {
  console.log('Starting documentation site crawler...');
  console.log('Make sure the docs site is running on http://localhost:3000');
  crawlDocsSite().catch(console.error);
}

module.exports = { crawlDocsSite };
