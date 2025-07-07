import React, { useState, useMemo, useEffect } from 'react';
import useDownloadContent from '../hooks/useDownloadContent';
import styles from './TemplateLibrary.module.css';

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: 'Automation' | 'Data Processing' | 'AI/LLM' | 'Monitoring' | 'Integration' | 'Utility';
  difficulty: 'Beginner' | 'Intermediate' | 'Advanced';
  tags: string[];
  requiredAgents: string[];
  useCase: string;
  csvFile: string;
  outputExample?: string;
  configNotes?: string[];
}

interface TemplateMetadata {
  version: string;
  lastUpdated: string;
  templates: WorkflowTemplate[];
}

// Template Card component that loads CSV content dynamically
interface TemplateCardProps {
  template: WorkflowTemplate;
  copiedTemplate: string | null;
  onCopy: (content: string, templateId: string) => void;
  onOpenInPlayground: (content: string) => void;
}

const TemplateCard: React.FC<TemplateCardProps> = ({ 
  template, 
  copiedTemplate, 
  onCopy, 
  onOpenInPlayground 
}) => {
  const { content: csvContent, loading, error } = useDownloadContent({
    contentPath: `/downloads/templates/${template.csvFile}`,
    fallbackContent: `# ${template.name} template file not found\n# Please check the template configuration`
  });

  const handleCopyClick = () => {
    if (csvContent) {
      onCopy(csvContent, template.id);
    }
  };

  const handlePlaygroundClick = () => {
    if (csvContent) {
      onOpenInPlayground(csvContent);
    }
  };

  return (
    <div className={styles.templateCard}>
      <div className={styles.cardHeader}>
        <div 
          className={styles.categoryBadge}
          style={{ backgroundColor: CATEGORY_COLORS[template.category] }}
        >
          {CATEGORY_ICONS[template.category]} {template.category}
        </div>
        <div 
          className={styles.difficultyBadge}
          style={{ backgroundColor: DIFFICULTY_COLORS[template.difficulty] }}
        >
          {DIFFICULTY_ICONS[template.difficulty]} {template.difficulty}
        </div>
      </div>

      <div className={styles.templateInfo}>
        <h3>{template.name}</h3>
        <p className={styles.description}>{template.description}</p>
        
        <div className={styles.useCase}>
          <strong>Use Case:</strong> {template.useCase}
        </div>

        <div className={styles.tags}>
          {template.tags.map(tag => (
            <span key={tag} className={styles.tag}>{tag}</span>
          ))}
        </div>

        <div className={styles.requirements}>
          <strong>Required Agents:</strong>
          <div className={styles.agentList}>
            {template.requiredAgents.map(agent => (
              <code key={agent} className={styles.agentType}>{agent}</code>
            ))}
          </div>
        </div>

        {template.outputExample && (
          <div className={styles.example}>
            <strong>Example Output:</strong>
            <div className={styles.exampleOutput}>{template.outputExample}</div>
          </div>
        )}

        {template.configNotes && template.configNotes.length > 0 && (
          <div className={styles.configNotes}>
            <strong>Configuration Notes:</strong>
            <ul>
              {template.configNotes.map((note, index) => (
                <li key={index}>{note}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className={styles.actions}>
        <button
          onClick={handleCopyClick}
          className={styles.copyButton}
          disabled={loading || error}
        >
          {loading ? 'Loading...' : copiedTemplate === template.id ? '✓ Copied!' : '📋 Copy CSV'}
        </button>
        <button
          onClick={handlePlaygroundClick}
          className={styles.playgroundButton}
          disabled={loading || error}
        >
          🚀 Open in Playground
        </button>
      </div>

      <details className={styles.csvPreview}>
        <summary>View CSV Content</summary>
        {loading && <p>Loading CSV content...</p>}
        {error && <p className={styles.error}>Error loading CSV: {error}</p>}
        {csvContent && <pre className={styles.csvCode}>{csvContent}</pre>}
      </details>
    </div>
  );
};

const CATEGORY_COLORS = {
  'Automation': '#4CAF50',      // Green
  'Data Processing': '#FF9800', // Orange
  'AI/LLM': '#2196F3',         // Blue
  'Monitoring': '#E91E63',     // Pink
  'Integration': '#9C27B0',    // Purple
  'Utility': '#607D8B'         // Blue Grey
};

const CATEGORY_ICONS = {
  'Automation': '🤖',
  'Data Processing': '📊',
  'AI/LLM': '🧠',
  'Monitoring': '👁️',
  'Integration': '🔗',
  'Utility': '🛠️'
};

const DIFFICULTY_COLORS = {
  'Beginner': '#4CAF50',    // Green
  'Intermediate': '#FF9800', // Orange
  'Advanced': '#F44336'     // Red
};

const DIFFICULTY_ICONS = {
  'Beginner': '🟢',
  'Intermediate': '🟡',
  'Advanced': '🔴'
};

export default function TemplateLibrary(): JSX.Element {
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>('All');
  const [copiedTemplate, setCopiedTemplate] = useState<string | null>(null);

  // Load templates metadata on component mount
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const response = await fetch('/downloads/templates/templates-metadata.json');
        if (!response.ok) {
          throw new Error(`Failed to load templates metadata: ${response.status}`);
        }
        const metadata: TemplateMetadata = await response.json();
        setTemplates(metadata.templates);
        setLoading(false);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
        setError(errorMessage);
        setLoading(false);
        console.error('Error loading templates metadata:', err);
      }
    };

    loadTemplates();
  }, []);

  const categories = ['All', ...Object.keys(CATEGORY_COLORS)];
  const difficulties = ['All', 'Beginner', 'Intermediate', 'Advanced'];

  const filteredTemplates = useMemo(() => {
    return templates.filter(template => {
      const matchesSearch = 
        template.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        template.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        template.useCase.toLowerCase().includes(searchTerm.toLowerCase()) ||
        template.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()));
      
      const matchesCategory = 
        selectedCategory === 'All' || template.category === selectedCategory;
      
      const matchesDifficulty = 
        selectedDifficulty === 'All' || template.difficulty === selectedDifficulty;
      
      return matchesSearch && matchesCategory && matchesDifficulty;
    });
  }, [templates, searchTerm, selectedCategory, selectedDifficulty]);

  const copyToClipboard = async (text: string, templateId: string) => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
          document.execCommand('copy');
        } catch (fallbackErr) {
          console.error('Fallback copy failed: ', fallbackErr);
        }
        document.body.removeChild(textArea);
      }
      setCopiedTemplate(templateId);
      setTimeout(() => setCopiedTemplate(null), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
      setCopiedTemplate(templateId);
      setTimeout(() => setCopiedTemplate(null), 1000);
    }
  };

  const openInPlayground = (csvContent: string) => {
    // This would integrate with the actual playground - for now just copy
    copyToClipboard(csvContent, 'playground');
    // In a real implementation, this would navigate to playground with the content pre-loaded
    console.log('Opening in playground...', csvContent);
  };

  if (loading) {
    return (
      <div className={styles.templateLibrary}>
        <div className={styles.header}>
          <h1>AgentMap Template Library</h1>
          <p>Loading templates...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.templateLibrary}>
        <div className={styles.header}>
          <h1>AgentMap Template Library</h1>
          <p className={styles.error}>Error loading templates: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.templateLibrary}>
      <div className={styles.header}>
        <h1>AgentMap Template Library</h1>
        <p>Ready-to-use workflow templates to get you started quickly</p>
      </div>

      <div className={styles.controls}>
        <div className={styles.searchContainer}>
          <input
            type="text"
            placeholder="Search templates by name, description, or tags..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className={styles.searchInput}
          />
        </div>

        <div className={styles.filters}>
          <div className={styles.filterGroup}>
            <label>Category:</label>
            <div className={styles.categoryFilters}>
              {categories.map(category => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`${styles.filterButton} ${
                    selectedCategory === category ? styles.active : ''
                  }`}
                  style={{
                    backgroundColor: selectedCategory === category 
                      ? (category !== 'All' ? CATEGORY_COLORS[category as keyof typeof CATEGORY_COLORS] : '#333')
                      : 'transparent',
                    borderColor: category !== 'All' 
                      ? CATEGORY_COLORS[category as keyof typeof CATEGORY_COLORS] 
                      : '#333'
                  }}
                >
                  {category !== 'All' && CATEGORY_ICONS[category as keyof typeof CATEGORY_ICONS]} {category}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.filterGroup}>
            <label>Difficulty:</label>
            <div className={styles.difficultyFilters}>
              {difficulties.map(difficulty => (
                <button
                  key={difficulty}
                  onClick={() => setSelectedDifficulty(difficulty)}
                  className={`${styles.filterButton} ${
                    selectedDifficulty === difficulty ? styles.active : ''
                  }`}
                  style={{
                    backgroundColor: selectedDifficulty === difficulty 
                      ? (difficulty !== 'All' ? DIFFICULTY_COLORS[difficulty as keyof typeof DIFFICULTY_COLORS] : '#333')
                      : 'transparent',
                    borderColor: difficulty !== 'All' 
                      ? DIFFICULTY_COLORS[difficulty as keyof typeof DIFFICULTY_COLORS] 
                      : '#333'
                  }}
                >
                  {difficulty !== 'All' && DIFFICULTY_ICONS[difficulty as keyof typeof DIFFICULTY_ICONS]} {difficulty}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className={styles.templateGrid}>
        {filteredTemplates.map((template) => (
          <TemplateCard 
            key={template.id}
            template={template}
            copiedTemplate={copiedTemplate}
            onCopy={copyToClipboard}
            onOpenInPlayground={openInPlayground}
          />
        ))}
      </div>

      {filteredTemplates.length === 0 && (
        <div className={styles.noResults}>
          <p>No templates found matching your criteria.</p>
          <p>Try adjusting your search term or filters.</p>
        </div>
      )}

      <div className={styles.footer}>
        <p>
          Found {filteredTemplates.length} of {templates.length} templates. 
          Need help customizing a template? Check out the{' '}
          <a href="/docs/guides/template-customization">template customization guide</a> or{' '}
          <a href="/docs/getting-started/quick-start">quick start tutorial</a>.
        </p>
      </div>
    </div>
  );
}
